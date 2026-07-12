from __future__ import annotations

import hashlib
import html
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from .image_brushup_design import (
    _ALLOWED_SOURCE_FIELDS,
    _normalize_relative_path,
    check_manifest_freshness,
    lesson_pages_sha256,
    validate_design_page,
    validate_manifest,
)
from .image_renderer import resolve_font_path, warn_missing_japanese_font
from .lesson_pages import LessonDocument, LessonPage, clean_dialogue_lines

# Phase 10.12: `brushup_design/pages/page_NNN.json`（AIエージェントが設計したデザイン指示）と
# `editable/lesson_pages.json`（確定済み本文）から、決定論的にブラッシュアップ済み教材画像
# （`rendered_brushup/page_NNN.png`）を生成するレンダラー。
#
# 本文はデザインJSONではなく、常に`LessonPage`（lesson_pages.json由来）から取得する
# （`source_field`はキー名の参照であり、本文そのものはデザインJSON内に存在しない）。
# 画像生成AIへ本文を描かせない・AIに本文を再生成させないという安全設計の核心部分。

_MIN_RENDER_FONT_SIZE = 8
_DEFAULT_LINE_SPACING_RATIOS = (1.4, 1.25, 1.1)
_COLUMN_GUTTER = 24
_BOX_CORNER_RADIUS = 12
_FOOTER_HEIGHT = 48
_FOOTER_FONT_SIZE = 18

_BOLD_SUBSTITUTIONS = (
    ("W3.ttc", "W6.ttc"),
    ("W4.ttc", "W6.ttc"),
    ("Regular.ttc", "Bold.ttc"),
    ("Regular.otf", "Bold.otf"),
    ("R.ttc", "B.ttc"),
)


def _hex_to_rgb(value: str | None, default: tuple[int, int, int] = (0, 0, 0)) -> tuple[int, int, int]:
    if not value:
        return default
    value = value.lstrip("#")
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))


def _bold_font_path(font_path: str | None) -> str | None:
    if not font_path:
        return font_path
    for needle, replacement in _BOLD_SUBSTITUTIONS:
        if needle in font_path:
            candidate = font_path.replace(needle, replacement)
            if Path(candidate).exists():
                return candidate
    return font_path


def _load_font(font_path: str | None, size: int, weight: str = "regular") -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    resolved = _bold_font_path(font_path) if weight == "bold" else font_path
    if resolved:
        try:
            return ImageFont.truetype(resolved, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    """1文字ずつ幅を測って折り返す（日本語は単語区切りが無いため文字単位で行う）。"""
    lines: list[str] = []
    for raw_line in text.splitlines() or [""]:
        if not raw_line:
            lines.append("")
            continue
        current = ""
        for ch in raw_line:
            candidate = current + ch
            if draw.textlength(candidate, font=font) > max_width and current:
                lines.append(current)
                current = ch
            else:
                current = candidate
        lines.append(current)
    return lines


# --- 本文取得（source_field） ------------------------------------------------------------------


def _paragraph_lines_for_field(
    page: LessonPage, source_field: str, line_range: list[int | None] | None = None
) -> list[str]:
    """`source_field`が指すLessonPageの値から、段落単位の行リストを作る。

    body: 話者・台詞ペア(clean_dialogue_lines)ごとに1段落。title/summary: 全体で1段落。
    `line_range`（`[start, end]`。0始まり、endはNoneで末尾まで）を指定すると、bodyの段落リストを
    その範囲だけに絞り込む。これは元の行を並べ替えたり複製したりせず、既存の行の一部だけを
    別ブロックとして参照するための機構であり、本文の改変・複製ではない
    （例: 1行目=タイトル重複行を除いて2行目以降だけを参照する等）。
    """
    if source_field not in _ALLOWED_SOURCE_FIELDS:
        raise ValueError(f"未許可のsource_fieldです: {source_field!r}")
    if source_field == "body":
        pairs = clean_dialogue_lines(page.body)
        paragraphs = [f"{speaker}: {text}" if speaker else text for speaker, text in pairs]
    else:
        value = getattr(page, source_field)
        paragraphs = [value] if value else []

    if line_range is not None:
        start = line_range[0] if line_range[0] is not None else 0
        end = line_range[1] if len(line_range) > 1 and line_range[1] is not None else len(paragraphs)
        paragraphs = paragraphs[start:end]
    return paragraphs


# --- レイアウト計算・shrink-to-fit ------------------------------------------------------------


@dataclass
class _FitResult:
    fits: bool
    font_size: int = 0
    line_height: int = 0
    padding: int = 0
    columns: int = 1
    wrapped_columns: list[list[str]] = field(default_factory=list)
    height: int = 0
    # "group"ブロック専用: 子ブロックごとの(block, _FitResult)一覧（1つの共有背景の中へ
    # 複数の子ブロックを積み重ねて描画するため）。それ以外のtypeでは常に空リスト。
    group_children: list[tuple[dict, "_FitResult"]] = field(default_factory=list)
    # columns=2の場合の左列の幅比率（0.5=均等）。測定時と描画時で同じ境界を使うため、
    # 描画側（_draw_paragraph_block）はwidthから独自に再計算せずこの値を再利用する。
    column_ratio: float = 0.5


def _measure_wrapped(draw, paragraphs: list[str], font, line_height: int, max_width: int) -> tuple[list[str], int]:
    wrapped: list[str] = []
    for para in paragraphs:
        wrapped.extend(_wrap_text(draw, para, font, max_width))
    return wrapped, len(wrapped) * line_height


def _column_widths(max_width: int, padding: int, column_ratio: float) -> tuple[int, int]:
    """2段組みの左右それぞれの実際の描画幅を計算する（測定・描画の両方で同じ値を使う）。"""
    available = max(0, max_width - _COLUMN_GUTTER)
    left_gross = available * column_ratio
    right_gross = available - left_gross
    left_width = max(40, int(left_gross) - padding * 2)
    right_width = max(40, int(right_gross) - padding * 2)
    return left_width, right_width


def _measure_columns(
    draw, paragraphs: list[str], font, line_height: int, max_width: int, padding: int, columns: int,
    split_at: int | None = None, column_ratio: float = 0.5,
) -> tuple[list[list[str]], int]:
    """columns=1なら通常の折り返し、columns=2なら段落の境界を保ったまま左右2列へ分配して測定する。

    段落（paragraphs）の途中で列をまたがせない（1つの段落の折り返し行が左右に分裂しないように
    段落単位で列を割り当てる）。`split_at`（paragraphsのインデックス）を指定すると、その位置で
    厳密に列を分ける（例: 「例1」の段落群を左列、「例2」の段落群を右列に固定する等、意味的な
    まとまりを保った2段組みを実現するため）。省略時は行数がなるべく均等になる段落境界を自動選択する。
    `column_ratio`（既定0.5=均等）で左右の幅配分を変えられる（片方の内容が明らかに長い場合に、
    不自然な位置で改行されるのを防ぐため）。
    """
    if columns == 1:
        content_width = max(40, max_width - padding * 2)
        wrapped, text_height = _measure_wrapped(draw, paragraphs, font, line_height, content_width)
        return [wrapped], text_height + padding * 2

    left_width, right_width = _column_widths(max_width, padding, column_ratio)

    if split_at is None:
        # 自動分割時は、まず左幅で仮の行数を測って境界を決める（左右で幅が異なる場合の近似）。
        probe_wrapped = [_wrap_text(draw, p, font, left_width) for p in paragraphs]
        total_lines = sum(len(w) for w in probe_wrapped)
        target = total_lines / 2
        cumulative = 0
        split_at = len(probe_wrapped)
        for i, w in enumerate(probe_wrapped):
            if cumulative >= target:
                split_at = i
                break
            cumulative += len(w)
    split_at = max(0, min(split_at, len(paragraphs)))

    left_wrapped = [_wrap_text(draw, p, font, left_width) for p in paragraphs[:split_at]]
    right_wrapped = [_wrap_text(draw, p, font, right_width) for p in paragraphs[split_at:]]
    left = [line for w in left_wrapped for line in w]
    right = [line for w in right_wrapped for line in w]
    return [left, right], max(len(left), len(right)) * line_height + padding * 2


def _fit_text_block(
    draw: ImageDraw.ImageDraw,
    paragraphs: list[str],
    *,
    font_path: str | None,
    base_font_size: int,
    weight: str,
    base_padding: int,
    max_width: int,
    available_height: int,
    force_columns: int = 1,
    allow_two_column_fallback: bool = False,
    split_at: int | None = None,
    column_ratio: float = 0.5,
) -> _FitResult:
    """spec 11節の縮小手順（1: 指定サイズ→2: 余白縮小→3: 行間縮小→4: 最小フォントまで縮小→
    5: 2段組みへ変更）を、この優先順で試し、収まる最初の組み合わせを返す。

    `force_columns=2`はデザインJSON側が明示的に指定した2段組み（spec 4.3節）で、
    オーバーフロー発生の有無に関わらず常に2段組みで測定する。`allow_two_column_fallback`は
    spec 11節ステップ5の「それでも収まらない場合だけ2段組みへ変更する」自動フォールバック。
    `split_at`はデザインJSON側が明示した列の分割位置（spec 4.5節）。`column_ratio`は左右の幅配分。
    """
    floor_size = max(_MIN_RENDER_FONT_SIZE, int(base_font_size * 0.6))
    size_candidates: list[int] = []
    for ratio in (1.0, 0.9, 0.8, 0.7, 0.6):
        candidate = max(floor_size, int(base_font_size * ratio))
        if candidate not in size_candidates:
            size_candidates.append(candidate)
    if floor_size not in size_candidates:
        size_candidates.append(floor_size)

    padding_candidates: list[int] = []
    for ratio in (1.0, 0.75, 0.5):
        candidate = max(8, int(base_padding * ratio))
        if candidate not in padding_candidates:
            padding_candidates.append(candidate)

    for font_size in size_candidates:
        font = _load_font(font_path, font_size, weight)
        for spacing_ratio in _DEFAULT_LINE_SPACING_RATIOS:
            line_height = max(font_size + 2, int(font_size * spacing_ratio))
            for padding in padding_candidates:
                wrapped_columns, total_height = _measure_columns(
                    draw, paragraphs, font, line_height, max_width, padding, force_columns, split_at, column_ratio
                )
                if total_height <= available_height:
                    return _FitResult(
                        fits=True, font_size=font_size, line_height=line_height, padding=padding,
                        columns=force_columns, wrapped_columns=wrapped_columns, height=total_height,
                        column_ratio=column_ratio,
                    )

    if allow_two_column_fallback and force_columns == 1:
        font_size = floor_size
        font = _load_font(font_path, font_size, weight)
        line_height = max(font_size + 2, int(font_size * _DEFAULT_LINE_SPACING_RATIOS[-1]))
        padding = padding_candidates[-1]
        wrapped_columns, total_height = _measure_columns(draw, paragraphs, font, line_height, max_width, padding, 2)
        if total_height <= available_height:
            return _FitResult(
                fits=True, font_size=font_size, line_height=line_height, padding=padding,
                columns=2, wrapped_columns=wrapped_columns, height=total_height, column_ratio=0.5,
            )

    return _FitResult(fits=False)


# --- ブロック描画 ---------------------------------------------------------------------------


def _draw_paragraph_block(
    draw: ImageDraw.ImageDraw, fit: _FitResult, font_path: str | None, weight: str,
    x: int, y: int, width: int, color: tuple[int, int, int], alignment: str,
) -> int:
    font = _load_font(font_path, fit.font_size, weight)
    if fit.columns == 1:
        cursor_y = y + fit.padding
        for line in fit.wrapped_columns[0]:
            _draw_aligned_line(draw, line, font, x + fit.padding, cursor_y, width - fit.padding * 2, color, alignment)
            cursor_y += fit.line_height
        return y + fit.height
    # 測定時（_measure_columns）と同じcolumn_ratioで境界を再計算する（描画時に独自の50/50を
    # 使うと、測定時に決めた折り返し幅とずれて文字がはみ出すため、必ず同じ計算式を使う）。
    left_width, right_width = _column_widths(width, fit.padding, fit.column_ratio)
    column_widths = (left_width, right_width)
    available = max(0, width - _COLUMN_GUTTER)
    left_gross = int(available * fit.column_ratio)
    col_x_offsets = (0, left_gross + _COLUMN_GUTTER)
    for col_index, lines in enumerate(fit.wrapped_columns):
        col_x = x + col_x_offsets[col_index] + fit.padding
        cursor_y = y + fit.padding
        for line in lines:
            _draw_aligned_line(draw, line, font, col_x, cursor_y, column_widths[col_index], color, alignment)
            cursor_y += fit.line_height
    return y + fit.height


def _draw_aligned_line(draw, line: str, font, x: int, y: int, width: int, color, alignment: str) -> None:
    line_width = draw.textlength(line, font=font)
    if alignment == "center":
        draw_x = x + max(0, (width - line_width) / 2)
    elif alignment == "right":
        draw_x = x + max(0, width - line_width)
    else:
        draw_x = x
    draw.text((draw_x, y), line, fill=color, font=font)


def _draw_itemized_block(
    draw: ImageDraw.ImageDraw, block_type: str, fit: _FitResult, font_path: str | None, weight: str,
    x: int, y: int, width: int, color: tuple[int, int, int], accent_color: tuple[int, int, int],
) -> int:
    """checklist/steps/quoteは、段落ごとに接頭辞（チェックボックス・番号・アクセントバー）を付ける。

    fitは_fit_text_blockが返す「段落を結合済みの折り返し行」ではなく、ここでは段落単位で
    再折り返しする（各段落＝1項目として、接頭辞のインデントを保つため）。
    """
    font = _load_font(font_path, fit.font_size, weight)
    indent = fit.font_size + 12
    cursor_y = y + fit.padding
    content_width = width - fit.padding * 2 - indent

    for para_lines in fit.wrapped_columns:
        if not para_lines:
            continue
        first_line_y = cursor_y
        if block_type == "checklist":
            box_size = int(fit.font_size * 0.6)
            box_y = first_line_y + (fit.line_height - box_size) // 2
            draw.rectangle(
                [x + fit.padding, box_y, x + fit.padding + box_size, box_y + box_size],
                outline=accent_color, width=2,
            )
        elif block_type == "quote":
            bar_height = len(para_lines) * fit.line_height
            draw.rectangle(
                [x + fit.padding, first_line_y, x + fit.padding + 4, first_line_y + bar_height],
                fill=accent_color,
            )
        for i, line in enumerate(para_lines):
            prefix = ""
            if block_type == "steps" and i == 0:
                prefix = ""
            draw.text((x + fit.padding + indent, cursor_y), line, fill=color, font=font)
            cursor_y += fit.line_height
    return y + fit.height


def _draw_step_numbers(
    draw: ImageDraw.ImageDraw, fit: _FitResult, font_path: str | None, weight: str,
    x: int, y: int, color: tuple[int, int, int],
) -> None:
    font = _load_font(font_path, fit.font_size, weight)
    cursor_y = y + fit.padding
    for step_index, para_lines in enumerate(fit.wrapped_columns, start=1):
        if not para_lines:
            continue
        draw.text((x + fit.padding, cursor_y), f"{step_index}.", fill=color, font=font)
        cursor_y += len(para_lines) * fit.line_height


# --- ページ全体の描画 -------------------------------------------------------------------------


@dataclass
class PageRenderResult:
    page_no: int
    succeeded: bool
    template: str
    rendered_fields: dict[str, str]
    source_fields: dict[str, str]
    text_match: bool
    overflow: bool
    warnings: list[str]
    output_path: Path | None
    font_used: str | None


def _block_paragraphs_by_item(page: LessonPage, block: dict[str, Any]) -> list[list[str]]:
    """checklist/steps/quote向けに、段落ごとに独立して折り返せるよう、段落のリストのリストを作る。"""
    paragraphs = _paragraph_lines_for_field(page, block["source_field"], block.get("line_range"))
    return [[p] for p in paragraphs]


_GROUP_CHILD_TYPES = ("title", "summary", "body")


def _measure_group(
    draw: ImageDraw.ImageDraw, page: LessonPage, group_block: dict[str, Any],
    font_path: str | None, max_width: int, available_height: int,
) -> _FitResult:
    """`group`ブロック（複数の子ブロックを1つの共有背景の中へ積み重ねて描画する）を測定する。

    元画像では、問いかけ（大きく太字）と補足説明（やや小さい通常文字）が同じ1枚のカードの中に
    収まっている。子ブロックごとに文字サイズ・太さを変えつつ、背景は1つだけ描画することで、
    「①〜の問いかけが本文の外へ独立して浮いて見える」という見た目のズレを防ぐ。
    """
    style = group_block.get("style", {})
    padding = style.get("padding", 16)
    inner_width = max(40, max_width - padding * 2)

    child_fits: list[tuple[dict, _FitResult]] = []
    used_height = padding * 2
    for child in group_block.get("blocks", []):
        child_type = child["type"]
        if child_type not in _GROUP_CHILD_TYPES:
            return _FitResult(fits=False)
        child_style = child.get("style", {})
        child_weight = child_style.get("font_weight", "regular")
        paragraphs = _paragraph_lines_for_field(page, child["source_field"], child.get("line_range"))
        remaining = max(0, available_height - used_height)
        child_fit = _fit_text_block(
            draw, paragraphs, font_path=font_path, base_font_size=child_style["font_size"], weight=child_weight,
            base_padding=child_style.get("padding", 0), max_width=inner_width, available_height=remaining,
            allow_two_column_fallback=False,
        )
        if not child_fit.fits:
            return _FitResult(fits=False)
        child_fits.append((child, child_fit))
        used_height += child_fit.height

    return _FitResult(fits=True, height=used_height, group_children=child_fits)


def _draw_group(
    draw: ImageDraw.ImageDraw, group_block: dict[str, Any], fit: _FitResult, theme: dict[str, Any],
    font_path: str | None, x: int, y: int, width: int,
) -> int:
    style = group_block.get("style", {})
    padding = style.get("padding", 16)
    bg = style.get("background_color")
    box_bg = _hex_to_rgb(bg) if bg else _hex_to_rgb(theme.get("secondary_color"), default=(240, 240, 235))
    draw.rounded_rectangle([x + 8, y, x + width - 8, y + fit.height], radius=_BOX_CORNER_RADIUS, fill=box_bg)

    cursor_y = y + padding
    inner_x = x + padding
    inner_width = width - padding * 2
    for child, child_fit in fit.group_children:
        child_style = child.get("style", {})
        color = _hex_to_rgb(child_style.get("color"), default=(20, 20, 20))
        alignment = child_style.get("alignment", "left")
        weight = child_style.get("font_weight", "regular")
        cursor_y = _draw_paragraph_block(draw, child_fit, font_path, weight, inner_x, cursor_y, inner_width, color, alignment)
    return y + fit.height


def render_design_page(
    page: LessonPage,
    design: dict[str, Any],
    output_dir: Path,
    dest_path: Path,
    font_path: str | None,
) -> PageRenderResult:
    """1ページ分のデザインJSON+確定済み本文から、ブラッシュアップ画像を描画する。"""
    canvas_cfg = design["canvas"]
    width, height = canvas_cfg["width"], canvas_cfg["height"]
    bg_color = _hex_to_rgb(canvas_cfg.get("background_color"), default=(255, 255, 255))
    theme = design.get("theme", {})
    muted_color = _hex_to_rgb(theme.get("muted_text_color"), default=(120, 120, 120))
    accent_color = _hex_to_rgb(theme.get("accent_color"), default=(180, 120, 40))

    image = Image.new("RGB", (width, height), color=bg_color)
    draw = ImageDraw.Draw(image)

    footer_cfg = design.get("footer", {})
    footer_height = _FOOTER_HEIGHT if (footer_cfg.get("show_page_number", True) or footer_cfg.get("show_source_notice", True)) else 0
    content_bottom = height - footer_height

    warnings: list[str] = []
    overflow = False
    rendered_fields: dict[str, str] = {}
    source_fields = {f: getattr(page, f) for f in _ALLOWED_SOURCE_FIELDS}

    # 1パス目: 実際には描画せず、各blockの高さだけを測定する。全ブロックの合計高さが
    # キャンバス内に余白を残す場合、2パス目の描画開始yを下げて縦方向に中央寄せし、
    # 内容が少ないページが不自然に上詰めにならないようにする。
    layout_items: list[tuple[dict, _FitResult | None]] = []
    probe_y = 0
    for block in design["blocks"]:
        block_type = block["type"]
        style = block.get("style", {})
        weight = style.get("font_weight", "regular")
        available_height = max(0, content_bottom - probe_y)

        if block_type == "divider":
            item_height = style.get("padding", 12) * 2
            layout_items.append((block, None))
            probe_y += item_height
            continue
        if block_type == "spacer":
            item_height = style.get("padding", 24)
            layout_items.append((block, None))
            probe_y += item_height
            continue

        if block_type == "group":
            fit = _measure_group(draw, page, block, font_path, width, available_height)
            if not fit.fits:
                overflow = True
                warnings.append(f"block[{block.get('id')}]が収まりませんでした（group）")
                break
            layout_items.append((block, fit))
            probe_y += fit.height
            continue

        source_field = block["source_field"]
        line_range = block.get("line_range")
        if block_type in ("title", "summary", "body"):
            paragraphs = _paragraph_lines_for_field(page, source_field, line_range)
            requested_columns = block.get("columns", 1) if block_type == "body" else 1
            fit = _fit_text_block(
                draw, paragraphs, font_path=font_path, base_font_size=style["font_size"], weight=weight,
                base_padding=style.get("padding", 0), max_width=width, available_height=available_height,
                force_columns=requested_columns, split_at=block.get("split_at"),
                column_ratio=block.get("column_ratio", 0.5),
                allow_two_column_fallback=(block_type == "body" and requested_columns == 1),
            )
        elif block_type == "note":
            paragraphs = _paragraph_lines_for_field(page, source_field, line_range)
            requested_columns = block.get("columns", 1)
            fit = _fit_text_block(
                draw, paragraphs, font_path=font_path, base_font_size=style["font_size"], weight=weight,
                base_padding=style.get("padding", 16), max_width=width, available_height=available_height,
                force_columns=requested_columns, split_at=block.get("split_at"),
                column_ratio=block.get("column_ratio", 0.5),
                allow_two_column_fallback=False,
            )
        elif block_type in ("checklist", "steps", "quote"):
            item_paragraphs = [p for group in _block_paragraphs_by_item(page, block) for p in group]
            fit = _fit_text_block(
                draw, item_paragraphs, font_path=font_path, base_font_size=style["font_size"], weight=weight,
                base_padding=style.get("padding", 12), max_width=width, available_height=available_height,
                allow_two_column_fallback=False,
            )
            if fit.fits:
                font = _load_font(font_path, fit.font_size, weight)
                indent = fit.font_size + 12
                content_width = width - fit.padding * 2 - indent
                fit.wrapped_columns = [_wrap_text(draw, item, font, content_width) for item in item_paragraphs]
        else:
            raise ValueError(f"未対応のblock.typeです: {block_type!r}")

        if not fit.fits:
            overflow = True
            warnings.append(f"block[{block.get('id')}]が収まりませんでした（{block_type}）")
            break
        layout_items.append((block, fit))
        probe_y += fit.height

    if not overflow:
        total_height = probe_y
        start_y = max(0, (content_bottom - total_height) // 2)
    else:
        start_y = 0

    # 2パス目: 1パス目で確定したfit結果を再利用し、start_yを起点に実際に描画する。
    y = start_y
    for block, fit in layout_items:
        block_type = block["type"]
        style = block.get("style", {})
        color = _hex_to_rgb(style.get("color"), default=(20, 20, 20))
        bg = style.get("background_color")
        block_bg_color = _hex_to_rgb(bg) if bg else None
        alignment = style.get("alignment", "left")
        weight = style.get("font_weight", "regular")

        if block_type == "divider":
            line_y = y + style.get("padding", 12)
            draw.line([(0, line_y), (width, line_y)], fill=muted_color, width=2)
            y = line_y + style.get("padding", 12)
            continue
        if block_type == "spacer":
            y += style.get("padding", 24)
            continue

        if block_type == "group":
            for child in block.get("blocks", []):
                rendered_fields[child["source_field"]] = getattr(page, child["source_field"])
            y = _draw_group(draw, block, fit, theme, font_path, 0, y, width)
            continue

        source_field = block["source_field"]
        rendered_fields[source_field] = getattr(page, source_field)

        if block_type in ("title", "summary", "body"):
            if block_bg_color is not None:
                draw.rectangle([0, y, width, y + fit.height], fill=block_bg_color)
            y = _draw_paragraph_block(draw, fit, font_path, weight, 0, y, width, color, alignment)
        elif block_type == "note":
            box_bg = block_bg_color or _hex_to_rgb(theme.get("secondary_color"), default=(240, 240, 235))
            draw.rounded_rectangle([8, y, width - 8, y + fit.height], radius=_BOX_CORNER_RADIUS, fill=box_bg)
            y = _draw_paragraph_block(draw, fit, font_path, weight, 0, y, width, color, alignment)
        elif block_type in ("checklist", "steps", "quote"):
            new_y = _draw_itemized_block(
                draw, block_type, fit, font_path, weight, 0, y, width, color, accent_color,
            )
            if block_type == "steps":
                _draw_step_numbers(draw, fit, font_path, weight, 0, y, accent_color)
            y = new_y

    if not overflow:
        if footer_cfg.get("show_page_number", True):
            footer_font = _load_font(font_path, _FOOTER_FONT_SIZE, "regular")
            footer_text = f"- {page.page_no} -"
            footer_width = draw.textlength(footer_text, font=footer_font)
            draw.text(((width - footer_width) / 2, content_bottom + 12), footer_text, fill=muted_color, font=footer_font)
        if footer_cfg.get("show_source_notice", True) and page.source_image:
            # 元画像ファイル名を小さく表示する（トレーサビリティ用途）。固定の著作権表記等の
            # 発明文言はここでは描画しない（本文に実在する注記はbody側のブロックで表示する）。
            notice_font = _load_font(font_path, _FOOTER_FONT_SIZE - 2, "regular")
            draw.text((12, content_bottom + 12), page.source_image, fill=muted_color, font=notice_font)

    text_match = all(rendered_fields.get(f, source_fields[f]) == source_fields[f] for f in rendered_fields)

    if overflow:
        return PageRenderResult(
            page_no=page.page_no, succeeded=False, template=design["template"],
            rendered_fields=rendered_fields, source_fields=source_fields, text_match=text_match,
            overflow=True, warnings=warnings, output_path=None, font_used=font_path,
        )

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(dest_path)
    return PageRenderResult(
        page_no=page.page_no, succeeded=True, template=design["template"],
        rendered_fields=rendered_fields, source_fields=source_fields, text_match=text_match,
        overflow=False, warnings=warnings, output_path=dest_path, font_used=font_path,
    )


# --- 元画像コピー検出 -------------------------------------------------------------------------


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_not_source_copy(source_path: Path, rendered_path: Path) -> bool:
    """`rendered_path`が`source_path`の単純コピーではない（ハッシュ・ピクセルデータが異なる）ことを確認する。

    True = 正しく異なる（コピーではない）。両ファイルが存在しない場合はTrue（比較不能として扱う）。
    """
    if not source_path.exists() or not rendered_path.exists():
        return True
    if _file_sha256(source_path) != _file_sha256(rendered_path):
        return True
    try:
        with Image.open(source_path) as src, Image.open(rendered_path) as dst:
            return list(src.getdata()) != list(dst.getdata())
    except Exception:
        return True


# --- 一括レンダリング -------------------------------------------------------------------------


@dataclass
class RenderRun:
    generated_at: str
    total_pages: int
    succeeded_pages: list[int]
    failed_pages: list[int]
    pages: list[PageRenderResult]
    template_counts: dict[str, int]
    manifest_errors: list[str]


def load_design_pages(paths, document: LessonDocument) -> tuple[dict[int, dict[str, Any]], list[str]]:
    """`design_manifest.json`とページ別デザインJSONを読み込み・検証する。

    戻り値は(page_no -> デザインJSON辞書, エラー一覧)。エラーが1件でもあれば呼び出し側は
    レンダリングを行わない。
    """
    errors: list[str] = []
    if not paths.manifest_path.exists():
        return {}, [f"design_manifest.jsonが見つかりません: {paths.manifest_path}"]
    try:
        manifest = json.loads(paths.manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return {}, [f"design_manifest.jsonのJSONが不正です: {e}"]

    expected_page_numbers = [p.page_no for p in document.pages]
    errors.extend(validate_manifest(manifest, expected_page_numbers=expected_page_numbers))

    if paths.lesson_pages_path.exists():
        freshness_error = check_manifest_freshness(
            manifest, current_lesson_pages_sha256=lesson_pages_sha256(paths.lesson_pages_path)
        )
        if freshness_error:
            errors.append(freshness_error)

    page_by_no = {p.page_no: p for p in document.pages}
    designs: dict[int, dict[str, Any]] = {}
    for entry in manifest.get("pages", []):
        if not isinstance(entry, dict) or "page_no" not in entry or "design_file" not in entry:
            continue
        page_no = entry["page_no"]
        try:
            design_path = _normalize_relative_path(entry["design_file"], label=f"page_no={page_no}のdesign_file")
        except ValueError as e:
            errors.append(str(e))
            continue
        full_path = paths.design_dir / design_path
        if not full_path.exists():
            errors.append(f"デザインJSONが見つかりません（page_no={page_no}）: {full_path}")
            continue
        try:
            data = json.loads(full_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            errors.append(f"デザインJSONのJSONが不正です（page_no={page_no}）: {e}")
            continue

        lesson_page = page_by_no.get(page_no)
        if lesson_page is None:
            errors.append(f"lesson_pages.jsonに存在しないpage_noです: {page_no}")
            continue
        try:
            validate_design_page(data, expected_page_no=page_no, expected_source_image=lesson_page.source_image)
        except ValueError as e:
            errors.append(f"page_no={page_no}のデザインJSONが不正です: {e}")
            continue
        designs[page_no] = data

    return designs, errors


def render_all_pages(
    document: LessonDocument, designs: dict[int, dict[str, Any]], output_dir: Path, rendered_dir: Path,
    font_path: str | None = None,
) -> RenderRun:
    from datetime import datetime

    resolved_font_path = resolve_font_path(font_path)
    if resolved_font_path is None:
        warn_missing_japanese_font()

    results: list[PageRenderResult] = []
    template_counts: dict[str, int] = {}
    for page in document.pages:
        design = designs.get(page.page_no)
        if design is None:
            results.append(PageRenderResult(
                page_no=page.page_no, succeeded=False, template="", rendered_fields={}, source_fields={},
                text_match=False, overflow=False, warnings=["デザインJSONがありません"], output_path=None,
                font_used=resolved_font_path,
            ))
            continue
        dest_path = rendered_dir / f"page_{page.page_no:03d}.png"
        result = render_design_page(page, design, output_dir, dest_path, resolved_font_path)
        template_counts[design["template"]] = template_counts.get(design["template"], 0) + 1

        if result.succeeded and page.source_image:
            source_path = output_dir / page.source_image
            if not verify_not_source_copy(source_path, dest_path):
                result.warnings.append("生成画像が元画像と同一です（元画像コピー検出）")
                result.succeeded = False

        results.append(result)

    succeeded_pages = [r.page_no for r in results if r.succeeded]
    failed_pages = [r.page_no for r in results if not r.succeeded]

    return RenderRun(
        generated_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        total_pages=len(document.pages), succeeded_pages=succeeded_pages, failed_pages=failed_pages,
        pages=results, template_counts=template_counts, manifest_errors=[],
    )


# --- レポート・比較HTML -----------------------------------------------------------------------


def render_report_json(run: RenderRun) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "generated_at": run.generated_at,
        "total_pages": run.total_pages,
        "succeeded_pages": run.succeeded_pages,
        "failed_pages": run.failed_pages,
        "template_counts": run.template_counts,
        "pages": [
            {
                "page_no": r.page_no, "succeeded": r.succeeded, "template": r.template,
                "rendered_fields": r.rendered_fields, "source_fields": r.source_fields,
                "text_match": r.text_match, "overflow": r.overflow, "warnings": r.warnings,
                "output_path": str(r.output_path) if r.output_path else None,
            }
            for r in run.pages
        ],
    }


def render_report_markdown(run: RenderRun) -> str:
    lines = ["# ブラッシュアップ画像 生成レポート", ""]
    lines.append(f"- 生成日時: {run.generated_at}")
    lines.append(f"- 対象ページ数: {run.total_pages}")
    lines.append(f"- 成功: {len(run.succeeded_pages)}")
    lines.append(f"- 失敗: {len(run.failed_pages)}")
    lines.append(f"- テンプレート内訳: {run.template_counts}")
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
    lines.append("| Page | 結果 | テンプレート | text_match | overflow | 警告 |")
    lines.append("|---|---|---|---|---|---|")
    for r in run.pages:
        lines.append(
            f"| {r.page_no} | {'成功' if r.succeeded else '失敗'} | {r.template} | {r.text_match} | "
            f"{r.overflow} | {'; '.join(r.warnings) if r.warnings else ''} |"
        )
    lines.append("")
    return "\n".join(lines)


def render_comparison_html(document: LessonDocument, designs: dict[int, dict[str, Any]], run: RenderRun, output_dir: Path) -> str:
    """外部CDN・外部CSS・外部JSに依存しない自己完結型のcomparison.htmlを生成する。"""
    results_by_no = {r.page_no: r for r in run.pages}
    page_by_no = {p.page_no: p for p in document.pages}

    def esc(s: str) -> str:
        return html.escape(s or "")

    sections = []
    for page in document.pages:
        result = results_by_no.get(page.page_no)
        design = designs.get(page.page_no)
        source_rel = page.source_image
        rendered_rel = f"../{run.pages[0].output_path.parent.name}/page_{page.page_no:03d}.png" if result and result.output_path else ""
        status = "成功" if (result and result.succeeded) else "失敗"
        template = design.get("template", "") if design else ""
        preserve = ", ".join(design.get("design_intent", {}).get("preserve", [])) if design else ""
        improve = ", ".join(design.get("design_intent", {}).get("improve", [])) if design else ""
        warnings_html = "".join(f"<li>{esc(w)}</li>" for w in (result.warnings if result else []))
        sections.append(f"""
<section class="page-compare">
  <h2>Page {page.page_no}</h2>
  <div class="images">
    <figure><img src="../{esc(source_rel)}" alt="元画像 page {page.page_no}"><figcaption>元画像</figcaption></figure>
    <figure>{f'<img src="{esc(rendered_rel)}" alt="ブラッシュアップ画像 page {page.page_no}">' if rendered_rel else '<div class="missing">生成なし</div>'}<figcaption>ブラッシュアップ画像（{esc(status)}）</figcaption></figure>
  </div>
  <dl>
    <dt>title</dt><dd>{esc(page.title)}</dd>
    <dt>body</dt><dd class="body-text">{esc(page.body)}</dd>
    <dt>テンプレート</dt><dd>{esc(template)}</dd>
    <dt>維持した要素</dt><dd>{esc(preserve)}</dd>
    <dt>改善した要素</dt><dd>{esc(improve)}</dd>
  </dl>
  {f'<ul class="warnings">{warnings_html}</ul>' if warnings_html else ''}
  <label class="check"><input type="checkbox"> このページを確認済み</label>
</section>
""")

    body = "\n".join(sections)
    return f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<title>ブラッシュアップ画像 比較確認</title>
<style>
body {{ font-family: sans-serif; margin: 24px; background: #f4f4f2; color: #202522; }}
.page-compare {{ background: #fff; border-radius: 12px; padding: 20px; margin-bottom: 24px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
.images {{ display: flex; gap: 16px; flex-wrap: wrap; }}
.images figure {{ margin: 0; }}
.images img {{ max-width: 320px; max-height: 420px; border: 1px solid #ddd; }}
.missing {{ width: 320px; height: 420px; display: flex; align-items: center; justify-content: center; background: #eee; }}
dl {{ margin-top: 12px; }}
dt {{ font-weight: bold; margin-top: 8px; }}
dd {{ margin: 0 0 0 12px; white-space: pre-wrap; }}
.body-text {{ max-height: 160px; overflow-y: auto; }}
.warnings {{ color: #a15c00; }}
</style>
</head>
<body>
<h1>ブラッシュアップ画像 比較確認</h1>
<p>成功: {len(run.succeeded_pages)} / {run.total_pages}　失敗: {len(run.failed_pages)}</p>
{body}
</body></html>
"""
