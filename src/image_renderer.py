from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .lesson_pages import LessonDocument, LessonPage, clean_dialogue_lines

_CANVAS_SIZE = (900, 1200)
_MARGIN = 60
_TITLE_FONT_SIZE = 40
_BODY_FONT_SIZE = 26
_LINE_SPACING = 10

# 日本語グリフを持つフォントを優先的に探す。見つからない環境ではPillow既定フォントにフォールバックする
# （既定フォントは日本語グリフを持たないため文字化けし得るが、画像自体の生成・保存は継続する）。
_JAPANESE_FONT_CANDIDATES = (
    "/System/Library/Fonts/ヒラギノ角ゴシック W4.ttc",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/AquaKana.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
)


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in _JAPANESE_FONT_CANDIDATES:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    lines: list[str] = []
    for raw_line in text.splitlines() or [""]:
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


def _synthesize_page_image(page: LessonPage) -> Image.Image:
    """source_imageが無いページ（generateモード等）向けに、title/summary/本文を描画した簡易画像を合成する。"""
    image = Image.new("RGB", _CANVAS_SIZE, color=(250, 250, 247))
    draw = ImageDraw.Draw(image)
    title_font = _load_font(_TITLE_FONT_SIZE)
    body_font = _load_font(_BODY_FONT_SIZE)
    max_width = _CANVAS_SIZE[0] - _MARGIN * 2

    y = _MARGIN
    for line in _wrap_text(draw, page.title or "(タイトル未設定)", title_font, max_width):
        draw.text((_MARGIN, y), line, fill=(20, 24, 20), font=title_font)
        y += _TITLE_FONT_SIZE + _LINE_SPACING

    y += _LINE_SPACING * 2
    if page.summary:
        for line in _wrap_text(draw, page.summary, body_font, max_width):
            draw.text((_MARGIN, y), line, fill=(70, 78, 70), font=body_font)
            y += _BODY_FONT_SIZE + _LINE_SPACING

    y += _LINE_SPACING * 2
    dialogue_lines = clean_dialogue_lines(page.body)
    for speaker, text in dialogue_lines:
        rendered = f"{speaker}: {text}" if speaker else text
        for line in _wrap_text(draw, rendered, body_font, max_width):
            if y > _CANVAS_SIZE[1] - _MARGIN:
                break
            draw.text((_MARGIN, y), line, fill=(30, 34, 30), font=body_font)
            y += _BODY_FONT_SIZE + _LINE_SPACING

    return image


def render_page_image(page: LessonPage, output_dir: str | Path, dest_path: str | Path) -> None:
    """1ページ分の完成画像を生成する。

    source_imageが存在する場合は、解析元のビジュアルを尊重してその画像をそのまま採用する
    （教材だけでなくチラシ・SNS投稿画像等、元の見た目をそのまま活かしたい用途を想定）。
    source_imageが無い場合（generateモード等）は、title/summary/本文を描画した簡易画像を合成する。
    """
    output_dir = Path(output_dir)
    dest_path = Path(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    if page.source_image:
        source_path = output_dir / page.source_image
        if source_path.exists():
            shutil.copyfile(source_path, dest_path)
            return

    image = _synthesize_page_image(page)
    image.save(dest_path)


def render_document_images(document: LessonDocument, output_dir: str | Path, rendered_dir: str | Path) -> list[Path]:
    """正データ全ページ分の完成画像を生成し、生成したファイルパスの一覧を返す。"""
    rendered_dir = Path(rendered_dir)
    dest_paths: list[Path] = []
    for page in document.pages:
        dest_path = rendered_dir / f"page_{page.page_no:03d}.png"
        render_page_image(page, output_dir, dest_path)
        dest_paths.append(dest_path)
    return dest_paths
