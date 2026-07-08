from __future__ import annotations

from .lesson_pages import LessonDocument, LessonPage

# ここでの「LLM」は、この中間ファイルを人間がChatGPT/Claude等の製品画面へ手作業で貼り付ける
# 運用を指す（当面の手作業検証用の製品名として扱う）。将来的な自動化対象としてはローカルLLMを
# 想定しており、この機能自体はAPI連携もローカルLLM本体も持たない、純粋なファイル生成にとどまる。
# 詳細は docs/11_llm_handoff_workflow.md、プロジェクト方針はREADME.md
# 「プロジェクト方針：外部API非依存・ローカルLLM移行前提」参照。

_CONSTITUTION = "ブラッシュアップであって、作り直しではない"


def _format_purpose_section() -> str:
    return (
        "## 1. 目的\n\n"
        "このファイルは、AI教材ブラッシュアップシステムが生成した教材データ（`editable/lesson_pages.json`）を、"
        "人間がChatGPT/Claude等のLLM製品の画面へ手作業で貼り付けて、構成チェック・文章改善案を得るための"
        "中間ファイルです。\n\n"
        "このファイル自体はLLMを呼び出しません。内容をコピーして、ChatGPT/Claude等のチャット画面に"
        "貼り付けて使ってください。"
    )


def _format_request_section() -> str:
    return (
        "## 2. 依頼内容\n\n"
        "以下の観点で、この教材の内容を確認し、指摘・改善案をください。\n\n"
        "- 元教材の構成を確認する\n"
        "- 説明が分かりにくい箇所を指摘する\n"
        "- 内容の重複を指摘する\n"
        "- 初心者に不足している説明を指摘する\n"
        "- 誇張表現や不自然な表現を指摘する\n"
        "- ページごとに改善案を出す\n\n"
        "最終的には、人間が`editable/lesson_pages.json`を編集しやすい形で改善案を出してください。"
    )


def _format_rules_section() -> str:
    return (
        "## 3. 作業ルール（必ず守ってください）\n\n"
        f"**憲法第1条：「{_CONSTITUTION}」**\n\n"
        "- 元教材の構成・雰囲気を尊重する\n"
        "- 勝手に内容を増やしすぎない\n"
        "- 元資料にない断定を追加しない\n"
        "- 誇張表現を避ける\n"
        "- 初心者に分かりやすくする\n"
        "- 50〜60代の受講者にも伝わる表現を意識する\n"
        "- Canva/Gamma等に移しやすい簡潔な構成にする\n"
        "- 最終編集は人間が行う前提で、あくまで改善案として出す（本文を勝手に確定させない）"
    )


def _format_response_format_section() -> str:
    return (
        "## 4. 出力してほしい形式\n\n"
        "以下のMarkdown形式で回答してください（見出し・箇条書きの構造をそのまま使ってください）。\n\n"
        "```markdown\n"
        "# 教材全体の構成チェック\n\n"
        "## 全体評価\n\n"
        "## 大きく直す必要がある点\n\n"
        "## 直しすぎない方がよい点\n\n"
        "# ページ別改善案\n\n"
        "## Page 1: タイトル\n\n"
        "- 現状の問題点：\n"
        "- 改善方針：\n"
        "- title 改善案：\n"
        "- summary 改善案：\n"
        "- body 改善案：\n"
        "- 注意点：\n\n"
        "## Page 2: タイトル\n\n"
        "（同様の形式で全ページ分）\n\n"
        "# editable/lesson_pages.json 編集時の注意\n\n"
        "- 直接置き換えてよい箇所：\n"
        "- 人間が判断すべき箇所：\n"
        "- 元資料確認が必要な箇所：\n"
        "```"
    )


def _format_overview_section(document: LessonDocument) -> str:
    metadata = document.metadata
    lines = [
        "## 5. 全体情報",
        "",
        f"- project_title: {metadata.project_title}",
        f"- target_audience: {metadata.target_audience}",
        f"- mode: {metadata.mode}",
        f"- ページ数: {len(document.pages)}",
    ]
    if metadata.generated_at:
        lines.append(f"- generated_at: {metadata.generated_at}")
    return "\n".join(lines)


def _format_list_field(values: list[str] | list[int]) -> str:
    if not values:
        return "(なし)"
    return ", ".join(str(v) for v in values)


def _format_page_section(page: LessonPage) -> str:
    lines = [
        f"### Page {page.page_no}",
        "",
        f"- page_no: {page.page_no}",
    ]
    if page.role:
        lines.append(f"- role: {page.role}")
    if page.source_page_no:
        lines.append(f"- source_page_no: {_format_list_field(page.source_page_no)}")
    if page.source_image:
        lines.append(f"- source_image: {page.source_image}")
    if page.source_assets:
        lines.append(f"- assets: {_format_list_field(page.source_assets)}")
    lines.append(f"- title: {page.title or '(未設定)'}")
    lines.append(f"- summary: {page.summary or '(未設定)'}")
    lines.append("- body:")
    lines.append("  ```text")
    body_text = page.body or "(未設定)"
    for body_line in body_text.splitlines() or [body_text]:
        lines.append(f"  {body_line}")
    lines.append("  ```")
    if page.layout_instruction:
        lines.append(f"- layout_instruction: {page.layout_instruction}")
    if page.notes:
        lines.append(f"- notes: {page.notes}")
    return "\n".join(lines)


def _select_pages(
    document: LessonDocument, page_start: int | None, page_end: int | None
) -> list[LessonPage]:
    pages = document.pages
    if page_start is not None:
        pages = [p for p in pages if p.page_no >= page_start]
    if page_end is not None:
        pages = [p for p in pages if p.page_no <= page_end]
    return pages


def _format_pages_section(
    document: LessonDocument, page_start: int | None, page_end: int | None
) -> str:
    pages = _select_pages(document, page_start, page_end)
    header = "## 6. ページごとのデータ"
    if not pages:
        return f"{header}\n\n（対象ページがありません。`--page-start`/`--page-end`の範囲を確認してください。）"
    body = "\n\n".join(_format_page_section(page) for page in pages)
    return f"{header}\n\n{body}"


def _format_notes_section() -> str:
    return (
        "## 7. 注意事項\n\n"
        "- このファイルはLLMへの出力を自動で取り込みません。LLMの回答を見ながら、"
        "人間が`output/editable/lesson_pages.json`を直接編集してください。\n"
        "- 編集後は`regenerate`コマンドで完成outputを作り直してください。\n"
        "- `source_page_no`/`source_image`/`assets`は元資料との対応関係を示す内部情報です。"
        "書き換えると元資料とのつながりが分からなくなるため、通常は編集しないでください。\n"
        "- 本文が長いページも省略せずに出力しています。分量が多い場合は、"
        "`--page-start`/`--page-end`でページ範囲を絞って複数回に分けて貼り付けることを検討してください。"
    )


def _format_editing_template_section() -> str:
    return (
        "## 8. 改善提案欄（人間が編集用にコピーして使えるメモ欄）\n\n"
        "LLMの回答を貼り付けたら、ページごとに以下のメモを埋めながら`editable/lesson_pages.json`を"
        "編集すると進めやすくなります。\n\n"
        "```text\n"
        "Page番号:\n"
        "採用する改善案: [ ] title  [ ] summary  [ ] body\n"
        "編集メモ:\n"
        "```"
    )


def render_llm_handoff_markdown(
    document: LessonDocument, page_start: int | None = None, page_end: int | None = None
) -> str:
    """editable/lesson_pages.json相当の正データから、LLM手作業投入用Markdownを生成する。

    人間がこの内容をコピーしてChatGPT/Claude等のチャット画面へ貼り付け、構成チェック・
    文章改善案を得るための中間ファイル。ここでの「LLM」は、まずChatGPT/Claude等の製品を
    手作業で使う運用を指す（外部API呼び出し・ローカルLLM本体はいずれも持たない）。

    `page_start`/`page_end`（`page_no`基準、両端含む）を指定すると、対象ページを絞り込める。
    将来的な自動分割・テンプレート分離に備え、セクションごとに関数を分けている。
    """
    title = document.metadata.project_title or "教材ブラッシュアップ設計書"
    sections = [
        f"# {title}：LLM手作業投入用ファイル",
        _format_purpose_section(),
        _format_request_section(),
        _format_rules_section(),
        _format_response_format_section(),
        _format_overview_section(document),
        _format_pages_section(document, page_start, page_end),
        _format_notes_section(),
        _format_editing_template_section(),
    ]
    return "\n\n".join(sections) + "\n"
