import re

from .lesson_pages import LessonDocument

_HEADING_OR_BULLET_PATTERN = re.compile(r"^(?:#{1,6}|[-*])(?=\s|$)\s*")


def _clean_canva_free_text(text: str) -> str:
    """canva_design.md表示時のみ、行頭のMarkdown見出し記法(#/##/###等)・箇条書き記法(-/*)を取り除く。

    lesson_pages.json側のsummary/image_text/layout_instruction自体は変更しない（呼び出し元で
    この関数の戻り値を表示にのみ使う）。ハッシュタグ(#の直後に空白が無い)や文中の#/-はそのまま保持する。
    """
    return "\n".join(_HEADING_OR_BULLET_PATTERN.sub("", line) for line in text.splitlines())


def render_canva_design(document: LessonDocument) -> str:
    lines: list[str] = []
    lines.append("# Canva向け画像・レイアウト設計書")
    lines.append("")
    lines.append(f"元プロジェクト: {document.project_title}")
    lines.append("")
    lines.append("## 全体デザインルール")
    lines.append("- スマホ閲覧を前提に縦長レイアウトにする。")
    lines.append("- 1ページ1メッセージを原則にする。")
    lines.append("- 文字は大きめ、余白は広めに取る。")
    lines.append("- 吹き出し・人物・強調語の位置をページごとに固定しすぎず、内容に合わせて調整する。")
    lines.append("")

    for page in document.pages:
        lines.append(f"## Page {page.page_no}: {page.title}")
        lines.append("")
        if page.source_image:
            lines.append(f"元画像: {page.source_image}")
        if page.source_assets:
            lines.append(f"参考画像: {', '.join(page.source_assets)}")
        if page.source_image or page.source_assets:
            lines.append("")
        lines.append("### 概要")
        lines.append(_clean_canva_free_text(page.summary) or "未設定")
        lines.append("")
        lines.append("### 画像内テキスト")
        lines.append(_clean_canva_free_text(page.image_text) or "未設定")
        lines.append("")
        lines.append("### レイアウト指示")
        lines.append(_clean_canva_free_text(page.layout_instruction) or "未設定")
        lines.append("")
        lines.append("### Canva AI投入用プロンプト")
        for prompt_line in page.canva_prompt.splitlines():
            lines.append(f"> {prompt_line}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
