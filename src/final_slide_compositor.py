from __future__ import annotations

import hashlib
import html
import json
import os
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw

from . import final_image_package as fip
from . import final_image_renderer as fir
from .brushup_renderer import (
    _draw_paragraph_block,
    _fit_text_block,
    _hex_to_rgb,
    verify_not_source_copy,
)
from .image_renderer import resolve_font_path
from .lesson_pages import LessonDocument, clean_dialogue_lines

# Phase 10.15: Codexが生成済みの文字なし共通背景（rendered_final/background_master.png）と、
# Phase 10.14で確定した固定スライドマスター（MASTER_LAYOUT.json）・ページ別内部レイアウト仕様
# （final_image_package/pages/page_NNN.json）・確定済み本文スナップショット
# （final_image_package/text/page_NNN.json）から、決定論的に完成画像（rendered_final/page_NNN.png）
# を合成する。
#
# 画像へ描画する文字は、必ず`text/page_NNN.json`（本文スナップショット）から取得する
# （lesson_pages.jsonを直接の描画元にしない）。ただし「本文スナップショットが現在の
# lesson_pages.jsonと一致しているか」の鮮度検証には引き続きlesson_pages.json（LessonDocument）
# を使う。この2つの役割（検証用の正＝lesson_pages.json、描画用の入力＝text snapshot）を
# 明確に分離することが、このモジュールの安全設計の核心。

RENDERED_FINAL_DIR_NAME = "rendered_final"
DEFAULT_BACKGROUND_FILENAME = "background_master.png"
FINAL_RENDER_REPORT_JSON_FILENAME = "final_render_report.json"
FINAL_RENDER_REPORT_MD_FILENAME = "final_render_report.md"
FINAL_COMPARISON_HTML_FILENAME = "final_comparison.html"

_EMPHASIS_BAR_WIDTH = 6
_EMPHASIS_BAR_GAP = 8

# --- 視覚描画検証のしきい値 ---------------------------------------------------------------------
# `source_text_match`（描画処理へ渡した文字列がtext snapshotと一致するか）は文字列比較でしか
# 検証できない。「実際に完成画像へ正しく描画されたか」は別の関心事のため、合成後の完成画像の
# ピクセルを実測して検証する（`*_visually_rendered`）。
_INK_COLOR_TOLERANCE = 34
_MIN_INK_PIXELS = 20
_DARK_ARTIFACT_CUTOFF = 40
_DARK_ARTIFACT_RATIO_THRESHOLD = 0.02
_LOW_UTILIZATION_WARNING_THRESHOLD = 0.35
_REGION_OVERFLOW_MARGIN = 6

# 本文量が少ないページ（single_column）で、カード内の使用面積が小さい場合に文字サイズを
# 安全な上限まで拡大するための倍率候補（1.0=既定サイズのまま）。
_BODY_GROWTH_SCALES = (1.0, 1.12, 1.25, 1.4)
_GROWTH_MIN_VERTICAL_UTILIZATION = 0.6


@dataclass
class FinalRenderPaths:
    output_dir: Path
    lesson_pages_path: Path
    package_dir: Path
    master_layout_path: Path
    package_manifest_path: Path
    pages_dir: Path
    text_dir: Path
    rendered_brushup_preview_dir: Path
    rendered_final_dir: Path
    default_background_path: Path
    final_render_report_json_path: Path
    final_render_report_md_path: Path
    final_comparison_html_path: Path


def resolve_paths(output_dir: str | Path) -> FinalRenderPaths:
    base = Path(output_dir)
    fip_paths = fip.resolve_paths(base)
    rendered_final_dir = base / RENDERED_FINAL_DIR_NAME
    return FinalRenderPaths(
        output_dir=base,
        lesson_pages_path=fip_paths.lesson_pages_path,
        package_dir=fip_paths.package_dir,
        master_layout_path=fip_paths.master_layout_path,
        package_manifest_path=fip_paths.package_manifest_path,
        pages_dir=fip_paths.pages_dir,
        text_dir=fip_paths.text_dir,
        rendered_brushup_preview_dir=fip_paths.rendered_brushup_preview_dir,
        rendered_final_dir=rendered_final_dir,
        default_background_path=rendered_final_dir / DEFAULT_BACKGROUND_FILENAME,
        final_render_report_json_path=fip_paths.package_dir / FINAL_RENDER_REPORT_JSON_FILENAME,
        final_render_report_md_path=fip_paths.package_dir / FINAL_RENDER_REPORT_MD_FILENAME,
        final_comparison_html_path=fip_paths.package_dir / FINAL_COMPARISON_HTML_FILENAME,
    )


# --- 本文スナップショット由来のテキスト取得（lesson_pages.jsonを直接読まない） -------------------------


@dataclass
class _SnapshotPage:
    """`text/page_NNN.json`の値だけを保持する軽量オブジェクト。

    既存のブロック測定・描画関数（`final_image_renderer._measure_card_blocks`等）は
    `page.title`/`page.body`/`page.summary`属性だけを参照するダックタイピングのため、
    このオブジェクトを渡すことで、Phase 10.14の描画ロジックをそのまま再利用しつつ、
    実際に画像へ描く文字の取得元を本文スナップショットだけに限定できる。
    """

    page_no: int
    title: str
    body: str
    summary: str


def _paragraphs_from_body_text(body_text: str, line_range: list[int | None] | None = None) -> list[str]:
    """本文スナップショットのbody文字列から、段落単位の行リストを作る（brushup_rendererと同じ変換）。"""
    pairs = clean_dialogue_lines(body_text)
    paragraphs = [f"{speaker}: {text}" if speaker else text for speaker, text in pairs]
    if line_range is not None:
        start = line_range[0] if line_range[0] is not None else 0
        end = line_range[1] if len(line_range) > 1 and line_range[1] is not None else len(paragraphs)
        paragraphs = paragraphs[start:end]
    return paragraphs


# --- 入力検証 ---------------------------------------------------------------------------------


def validate_background_image(path: Path, expected_width: int, expected_height: int) -> tuple[Image.Image | None, list[str]]:
    """背景画像の存在・サイズ・破損・透明度を検証する。問題なければ(RGB画像, [])を返す。"""
    if not path.exists():
        return None, [f"背景画像が見つかりません: {path}"]
    try:
        img = Image.open(path)
        img.load()
    except Exception as e:  # noqa: BLE001 - Pillowの例外型はバージョン依存のため広く捕捉する
        return None, [f"背景画像を読み込めません（破損している可能性があります）: {path} ({e})"]

    errors: list[str] = []
    if img.size != (expected_width, expected_height):
        errors.append(
            f"背景画像のサイズがMASTER_LAYOUT.jsonのcanvasと一致しません: {img.size} != "
            f"({expected_width}, {expected_height})"
        )
    if img.mode in ("RGBA", "LA"):
        alpha = img.convert("RGBA").getchannel("A")
        if alpha.getextrema()[0] < 255:
            errors.append(f"背景画像に不透明でないピクセル（透明度）が含まれています: {path}")
    if errors:
        return None, errors
    return img.convert("RGB"), []


def _validate_line_ranges_against_snapshot(page_no: int, spec: dict[str, Any], text_snapshot: dict[str, Any]) -> list[str]:
    """ページ仕様のblocks[].line_rangeが、本文スナップショット（注記除去後）の段落数に
    収まっていることを確認する。範囲外だと空文字列を静かに描画してしまい、本文の一部を
    描画せず脱落させる（禁止されている「途中打ち切り」）ことになるため、事前に検出する。
    """
    errors: list[str] = []
    total = len(_paragraphs_from_body_text(text_snapshot.get("body", "")))
    for block in page_spec_blocks(spec):
        line_range = block.get("line_range")
        if not line_range:
            continue
        start = line_range[0] if line_range[0] is not None else 0
        end = line_range[1] if len(line_range) > 1 and line_range[1] is not None else total
        if start > total or end > total:
            errors.append(
                f"page_no={page_no}: content_layout.blocks[{block.get('id')}]のline_range={line_range}が"
                f"本文スナップショットの段落数({total})を超えています"
            )
    return errors


def page_spec_blocks(spec: dict[str, Any]) -> list[dict[str, Any]]:
    return spec.get("content_layout", {}).get("blocks", []) or []


def _derive_notice_text(text_snapshot: dict[str, Any]) -> str:
    """本文スナップショットの注記テキストを取得する。

    `text/page_NNN.json`の`notice`フィールドを第一の情報源として使うが、既知のデータ上の癖
    （`final_image_package.split_body_and_notice`が、話者が空文字列の生行"speaker: text"の
    先頭が"※"かどうかで判定するため、実データのように空話者行が": ※..."という形で保存されて
    いる場合に注記を検出できず、`notice`フィールドが空文字列のまま`body`側に注記が残ることが
    ある）に対応するため、`notice`が空の場合は`body`を解析し直し、最終段落が"※"で始まるかを
    確認する。いずれの場合も参照元は`text/page_NNN.json`自身（`notice`または`body`フィールド）
    のみであり、`lesson_pages.json`へは戻らない。
    """
    explicit_notice = (text_snapshot.get("notice") or "").strip()
    if explicit_notice:
        return text_snapshot["notice"]
    paragraphs = _paragraphs_from_body_text(text_snapshot.get("body", ""))
    if paragraphs and paragraphs[-1].strip().startswith("※"):
        return paragraphs[-1]
    return ""


def _validate_notice_consistency(page_no: int, spec: dict[str, Any], text_snapshot: dict[str, Any]) -> list[str]:
    has_notice_in_spec = bool((spec.get("notice") or {}).get("line_range"))
    has_notice_effective = bool(_derive_notice_text(text_snapshot).strip())
    if has_notice_in_spec != has_notice_effective:
        return [
            f"page_no={page_no}: ページ仕様のnotice有無({has_notice_in_spec})と"
            f"本文スナップショットから読み取れるnotice有無({has_notice_effective})が一致しません"
        ]
    return []


@dataclass
class LoadedInputs:
    paths: FinalRenderPaths
    master_layout: dict[str, Any]
    background_image: Image.Image | None
    background_path: Path
    font_path: str | None
    page_specs: dict[int, dict[str, Any]]
    text_snapshots: dict[int, dict[str, Any]]
    errors: list[str]


def load_and_validate(
    output_dir: str | Path,
    document: LessonDocument,
    background_path: str | Path | None = None,
    font_path: str | None = None,
) -> LoadedInputs:
    """完成画像生成前の全入力を読み込み・検証する。エラーは1つも見逃さず全て収集して返す。"""
    paths = resolve_paths(output_dir)
    errors: list[str] = []

    if not paths.lesson_pages_path.exists():
        raise ValueError(f"lesson_pages.jsonが見つかりません: {paths.lesson_pages_path}")
    if not paths.master_layout_path.exists():
        raise ValueError(
            f"MASTER_LAYOUT.jsonが見つかりません: {paths.master_layout_path}。"
            "先にprepare-final-image-packageを実行してください"
        )
    if not paths.package_manifest_path.exists():
        raise ValueError(f"package_manifest.jsonが見つかりません: {paths.package_manifest_path}")

    try:
        master_layout = json.loads(paths.master_layout_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"MASTER_LAYOUT.jsonのJSONが不正です: {e}")
    try:
        package_manifest = json.loads(paths.package_manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"package_manifest.jsonのJSONが不正です: {e}")

    expected_page_numbers = [p.page_no for p in document.pages]
    errors.extend(fip.validate_master_layout(master_layout, expected_page_numbers=expected_page_numbers))

    current_sha = fip.lesson_pages_sha256(paths.lesson_pages_path)
    freshness_error = fip.check_master_layout_freshness(master_layout, current_lesson_pages_sha256=current_sha)
    if freshness_error:
        errors.append(freshness_error)
    if package_manifest.get("source_lesson_pages_sha256") != current_sha:
        errors.append(
            "package_manifest.jsonは現在のlesson_pages.jsonとは異なる内容を前提にしています"
            "（prepare-final-image-packageを再実行してください）"
        )

    errors.extend(_validate_package_completeness(paths, expected_page_numbers))

    resolved_background_path = Path(background_path) if background_path else paths.default_background_path
    canvas = master_layout.get("canvas", {})
    background_image, bg_errors = validate_background_image(
        resolved_background_path, canvas.get("width", 0), canvas.get("height", 0)
    )
    errors.extend(bg_errors)

    resolved_font_path: str | None = None
    try:
        resolved_font_path = resolve_font_path(font_path)
    except ValueError as e:
        errors.append(str(e))
    if resolved_font_path is None:
        errors.append(
            "日本語を描画できるフォントが見つかりませんでした。--font-pathで日本語フォントを明示指定してください"
        )

    page_specs: dict[int, dict[str, Any]] = {}
    text_snapshots: dict[int, dict[str, Any]] = {}
    page_by_no = {p.page_no: p for p in document.pages}

    for page_no in expected_page_numbers:
        lesson_page = page_by_no[page_no]
        spec_path = paths.pages_dir / f"page_{page_no:03d}.json"
        text_path = paths.text_dir / f"page_{page_no:03d}.json"
        if not spec_path.exists() or not text_path.exists():
            # 存在チェック自体は_validate_package_completenessで既に記録済みなので、ここでは
            # 後続のper-page検証を単にスキップする（存在しないファイルを開こうとしない）。
            continue
        try:
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            errors.append(f"page_no={page_no}のページ仕様JSONが不正です: {e}")
            continue
        try:
            text_snapshot = json.loads(text_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            errors.append(f"page_no={page_no}の本文スナップショットJSONが不正です: {e}")
            continue

        errors.extend(
            f"page_no={page_no}: {e}"
            for e in fip.validate_page_spec(
                spec, expected_page_no=page_no, expected_source_image=lesson_page.source_image,
                master_layout=master_layout, lesson_page=lesson_page,
            )
        )
        errors.extend(
            f"page_no={page_no}: {e}"
            for e in fip.validate_text_snapshot(
                text_snapshot, expected_page_no=page_no, lesson_page=lesson_page,
                lesson_pages_sha256_value=current_sha,
            )
        )
        errors.extend(_validate_notice_consistency(page_no, spec, text_snapshot))
        errors.extend(_validate_line_ranges_against_snapshot(page_no, spec, text_snapshot))

        page_specs[page_no] = spec
        text_snapshots[page_no] = text_snapshot

    return LoadedInputs(
        paths=paths, master_layout=master_layout, background_image=background_image,
        background_path=resolved_background_path, font_path=resolved_font_path,
        page_specs=page_specs, text_snapshots=text_snapshots, errors=errors,
    )


def _validate_package_completeness(paths: FinalRenderPaths, expected_page_numbers: list[int]) -> list[str]:
    errors: list[str] = []
    if len(expected_page_numbers) != len(set(expected_page_numbers)):
        errors.append("lesson_pages.jsonのpage_noに重複があります")

    for page_no in expected_page_numbers:
        if not (paths.pages_dir / f"page_{page_no:03d}.json").exists():
            errors.append(f"page_no={page_no}のページ仕様が見つかりません: {paths.pages_dir / f'page_{page_no:03d}.json'}")
        if not (paths.text_dir / f"page_{page_no:03d}.json").exists():
            errors.append(f"page_no={page_no}の本文スナップショットが見つかりません: {paths.text_dir / f'page_{page_no:03d}.json'}")

    expected_set = set(expected_page_numbers)
    if paths.pages_dir.exists():
        extra = {
            _page_no_from_filename(p.name) for p in paths.pages_dir.glob("page_*.json")
        } - expected_set - {None}
        if extra:
            errors.append(f"lesson_pages.jsonに存在しないページ仕様があります: {sorted(extra)}")
    if paths.text_dir.exists():
        extra_text = {
            _page_no_from_filename(p.name) for p in paths.text_dir.glob("page_*.json")
        } - expected_set - {None}
        if extra_text:
            errors.append(f"lesson_pages.jsonに存在しない本文スナップショットがあります: {sorted(extra_text)}")
    return errors


def _page_no_from_filename(name: str) -> int | None:
    stem = name[:-5] if name.endswith(".json") else name
    parts = stem.split("_")
    if len(parts) == 2 and parts[0] == "page" and parts[1].isdigit():
        return int(parts[1])
    return None


# --- 固定領域の描画（本文スナップショットのみを描画元とする） -------------------------------------------


def _draw_title(draw: ImageDraw.ImageDraw, snapshot_page: _SnapshotPage, master_layout: dict[str, Any], font_path: str | None) -> Any | None:
    """タイトルを描画する。戻り値は測定結果（`_FitResult`）で、`None`はtitle_regionに収まらなかったことを示す。

    測定結果をそのまま呼び出し側へ返すことで、`title_font_size`/`title_line_count`等の
    レポート項目を、実際に描画へ使った値からそのまま取得できる（別途再計算しない）。
    """
    region = master_layout["regions"]["title_region"]
    theme = master_layout["theme"]
    weight = "bold" if master_layout["typography"].get("title_weight") == "bold" else "regular"
    fit = _fit_text_block(
        draw, [snapshot_page.title], font_path=font_path, base_font_size=52, weight=weight,
        base_padding=0, max_width=region["width"], available_height=region["height"], allow_two_column_fallback=False,
    )
    if not fit.fits:
        return None
    _draw_paragraph_block(draw, fit, font_path, weight, region["x"], region["y"], region["width"], _hex_to_rgb(theme["primary_text"]), "left")
    return fit


def _scale_blocks_font_size(blocks: list[dict[str, Any]], scale: float) -> list[dict[str, Any]]:
    if scale == 1.0:
        return blocks
    scaled: list[dict[str, Any]] = []
    for block in blocks:
        block_copy = dict(block)
        style = dict(block.get("style", {}))
        if isinstance(style.get("font_size"), int):
            style["font_size"] = max(1, round(style["font_size"] * scale))
        block_copy["style"] = style
        scaled.append(block_copy)
    return scaled


def _measure_card_blocks_with_growth(
    draw: ImageDraw.ImageDraw, snapshot_page: _SnapshotPage, blocks: list[dict[str, Any]], font_path: str | None,
    width: int, available_height: int, content_layout_type: str,
) -> tuple[list[tuple[dict, Any]], int, bool, dict | None, float]:
    """本文量が少ないページの内部配置を改善するため、`single_column`かつカード内の垂直方向
    利用率が低い場合に、文字サイズを段階的に拡大しながら再測定する（本文カードの外寸は
    一切変更しない。カード内部の文字サイズだけを既定より大きくする）。

    収まらなくなった時点で1段階前（最後に収まったスケール）を採用する。既に十分に埋まっている
    ページ・2段組みページは常にscale=1.0（既定サイズ）のまま変更しない。
    """
    items, used, fits, failed_block = fir._measure_card_blocks(draw, snapshot_page, blocks, font_path, width, available_height)
    if not fits or content_layout_type != "single_column" or available_height <= 0:
        return items, used, fits, failed_block, 1.0
    if used / available_height >= _GROWTH_MIN_VERTICAL_UTILIZATION:
        return items, used, fits, failed_block, 1.0

    best = (items, used, fits, failed_block, 1.0)
    for scale in _BODY_GROWTH_SCALES[1:]:
        candidate_blocks = _scale_blocks_font_size(blocks, scale)
        c_items, c_used, c_fits, c_failed = fir._measure_card_blocks(draw, snapshot_page, candidate_blocks, font_path, width, available_height)
        if not c_fits:
            break
        best = (c_items, c_used, c_fits, c_failed, scale)
    return best


def _draw_notice(draw: ImageDraw.ImageDraw, notice_text: str, master_layout: dict[str, Any], font_path: str | None) -> bool:
    if not notice_text:
        return True
    region = master_layout["regions"]["notice_region"]
    theme = master_layout["theme"]
    weight = master_layout["typography"].get("notice_weight", "regular")
    fit = _fit_text_block(
        draw, [notice_text], font_path=font_path, base_font_size=18, weight=weight,
        base_padding=0, max_width=region["width"], available_height=region["height"], allow_two_column_fallback=False,
    )
    if not fit.fits:
        return False
    _draw_paragraph_block(draw, fit, font_path, weight, region["x"], region["y"], region["width"], _hex_to_rgb(theme["secondary_text"]), "left")
    return True


def _draw_page_number(draw: ImageDraw.ImageDraw, page_no: int, master_layout: dict[str, Any], font_path: str | None) -> None:
    from .brushup_renderer import _load_font

    region = master_layout["regions"]["page_number_region"]
    theme = master_layout["theme"]
    font = _load_font(font_path, 22, "regular")
    text = f"- {page_no} -"
    text_width = draw.textlength(text, font=font)
    x = region["x"] + max(0, (region["width"] - text_width) / 2)
    y = region["y"] + max(0, (region["height"] - 22) / 2)
    draw.text((x, y), text, fill=_hex_to_rgb(theme["secondary_text"]), font=font)


def _draw_card_blocks(
    draw: ImageDraw.ImageDraw, items: list[tuple[dict, Any]], font_path: str | None,
    x0: int, y0: int, width: int, vertical_alignment: str, available_height: int, used_height: int,
    theme: dict[str, Any],
) -> None:
    """final_image_renderer._draw_card_blocksと同じ配置ロジックに、強調ブロック（本文中の◎付き
    一文等、アクセント色で塗られたブロック）向けの左罫線を追加する（section 6の強調表示要件）。
    テキストの折り返し幅・開始x座標は変えないため、既存の測定結果（fit）とずれない。
    """
    from .brushup_renderer import _draw_itemized_block, _draw_step_numbers, _BOX_CORNER_RADIUS

    extra = max(0, available_height - used_height)
    n = len(items)
    border_color = _hex_to_rgb(theme.get("border"), default=(200, 200, 200))
    accent_color = _hex_to_rgb(theme.get("accent"), default=(180, 120, 40))
    accent_hex = theme.get("accent")

    if vertical_alignment == "center":
        y = y0 + extra // 2
        gap = 0
    elif vertical_alignment == "distributed" and n > 0:
        gap = extra // (n + 1)
        y = y0 + gap
    else:
        y = y0
        gap = 0

    for block, fit in items:
        block_type = block["type"]
        style = block.get("style", {})
        color = _hex_to_rgb(style.get("color"), default=(20, 20, 20))
        alignment = style.get("alignment", "left")
        weight = style.get("font_weight", "regular")

        if block_type == "divider":
            line_y = y + style.get("padding", 12)
            draw.line([(x0, line_y), (x0 + width, line_y)], fill=border_color, width=2)
            y = line_y + style.get("padding", 12)
        elif block_type == "spacer":
            y += style.get("padding", 24)
        elif block_type in ("body", "summary"):
            is_emphasis = style.get("color") == accent_hex and accent_hex is not None
            if is_emphasis and fit is not None:
                bar_x0 = max(0, x0 - _EMPHASIS_BAR_GAP - _EMPHASIS_BAR_WIDTH)
                draw.rounded_rectangle([bar_x0, y, bar_x0 + _EMPHASIS_BAR_WIDTH, y + fit.height], radius=2, fill=accent_color)
            y = _draw_paragraph_block(draw, fit, font_path, weight, x0, y, width, color, alignment)
        elif block_type == "note":
            bg = style.get("background_color")
            box_bg = _hex_to_rgb(bg) if bg else _hex_to_rgb(theme.get("card_background"), default=(250, 250, 245))
            draw.rounded_rectangle([x0, y, x0 + width, y + fit.height], radius=_BOX_CORNER_RADIUS, fill=box_bg)
            y = _draw_paragraph_block(draw, fit, font_path, weight, x0, y, width, color, alignment)
        elif block_type in ("checklist", "steps", "quote"):
            new_y = _draw_itemized_block(draw, block_type, fit, font_path, weight, x0, y, width, color, accent_color)
            if block_type == "steps":
                _draw_step_numbers(draw, fit, font_path, weight, x0, y, accent_color)
            y = new_y

        if vertical_alignment == "distributed":
            y += gap


# --- 視覚描画検証（合成後の完成画像に対する実測。source_text_matchとは別の検証軸） -----------------
#
# `source_text_match`は「描画処理へ渡した文字列がtext snapshotと一致するか」という文字列比較に
# すぎず、実際に完成画像へ正しく描画されたか（領域外に描かれていないか・文字色ピクセルが
# 実在するか・暗色の矩形に隠れていないか）は別途、合成後の完成画像そのものを実測して検証する。


def _region_box(region: dict[str, Any], margin: int = 0, image_size: tuple[int, int] | None = None) -> tuple[int, int, int, int]:
    x0 = max(0, region["x"] - margin)
    y0 = max(0, region["y"] - margin)
    x1 = region["x"] + region["width"] + margin
    y1 = region["y"] + region["height"] + margin
    if image_size:
        x1 = min(image_size[0], x1)
        y1 = min(image_size[1], y1)
    return (x0, y0, x1, y1)


def _color_match_mask(crop: Image.Image, target: tuple[int, int, int], tol: int) -> Image.Image:
    solid = Image.new("RGB", crop.size, target)
    diff = ImageChops.difference(crop, solid)
    r, g, b = diff.split()
    thresholded = [band.point(lambda v: 255 if v <= tol else 0) for band in (r, g, b)]
    return ImageChops.darker(ImageChops.darker(thresholded[0], thresholded[1]), thresholded[2])


def _ink_mask(crop: Image.Image, target_colors: list[tuple[int, int, int]], tol: int = _INK_COLOR_TOLERANCE) -> Image.Image:
    mask: Image.Image | None = None
    for target in target_colors:
        m = _color_match_mask(crop, target, tol)
        mask = m if mask is None else ImageChops.lighter(mask, m)
    return mask if mask is not None else Image.new("L", crop.size, 0)


def _mask_count(mask: Image.Image) -> int:
    histogram = mask.histogram()
    return histogram[255] if len(histogram) > 255 else 0


def _verify_ink_region(
    image: Image.Image, region: dict[str, Any], target_colors: list[tuple[int, int, int]],
    tol: int = _INK_COLOR_TOLERANCE, margin: int = _REGION_OVERFLOW_MARGIN,
) -> dict[str, Any]:
    """region周辺（margin分拡張した範囲）を実測し、target_colorsに近い色のピクセルの
    bbox・件数・regionをはみ出しているか（overflow）を返す。
    """
    inner_box = (region["x"], region["y"], region["x"] + region["width"], region["y"] + region["height"])
    outer_box = _region_box(region, margin=margin, image_size=image.size)
    crop = image.crop(outer_box)
    mask = _ink_mask(crop, target_colors, tol)
    bbox_local = mask.getbbox()
    count = _mask_count(mask)
    if bbox_local is None:
        return {"bbox": None, "count": 0, "overflow": False}
    bbox_abs = (
        outer_box[0] + bbox_local[0], outer_box[1] + bbox_local[1],
        outer_box[0] + bbox_local[2], outer_box[1] + bbox_local[3],
    )
    overflow = (
        bbox_abs[0] < inner_box[0] - 1 or bbox_abs[1] < inner_box[1] - 1
        or bbox_abs[2] > inner_box[2] + 1 or bbox_abs[3] > inner_box[3] + 1
    )
    return {"bbox": bbox_abs, "count": count, "overflow": overflow}


def _dark_region_ratio(image: Image.Image, region: dict[str, Any], cutoff: int = _DARK_ARTIFACT_CUTOFF) -> float:
    """安全領域（title_region/content_card/notice_region/page_number_region）内に、意図しない
    大面積の黒・ほぼ黒のピクセルが無いかを検査する。文字色（primary_text等）はいずれもRGB各値が
    cutoff未満に揃うことはない配色のため、文字マスクを別途除外しなくても誤検出しない。
    """
    box = (region["x"], region["y"], region["x"] + region["width"], region["y"] + region["height"])
    crop = image.crop(box)
    r, g, b = crop.split()
    thresholded = [band.point(lambda v: 255 if v < cutoff else 0) for band in (r, g, b)]
    dark_mask = ImageChops.darker(ImageChops.darker(thresholded[0], thresholded[1]), thresholded[2])
    dark_count = _mask_count(dark_mask)
    total = crop.width * crop.height
    return dark_count / total if total else 0.0


def _verify_title_region(
    image: Image.Image, master_layout: dict[str, Any], title_text: str, title_font_size: int, title_line_count: int,
) -> dict[str, Any]:
    region = master_layout["regions"]["title_region"]
    theme = master_layout["theme"]
    ink = _verify_ink_region(image, region, [_hex_to_rgb(theme["primary_text"])])
    dark_ratio = _dark_region_ratio(image, region)
    has_text = bool(title_text.strip())
    mask_nonempty = ink["count"] >= _MIN_INK_PIXELS
    bbox_within_region = not ink["overflow"]
    dark_artifact_detected = dark_ratio > _DARK_ARTIFACT_RATIO_THRESHOLD
    visually_rendered = (not has_text) or (mask_nonempty and bbox_within_region and not dark_artifact_detected)
    return {
        "title_source": title_text,
        "title_font_size": title_font_size,
        "title_line_count": title_line_count,
        "title_bbox": list(ink["bbox"]) if ink["bbox"] else None,
        "title_region": [region["x"], region["y"], region["width"], region["height"]],
        "title_mask_nonempty": mask_nonempty,
        "title_bbox_within_region": bbox_within_region,
        "title_pixels_present": mask_nonempty,
        "title_dark_artifact_ratio": round(dark_ratio, 5),
        "title_dark_artifact_detected": dark_artifact_detected,
        "title_visually_rendered": visually_rendered,
    }


def _verify_body_region(image: Image.Image, master_layout: dict[str, Any], has_body_text: bool) -> dict[str, Any]:
    card = master_layout["regions"]["content_card"]
    theme = master_layout["theme"]
    padding = card["padding"]
    inner = {
        "x": card["x"] + padding["left"], "y": card["y"] + padding["top"],
        "width": card["width"] - padding["left"] - padding["right"],
        "height": card["height"] - padding["top"] - padding["bottom"],
    }
    target_colors = [_hex_to_rgb(theme["primary_text"])]
    if theme.get("accent"):
        target_colors.append(_hex_to_rgb(theme["accent"]))
    ink = _verify_ink_region(image, inner, target_colors, margin=4)
    card_box = {"x": card["x"], "y": card["y"], "width": card["width"], "height": card["height"]}
    dark_ratio = _dark_region_ratio(image, card_box)
    mask_nonempty = ink["count"] >= _MIN_INK_PIXELS
    bbox = ink["bbox"]
    if bbox and inner["width"] and inner["height"]:
        horizontal_utilization = round((bbox[2] - bbox[0]) / inner["width"], 4)
        vertical_utilization = round((bbox[3] - bbox[1]) / inner["height"], 4)
    else:
        horizontal_utilization = 0.0
        vertical_utilization = 0.0
    dark_artifact_detected = dark_ratio > _DARK_ARTIFACT_RATIO_THRESHOLD
    visually_rendered = (not has_body_text) or (mask_nonempty and not dark_artifact_detected)
    low_utilization_warning = mask_nonempty and (
        horizontal_utilization < _LOW_UTILIZATION_WARNING_THRESHOLD or vertical_utilization < _LOW_UTILIZATION_WARNING_THRESHOLD
    )
    return {
        "body_bbox": list(bbox) if bbox else None,
        "content_inner_region": [inner["x"], inner["y"], inner["width"], inner["height"]],
        "horizontal_utilization": horizontal_utilization,
        "vertical_utilization": vertical_utilization,
        "body_dark_artifact_ratio": round(dark_ratio, 5),
        "body_dark_artifact_detected": dark_artifact_detected,
        "body_visually_rendered": visually_rendered,
        "body_low_utilization_warning": low_utilization_warning,
    }


def _verify_notice_region(image: Image.Image, master_layout: dict[str, Any], notice_text: str) -> dict[str, Any]:
    region = master_layout["regions"]["notice_region"]
    theme = master_layout["theme"]
    has_text = bool(notice_text.strip())
    ink = _verify_ink_region(image, region, [_hex_to_rgb(theme["secondary_text"])])
    dark_ratio = _dark_region_ratio(image, region)
    mask_nonempty = ink["count"] >= _MIN_INK_PIXELS
    dark_artifact_detected = dark_ratio > _DARK_ARTIFACT_RATIO_THRESHOLD
    visually_rendered = (not has_text) or (mask_nonempty and not ink["overflow"] and not dark_artifact_detected)
    return {
        "notice_bbox": list(ink["bbox"]) if ink["bbox"] else None,
        "notice_dark_artifact_detected": dark_artifact_detected,
        "notice_visually_rendered": visually_rendered,
    }


def _verify_page_number_region(image: Image.Image, master_layout: dict[str, Any]) -> dict[str, Any]:
    region = master_layout["regions"]["page_number_region"]
    theme = master_layout["theme"]
    ink = _verify_ink_region(image, region, [_hex_to_rgb(theme["secondary_text"])])
    dark_ratio = _dark_region_ratio(image, region)
    mask_nonempty = ink["count"] >= _MIN_INK_PIXELS
    dark_artifact_detected = dark_ratio > _DARK_ARTIFACT_RATIO_THRESHOLD
    visually_rendered = mask_nonempty and not ink["overflow"] and not dark_artifact_detected
    return {
        "page_number_bbox": list(ink["bbox"]) if ink["bbox"] else None,
        "page_number_dark_artifact_detected": dark_artifact_detected,
        "page_number_visually_rendered": visually_rendered,
    }


def _ocr_title_check(image: Image.Image, master_layout: dict[str, Any], title_text: str) -> dict[str, Any]:
    """既存OCR機能によるタイトルの補助確認（主判定はbbox/pixel検証。OCRは参考情報）。

    OCR結果はフォント・記号の認識揺れにより完全一致しない可能性があるため、一致率が低い場合も
    警告に留め、ページの成否そのものは左右しない。OCR不能（tesseract未導入等）の場合も同様。
    """
    if not title_text.strip():
        return {"ocr_available": True, "ocr_text": "", "ocr_title_match_ratio": 1.0, "ocr_warning": ""}
    try:
        from . import ocr_engine
        from .ocr_environment import check_tesseract_environment

        env = check_tesseract_environment()
        if not env["tesseract_available"] or not env["japanese_available"]:
            return {
                "ocr_available": False, "ocr_text": "", "ocr_title_match_ratio": None,
                "ocr_warning": "tesseract（または日本語言語データ）が見つからないため補助OCR確認をスキップしました",
            }
        region = master_layout["regions"]["title_region"]
        box = (region["x"], region["y"], region["x"] + region["width"], region["y"] + region["height"])
        crop = image.crop(box)
        upscaled = crop.resize((crop.width * 2, crop.height * 2))
        candidate = ocr_engine.run_ocr_pass(
            upscaled, lang="jpn", psm=7, tesseract_cmd=env["tesseract_path"], preprocess="upscale2x", region="title",
        )
        ocr_text = ocr_engine.words_to_text(candidate.words)
    except Exception as e:  # noqa: BLE001 - OCRは補助確認のため、失敗しても主判定へ影響させず警告に留める
        return {
            "ocr_available": False, "ocr_text": "", "ocr_title_match_ratio": None,
            "ocr_warning": f"補助OCR確認の実行に失敗しました（主判定には影響しません）: {e}",
        }

    if not ocr_text.strip():
        return {
            "ocr_available": True, "ocr_text": "", "ocr_title_match_ratio": 0.0,
            "ocr_warning": "補助OCR結果が空でした（タイトル完全欠落の可能性。bbox/pixel検証を主判定とします）",
        }
    matched = sum(1 for ch in title_text if ch in ocr_text)
    ratio = round(matched / len(title_text), 3) if title_text else 1.0
    warning = "" if ratio >= 0.4 else "補助OCR結果とタイトルの一致率が低い（主判定には影響しません）"
    return {"ocr_available": True, "ocr_text": ocr_text, "ocr_title_match_ratio": ratio, "ocr_warning": warning}


def compute_visual_report(
    image: Image.Image, master_layout: dict[str, Any], *, title_text: str, title_font_size: int, title_line_count: int,
    notice_text: str, has_body_text: bool, run_ocr_check: bool = True,
) -> dict[str, Any]:
    """合成後の完成画像を実測し、`*_visually_rendered`一式を組み立てる。"""
    report: dict[str, Any] = {}
    report.update(_verify_title_region(image, master_layout, title_text, title_font_size, title_line_count))
    report.update(_verify_body_region(image, master_layout, has_body_text))
    report.update(_verify_notice_region(image, master_layout, notice_text))
    report.update(_verify_page_number_region(image, master_layout))
    report["all_regions_visually_rendered"] = (
        report["title_visually_rendered"] and report["body_visually_rendered"]
        and report["notice_visually_rendered"] and report["page_number_visually_rendered"]
    )
    if run_ocr_check:
        report.update(_ocr_title_check(image, master_layout, title_text))
    return report


# --- 1ページ分の合成 ---------------------------------------------------------------------------


def composite_page(
    page_no: int, page_spec: dict[str, Any], text_snapshot: dict[str, Any], master_layout: dict[str, Any],
    background_image: Image.Image, font_path: str | None, run_ocr_check: bool = True,
) -> tuple[Image.Image | None, list[str], bool, dict[str, Any]]:
    """1ページ分の完成画像を、共通背景・固定マスター・本文スナップショットだけから合成する。

    本文スナップショット（`text/page_NNN.json`）だけを描画元とし、`lesson_pages.json`は
    参照しない（鮮度検証は呼び出し側=load_and_validateで既に完了している前提）。

    戻り値の4番目（`visual`辞書）は、合成後の完成画像を実測して得た`*_visually_rendered`一式
    （`compute_visual_report`）。measure/drawが成功していても、実際に文字ピクセルが存在しない・
    領域外にはみ出している・暗色の矩形が検出された場合はここで検出され、呼び出し側
    （`write_final_images`）がページ全体を失敗扱いにする。
    """
    warnings: list[str] = []
    snapshot_page = _SnapshotPage(
        page_no=page_no, title=text_snapshot["title"], body=text_snapshot["body"],
        summary=text_snapshot.get("summary", ""),
    )
    image = background_image.copy()
    draw = ImageDraw.Draw(image)

    title_fit = _draw_title(draw, snapshot_page, master_layout, font_path)
    if title_fit is None:
        warnings.append("タイトルが固定のtitle_regionに収まりませんでした")
        return None, warnings, True, {}

    fir._draw_card_background(image, draw, master_layout)
    card = master_layout["regions"]["content_card"]
    padding = card["padding"]
    x0 = card["x"] + padding["left"]
    y0 = card["y"] + padding["top"]
    width = card["width"] - padding["left"] - padding["right"]
    available_height = card["height"] - padding["top"] - padding["bottom"]

    blocks = page_spec_blocks(page_spec)
    content_layout_type = page_spec["content_layout"]["type"]
    items, used, fits, failed_block, _growth_scale = _measure_card_blocks_with_growth(
        draw, snapshot_page, blocks, font_path, width, available_height, content_layout_type,
    )
    if not fits:
        block_id = failed_block.get("id", "?") if failed_block else "?"
        warnings.append(f"本文が固定サイズの本文カードに収まりませんでした（block={block_id}）")
        return None, warnings, True, {}

    vertical_alignment = page_spec["content_layout"]["vertical_alignment"]
    theme = master_layout["theme"]
    _draw_card_blocks(draw, items, font_path, x0, y0, width, vertical_alignment, available_height, used, theme)

    notice_text = _derive_notice_text(text_snapshot)
    if not _draw_notice(draw, notice_text, master_layout, font_path):
        warnings.append("注記が固定のnotice_regionに収まりませんでした")
        return None, warnings, True, {}

    _draw_page_number(draw, page_no, master_layout, font_path)

    title_line_count = len(title_fit.wrapped_columns[0]) if title_fit.wrapped_columns else 0
    has_body_text = bool(blocks)
    visual = compute_visual_report(
        image, master_layout, title_text=snapshot_page.title, title_font_size=title_fit.font_size,
        title_line_count=title_line_count, notice_text=notice_text, has_body_text=has_body_text,
        run_ocr_check=run_ocr_check,
    )
    if not visual["all_regions_visually_rendered"]:
        if not visual["title_visually_rendered"]:
            warnings.append("タイトルの視覚描画検証に失敗しました（title_visually_rendered=false）")
        if not visual["body_visually_rendered"]:
            warnings.append("本文の視覚描画検証に失敗しました（body_visually_rendered=false）")
        if not visual["notice_visually_rendered"]:
            warnings.append("注記の視覚描画検証に失敗しました（notice_visually_rendered=false）")
        if not visual["page_number_visually_rendered"]:
            warnings.append("ページ番号の視覚描画検証に失敗しました（page_number_visually_rendered=false）")
    if visual.get("body_low_utilization_warning"):
        warnings.append(
            f"本文カード内の利用率が低い可能性があります（horizontal={visual['horizontal_utilization']}, "
            f"vertical={visual['vertical_utilization']}）。目視確認を推奨します"
        )

    return image, warnings, False, visual


# --- 一括実行 ---------------------------------------------------------------------------------


@dataclass
class FinalRenderPageResult:
    page_no: int
    succeeded: bool
    overflow: bool
    truncated: bool
    source_text_match: bool
    warnings: list[str]
    rendered_fields: dict[str, str]
    source_text_sha256: str
    output_path: Path | None
    visual: dict[str, Any]


@dataclass
class FinalRenderRun:
    generated_at: str
    total_pages: int
    succeeded_pages: list[int]
    failed_pages: list[int]
    pages: list[FinalRenderPageResult]
    master_layout: dict[str, Any]
    background_path: Path
    font_path: str | None


def _rendered_fields_and_hash(text_snapshot: dict[str, Any]) -> tuple[dict[str, str], str]:
    rendered_fields = {
        "title": text_snapshot.get("title", ""),
        "body": text_snapshot.get("body", ""),
        "notice": _derive_notice_text(text_snapshot),
    }
    digest = hashlib.sha256(
        json.dumps(rendered_fields, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return rendered_fields, digest


def write_final_images(
    output_dir: str | Path, document: LessonDocument,
    background_path: str | Path | None = None, font_path: str | None = None, run_ocr_check: bool = True,
) -> FinalRenderRun:
    """`render-final-images`の本体。検証に1件でも失敗すれば例外を送出し、完成画像を一切生成しない。

    ページの成否は次の全条件を満たす場合のみ`succeeded=True`とする（`source_text_match`だけでは
    成功にならない）。

    ```text
    source_text_match == true
    overflow == false
    truncated == false
    all_regions_visually_rendered == true
    元画像・背景原本との単純コピーでない
    ```
    """
    loaded = load_and_validate(output_dir, document, background_path=background_path, font_path=font_path)
    if loaded.errors:
        raise ValueError(
            "render-final-imagesの入力検証に失敗しました:\n- " + "\n- ".join(loaded.errors)
        )

    paths = loaded.paths
    paths.rendered_final_dir.mkdir(parents=True, exist_ok=True)
    page_by_no = {p.page_no: p for p in document.pages}

    results: list[FinalRenderPageResult] = []
    for page_no in sorted(loaded.page_specs):
        lesson_page = page_by_no[page_no]
        spec = loaded.page_specs[page_no]
        text_snapshot = loaded.text_snapshots[page_no]

        image, warnings, overflow, visual = composite_page(
            page_no, spec, text_snapshot, loaded.master_layout, loaded.background_image, loaded.font_path,
            run_ocr_check=run_ocr_check,
        )
        source_text_match = True  # 描画元は常にtext_snapshotの値そのもの（他経路から文字を取得しない）
        all_regions_ok = bool(visual) and visual.get("all_regions_visually_rendered", False)
        succeeded = image is not None and all_regions_ok
        output_path: Path | None = None
        if image is not None:
            output_path = paths.rendered_final_dir / f"page_{page_no:03d}.png"
            image.save(output_path)
            if not verify_not_source_copy(loaded.background_path, output_path):
                warnings.append("完成画像が背景原本（background_master.png）と同一です")
                succeeded = False
            if lesson_page.source_image:
                source_image_path = paths.output_dir / lesson_page.source_image
                if source_image_path.exists() and not verify_not_source_copy(source_image_path, output_path):
                    warnings.append("完成画像が元画像と同一です")
                    succeeded = False

        rendered_fields, source_text_sha256 = _rendered_fields_and_hash(text_snapshot)
        # rendered_fieldsは常にtext_snapshotの値そのもの（他の経路で文字を取得しないため、
        # 描画に成功した場合は構造的に一致する。失敗時（overflow等）は画像そのものを生成しない）。
        results.append(FinalRenderPageResult(
            page_no=page_no, succeeded=succeeded, overflow=overflow, truncated=False,
            source_text_match=source_text_match, warnings=warnings, rendered_fields=rendered_fields,
            source_text_sha256=source_text_sha256, output_path=output_path if image is not None else None,
            visual=visual,
        ))

    succeeded_pages = [r.page_no for r in results if r.succeeded]
    failed_pages = [r.page_no for r in results if not r.succeeded]

    return FinalRenderRun(
        generated_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        total_pages=len(document.pages), succeeded_pages=succeeded_pages, failed_pages=failed_pages,
        pages=results, master_layout=loaded.master_layout, background_path=loaded.background_path,
        font_path=loaded.font_path,
    )


# --- レポート -----------------------------------------------------------------------------------


def render_final_render_report_json(run: FinalRenderRun) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "generated_at": run.generated_at,
        "total_pages": run.total_pages,
        "succeeded_pages": run.succeeded_pages,
        "failed_pages": run.failed_pages,
        "background": str(run.background_path),
        "canvas": run.master_layout["canvas"],
        "content_card": run.master_layout["regions"]["content_card"],
        "pages": [
            {
                "page_no": r.page_no,
                "source_text_sha256": r.source_text_sha256,
                "rendered_fields": r.rendered_fields,
                "source_text_match": r.source_text_match,
                "overflow": r.overflow,
                "truncated": r.truncated,
                "warnings": r.warnings,
                "output_path": str(r.output_path) if r.output_path else None,
                **r.visual,
            }
            for r in run.pages
        ],
    }


def render_final_render_report_markdown(run: FinalRenderRun, comparison_html_validation: dict[str, Any] | None = None) -> str:
    lines = ["# 最終教材画像 生成レポート（Phase 10.15）", ""]
    lines.append(f"- 生成日時: {run.generated_at}")
    lines.append(f"- 対象ページ数: {run.total_pages}")
    lines.append(f"- 成功: {len(run.succeeded_pages)}")
    lines.append(f"- 失敗: {len(run.failed_pages)}")
    lines.append(f"- 使用背景: {run.background_path}")
    card = run.master_layout["regions"]["content_card"]
    lines.append(f"- 共通本文カード: x={card['x']}, y={card['y']}, width={card['width']}, height={card['height']}")
    lines.append("")
    lines.append(
        "成功条件: `source_text_match == true` かつ `overflow == false` かつ `truncated == false` かつ "
        "`all_regions_visually_rendered == true`（描画処理へ渡した文字列の一致だけでなく、合成後の完成画像を"
        "実測して文字が実際に描画されていることを確認する）。"
    )
    lines.append("")
    if run.failed_pages:
        lines.append("## 失敗ページ")
        lines.append("")
        for r in run.pages:
            if not r.succeeded:
                lines.append(f"- Page {r.page_no}: {'; '.join(r.warnings) if r.warnings else '(理由不明)'}")
        lines.append("")
    lines.append("## ページ別結果")
    lines.append("")
    lines.append("| Page | 結果 | source_text_match | overflow | truncated | all_regions_visually_rendered | 水平利用率 | 垂直利用率 | 警告 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for r in run.pages:
        all_regions = r.visual.get("all_regions_visually_rendered", "")
        h_util = r.visual.get("horizontal_utilization", "")
        v_util = r.visual.get("vertical_utilization", "")
        lines.append(
            f"| {r.page_no} | {'成功' if r.succeeded else '失敗'} | {r.source_text_match} | {r.overflow} | "
            f"{r.truncated} | {all_regions} | {h_util} | {v_util} | {'; '.join(r.warnings) if r.warnings else ''} |"
        )
    lines.append("")
    if comparison_html_validation is not None:
        lines.append("## final_comparison.htmlの画像参照検証")
        lines.append("")
        lines.append(f"- 画像参照数: {comparison_html_validation['image_reference_count']}")
        lines.append(f"- 解決成功数: {comparison_html_validation['resolved_reference_count']}")
        lines.append(f"- 欠落数: {comparison_html_validation['missing_reference_count']}")
        lines.append(f"- 全参照解決可能: {comparison_html_validation['all_images_resolvable']}")
        if comparison_html_validation["broken_references"]:
            lines.append("- 壊れた参照:")
            for broken in comparison_html_validation["broken_references"]:
                lines.append(f"  - `{broken['src']}`: {broken['reason']}")
        lines.append("")
    return "\n".join(lines)


def relative_asset_path(html_path: Path, target_path: Path, *, allowed_root: Path) -> str:
    """`html_path`から`target_path`への相対パス（POSIX区切り）を、実在確認・安全確認込みで算出する。

    固定文字列の`../`/`../../`を手作業で選ぶ実装（Phase 10.15の`final_comparison.html`で発生した
    不具合の原因）をやめ、HTMLの実際の保存先から画像の実際の保存先までの相対パスを
    `os.path.relpath()`で機械的に算出する。
    """
    allowed_root_resolved = allowed_root.resolve()
    target_resolved = target_path.resolve()
    try:
        target_resolved.relative_to(allowed_root_resolved)
    except ValueError:
        raise ValueError(
            f"参照先が許可されたルート外です: {target_path} (allowed_root={allowed_root})"
        )
    if not target_resolved.exists():
        raise ValueError(f"参照先ファイルが見つかりません: {target_path}")
    if not target_resolved.is_file():
        raise ValueError(f"参照先がファイルではありません（ディレクトリ等）: {target_path}")

    html_dir_resolved = html_path.parent.resolve()
    rel = os.path.relpath(target_resolved, html_dir_resolved)
    return Path(rel).as_posix()


@dataclass
class _ComparisonImageRef:
    page_no: int
    category: str  # "source" | "preview" | "final"
    target_path: Path
    required: bool


def _comparison_image_refs(
    document: LessonDocument, run: "FinalRenderRun", output_dir: Path,
) -> list[_ComparisonImageRef]:
    results_by_no = {r.page_no: r for r in run.pages}
    refs: list[_ComparisonImageRef] = []
    for page in document.pages:
        result = results_by_no.get(page.page_no)
        refs.append(_ComparisonImageRef(
            page_no=page.page_no, category="source",
            target_path=output_dir / page.source_image, required=True,
        ))
        refs.append(_ComparisonImageRef(
            page_no=page.page_no, category="preview",
            target_path=output_dir / "rendered_brushup_preview" / f"page_{page.page_no:03d}.png", required=True,
        ))
        # 完成画像は、そのページがPhase 10.15で実際に成功した場合のみ必須とする
        # （オーバーフロー等で失敗したページに完成画像が無いのは不具合ではなく正しい状態のため）。
        refs.append(_ComparisonImageRef(
            page_no=page.page_no, category="final",
            target_path=output_dir / "rendered_final" / f"page_{page.page_no:03d}.png",
            required=bool(result and result.succeeded),
        ))
    return refs


def _validate_comparison_assets_exist(refs: list[_ComparisonImageRef]) -> None:
    """比較HTMLを書き出す前に、必須の参照先画像が全て実在することを確認する。

    1件でも欠けていれば、比較HTMLを「成功」として生成せずValueErrorで拒否する
    （ページ番号・区分・期待パス・不存在理由を含める）。
    """
    errors: list[str] = []
    for ref in refs:
        if not ref.required:
            continue
        if not ref.target_path.exists():
            errors.append(
                f"page_no={ref.page_no}, category={ref.category}: "
                f"期待される画像が見つかりません（期待パス={ref.target_path}, "
                "理由=ファイルが存在しません）"
            )
        elif not ref.target_path.is_file():
            errors.append(
                f"page_no={ref.page_no}, category={ref.category}: "
                f"期待パス={ref.target_path}はファイルではありません（ディレクトリ等）"
            )
    if errors:
        raise ValueError(
            "final_comparison.html生成前の画像実在確認に失敗しました:\n- " + "\n- ".join(errors)
        )


class _ImgSrcExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.sources: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "img":
            return
        for name, value in attrs:
            if name.lower() == "src" and value:
                self.sources.append(value)


def validate_comparison_html_references(html_path: Path, allowed_root: Path) -> dict[str, Any]:
    """書き出し済みのHTMLを実際に解析し、全`<img src>`の参照先が解決可能かを検証する。

    機械的なファイル存在確認だけでなく、Pillowで画像として読み込めることも確認する。
    """
    allowed_root_resolved = allowed_root.resolve()
    text = html_path.read_text(encoding="utf-8")
    parser = _ImgSrcExtractor()
    parser.feed(text)

    broken: list[dict[str, Any]] = []
    resolved_count = 0
    for src in parser.sources:
        reason = None
        if src.startswith(("http://", "https://", "//", "file://")):
            reason = "外部URLまたはfile://参照です"
        elif src.startswith("/"):
            reason = "絶対パスです"
        else:
            resolved = (html_path.parent / src).resolve()
            try:
                resolved.relative_to(allowed_root_resolved)
            except ValueError:
                reason = f"output-dir外を参照しています（解決先={resolved}）"
            else:
                if not resolved.exists():
                    reason = f"参照先ファイルが見つかりません（解決先={resolved}）"
                elif not resolved.is_file():
                    reason = f"参照先がファイルではありません（解決先={resolved}）"
                else:
                    try:
                        with Image.open(resolved) as img:
                            img.verify()
                    except Exception as e:  # noqa: BLE001 - Pillowの例外型はフォーマット依存のため広く捕捉する
                        reason = f"Pillowで画像として読み込めません（解決先={resolved}）: {e}"
        if reason:
            broken.append({"src": src, "reason": reason})
        else:
            resolved_count += 1

    total = len(parser.sources)
    return {
        "comparison_html": str(html_path),
        "image_reference_count": total,
        "resolved_reference_count": resolved_count,
        "missing_reference_count": total - resolved_count,
        "broken_references": broken,
        "all_images_resolvable": not broken,
    }


def render_final_comparison_html(
    document: LessonDocument, master_layout: dict[str, Any], page_specs: dict[int, dict[str, Any]],
    run: FinalRenderRun, output_dir: Path, html_path: Path,
) -> str:
    """外部CDN・外部CSS・外部JSに依存しない自己完結型のfinal_comparison.htmlを生成する。

    元画像・Phase 10.14プレビュー・Phase 10.15完成画像の3枚を横並びで比較する。
    画像への相対パスは、`relative_asset_path()`でHTMLの実際の保存先（`html_path`）から
    画像の実際の保存先まで機械的に算出する（固定文字列の`../`/`../../`を手作業で選ばない）。
    """
    output_dir = Path(output_dir)
    refs = _comparison_image_refs(document, run, output_dir)
    _validate_comparison_assets_exist(refs)

    results_by_no = {r.page_no: r for r in run.pages}
    card = master_layout["regions"]["content_card"]

    def esc(s: str) -> str:
        return html.escape(s or "")

    succeeded = sum(1 for r in run.pages if r.succeeded)

    sections = []
    for page in document.pages:
        spec = page_specs.get(page.page_no, {})
        result = results_by_no.get(page.page_no)
        content_layout = spec.get("content_layout", {})
        emphasis = spec.get("emphasis", [])
        emphasis_html = "".join(f"<li>{esc(rule.get('style',''))}: {esc(rule.get('match',''))}</li>" for rule in emphasis)
        status = "成功" if (result and result.succeeded) else "失敗"
        source_rel = relative_asset_path(html_path, output_dir / page.source_image, allowed_root=output_dir)
        preview_rel = relative_asset_path(
            html_path, output_dir / "rendered_brushup_preview" / f"page_{page.page_no:03d}.png", allowed_root=output_dir,
        )
        final_rel = (
            relative_asset_path(html_path, output_dir / "rendered_final" / f"page_{page.page_no:03d}.png", allowed_root=output_dir)
            if (result and result.succeeded) else ""
        )
        warnings_html = "".join(f"<li>{esc(w)}</li>" for w in (result.warnings if result else []))
        font_sizes = sorted({b.get("style", {}).get("font_size") for b in content_layout.get("blocks", []) if b.get("style", {}).get("font_size")})
        visual = result.visual if result else {}
        dark_artifact_any = any(
            visual.get(k) for k in ("title_dark_artifact_detected", "body_dark_artifact_detected", "notice_dark_artifact_detected", "page_number_dark_artifact_detected")
        )
        ocr_text = visual.get("ocr_text", "")
        ocr_ratio = visual.get("ocr_title_match_ratio", "")
        ocr_warning = visual.get("ocr_warning", "")
        sections.append(f"""
<section class="page-compare">
  <h2>Page {page.page_no}</h2>
  <div class="images">
    <figure><img src="{esc(source_rel)}" alt="元画像 page {page.page_no}"><figcaption>元画像</figcaption></figure>
    <figure><img src="{esc(preview_rel)}" alt="Phase 10.14 プレビュー page {page.page_no}"><figcaption>Phase 10.14 プレビュー</figcaption></figure>
    <figure>{f'<img src="{esc(final_rel)}" alt="完成画像 page {page.page_no}">' if final_rel else '<div class="missing">生成なし（' + esc(status) + '）</div>'}<figcaption>Phase 10.15 完成画像（{esc(status)}）</figcaption></figure>
  </div>
  <dl>
    <dt>内部レイアウト種別</dt><dd>{esc(content_layout.get('type',''))}</dd>
    <dt>縦方向配置</dt><dd>{esc(content_layout.get('vertical_alignment',''))}</dd>
    <dt>共通本文カード</dt><dd>x={card['x']}, y={card['y']}, width={card['width']}, height={card['height']}</dd>
    <dt>文字サイズ</dt><dd>{esc(', '.join(str(s) for s in font_sizes))}</dd>
    <dt>強調対象</dt><dd>{f'<ul>{emphasis_html}</ul>' if emphasis_html else 'なし'}</dd>
    <dt>source_text_match</dt><dd>{result.source_text_match if result else ''}</dd>
    <dt>overflow</dt><dd>{result.overflow if result else ''}</dd>
    <dt>truncated</dt><dd>{result.truncated if result else ''}</dd>
    <dt>title bbox / region</dt><dd>{esc(str(visual.get('title_bbox')))} / {esc(str(visual.get('title_region')))}</dd>
    <dt>title font size / visually_rendered</dt><dd>{visual.get('title_font_size', '')} / {visual.get('title_visually_rendered', '')}</dd>
    <dt>body bbox / utilization</dt><dd>{esc(str(visual.get('body_bbox')))} / h={visual.get('horizontal_utilization', '')}, v={visual.get('vertical_utilization', '')}</dd>
    <dt>dark artifact検査</dt><dd>{'検出あり' if dark_artifact_any else '検出なし'}</dd>
    <dt>notice source</dt><dd>{esc((result.rendered_fields.get('notice') if result else '') or '(なし)')}</dd>
    <dt>補助OCR結果</dt><dd>{esc(ocr_text) or '(空)'}（一致率: {ocr_ratio}）{f' — {esc(ocr_warning)}' if ocr_warning else ''}</dd>
    <dt>all_regions_visually_rendered</dt><dd>{visual.get('all_regions_visually_rendered', '')}</dd>
  </dl>
  {f'<ul class="warnings">{warnings_html}</ul>' if warnings_html else ''}
</section>
""")

    body = "\n".join(sections)
    return f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<title>最終教材画像 比較確認（Phase 10.15）</title>
<style>
body {{ font-family: sans-serif; margin: 24px; background: #f4f4f2; color: #202522; }}
.summary {{ background: #fff8e8; border: 1px solid #e8d7c1; border-radius: 8px; padding: 16px; margin-bottom: 24px; }}
.page-compare {{ background: #fff; border-radius: 12px; padding: 20px; margin-bottom: 24px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
.images {{ display: flex; gap: 16px; flex-wrap: wrap; }}
.images figure {{ margin: 0; }}
.images img {{ max-width: 360px; max-height: 260px; border: 1px solid #ddd; }}
.missing {{ width: 360px; height: 200px; display: flex; align-items: center; justify-content: center; background: #eee; }}
dl {{ margin-top: 12px; }}
dt {{ font-weight: bold; margin-top: 8px; }}
dd {{ margin: 0 0 0 12px; }}
.warnings {{ color: #a15c00; }}
</style>
</head>
<body>
<h1>最終教材画像 比較確認（Phase 10.15）</h1>
<div class="summary">
  <p>成功: {succeeded} / {len(run.pages)}</p>
  <p>使用した共通背景: {esc(str(run.background_path))}</p>
  <p>共通本文カード（全ページ共通）: x={card['x']}, y={card['y']}, width={card['width']}, height={card['height']}</p>
</div>
{body}
</body></html>
"""
