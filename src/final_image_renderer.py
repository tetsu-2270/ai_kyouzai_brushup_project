from __future__ import annotations

import html
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from . import final_image_package
from . import image_brushup_design
from . import brushup_renderer
from .brushup_renderer import (
    _BOX_CORNER_RADIUS,
    _block_paragraphs_by_item,
    _draw_itemized_block,
    _draw_paragraph_block,
    _draw_step_numbers,
    _fit_text_block,
    _hex_to_rgb,
    _load_font,
    _paragraph_lines_for_field,
    _wrap_text,
)
from .image_renderer import resolve_font_path, warn_missing_japanese_font
from .lesson_pages import LessonDocument, LessonPage

# Phase 10.14: `final_image_package.py`が組み立てたマスターレイアウト・ページ別仕様を使い、
# (1) レイアウト確認用のプレビュー画像（完成画像ではない）、(2) 全ページ共通のマスターレイアウトを
# 可視化するガイド画像、(3) 比較確認用HTML を決定論的に生成する。
#
# 実際の完成画像生成（Codexの文字なし背景 + このモジュールと同様の決定論的合成）はPhase 10.15の
# 役割であり、ここでは`rendered_final/`を一切生成しない。


def _hex_to_rgba_alpha(value: str) -> tuple[tuple[int, int, int], int]:
    v = value.lstrip("#")
    r, g, b = int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)
    a = int(v[6:8], 16) if len(v) >= 8 else 255
    return (r, g, b), a


def _blend(bg: tuple[int, int, int], fg: tuple[int, int, int], alpha: int) -> tuple[int, int, int]:
    a = alpha / 255
    return tuple(round(b * (1 - a) + f * a) for b, f in zip(bg, fg))  # type: ignore[return-value]


# --- カード内部ブロックの測定・描画（brushup_rendererの低レベル部品を再利用） ------------------------


def _measure_card_blocks(
    draw: ImageDraw.ImageDraw, page: LessonPage, blocks: list[dict[str, Any]], font_path: str | None,
    width: int, available_height: int,
) -> tuple[list[tuple[dict, Any]], int, bool, dict | None]:
    items: list[tuple[dict, Any]] = []
    used = 0
    for block in blocks:
        block_type = block["type"]
        style = block.get("style", {})
        weight = style.get("font_weight", "regular")
        remaining = max(0, available_height - used)

        if block_type == "divider":
            h = style.get("padding", 12) * 2
            items.append((block, None))
            used += h
            continue
        if block_type == "spacer":
            h = style.get("padding", 24)
            items.append((block, None))
            used += h
            continue

        source_field = block.get("source_field")
        line_range = block.get("line_range")
        if block_type in ("body", "summary"):
            paragraphs = _paragraph_lines_for_field(page, source_field, line_range)
            requested_columns = block.get("columns", 1)
            fit = _fit_text_block(
                draw, paragraphs, font_path=font_path, base_font_size=style["font_size"], weight=weight,
                base_padding=style.get("padding", 0), max_width=width, available_height=remaining,
                force_columns=requested_columns, split_at=block.get("split_at"),
                column_ratio=block.get("column_ratio", 0.5),
                allow_two_column_fallback=(requested_columns == 1),
            )
        elif block_type == "note":
            paragraphs = _paragraph_lines_for_field(page, source_field, line_range)
            requested_columns = block.get("columns", 1)
            fit = _fit_text_block(
                draw, paragraphs, font_path=font_path, base_font_size=style["font_size"], weight=weight,
                base_padding=style.get("padding", 16), max_width=width, available_height=remaining,
                force_columns=requested_columns, split_at=block.get("split_at"),
                column_ratio=block.get("column_ratio", 0.5), allow_two_column_fallback=False,
            )
        elif block_type in ("checklist", "steps", "quote"):
            item_paragraphs = [p for grp in _block_paragraphs_by_item(page, block) for p in grp]
            fit = _fit_text_block(
                draw, item_paragraphs, font_path=font_path, base_font_size=style["font_size"], weight=weight,
                base_padding=style.get("padding", 12), max_width=width, available_height=remaining,
                allow_two_column_fallback=False,
            )
            if fit.fits:
                font = _load_font(font_path, fit.font_size, weight)
                indent = fit.font_size + 12
                content_width = width - fit.padding * 2 - indent
                fit.wrapped_columns = [_wrap_text(draw, item, font, content_width) for item in item_paragraphs]
        else:
            raise ValueError(f"final_image_packageで未対応のblock.typeです: {block_type!r}")

        if not fit.fits:
            return items, used, False, block
        items.append((block, fit))
        used += fit.height

    return items, used, True, None


def _draw_card_blocks(
    draw: ImageDraw.ImageDraw, items: list[tuple[dict, Any]], font_path: str | None,
    x0: int, y0: int, width: int, vertical_alignment: str, available_height: int, used_height: int,
    theme: dict[str, Any],
) -> None:
    extra = max(0, available_height - used_height)
    n = len(items)
    border_color = _hex_to_rgb(theme.get("border"), default=(200, 200, 200))
    accent_color = _hex_to_rgb(theme.get("accent"), default=(180, 120, 40))

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


# --- 固定領域（タイトル・注記・ページ番号）の描画 ----------------------------------------------


def _draw_title_region(draw, page: LessonPage, page_spec: dict[str, Any], master_layout: dict[str, Any], font_path: str | None) -> bool:
    region = master_layout["regions"]["title_region"]
    theme = master_layout["theme"]
    typography = page_spec.get("typography", {})
    weight = "bold" if master_layout["typography"].get("title_weight") == "bold" else "regular"
    fit = _fit_text_block(
        draw, [page.title], font_path=font_path, base_font_size=typography.get("title_font_size", 52), weight=weight,
        base_padding=0, max_width=region["width"], available_height=region["height"], allow_two_column_fallback=False,
    )
    if not fit.fits:
        return False
    _draw_paragraph_block(draw, fit, font_path, weight, region["x"], region["y"], region["width"], _hex_to_rgb(theme["primary_text"]), "left")
    return True


def _draw_notice_region(draw, page: LessonPage, page_spec: dict[str, Any], master_layout: dict[str, Any], font_path: str | None) -> bool:
    region = master_layout["regions"]["notice_region"]
    theme = master_layout["theme"]
    notice_cfg = page_spec.get("notice") or {}
    line_range = notice_cfg.get("line_range")
    if not line_range:
        return True
    paragraphs = _paragraph_lines_for_field(page, "body", line_range)
    if not paragraphs or not paragraphs[0]:
        return True
    weight = master_layout["typography"].get("notice_weight", "regular")
    fit = _fit_text_block(
        draw, paragraphs, font_path=font_path, base_font_size=18, weight=weight,
        base_padding=0, max_width=region["width"], available_height=region["height"], allow_two_column_fallback=False,
    )
    if not fit.fits:
        return False
    _draw_paragraph_block(draw, fit, font_path, weight, region["x"], region["y"], region["width"], _hex_to_rgb(theme["secondary_text"]), "left")
    return True


def _draw_page_number_region(draw, page: LessonPage, master_layout: dict[str, Any], font_path: str | None) -> None:
    region = master_layout["regions"]["page_number_region"]
    theme = master_layout["theme"]
    font = _load_font(font_path, 22, "regular")
    text = f"- {page.page_no} -"
    text_width = draw.textlength(text, font=font)
    x = region["x"] + max(0, (region["width"] - text_width) / 2)
    y = region["y"] + max(0, (region["height"] - 22) / 2)
    draw.text((x, y), text, fill=_hex_to_rgb(theme["secondary_text"]), font=font)


def _draw_card_background(image: Image.Image, draw: ImageDraw.ImageDraw, master_layout: dict[str, Any]) -> None:
    card = master_layout["regions"]["content_card"]
    theme = master_layout["theme"]
    bg_rgb = _hex_to_rgb(theme["background_base"])
    shadow_rgb, shadow_alpha = _hex_to_rgba_alpha(theme.get("shadow", "#00000020"))
    shadow_color = _blend(bg_rgb, shadow_rgb, shadow_alpha)

    offset = card.get("shadow_offset_y", 0)
    if offset:
        draw.rounded_rectangle(
            [card["x"], card["y"] + offset, card["x"] + card["width"], card["y"] + card["height"] + offset],
            radius=card["corner_radius"], fill=shadow_color,
        )
    draw.rounded_rectangle(
        [card["x"], card["y"], card["x"] + card["width"], card["y"] + card["height"]],
        radius=card["corner_radius"], fill=_hex_to_rgb(theme["card_background"]),
        outline=_hex_to_rgb(theme.get("border"), default=(220, 220, 210)), width=card.get("border_width", 1),
    )


@dataclass
class PagePreviewResult:
    page_no: int
    succeeded: bool
    overflow: bool
    warnings: list[str] = field(default_factory=list)
    output_path: Path | None = None


def render_page_preview(
    page: LessonPage, page_spec: dict[str, Any], master_layout: dict[str, Any], font_path: str | None,
) -> tuple[Image.Image | None, list[str], bool]:
    """1ページ分のプレビュー画像を、固定マスターレイアウトに従って生成する。

    タイトル領域・本文カード（固定サイズ）・注記領域・ページ番号領域はすべて`master_layout`の
    座標を使い、ページごとに変えない。カード内部の構成（`content_layout.blocks`）だけがページ別。
    """
    canvas = master_layout["canvas"]
    theme = master_layout["theme"]
    image = Image.new("RGB", (canvas["width"], canvas["height"]), color=_hex_to_rgb(theme["background_base"]))
    draw = ImageDraw.Draw(image)
    warnings: list[str] = []

    if not _draw_title_region(draw, page, page_spec, master_layout, font_path):
        warnings.append("タイトルが固定のtitle_regionに収まりませんでした")
        return None, warnings, True

    _draw_card_background(image, draw, master_layout)
    card = master_layout["regions"]["content_card"]
    padding = card["padding"]
    x0 = card["x"] + padding["left"]
    y0 = card["y"] + padding["top"]
    width = card["width"] - padding["left"] - padding["right"]
    available_height = card["height"] - padding["top"] - padding["bottom"]

    blocks = page_spec["content_layout"]["blocks"]
    items, used, fits, failed_block = _measure_card_blocks(draw, page, blocks, font_path, width, available_height)
    if not fits:
        block_id = failed_block.get("id", "?") if failed_block else "?"
        warnings.append(f"本文が固定サイズの本文カードに収まりませんでした（block={block_id}）")
        return None, warnings, True

    vertical_alignment = page_spec["content_layout"]["vertical_alignment"]
    _draw_card_blocks(draw, items, font_path, x0, y0, width, vertical_alignment, available_height, used, theme)

    if not _draw_notice_region(draw, page, page_spec, master_layout, font_path):
        warnings.append("注記が固定のnotice_regionに収まりませんでした")
        return None, warnings, True

    _draw_page_number_region(draw, page, master_layout, font_path)
    return image, warnings, False


# --- マスターガイド画像 -----------------------------------------------------------------------


def render_master_guides(master_layout: dict[str, Any], font_path: str | None) -> Image.Image:
    """全ページ共通のマスターレイアウト（キャンバス・各固定領域）を可視化するガイド画像を作る。"""
    canvas = master_layout["canvas"]
    regions = master_layout["regions"]
    image = Image.new("RGB", (canvas["width"], canvas["height"]), color=(248, 248, 244))
    draw = ImageDraw.Draw(image)
    label_font = _load_font(font_path, 20, "regular")

    margin = regions["outer_margin"]
    draw.rectangle([margin, margin, canvas["width"] - margin, canvas["height"] - margin], outline=(140, 140, 140), width=2)
    draw.text((10, 8), f"canvas {canvas['width']}x{canvas['height']} / outer_margin={margin}", fill=(90, 90, 90), font=label_font)

    region_colors = {
        "title_region": (70, 120, 190),
        "content_card": (200, 90, 80),
        "notice_region": (90, 150, 90),
        "page_number_region": (150, 110, 190),
    }
    for name, color in region_colors.items():
        r = regions[name]
        draw.rectangle([r["x"], r["y"], r["x"] + r["width"], r["y"] + r["height"]], outline=color, width=3)
        draw.text((r["x"] + 6, r["y"] + 6), f"{name}  x={r['x']} y={r['y']} w={r['width']} h={r['height']}", fill=color, font=label_font)

    card = regions["content_card"]
    pad = card["padding"]
    inner = [card["x"] + pad["left"], card["y"] + pad["top"], card["x"] + card["width"] - pad["right"], card["y"] + card["height"] - pad["bottom"]]
    draw.rectangle(inner, outline=(210, 160, 60), width=2)
    draw.text((inner[0] + 4, inner[1] + 4), f"card padding: top={pad['top']} right={pad['right']} bottom={pad['bottom']} left={pad['left']}", fill=(150, 110, 30), font=label_font)

    return image


# --- 比較確認HTML ---------------------------------------------------------------------------


def render_comparison_html(
    document: LessonDocument, master_layout: dict[str, Any], page_specs: dict[int, dict[str, Any]],
    page_results: list[dict[str, Any]], output_dir: Path,
) -> str:
    """外部CDN・外部CSS・外部JSに依存しない自己完結型のcomparison.htmlを生成する。"""
    results_by_no = {r["page_no"]: r for r in page_results}
    card = master_layout["regions"]["content_card"]

    def esc(s: str) -> str:
        return html.escape(s or "")

    succeeded = sum(1 for r in page_results if r["succeeded"])

    sections = []
    for page in document.pages:
        spec = page_specs.get(page.page_no, {})
        result = results_by_no.get(page.page_no, {})
        content_layout = spec.get("content_layout", {})
        emphasis = spec.get("emphasis", [])
        emphasis_html = "".join(f"<li>{esc(rule.get('style',''))}: {esc(rule.get('match',''))}</li>" for rule in emphasis)
        warnings_html = "".join(f"<li>{esc(w)}</li>" for w in result.get("warnings", []))
        status = "成功" if result.get("succeeded") else "失敗"
        preview_rel = f"../preview/page_{page.page_no:03d}.png" if result.get("succeeded") else ""
        sections.append(f"""
<section class="page-compare">
  <h2>Page {page.page_no}</h2>
  <div class="images">
    <figure><img src="../../{esc(page.source_image)}" alt="元画像 page {page.page_no}"><figcaption>元画像</figcaption></figure>
    <figure>{f'<img src="{esc(preview_rel)}" alt="固定マスター プレビュー page {page.page_no}">' if preview_rel else '<div class="missing">生成なし（' + esc(status) + '）</div>'}<figcaption>固定マスター プレビュー（{esc(status)}・完成画像ではありません）</figcaption></figure>
  </div>
  <dl>
    <dt>内部レイアウト種別</dt><dd>{esc(content_layout.get('type',''))}</dd>
    <dt>縦方向配置</dt><dd>{esc(content_layout.get('vertical_alignment',''))}</dd>
    <dt>本文カード（全ページ共通）</dt><dd>x={card['x']}, y={card['y']}, width={card['width']}, height={card['height']}</dd>
    <dt>強調ルール</dt><dd>{f'<ul>{emphasis_html}</ul>' if emphasis_html else 'なし'}</dd>
  </dl>
  {f'<ul class="warnings">{warnings_html}</ul>' if warnings_html else ''}
</section>
""")

    body = "\n".join(sections)
    return f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<title>最終画像生成パッケージ 比較確認</title>
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
<h1>最終画像生成パッケージ 比較確認</h1>
<div class="summary">
  <p>成功: {succeeded} / {len(page_results)}</p>
  <p>全ページで本文カードのx/y/width/heightが完全に同一であることを、この一覧の「本文カード」欄で確認できます。</p>
  <p><strong>この画面のプレビューは完成画像ではありません。</strong> Phase 10.15でCodexが背景を生成し、
  確定済み本文を合成した後の`rendered_final/`が完成画像です。</p>
</div>
{body}
</body></html>
"""


# --- 一括実行（`prepare-final-image-package`本体） -----------------------------------------------


@dataclass
class FinalImagePackageRun:
    total_pages: int
    succeeded_pages: list[int]
    failed_pages: list[int]
    warnings: dict[int, list[str]]
    master_layout: dict[str, Any]
    handoff_sentence: str


def write_final_image_package(
    output_dir: str | Path, document: LessonDocument, font_path: str | None = None,
) -> FinalImagePackageRun:
    """`prepare-final-image-package`の本体。

    前提として、Phase 10.12/10.13の画像デザイン（`brushup_design/`）が現在の`lesson_pages.json`を
    前提に完成していることを、既存のローダー（`brushup_renderer.load_design_pages`）を再利用して
    確認する（デザインが古い・欠落している場合はここで拒否する）。実際のカード内部レイアウトは
    このモジュール自身のロジックで組み立てるが、「本文ブラッシュアップ後のデザインが揃っているか」
    の検証は既存資産をそのまま再利用する。
    """
    output_dir = Path(output_dir)
    paths = final_image_package.resolve_paths(output_dir)
    lesson_pages_path = paths.lesson_pages_path
    if not lesson_pages_path.exists():
        raise ValueError(f"lesson_pages.jsonが見つかりません: {lesson_pages_path}")

    design_paths = image_brushup_design.resolve_paths(output_dir)
    _designs, design_errors = brushup_renderer.load_design_pages(design_paths, document)
    if design_errors:
        raise ValueError(
            "brushup_design（Phase 10.12の画像デザイン）が現在のlesson_pages.jsonと整合していません: "
            + "; ".join(design_errors)
            + " prepare-image-brushup / render-brushupを先に実行してください"
        )

    resolved_font_path = resolve_font_path(font_path)
    if resolved_font_path is None:
        warn_missing_japanese_font()

    for d in (paths.package_dir, paths.pages_dir, paths.text_dir, paths.prompts_dir, paths.preview_dir, paths.rendered_brushup_preview_dir):
        d.mkdir(parents=True, exist_ok=True)

    lesson_pages_sha = final_image_package.lesson_pages_sha256(lesson_pages_path)
    master_layout = final_image_package.build_master_layout(document, output_dir, lesson_pages_path)
    paths.master_layout_path.write_text(json.dumps(master_layout, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    asset_manifest = final_image_package.build_asset_manifest(document, output_dir)
    paths.asset_manifest_path.write_text(json.dumps(asset_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    paths.instructions_path.write_text(
        final_image_package.render_codex_final_image_generation_instructions(document, output_dir, master_layout),
        encoding="utf-8",
    )
    paths.readme_path.write_text(final_image_package.render_package_readme(), encoding="utf-8")
    paths.master_background_prompt_path.write_text(
        final_image_package.render_master_background_prompt(document, master_layout), encoding="utf-8"
    )

    page_specs: dict[int, dict[str, Any]] = {}
    page_manifest_entries: list[dict[str, Any]] = []
    render_results: list[dict[str, Any]] = []
    warnings_by_page: dict[int, list[str]] = {}
    succeeded_pages: list[int] = []
    failed_pages: list[int] = []

    for page in document.pages:
        spec = final_image_package.build_page_spec(page, lesson_pages_sha, resolved_font_path)
        spec_errors = final_image_package.validate_page_spec(
            spec, expected_page_no=page.page_no, expected_source_image=page.source_image,
            master_layout=master_layout, lesson_page=page,
        )
        if spec_errors:
            raise ValueError(f"page_no={page.page_no}の生成仕様の検証に失敗しました: {'; '.join(spec_errors)}")
        page_specs[page.page_no] = spec
        (paths.pages_dir / f"page_{page.page_no:03d}.json").write_text(
            json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        text_snapshot = final_image_package.build_text_snapshot(page, lesson_pages_sha)
        (paths.text_dir / f"page_{page.page_no:03d}.json").write_text(
            json.dumps(text_snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        (paths.prompts_dir / f"page_{page.page_no:03d}.md").write_text(
            final_image_package.render_page_background_prompt(page, master_layout), encoding="utf-8"
        )

        image, warnings, overflow = render_page_preview(page, spec, master_layout, resolved_font_path)
        succeeded = image is not None
        preview_rel = None
        if succeeded:
            preview_path = paths.preview_dir / f"page_{page.page_no:03d}.png"
            image.save(preview_path)
            image.save(paths.rendered_brushup_preview_dir / f"page_{page.page_no:03d}.png")
            preview_rel = f"preview/page_{page.page_no:03d}.png"
            succeeded_pages.append(page.page_no)
        else:
            failed_pages.append(page.page_no)
        if warnings:
            warnings_by_page[page.page_no] = warnings

        render_results.append({"page_no": page.page_no, "succeeded": succeeded, "overflow": overflow, "warnings": warnings})
        page_manifest_entries.append({
            "page_no": page.page_no, "page_spec": f"pages/page_{page.page_no:03d}.json",
            "text": f"text/page_{page.page_no:03d}.json", "prompt": f"prompts/page_{page.page_no:03d}.md",
            "preview": preview_rel,
        })

    package_manifest = final_image_package.build_package_manifest(document, master_layout, page_manifest_entries)
    paths.package_manifest_path.write_text(json.dumps(package_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    master_guides_image = render_master_guides(master_layout, resolved_font_path)
    master_guides_image.save(paths.master_guides_path)

    comparison_html = render_comparison_html(document, master_layout, page_specs, render_results, output_dir)
    paths.comparison_html_path.write_text(comparison_html, encoding="utf-8")

    rel_dir = final_image_package._relative_output_dir(output_dir)
    instructions_rel = f"{rel_dir}/{final_image_package.PACKAGE_DIR_NAME}/{final_image_package.INSTRUCTIONS_FILENAME}"

    return FinalImagePackageRun(
        total_pages=len(document.pages), succeeded_pages=succeeded_pages, failed_pages=failed_pages,
        warnings=warnings_by_page, master_layout=master_layout,
        handoff_sentence=final_image_package.build_handoff_sentence(instructions_rel),
    )
