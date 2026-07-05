from __future__ import annotations

import shutil
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .lesson_pages import LessonDocument, LessonPage, clean_dialogue_lines

_CANVAS_SIZE = (900, 1200)
_MARGIN = 60
_HEADER_FONT_SIZE = 20
_TITLE_FONT_SIZE = 40
_SUMMARY_FONT_SIZE = 26
_BODY_FONT_SIZE = 26
_FOOTER_FONT_SIZE = 18
_LINE_SPACING = 10
_SECTION_GAP = 24

_BG_COLOR = (250, 250, 247)
_HEADER_COLOR = (140, 146, 138)
_TITLE_COLOR = (20, 24, 20)
_DIVIDER_COLOR = (210, 212, 206)
_SUMMARY_COLOR = (70, 78, 70)
_BODY_COLOR = (30, 34, 30)
_FOOTER_COLOR = (150, 156, 148)
_TRUNCATION_COLOR = (150, 100, 40)

# 日本語グリフを持つフォントの探索候補。macOS/Linux/Windowsそれぞれで一般的なパスを列挙し、
# 実際に存在確認・読み込み確認ができたものだけを採用する。
_JAPANESE_FONT_CANDIDATES = (
    # macOS
    "/System/Library/Fonts/ヒラギノ角ゴシック W4.ttc",
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
    "/System/Library/Fonts/ヒラギノ明朝 ProN.ttc",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/AquaKana.ttc",
    # Linux
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansJP-Regular.otf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-JP-Regular.otf",
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
    "/usr/share/fonts/truetype/takao-gothic/TakaoGothic.ttf",
    # Windows
    r"C:\Windows\Fonts\YuGothM.ttc",
    r"C:\Windows\Fonts\YuGothR.ttc",
    r"C:\Windows\Fonts\meiryo.ttc",
    r"C:\Windows\Fonts\msgothic.ttc",
)

_MISSING_FONT_WARNING = (
    "WARNING: Japanese font was not found. Rendered images may contain garbled Japanese text. "
    "Use --font-path to specify a Japanese font.\n"
    "警告: 日本語フォントが見つかりませんでした。生成される画像内の日本語が文字化けする可能性があります。"
    "--font-path で日本語フォントのパスを指定してください。"
)


def _font_is_loadable(path: str) -> bool:
    try:
        ImageFont.truetype(path, 10)
        return True
    except OSError:
        return False


def resolve_font_path(explicit_path: str | Path | None = None) -> str | None:
    """画像output合成に使う日本語対応フォントのパスを解決する。

    explicit_pathが指定された場合はそれを検証して使う（存在しない/読み込めない場合はValueError）。
    未指定の場合はmacOS/Linux/Windowsの一般的な日本語フォント候補を順に探索し、
    実際に存在し読み込めた最初のパスを返す。見つからない場合はNoneを返す
    （呼び出し側でPillow既定フォントへのフォールバックと警告要否の判断に使う）。
    """
    if explicit_path:
        path_str = str(explicit_path)
        if not Path(path_str).exists():
            raise ValueError(f"指定されたフォントが見つかりません: {path_str}")
        if not _font_is_loadable(path_str):
            raise ValueError(f"指定されたフォントを読み込めません: {path_str}")
        return path_str

    for candidate in _JAPANESE_FONT_CANDIDATES:
        if Path(candidate).exists() and _font_is_loadable(candidate):
            return candidate
    return None


def warn_missing_japanese_font() -> None:
    """日本語フォントが見つからない旨の警告を標準エラー出力に一度だけ表示する。

    黙ってPillow既定フォント（日本語グリフを持たない）にフォールバックして文字化けを
    見過ごすことを避けるため、画像合成が実際に発生する場合に呼び出す。
    """
    print(_MISSING_FONT_WARNING, file=sys.stderr)


def _load_font(font_path: str | None, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if font_path:
        return ImageFont.truetype(font_path, size)
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


def _draw_wrapped(
    draw: ImageDraw.ImageDraw,
    text: str,
    font,
    max_width: int,
    x: int,
    y: int,
    line_height: int,
    color: tuple[int, int, int],
    max_y: int,
) -> tuple[int, bool]:
    """折り返しテキストを描画し、次のy座標と「途中で打ち切ったか」を返す。"""
    truncated = False
    for line in _wrap_text(draw, text, font, max_width):
        if y + line_height > max_y:
            truncated = True
            break
        draw.text((x, y), line, fill=color, font=font)
        y += line_height
    return y, truncated


def _synthesize_page_image(page: LessonPage, font_path: str | None) -> Image.Image:
    """source_imageが無いページ（generateモード等）向けに、title/summary/本文を描画した簡易画像を合成する。

    配布前確認・簡易output用途として、読みやすさ（余白・折り返し・コントラスト・ページ番号の明示）を
    最低限確保する。装飾は最小限にとどめ、全ページで同じレイアウトテンプレートを使うことで
    一貫した見た目にする。
    """
    image = Image.new("RGB", _CANVAS_SIZE, color=_BG_COLOR)
    draw = ImageDraw.Draw(image)

    header_font = _load_font(font_path, _HEADER_FONT_SIZE)
    title_font = _load_font(font_path, _TITLE_FONT_SIZE)
    summary_font = _load_font(font_path, _SUMMARY_FONT_SIZE)
    body_font = _load_font(font_path, _BODY_FONT_SIZE)
    footer_font = _load_font(font_path, _FOOTER_FONT_SIZE)

    max_width = _CANVAS_SIZE[0] - _MARGIN * 2
    footer_zone_top = _CANVAS_SIZE[1] - _MARGIN - _FOOTER_FONT_SIZE - _LINE_SPACING
    content_bottom = footer_zone_top - _LINE_SPACING

    # ヘッダー: ページ番号（複数ページでも一貫して見出しの位置が分かるようにする）。
    y = _MARGIN
    draw.text((_MARGIN, y), f"Page {page.page_no}", fill=_HEADER_COLOR, font=header_font)
    y += _HEADER_FONT_SIZE + _LINE_SPACING

    # タイトル。
    y, _ = _draw_wrapped(
        draw, page.title or "(タイトル未設定)", title_font, max_width,
        _MARGIN, y, _TITLE_FONT_SIZE + _LINE_SPACING, _TITLE_COLOR, content_bottom,
    )

    # タイトル直下に区切り線を入れ、構造を分かりやすくする。
    y += _LINE_SPACING
    draw.line([(_MARGIN, y), (_CANVAS_SIZE[0] - _MARGIN, y)], fill=_DIVIDER_COLOR, width=2)
    y += _SECTION_GAP

    truncated = False
    if page.summary:
        y, section_truncated = _draw_wrapped(
            draw, page.summary, summary_font, max_width,
            _MARGIN, y, _SUMMARY_FONT_SIZE + _LINE_SPACING, _SUMMARY_COLOR, content_bottom,
        )
        truncated = truncated or section_truncated
        y += _SECTION_GAP

    dialogue_lines = clean_dialogue_lines(page.body)
    for speaker, text in dialogue_lines:
        rendered = f"{speaker}: {text}" if speaker else text
        y, section_truncated = _draw_wrapped(
            draw, rendered, body_font, max_width,
            _MARGIN, y, _BODY_FONT_SIZE + _LINE_SPACING, _BODY_COLOR, content_bottom,
        )
        truncated = truncated or section_truncated
        if truncated:
            break

    if truncated:
        draw.text(
            (_MARGIN, content_bottom - _FOOTER_FONT_SIZE),
            "…（続きはeditable/lesson_pages.jsonまたはexports/を参照）",
            fill=_TRUNCATION_COLOR, font=footer_font,
        )

    # フッター: 一貫した位置にページ番号を再掲し、複数ページを並べたときの一体感を出す。
    footer_text = f"- {page.page_no} -"
    footer_width = draw.textlength(footer_text, font=footer_font)
    draw.text(
        ((_CANVAS_SIZE[0] - footer_width) / 2, footer_zone_top),
        footer_text, fill=_FOOTER_COLOR, font=footer_font,
    )

    return image


def render_page_image(
    page: LessonPage,
    output_dir: str | Path,
    dest_path: str | Path,
    font_path: str | None = None,
) -> None:
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

    image = _synthesize_page_image(page, font_path)
    image.save(dest_path)


def render_document_images(
    document: LessonDocument,
    output_dir: str | Path,
    rendered_dir: str | Path,
    font_path: str | None = None,
) -> list[Path]:
    """正データ全ページ分の完成画像を生成し、生成したファイルパスの一覧を返す。

    font_pathを指定しない場合は環境ごとの日本語フォント候補を自動探索する
    （resolve_font_path参照）。テキスト合成が必要なページ（source_imageが無いページ）が
    存在するにもかかわらず日本語フォントが見つからない場合は、黙って文字化けリスクを
    抱えたまま処理を続けず、警告を1回だけ表示する。
    """
    resolved_font_path = resolve_font_path(font_path)

    needs_synthesis = any(not page.source_image for page in document.pages)
    if needs_synthesis and resolved_font_path is None:
        warn_missing_japanese_font()

    rendered_dir = Path(rendered_dir)
    dest_paths: list[Path] = []
    for page in document.pages:
        dest_path = rendered_dir / f"page_{page.page_no:03d}.png"
        render_page_image(page, output_dir, dest_path, font_path=resolved_font_path)
        dest_paths.append(dest_path)
    return dest_paths
