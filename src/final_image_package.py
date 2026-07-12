from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

from PIL import Image

from .brushup_renderer import _paragraph_lines_for_field
from .image_brushup_design import (
    _normalize_relative_path,
    lesson_pages_sha256,
)

if TYPE_CHECKING:
    from .lesson_pages import LessonDocument, LessonPage

# Phase 10.14: 確定済み本文（editable/lesson_pages.json、Phase 10.13でブラッシュアップ済み）と
# Phase 10.12のデザインJSON（brushup_design/）から、全ページ共通の「スライドマスター」
# （MASTER_LAYOUT.json）と、Codex（次工程・Phase 10.15）が最終ビジュアルを生成するための
# 自己完結パッケージ（final_image_package/）を作る。
#
# 最終目的（このプロジェクト全体）:
#   OCR確定原文 → 本文ブラッシュアップ → 構成・デザイン設計
#   → Codexによる最終ビジュアル生成 → 確定済み日本語本文の決定論的合成 → 完成画像
# Phase 10.7〜10.13で「本文ブラッシュアップ」まで確定した。Phase 10.12でPillowによる
# レイアウトの器（デザインJSON・レンダラー）ができた。本Phaseはその上に、
# 「全ページで完全に固定されたカード寸法」という制約を追加し、Codex向けの生成指示一式を作る。
# 実際の最終画像生成（Codexの背景生成・最終合成）はPhase 10.15（次工程・別セッション）の役割で
# あり、このモジュール自体はCodexを呼び出さず、`rendered_final/`も生成しない。

MASTER_ID = "deck_master_v1"
PACKAGE_DIR_NAME = "final_image_package"
RENDERED_BRUSHUP_PREVIEW_DIR_NAME = "rendered_brushup_preview"
INSTRUCTIONS_FILENAME = "CODEX_FINAL_IMAGE_GENERATION.md"
README_FILENAME = "README.md"
MASTER_LAYOUT_FILENAME = "MASTER_LAYOUT.json"
PACKAGE_MANIFEST_FILENAME = "package_manifest.json"
ASSET_MANIFEST_FILENAME = "asset_manifest.json"

# 通知文の固定文言（このコマンド実行後にユーザーがCodexへそのまま貼り付ける1文）。
_HANDOFF_SENTENCE_TEMPLATE = "{path}を読み、記載された手順を最後まで実行してください。"

# 元画像1706x960(16:9)を基準に、標準比率へ正規化する。実データは全ページ16:9で統一されている。
_STANDARD_RATIOS: tuple[tuple[str, float, tuple[int, int]], ...] = (
    ("16:9", 16 / 9, (1600, 900)),
    ("4:3", 4 / 3, (1600, 1200)),
    ("1:1", 1.0, (1400, 1400)),
    ("3:4", 3 / 4, (1200, 1600)),
    ("9:16", 9 / 16, (900, 1600)),
)

# マスターレイアウトの基準テンプレート（1600x900基準）。他の正規化キャンバスサイズでは
# width/heightの比率でスケーリングする（全ページで完全に同一の値を使う。ページごとに変えない）。
_BASE_CANVAS = (1600, 900)
_BASE_REGIONS = {
    "outer_margin": 56,
    "title_region": {"x": 72, "y": 52, "width": 1456, "height": 130},
    "content_card": {
        "x": 56, "y": 200, "width": 1488, "height": 590,
        "corner_radius": 28, "border_width": 1, "shadow_blur": 16, "shadow_offset_y": 6,
        "padding": {"top": 38, "right": 42, "bottom": 38, "left": 42},
    },
    "notice_region": {"x": 72, "y": 802, "width": 900, "height": 40},
    "page_number_region": {"x": 700, "y": 842, "width": 200, "height": 36},
}

_BASE_THEME = {
    "background_base": "#F6ECD9",
    "card_background": "#FFFDF8",
    "primary_text": "#4A1422",
    "secondary_text": "#6A4E50",
    "accent": "#D9835C",
    "border": "#E8D7C1",
    "shadow": "#00000020",
}

_BASE_TYPOGRAPHY = {
    "font_family_role": "japanese_gothic",
    "title_weight": "bold",
    "body_weight": "regular",
    "notice_weight": "regular",
}

_DEFAULT_PAGE_TYPOGRAPHY = {
    "title_font_size": 52, "body_font_size": 30, "minimum_body_font_size": 24, "line_spacing": 12,
}

_ALLOWED_CONTENT_LAYOUT_TYPES = ("single_column", "two_column")
_ALLOWED_VERTICAL_ALIGNMENTS = ("top", "center", "distributed")
_ALLOWED_CARD_BLOCK_TYPES = ("body", "summary", "note", "checklist", "steps", "quote", "divider", "spacer")
_ALLOWED_EMPHASIS_STYLES = ("strong", "section_heading")
_ALLOWED_SOURCE_FIELDS_FOR_EMPHASIS = ("title", "body", "summary")

_EXAMPLE_MARKER_RE = re.compile(r"^例\s*\d[）)]")
_NOTICE_PREFIX = "※"


# --- パス解決 -----------------------------------------------------------------------------


@dataclass
class FinalImagePackagePaths:
    output_dir: Path
    lesson_pages_path: Path
    assets_dir: Path
    design_manifest_path: Path
    design_pages_dir: Path
    package_dir: Path
    instructions_path: Path
    readme_path: Path
    master_layout_path: Path
    package_manifest_path: Path
    asset_manifest_path: Path
    pages_dir: Path
    text_dir: Path
    prompts_dir: Path
    master_background_prompt_path: Path
    preview_dir: Path
    master_guides_path: Path
    comparison_html_path: Path
    rendered_brushup_preview_dir: Path


def resolve_paths(output_dir: str | Path) -> FinalImagePackagePaths:
    base = Path(output_dir)
    package_dir = base / PACKAGE_DIR_NAME
    preview_dir = package_dir / "preview"
    return FinalImagePackagePaths(
        output_dir=base,
        lesson_pages_path=base / "editable" / "lesson_pages.json",
        assets_dir=base / "assets",
        design_manifest_path=base / "brushup_design" / "design_manifest.json",
        design_pages_dir=base / "brushup_design" / "pages",
        package_dir=package_dir,
        instructions_path=package_dir / INSTRUCTIONS_FILENAME,
        readme_path=package_dir / README_FILENAME,
        master_layout_path=package_dir / MASTER_LAYOUT_FILENAME,
        package_manifest_path=package_dir / PACKAGE_MANIFEST_FILENAME,
        asset_manifest_path=package_dir / ASSET_MANIFEST_FILENAME,
        pages_dir=package_dir / "pages",
        text_dir=package_dir / "text",
        prompts_dir=package_dir / "prompts",
        master_background_prompt_path=package_dir / "prompts" / "master_background.md",
        preview_dir=preview_dir,
        master_guides_path=preview_dir / "master_guides.png",
        comparison_html_path=preview_dir / "comparison.html",
        rendered_brushup_preview_dir=base / RENDERED_BRUSHUP_PREVIEW_DIR_NAME,
    )


def _relative_output_dir(output_dir: Path) -> str:
    from .ocr_claude_review import _relative_output_dir as _rel

    return _rel(output_dir)


def format_page_number_ranges(page_numbers: list[int]) -> str:
    from .ocr_claude_review import format_page_number_ranges as _format

    return _format(page_numbers)


def build_handoff_sentence(instructions_path_rel: str) -> str:
    return _HANDOFF_SENTENCE_TEMPLATE.format(path=instructions_path_rel)


# --- キャンバス正規化 -------------------------------------------------------------------------


def analyze_canvas_size(document: "LessonDocument", output_dir: Path) -> dict[str, Any]:
    """デッキ内の元画像サイズを集計し、標準比率へ正規化したキャンバスサイズを決める。

    決め方: (1) 各ページの元画像の縦横比を集計 (2) 標準比率(16:9/4:3/1:1/3:4/9:16)のうち
    最も近いものを多数決で選ぶ (3) その標準比率に対応する固定サイズを、デッキ全体で1つだけ使う。
    ページごとにキャンバスサイズを変えることは絶対にしない。
    """
    ratios: list[float] = []
    sizes: list[tuple[int, int]] = []
    for page in document.pages:
        if not page.source_image:
            continue
        image_path = output_dir / page.source_image
        if not image_path.exists():
            continue
        with Image.open(image_path) as img:
            w, h = img.size
        if h > 0:
            ratios.append(w / h)
            sizes.append((w, h))

    if not ratios:
        # 元画像を確認できない場合は安全側で16:9既定を使う。
        name, ratio, canvas = _STANDARD_RATIOS[0]
        return {
            "canvas": {"width": canvas[0], "height": canvas[1]},
            "standard_ratio": name, "source_ratio_average": None,
            "source_image_sizes": [], "warnings": ["元画像のサイズを1件も確認できなかったため16:9既定を使用しました"],
        }

    average_ratio = sum(ratios) / len(ratios)
    best = min(_STANDARD_RATIOS, key=lambda entry: abs(entry[1] - average_ratio))
    name, _, canvas = best
    return {
        "canvas": {"width": canvas[0], "height": canvas[1]},
        "standard_ratio": name, "source_ratio_average": round(average_ratio, 4),
        "source_image_sizes": sizes, "warnings": [],
    }


# --- マスターレイアウト -----------------------------------------------------------------------


def _scale_box(box: dict[str, Any], sx: float, sy: float) -> dict[str, Any]:
    return {"x": round(box["x"] * sx), "y": round(box["y"] * sy), "width": round(box["width"] * sx), "height": round(box["height"] * sy)}


def build_master_layout(document: "LessonDocument", output_dir: Path, lesson_pages_path: Path) -> dict[str, Any]:
    """全ページで完全に共通の`MASTER_LAYOUT.json`を組み立てる。

    1600x900を基準テンプレートとし、実際のキャンバスサイズに合わせて座標をスケーリングする
    （実データは元画像が全ページ16:9で統一されているため、そのまま1600x900になる）。
    スケーリング後の値は、この関数の戻り値としてただ1つに確定し、以後全ページで再利用する
    （ページごとに再計算・再スケーリングは行わない）。
    """
    canvas_info = analyze_canvas_size(document, output_dir)
    width, height = canvas_info["canvas"]["width"], canvas_info["canvas"]["height"]
    sx, sy = width / _BASE_CANVAS[0], height / _BASE_CANVAS[1]
    s_avg = (sx + sy) / 2

    content_card_base = _BASE_REGIONS["content_card"]
    content_card = _scale_box(content_card_base, sx, sy)
    content_card["corner_radius"] = round(content_card_base["corner_radius"] * s_avg)
    content_card["border_width"] = max(1, round(content_card_base["border_width"] * s_avg))
    content_card["shadow_blur"] = round(content_card_base["shadow_blur"] * s_avg)
    content_card["shadow_offset_y"] = round(content_card_base["shadow_offset_y"] * s_avg)
    content_card["padding"] = {
        "top": round(content_card_base["padding"]["top"] * sy),
        "right": round(content_card_base["padding"]["right"] * sx),
        "bottom": round(content_card_base["padding"]["bottom"] * sy),
        "left": round(content_card_base["padding"]["left"] * sx),
    }

    regions = {
        "outer_margin": round(_BASE_REGIONS["outer_margin"] * s_avg),
        "title_region": _scale_box(_BASE_REGIONS["title_region"], sx, sy),
        "content_card": content_card,
        "notice_region": _scale_box(_BASE_REGIONS["notice_region"], sx, sy),
        "page_number_region": _scale_box(_BASE_REGIONS["page_number_region"], sx, sy),
    }

    return {
        "schema_version": 1,
        "master_id": MASTER_ID,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_lesson_pages_sha256": lesson_pages_sha256(lesson_pages_path),
        "canvas": {"width": width, "height": height, "background_color": _BASE_THEME["background_base"]},
        "canvas_normalization": {
            "standard_ratio": canvas_info["standard_ratio"],
            "source_ratio_average": canvas_info["source_ratio_average"],
        },
        "regions": regions,
        "theme": dict(_BASE_THEME),
        "typography": dict(_BASE_TYPOGRAPHY),
        "card": {
            "corner_radius": content_card["corner_radius"], "border_width": content_card["border_width"],
            "shadow_blur": content_card["shadow_blur"], "shadow_offset_y": content_card["shadow_offset_y"],
        },
    }


def check_master_layout_freshness(master_layout: Any, *, current_lesson_pages_sha256: str) -> str | None:
    """既存の`MASTER_LAYOUT.json`が現在の`lesson_pages.json`を前提に作られたものかを確認する。"""
    if not isinstance(master_layout, dict):
        return None
    recorded = master_layout.get("source_lesson_pages_sha256")
    if not recorded:
        return "MASTER_LAYOUT.jsonにsource_lesson_pages_sha256が記録されていません。prepare-final-image-packageを再実行してください"
    if recorded != current_lesson_pages_sha256:
        return (
            "MASTER_LAYOUT.jsonは現在のlesson_pages.jsonとは異なる内容を前提に作られています"
            "（本文ブラッシュアップ等で内容が更新された可能性があります）。"
            "prepare-final-image-packageを再実行してください"
        )
    return None


# --- 本文の区分（本文＋注記の分離。行の並べ替え・複製はしない） -------------------------------------


@dataclass
class PageTextLayout:
    content_start: int
    content_end: int
    has_notice: bool
    emphasis_indices: list[int]
    two_column_range: tuple[int, int] | None
    two_column_split_at: int | None


def analyze_page_text(page: "LessonPage") -> PageTextLayout:
    """bodyの段落構造を機械的に分析し、レイアウト決定に必要な情報を返す。

    - 1行目はOCR取り込み時からの慣例でタイトル重複行のため、カード内容からは除外する
      （line_rangeで参照範囲を絞るだけで、行の並べ替え・複製は一切行わない）。
    - 最終行が「※」で始まる場合は独立した注記行として扱う（notice_region専用）。
    - 「◎」を含む行は強調対象、「例1）」「例2）」のような番号付き例示が2箇所ある場合は
      2段組みの分割対象として検出する。
    """
    paragraphs = _paragraph_lines_for_field(page, "body")
    n = len(paragraphs)
    has_notice = n > 0 and paragraphs[-1].strip().startswith(_NOTICE_PREFIX)
    content_end = n - 1 if has_notice else n
    content_start = min(1, content_end)

    emphasis_indices = [i for i in range(content_start, content_end) if "◎" in paragraphs[i]]
    marker_indices = [i for i in range(content_start, content_end) if _EXAMPLE_MARKER_RE.match(paragraphs[i].strip())]

    two_column_range = None
    two_column_split_at = None
    if len(marker_indices) == 2:
        two_column_range = (marker_indices[0], content_end)
        two_column_split_at = marker_indices[1]
        emphasis_indices = [i for i in emphasis_indices if i < marker_indices[0]]

    return PageTextLayout(
        content_start=content_start, content_end=content_end, has_notice=has_notice,
        emphasis_indices=emphasis_indices, two_column_range=two_column_range, two_column_split_at=two_column_split_at,
    )


def split_body_and_notice(body: str) -> tuple[str, str]:
    """text/page_NNN.json用に、bodyの生テキストを「本文」と「注記」へ分割する（改行・表記は保持）。

    生の本文行は`"speaker: text"`形式で保存されており、話者が空文字列の行は`": ※..."`のように
    先頭に区切り文字だけが付く。末尾行の生テキストの先頭文字だけで注記判定すると、この空話者行を
    検出できない（例: `": ※無断転載禁止（おとスタ）"`は`"※"`ではなく`":"`から始まる）ため、
    `parse_body_lines`と同じ話者・本文の分解ロジックを最終行にも適用し、分解後の本文部分が
    `"※"`で始まるかどうかで判定する（`analyze_page_text`が使う`_paragraph_lines_for_field`と
    一貫した判定にするため）。
    """
    from .lesson_pages import parse_body_lines

    lines = body.splitlines()
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        return body, ""
    parsed_last = parse_body_lines(lines[-1])
    if not parsed_last:
        return body, ""
    _, notice_text = parsed_last[0]
    if notice_text.strip().startswith(_NOTICE_PREFIX):
        return "\n".join(lines[:-1]), notice_text.strip()
    return body, ""


def _suggest_column_ratio(paragraphs: list[str], split_at: int, font_path: str | None, font_size: int) -> float:
    """2段組みの左右幅比率を、両列の最長行の実測幅から提案する（0.35〜0.65にクランプ）。"""
    from .brushup_renderer import _load_font

    font = _load_font(font_path, font_size, "regular")
    dummy = Image.new("RGB", (10, 10))
    from PIL import ImageDraw

    draw = ImageDraw.Draw(dummy)
    left = paragraphs[:split_at]
    right = paragraphs[split_at:]
    left_width = max((draw.textlength(p, font=font) for p in left), default=1.0)
    right_width = max((draw.textlength(p, font=font) for p in right), default=1.0)
    ratio = left_width / (left_width + right_width)
    return round(min(0.65, max(0.35, ratio)), 2)


def build_card_blocks(page: "LessonPage", layout: PageTextLayout, font_path: str | None) -> tuple[str, list[dict[str, Any]]]:
    """`analyze_page_text()`の結果から、content_card内に描画するblocksを組み立てる。

    `line_range`で本文の一部を参照するだけで、段落を複製・並べ替えしない
    （既存のPhase 10.12/10.13の設計制約を踏襲）。
    """
    typography = _DEFAULT_PAGE_TYPOGRAPHY

    def _segment_blocks(start: int, end: int) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = []
        cursor = start
        for idx in layout.emphasis_indices:
            if not (start <= idx < end):
                continue
            if cursor < idx:
                blocks.append(_normal_block(cursor, idx))
            blocks.append(_strong_block(idx, idx + 1))
            cursor = idx + 1
        if cursor < end:
            blocks.append(_normal_block(cursor, end))
        return blocks

    def _normal_block(start: int, end: int) -> dict[str, Any]:
        return {
            "id": f"body_{start}_{end}", "type": "body", "source_field": "body", "line_range": [start, end],
            "style": {
                "font_size": typography["body_font_size"], "font_weight": "regular",
                "color": _BASE_THEME["primary_text"], "alignment": "left", "padding": 0,
            },
        }

    def _strong_block(start: int, end: int) -> dict[str, Any]:
        return {
            "id": f"body_{start}_{end}_strong", "type": "body", "source_field": "body", "line_range": [start, end],
            "style": {
                "font_size": typography["body_font_size"] + 4, "font_weight": "bold",
                "color": _BASE_THEME["accent"], "alignment": "left", "padding": 0,
            },
        }

    if layout.two_column_range is not None:
        tc_start, tc_end = layout.two_column_range
        content_layout_type = "two_column"
        blocks = _segment_blocks(layout.content_start, tc_start)
        all_paragraphs = _paragraph_lines_for_field(page, "body", [tc_start, tc_end])
        relative_split = layout.two_column_split_at - tc_start
        column_ratio = _suggest_column_ratio(all_paragraphs, relative_split, font_path, typography["body_font_size"])
        blocks.append({
            "id": "body_columns", "type": "body", "source_field": "body", "columns": 2,
            "line_range": [tc_start, tc_end], "split_at": relative_split, "column_ratio": column_ratio,
            "style": {
                "font_size": typography["body_font_size"], "font_weight": "regular",
                "color": _BASE_THEME["primary_text"], "alignment": "left", "padding": 0,
            },
        })
    else:
        content_layout_type = "single_column"
        blocks = _segment_blocks(layout.content_start, layout.content_end)

    return content_layout_type, blocks


def _vertical_alignment_for(paragraph_count: int) -> str:
    if paragraph_count <= 6:
        return "center"
    if paragraph_count <= 9:
        return "distributed"
    return "top"


def build_emphasis_rules(page: "LessonPage", layout: PageTextLayout) -> list[dict[str, str]]:
    """Codex向け`emphasis`一覧を作る（本文を複製せず、実在する部分文字列への参照のみを持つ）。"""
    paragraphs = _paragraph_lines_for_field(page, "body")
    rules: list[dict[str, str]] = []
    for idx in layout.emphasis_indices:
        rules.append({"source": "body", "match": paragraphs[idx], "style": "strong"})
    if layout.two_column_range is not None:
        for idx in (layout.two_column_range[0], layout.two_column_split_at):
            if idx is not None:
                rules.append({"source": "body", "match": paragraphs[idx], "style": "section_heading"})
    return rules


def build_page_spec(page: "LessonPage", lesson_pages_sha256_value: str, font_path: str | None) -> dict[str, Any]:
    layout = analyze_page_text(page)
    content_layout_type, blocks = build_card_blocks(page, layout, font_path)
    paragraphs = _paragraph_lines_for_field(page, "body")
    vertical_alignment = _vertical_alignment_for(layout.content_end - layout.content_start)
    return {
        "schema_version": 1,
        "page_no": page.page_no,
        "master_layout": MASTER_ID,
        "source_lesson_pages_sha256": lesson_pages_sha256_value,
        "source_image": page.source_image,
        "content_layout": {"type": content_layout_type, "vertical_alignment": vertical_alignment, "blocks": blocks},
        "notice": {
            "line_range": [layout.content_end, None] if layout.has_notice else None,
        },
        "typography": dict(_DEFAULT_PAGE_TYPOGRAPHY),
        "emphasis": build_emphasis_rules(page, layout),
    }


# --- ページ仕様の検証 -------------------------------------------------------------------------


def _validate_line_range(line_range: Any, *, label: str) -> None:
    if not isinstance(line_range, list) or not (1 <= len(line_range) <= 2):
        raise ValueError(f"{label}は[start]または[start, end]の配列で指定してください: {line_range!r}")
    start = line_range[0]
    if not isinstance(start, int) or isinstance(start, bool) or start < 0:
        raise ValueError(f"{label}[0]は0以上の整数で指定してください: {start!r}")
    if len(line_range) == 2 and line_range[1] is not None:
        end = line_range[1]
        if not isinstance(end, int) or isinstance(end, bool) or end <= start:
            raise ValueError(f"{label}[1]は{label}[0]より大きい整数またはnullで指定してください: {end!r}")


def _validate_card_block(block: Any, *, block_index: int) -> None:
    if not isinstance(block, dict):
        raise ValueError(f"content_layout.blocks[{block_index}]がオブジェクト形式ではありません")
    block_type = block.get("type")
    if block_type not in _ALLOWED_CARD_BLOCK_TYPES:
        raise ValueError(f"content_layout.blocks[{block_index}].typeが不正です: {block_type!r}")
    if block_type in ("divider", "spacer"):
        return
    source_field = block.get("source_field")
    if source_field not in ("body", "summary"):
        raise ValueError(f"content_layout.blocks[{block_index}].source_fieldはbody/summaryのみ許可します: {source_field!r}")
    for forbidden_key in ("text", "content", "value", "html", "code"):
        if forbidden_key in block:
            raise ValueError(f"content_layout.blocks[{block_index}]で本文を複製するフィールド（{forbidden_key!r}）は使用できません")
    if "line_range" in block and block["line_range"] is not None:
        _validate_line_range(block["line_range"], label=f"content_layout.blocks[{block_index}].line_range")
    columns = block.get("columns", 1)
    if columns not in (1, 2):
        raise ValueError(f"content_layout.blocks[{block_index}].columnsは1または2で指定してください: {columns!r}")
    style = block.get("style")
    if not isinstance(style, dict) or not isinstance(style.get("font_size"), int):
        raise ValueError(f"content_layout.blocks[{block_index}].style.font_sizeが不正です")


def validate_page_spec(
    data: Any, *, expected_page_no: int, expected_source_image: str, master_layout: dict[str, Any], lesson_page: "LessonPage",
) -> list[str]:
    """ページ別仕様（`final_image_package/pages/page_NNN.json`）を検証し、問題点一覧を返す。

    マスター座標（canvas/content_card等）を上書きするフィールドが含まれていないことも
    ここで確認する（許可されたキーのみを読み取り、それ以外の座標系フィールドは仕様に存在しない）。
    """
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["デザインJSONがオブジェクト形式ではありません"]
    if data.get("schema_version") != 1:
        errors.append(f"schema_versionが未対応です: {data.get('schema_version')!r}")
    if data.get("page_no") != expected_page_no:
        errors.append(f"page_noが一致しません: {data.get('page_no')!r} != {expected_page_no!r}")
    if data.get("master_layout") != master_layout.get("master_id"):
        errors.append(f"master_layoutがMASTER_LAYOUT.jsonのmaster_idと一致しません: {data.get('master_layout')!r}")
    if data.get("source_lesson_pages_sha256") != master_layout.get("source_lesson_pages_sha256"):
        errors.append("source_lesson_pages_sha256がMASTER_LAYOUT.jsonと一致しません（古い仕様の可能性があります）")

    try:
        normalized_expected = _normalize_relative_path(expected_source_image, label="lesson_pages.jsonのsource_image")
        normalized_actual = _normalize_relative_path(str(data.get("source_image", "")), label=f"Page{expected_page_no}のsource_image")
        if normalized_actual != normalized_expected:
            errors.append(f"source_imageがlesson_pages.jsonと一致しません: {normalized_actual!r} != {normalized_expected!r}")
    except ValueError as e:
        errors.append(str(e))

    content_layout = data.get("content_layout")
    if not isinstance(content_layout, dict):
        errors.append("content_layoutがオブジェクト形式ではありません")
    else:
        if content_layout.get("type") not in _ALLOWED_CONTENT_LAYOUT_TYPES:
            errors.append(f"content_layout.typeが不正です: {content_layout.get('type')!r}")
        if content_layout.get("vertical_alignment") not in _ALLOWED_VERTICAL_ALIGNMENTS:
            errors.append(f"content_layout.vertical_alignmentが不正です: {content_layout.get('vertical_alignment')!r}")
        blocks = content_layout.get("blocks")
        if not isinstance(blocks, list) or not blocks:
            errors.append("content_layout.blocksは1件以上の配列で指定してください")
        else:
            for i, block in enumerate(blocks):
                try:
                    _validate_card_block(block, block_index=i)
                except ValueError as e:
                    errors.append(str(e))
        # マスター座標を上書きしようとしていないことの確認（そもそもキーが存在しないことを確認）。
        for forbidden_key in ("canvas", "content_card", "regions", "title_region", "notice_region", "page_number_region"):
            if forbidden_key in content_layout:
                errors.append(f"content_layoutはマスター座標（{forbidden_key!r}）を上書きできません")

    for i, rule in enumerate(data.get("emphasis", []) or []):
        if not isinstance(rule, dict):
            errors.append(f"emphasis[{i}]がオブジェクト形式ではありません")
            continue
        source = rule.get("source")
        match = rule.get("match")
        style = rule.get("style")
        if source not in _ALLOWED_SOURCE_FIELDS_FOR_EMPHASIS:
            errors.append(f"emphasis[{i}].sourceが不正です: {source!r}")
            continue
        if style not in _ALLOWED_EMPHASIS_STYLES:
            errors.append(f"emphasis[{i}].styleが不正です: {style!r}")
        if not isinstance(match, str) or not match:
            errors.append(f"emphasis[{i}].matchが空です")
            continue
        current_value = getattr(lesson_page, source, "")
        if match not in current_value:
            errors.append(f"emphasis[{i}].matchが現在のlesson_pages.json（{source}）に見つかりません: {match!r}")

    return errors


def validate_text_snapshot(data: Any, *, expected_page_no: int, lesson_page: "LessonPage", lesson_pages_sha256_value: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["text snapshotがオブジェクト形式ではありません"]
    if data.get("page_no") != expected_page_no:
        errors.append(f"text/page_no不一致: {data.get('page_no')!r} != {expected_page_no!r}")
    if data.get("source_lesson_pages_sha256") != lesson_pages_sha256_value:
        errors.append("text snapshotのsource_lesson_pages_sha256が現在のlesson_pages.jsonと一致しません")
    if data.get("title") != lesson_page.title:
        errors.append("text snapshotのtitleがlesson_pages.jsonと一致しません")
    if data.get("summary") != lesson_page.summary:
        errors.append("text snapshotのsummaryがlesson_pages.jsonと一致しません")
    expected_body, expected_notice = split_body_and_notice(lesson_page.body)
    if data.get("body") != expected_body:
        errors.append("text snapshotのbodyがlesson_pages.jsonの本文（注記除く）と一致しません")
    if data.get("notice") != expected_notice:
        errors.append("text snapshotのnoticeがlesson_pages.jsonの注記行と一致しません")
    return errors


def validate_master_layout(master_layout: Any, *, expected_page_numbers: list[int]) -> list[str]:
    errors: list[str] = []
    if not isinstance(master_layout, dict):
        return ["MASTER_LAYOUT.jsonがオブジェクト形式ではありません"]
    if master_layout.get("schema_version") != 1:
        errors.append(f"MASTER_LAYOUT.jsonのschema_versionが未対応です: {master_layout.get('schema_version')!r}")
    if master_layout.get("master_id") != MASTER_ID:
        errors.append(f"MASTER_LAYOUT.jsonのmaster_idが不正です: {master_layout.get('master_id')!r}")
    regions = master_layout.get("regions", {})
    for key in ("title_region", "content_card", "notice_region", "page_number_region"):
        if key not in regions:
            errors.append(f"MASTER_LAYOUT.jsonのregions.{key}がありません")
    return errors


# --- 指示書生成（Codex向け） -----------------------------------------------------------------


def render_codex_final_image_generation_instructions(
    document: "LessonDocument", output_dir: Path, master_layout: dict[str, Any],
) -> str:
    """`CODEX_FINAL_IMAGE_GENERATION.md`（自己完結。追加質問なしで最後まで実行できる指示書）。"""
    rel_dir = _relative_output_dir(output_dir)
    package_rel = f"{rel_dir}/{PACKAGE_DIR_NAME}"
    page_numbers = [p.page_no for p in document.pages]
    page_range_text = format_page_number_ranges(page_numbers)
    canvas = master_layout["canvas"]
    card = master_layout["regions"]["content_card"]

    lines: list[str] = []
    a = lines.append

    a("# Codex向け 最終画像生成パッケージ 実行指示書")
    a("")
    a("（`prepare-final-image-package`が自動生成。このファイルだけで、追加の質問をせず")
    a("最後まで作業を進められる自己完結した指示書です）")
    a("")

    a("## 0. 最終目的と、この工程（Phase 10.15）の位置づけ")
    a("")
    a("```text")
    a("OCR確定原文 → 本文ブラッシュアップ → 構成・デザイン設計")
    a("→ Codexによる最終ビジュアル生成 → 確定済み日本語本文の決定論的合成 → 完成画像")
    a("```")
    a("")
    a("あなた（Codex）が担当するのはこの矢印の**Codexによる最終ビジュアル生成**の部分だけです。")
    a("最終画像の生成そのもの（完成画像の確定）はこの指示書の作業範囲外であり、")
    a("あなたが作った文字なし背景・装飾画像の上に、確定済み日本語本文を決定論的に合成する")
    a("処理は、別の（Pillowベースの）レンダラーが行います。")
    a("")
    a("**あなたが行うこと:**")
    a("")
    a("- `prompts/master_background.md`の指示に従い、文字を一切含まない共通背景・装飾画像を生成する")
    a("- 必要であれば`prompts/page_NNN.md`（マスター背景の派生）に従いページ別の装飾差分を生成する")
    a("- 生成した画像を指定の出力先へ保存する")
    a("")
    a("**あなたが行わないこと（禁止事項）:**")
    a("")
    a("- **生成する画像へ日本語・英語を問わず一切の文字を描画しないこと**（タイトル・本文・")
    a("  注記・ページ番号を画像内へ焼き込まない。文字はすべて後工程が合成します）")
    a("- ロゴ・透かし・署名の追加")
    a("- 元画像の内容をそのまま模写・コピーすること")
    a("- `editable/lesson_pages.json`・元画像（`assets/`）・既存の`rendered/`・`rendered_brushup/`の変更")
    a(f"- `{package_rel}/rendered_final/`以外の場所への完成画像の保存")
    a("- Claude API等の外部AI呼び出し（あなた自身が画像生成モデルであるため対象外）")
    a("- Git commit・tag・push、ステージング")
    a("")

    a("## 1. 入力ファイル一覧")
    a("")
    a(f"- マスターレイアウト: `{package_rel}/{MASTER_LAYOUT_FILENAME}`（全ページ共通。カード位置・")
    a("  サイズ・配色・タイポグラフィが定義されています。座標を変更しないでください）")
    a(f"- ページ別内部レイアウト仕様: `{package_rel}/pages/page_NNN.json`")
    a(f"- 確定済み本文（Codex向けスナップショット）: `{package_rel}/text/page_NNN.json`")
    a(f"- 背景生成プロンプト（共通）: `{package_rel}/prompts/master_background.md`")
    a(f"- 背景生成プロンプト（ページ別差分・任意）: `{package_rel}/prompts/page_NNN.md`")
    a(f"- レイアウト確認用プレビュー（**完成画像ではありません**）: `{package_rel}/preview/page_NNN.png`")
    a("")
    a(f"- 対象ページ総数: {len(page_numbers)}")
    a(f"- ページ番号一覧: {page_range_text}")
    a(f"- 共通キャンバスサイズ: {canvas['width']}x{canvas['height']}（全ページ完全に同一）")
    a(f"- 共通本文カード: x={card['x']}, y={card['y']}, width={card['width']}, height={card['height']}")
    a("  （全ページで完全に同一の位置・サイズです。あなたが生成する背景画像は、この矩形の")
    a("  内側に装飾を置かないでください。後工程が白いカード・文字をこの矩形へ重ねて描画します）")
    a("")

    a("## 2. MASTER_LAYOUT.jsonの読み方")
    a("")
    a("```json")
    a(json.dumps({k: master_layout[k] for k in ("schema_version", "master_id", "canvas", "regions", "theme", "typography", "card")}, ensure_ascii=False, indent=2))
    a("```")
    a("")
    a("`regions.content_card`が「文字を後から合成する固定領域（装飾を避けるべき領域）」です。")
    a("`regions.title_region`・`regions.notice_region`・`regions.page_number_region`も同様に、")
    a("後工程が文字を描画する固定領域です。")
    a("")

    a("## 3. ページ別仕様（`pages/page_NNN.json`）の読み方")
    a("")
    a("```json")
    a('{"schema_version": 1, "page_no": 3, "master_layout": "deck_master_v1",')
    a(' "content_layout": {"type": "two_column", "vertical_alignment": "top", "blocks": [...]},')
    a(' "emphasis": [{"source": "body", "match": "（本文中の実在の一節）", "style": "section_heading"}]}')
    a("```")
    a("")
    a("`content_layout.type`はカード内部の構成種別（`single_column`/`two_column`）、")
    a("`emphasis`はレイアウト設計者が重要と判断した本文中の一節への参照です（本文そのものは")
    a("含まれていません。実際の文言は3節の`text/page_NNN.json`を参照してください）。")
    a("あなたが装飾を作る上で「このあたりが重要な情報らしい」という参考程度に使えますが、")
    a("**その文言を画像内に文字として描画してはいけません**。")
    a("")

    a("## 4. 確定済み本文データ（`text/page_NNN.json`）")
    a("")
    a("```json")
    a('{"schema_version": 1, "page_no": 3, "source_lesson_pages_sha256": "...",')
    a(' "title": "...", "body": "...", "summary": "...", "notice": "※無断転載禁止（おとスタ）"}')
    a("```")
    a("")
    a("これは`editable/lesson_pages.json`の確定済み本文（Phase 10.13で人間承認済みの改善後の")
    a("本文）そのものです。**あなたはこのテキストを画像へ描画しません。** 後工程の決定論的な")
    a("合成処理が使うためのデータであり、あなたにとっては「どんな内容の教材ページか」を")
    a("把握するための参考情報です。")
    a("")

    a("## 5. 背景生成プロンプト（`prompts/master_background.md`）")
    a("")
    a("共通の背景・装飾画像を1つ生成するためのプロンプトです。全ページで同じ背景を使うか、")
    a("ページ別プロンプト（`prompts/page_NNN.md`。存在する場合）でマスター背景からの")
    a("小さな差分（色味の微調整・装飾要素の位置替え等）を加えるかは、あなたの判断で構いません。")
    a("ただし、ページ別プロンプトは常にマスター背景の派生として扱い、まったく別の世界観の")
    a("背景を作らないでください（デッキ全体の視覚的統一感を保つため）。")
    a("")

    a("## 6. 出力先")
    a("")
    a(f"生成した文字なし背景画像は、`{rel_dir}/rendered_final/`（Phase 10.14時点では存在しません。")
    a("あなたが新規作成してください）へ保存してください。ファイル名は")
    a("`background_page_NNN.png`（ページ別背景がある場合）または`background_master.png`")
    a("（全ページ共通の場合）としてください。")
    a("")
    a("**`rendered_final/`へ、文字を含む完成画像そのものを保存しないでください。** 文字入りの")
    a("最終合成は、この指示書の作業範囲外です（別の決定論的レンダラーが行います）。")
    a("")

    a("## 7. 保存の単位・中断・再開")
    a("")
    a("ページ数が多い場合、1回のコンテキストへ全ページを読み込もうとしないでください。")
    a("")
    a("- 背景を1件（またはページ別差分を1ページ）生成するたびに、その場で保存する")
    a("- 既に保存済みのファイルがあるページはスキップしてよい（再実行時の再開に対応するため）")
    a("- 途中で作業を中断してよい。次回は未生成のファイルから再開する")
    a("")

    a("## 8. 品質確認・完了条件")
    a("")
    a("- [ ] 生成した画像に一切の文字（日本語・英語問わず）が含まれていない")
    a("- [ ] 生成した画像にロゴ・透かし・署名が含まれていない")
    a("- [ ] `regions.content_card`の内側に装飾を配置していない（後工程が白いカードを重ねます）")
    a("- [ ] 元画像をそのまま模写・コピーしていない")
    a("- [ ] 全ページ分の背景（または共通の1枚）が生成されている")
    a("- [ ] `editable/lesson_pages.json`・元画像・既存の`rendered/`・`rendered_brushup/`を変更していない")
    a(f"- [ ] `{rel_dir}/rendered_final/`以外へ完成画像を保存していない")
    a("")

    a("## 9. 次のステップ（あなたの作業範囲外）")
    a("")
    a("あなたが文字なし背景を保存したら、この工程（Phase 10.15の前半）は完了です。")
    a("確定済み本文をその背景の上へ決定論的に合成する処理（白いカード・タイトル・本文・")
    a("注記・ページ番号の描画）は、人間が別途実行する決定論的レンダラーの役割です。")
    a("")

    return "\n".join(lines) + "\n"


def render_package_readme() -> str:
    return f"""# {PACKAGE_DIR_NAME}/ ディレクトリについて

このディレクトリは、`prepare-final-image-package`が生成する、Codex（Phase 10.15）向けの
自己完結した最終画像生成パッケージです。

## このディレクトリの位置づけ

```text
OCR確定原文 → 本文ブラッシュアップ → 構成・デザイン設計
→ Codexによる最終ビジュアル生成 → 確定済み日本語本文の決定論的合成 → 完成画像
```

このディレクトリの中身は「Codexによる最終ビジュアル生成」に必要な入力一式です。
**このディレクトリ自体には、まだ完成画像は含まれていません。**

## 含まれるもの

- `{INSTRUCTIONS_FILENAME}` — Codex向け自己完結指示書
- `{MASTER_LAYOUT_FILENAME}` — 全ページ共通のスライドマスター（カード位置・サイズ・配色）
- `{PACKAGE_MANIFEST_FILENAME}` — パッケージ全体の集約manifest
- `{ASSET_MANIFEST_FILENAME}` — 元画像の一覧（sha256・サイズ付き）
- `pages/page_NNN.json` — ページ別の内部レイアウト仕様（カード内部の構成のみ。マスター座標は含まない）
- `text/page_NNN.json` — 確定済み本文のCodex向けスナップショット
- `prompts/master_background.md` — 共通背景生成プロンプト
- `prompts/page_NNN.md` — ページ別背景生成プロンプト（マスター背景の派生）
- `preview/page_NNN.png` — レイアウト確認用プレビュー（**完成画像ではありません**）
- `preview/master_guides.png` — 全ページ共通のマスターレイアウトを可視化したガイド画像
- `preview/comparison.html` — 元画像とプレビューの比較確認画面

## 完成画像について

`preview/page_NNN.png`および`{RENDERED_BRUSHUP_PREVIEW_DIR_NAME}/page_NNN.png`は、
レイアウト・文字量が固定カードへ収まるかを確認するためのプレビューであり、
**「完成画像」「最終画像」「ブラッシュアップ完了」ではありません。**

実際の完成画像（`rendered_final/`）は、Phase 10.15でCodexが文字なし背景を生成し、
その上へ確定済み本文を決定論的に合成した後に初めて確定します。本Phase（10.14）では
`rendered_final/`は生成しません。

## Git管理対象外

このディレクトリは`output/`配下にあるため、プロジェクトの既存方針によりGit管理対象外です。
"""


# --- テキストスナップショット --------------------------------------------------------------------


def build_text_snapshot(page: "LessonPage", lesson_pages_sha256_value: str) -> dict[str, Any]:
    body, notice = split_body_and_notice(page.body)
    return {
        "schema_version": 1,
        "page_no": page.page_no,
        "source_lesson_pages_sha256": lesson_pages_sha256_value,
        "title": page.title,
        "body": body,
        "summary": page.summary,
        "notice": notice,
    }


# --- 背景生成プロンプト -----------------------------------------------------------------------


def render_master_background_prompt(document: "LessonDocument", master_layout: dict[str, Any]) -> str:
    theme = master_layout["theme"]
    card = master_layout["regions"]["content_card"]
    canvas = master_layout["canvas"]
    return f"""# 共通背景・装飾画像 生成プロンプト（マスター背景）

## 素材テーマ

SNS運用・キャラクター設定をテーマにしたオンライン教材（実践ワークシート形式）。

## 想定読者

SNSアカウント運用でキャラクター設定を考える初心者〜中級者。

## アスペクト比・キャンバス

{canvas['width']}x{canvas['height']}（このプロジェクトのデッキ全体で共通の1枚として使えるように設計してください）

## デザインの方向性

- 温かみのある落ち着いたトーン。派手すぎず、長時間読んでも疲れない配色
- 教材・ワークシートらしい、整理された印象
- SNS運用・キャラクター設定というテーマに合う、柔らかく親しみやすい雰囲気

## カラーパレット（目安）

- 背景ベース: {theme['background_base']}
- カード（白）: {theme['card_background']}
- アクセント: {theme['accent']}
- 罫線: {theme['border']}

## テクスチャ・外周装飾

紙・布のような柔らかいテクスチャ、または控えめな幾何学装飾を外周部に配置してください。
装飾は画面の外周・余白部分に留め、中央付近を空けてください。

## 絶対に装飾を置いてはいけない領域（後工程が白いカード・文字を重ねます）

- 本文カード領域: x={card['x']}, y={card['y']}, width={card['width']}, height={card['height']}
- タイトル領域: {master_layout['regions']['title_region']}
- 注記領域: {master_layout['regions']['notice_region']}
- ページ番号領域: {master_layout['regions']['page_number_region']}

これらの領域は無地または非常に控えめな背景のみとし、視覚的に主張する装飾（人物・大きな図形・
高コントラストの模様等）を配置しないでください。

## 厳守事項

- **日本語・英語を問わず、一切の文字を画像内に生成しないでください**
- ロゴ・透かし・署名を含めないでください
- 元教材画像の内容をそのまま模写・コピーしないでください
- このデッキの全ページで共通して使える、1枚の背景として設計してください
- 後工程で白いカードと文字を精密に重ねて合成することを前提に設計してください
"""


def render_page_background_prompt(page: "LessonPage", master_layout: dict[str, Any]) -> str:
    card = master_layout["regions"]["content_card"]
    return f"""# ページ別 背景装飾差分プロンプト（Page {page.page_no}）

このプロンプトは`master_background.md`で生成した共通背景の**派生**です。まったく別の
世界観の背景を新規に作らないでください。共通背景をベースに、必要であれば以下の程度の
軽微な差分のみを加えてください。

## 差分の目安

- 装飾要素の位置をわずかにずらす
- 色味の彩度・明度を数%調整する
- 外周装飾の一部モチーフを変える（テーマは統一したまま）

## 装飾を置いてはいけない領域（共通背景と同じ制約）

- 本文カード領域: x={card['x']}, y={card['y']}, width={card['width']}, height={card['height']}

## 厳守事項（共通背景と同じ）

- 日本語・英語を問わず、一切の文字を画像内に生成しないでください
- ロゴ・透かし・署名を含めないでください
- 元教材画像の内容をそのまま模写・コピーしないでください
"""


# --- asset_manifest / package_manifest ---------------------------------------------------------


def build_asset_manifest(document: "LessonDocument", output_dir: Path) -> dict[str, Any]:
    assets = []
    for page in document.pages:
        entry: dict[str, Any] = {"page_no": page.page_no, "source_image": page.source_image}
        image_path = output_dir / page.source_image if page.source_image else None
        if image_path and image_path.exists():
            with Image.open(image_path) as img:
                entry["width"], entry["height"] = img.size
            entry["sha256"] = hashlib.sha256(image_path.read_bytes()).hexdigest()
        assets.append(entry)
    return {
        "schema_version": 1, "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "assets": assets,
    }


def build_package_manifest(
    document: "LessonDocument", master_layout: dict[str, Any], page_results: list[dict[str, Any]],
) -> dict[str, Any]:
    card = master_layout["regions"]["content_card"]
    return {
        "schema_version": 1,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": "codex_final_image_package",
        "source_lesson_pages_sha256": master_layout["source_lesson_pages_sha256"],
        "master_layout": MASTER_LAYOUT_FILENAME,
        "total_pages": len(document.pages),
        "completed_pages": len(page_results),
        "canvas_size": [master_layout["canvas"]["width"], master_layout["canvas"]["height"]],
        "content_card": {"x": card["x"], "y": card["y"], "width": card["width"], "height": card["height"]},
        "pages": page_results,
    }
