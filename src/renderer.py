import re

from .lesson_pages import LessonDocument, parse_body_lines

_HEADING_OR_BULLET_PATTERN = re.compile(r"^(?:#{1,6}|[-*])(?=\s|$)\s*")


def _clean_summary_for_display(text: str) -> str:
    """brushup.md表示時のみ、行頭のMarkdown見出し記法(#/##/###等)・箇条書き記法(-/*)を取り除く。

    lesson_pages.json側のsummary自体は変更しない（呼び出し元でこの関数の戻り値を表示にのみ使う）。
    ハッシュタグ(#の直後に空白が無い)や文中の#/-はそのまま保持する。bodyはこの対象外
    （見出し記法を含む本文構造をそのまま維持する）。
    """
    return "\n".join(_HEADING_OR_BULLET_PATTERN.sub("", line) for line in text.splitlines())


def render_brushup(document: LessonDocument) -> str:
    lines: list[str] = []
    lines.append(f"# {document.project_title}")
    lines.append("")
    lines.append(f"対象読者: {document.target_reader}")
    lines.append("")
    lines.append("## 全体方針")
    lines.append("- ページ単位で情報を整理する。")
    lines.append("- 話者ごとに台詞を分ける。")
    lines.append("- 教材として理解しやすい順序・表現に整える。")
    lines.append("")

    for page in document.pages:
        lines.append(f"## Page {page.page_no}: {page.title}")
        lines.append("")
        lines.append("### 概要")
        lines.append(_clean_summary_for_display(page.summary) or "未設定")
        lines.append("")
        lines.append("### 本文")
        parsed = parse_body_lines(page.body)
        if parsed:
            for speaker, text in parsed:
                lines.append(f"- **{speaker}**: {text}" if speaker else f"- {text}")
        else:
            lines.append("未設定")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
