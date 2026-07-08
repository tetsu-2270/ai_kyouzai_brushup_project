from __future__ import annotations

from .lesson_pages import LessonDocument, LessonPage

# ここでの「LLM」は、この中間ファイルを人間がChatGPT/Claude等の製品画面へ手作業で貼り付ける
# 運用を指す（当面の手作業検証用の製品名として扱う）。将来的な自動化対象としてはローカルLLMを
# 想定しており、この機能自体はAPI連携もローカルLLM本体も持たない、純粋なファイル生成にとどまる。
# 詳細は docs/11_llm_handoff_workflow.md、プロジェクト方針はREADME.md
# 「プロジェクト方針：外部API非依存・ローカルLLM移行前提」参照。
#
# このモジュールは特定の教材・特定の年代/属性・特定ジャンルに依存しない汎用設計とする。
# 「50〜60代の受講者」のような固定文言はコードに埋め込まない。対象読者はlesson_pages.jsonの
# target_audienceから可変的に扱い、未指定の場合は特定の属性を勝手に補完しない
# （詳細はdocs/11_llm_handoff_workflow.md「target_audienceの扱い」参照）。

_CONSTITUTION = "ブラッシュアップであって、作り直しではない"

# LessonMetadata/Projectの既定値（未指定時のシステム内部プレースホルダ）。この値のままの場合は
# 「実質未指定」として扱う（src/lesson_pages.py LessonMetadata.target_audience、
# src/models.py Project.target_readerの既定値と対応）。
_UNSPECIFIED_TARGET_AUDIENCE_PLACEHOLDER = "教材制作者"


def _is_target_audience_specified(target_audience: str) -> bool:
    value = (target_audience or "").strip()
    return bool(value) and value != _UNSPECIFIED_TARGET_AUDIENCE_PLACEHOLDER


def _format_target_audience_rule(target_audience: str) -> str:
    """対象読者に関する作業ルールの1行を、target_audienceの有無に応じて可変的に生成する。

    target_audienceが指定されている場合のみ、その値をそのまま使って「対象読者に合わせる」と
    伝える。未指定の場合は、特定の年代・属性を勝手に補完せず、汎用的な表現にとどめる。
    """
    if _is_target_audience_specified(target_audience):
        return f"- 対象読者「{target_audience}」に合わせて分かりやすく調整する"
    return "- 想定読者が明示されていないため、元資料の文脈から過度に決め打ちせず、一般的に分かりやすい表現に整える"


def _format_purpose_section() -> str:
    return (
        "## 1. 目的\n\n"
        "このファイルは、AI教材ブラッシュアップシステムが生成した教材データ（`editable/lesson_pages.json`）を、"
        "人間がChatGPT/Claude等のLLM製品の画面へ手作業で貼り付けて、構成チェック・文章改善案を得るための"
        "中間ファイルです。\n\n"
        "このファイル自体はLLMを呼び出しません。内容をコピーして、ChatGPT/Claude等のチャット画面に"
        "貼り付けて使ってください。"
    )


def _format_request_section(mode: str) -> str:
    if mode == "generate":
        items = [
            "教材の目的・対象読者・トーンに沿っているか確認する",
            "説明が分かりにくい箇所や、読者にとって不足している説明を指摘する",
            "内容の重複を指摘する",
            "誇張表現や根拠のない断定を指摘する",
            "ページごとに改善案・追加案を出す",
        ]
    elif mode == "restructure":
        items = [
            "元教材の構成を確認する",
            "説明が分かりにくい箇所や、読者にとって不足している説明を指摘する",
            "内容の重複を指摘する",
            "誇張表現や不自然な表現を指摘する",
            "ページ構成（統合・分割・順序）に改善の余地がないか指摘する",
            "ページごとに改善案を出す",
        ]
    else:
        # proofreadおよびmode不明の場合。proofreadに合わせた最も慎重な依頼内容にする。
        items = [
            "元教材の構成を確認する",
            "説明が分かりにくい箇所や、読者にとって不足している説明を指摘する",
            "内容の重複を指摘する",
            "誇張表現や不自然な表現を指摘する",
            "ページごとに改善案を出す",
        ]
    bullet_list = "\n".join(f"- {item}" for item in items)
    return (
        "## 2. 依頼内容\n\n"
        "以下の観点で、この教材の内容を確認し、指摘・改善案をください。\n\n"
        f"{bullet_list}\n\n"
        "最終的には、人間が`editable/lesson_pages.json`を編集しやすい形で改善案を出してください。"
    )


def _format_rules_section(mode: str, target_audience: str) -> str:
    audience_rule = _format_target_audience_rule(target_audience)

    if mode == "proofread":
        return (
            "## 3. 作業ルール（必ず守ってください）\n\n"
            f"**憲法第1条：「{_CONSTITUTION}」**\n\n"
            "- 元教材の構成・雰囲気を尊重する\n"
            "- 誤字脱字、表現の分かりにくさ、説明不足、読みにくさを中心に改善案を出す\n"
            "- 大きな構成変更（ページの追加・削除・大幅な入れ替え）は提案しない\n"
            "- 元資料にない断定を追加しない\n"
            "- 誇張表現を避ける\n"
            f"{audience_rule}\n"
            "- 最終編集は人間が行う前提で、あくまで改善案として出す（本文を勝手に確定させない）"
        )
    if mode == "restructure":
        return (
            "## 3. 作業ルール（必ず守ってください）\n\n"
            f"**憲法第1条：「{_CONSTITUTION}」（ただし、ページの統合・分割・順序整理などの構成整理は許容する）**\n\n"
            "- 元教材の意図・雰囲気を尊重する\n"
            "- ページの統合・分割・順序整理・見出し整理などの構成改善は提案してよい\n"
            "- 元資料から大きく逸脱した新規内容の追加は避ける\n"
            "- 元資料にない断定を追加しない\n"
            "- 誇張表現を避ける\n"
            f"{audience_rule}\n"
            "- 最終編集は人間が行う前提で、あくまで改善案として出す（本文を勝手に確定させない）"
        )
    if mode == "generate":
        return (
            "## 3. 作業ルール（必ず守ってください）\n\n"
            "このモードは新規教材生成寄りのため、"
            f"「{_CONSTITUTION}」を最重要ルールとしては固定しません。代わりに以下を重視してください。\n\n"
            "- 目的・対象読者・トーンを守る\n"
            "- 必要な説明補足、章立て、ページ構成案の追加は許容する\n"
            "- 元情報にない断定や根拠のない内容の追加は避ける\n"
            "- 誇張表現を避ける\n"
            f"{audience_rule}\n"
            "- 最終編集は人間が行う前提で、あくまで改善案として出す（本文を勝手に確定させない）"
        )
    # mode不明: 汎用レビューとして扱う。generateのような新規追加も、proofreadのような
    # 強い固定ルールも避け、弱めの表現にとどめる。
    return (
        "## 3. 作業ルール（必ず守ってください）\n\n"
        "modeが不明なため、汎用的なレビューとして扱ってください。\n\n"
        "- 元資料の意図・雰囲気を尊重し、過度な作り替えは避ける\n"
        "- 元資料にない断定を追加しない\n"
        "- 誇張表現を避ける\n"
        f"{audience_rule}\n"
        "- 最終編集は人間が行う前提で、あくまで改善案として出す（本文を勝手に確定させない）"
    )


def _format_response_format_section(mode: str) -> str:
    if mode == "proofread":
        preamble = "proofreadモードのため、大きな構成変更（ページの追加・削除・入れ替え）は提案せず、文章レベルの改善案を中心にしてください。\n\n"
    elif mode == "restructure":
        preamble = "restructureモードのため、文章レベルの改善に加えて、ページ構成の整理案（統合・分割・順序変更）も歓迎します。\n\n"
    elif mode == "generate":
        preamble = "generateモードのため、目的・対象読者・トーンに沿っていれば、説明の追加やページ構成案の提案も歓迎します。\n\n"
    else:
        preamble = ""

    return (
        "## 4. 出力してほしい形式\n\n"
        f"{preamble}"
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
    ]
    if _is_target_audience_specified(metadata.target_audience):
        lines.append(f"- target_audience: {metadata.target_audience}")
    else:
        lines.append("- target_audience: (未指定)")
    lines.append(f"- mode: {metadata.mode}")
    lines.append(f"- ページ数: {len(document.pages)}")
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
        "- 元資料のOCR結果に崩れが多い場合は、このファイルをLLMへ貼り付ける前に`ocr-check`で"
        "OCR崩れ候補・修正候補を確認してください（先にOCR補正を行わないと、LLMの回答が誤字修正の"
        "指摘中心になりやすいため）。\n\n"
        "  ```bash\n"
        "  python3 -m src.cli ocr-check --input output/editable/lesson_pages.json "
        "--output output/ocr_check_report.md "
        "--candidates-output output/ocr_correction_candidates.json\n"
        "  ```\n\n"
        "  詳細は`docs/13_ocr_quality_check_workflow.md`を参照してください。OCR補正候補を"
        "承認・反映した場合は、`apply-ocr-corrections`が生成した`lesson_pages.ocr_fixed.json`を"
        "このコマンドの`--input`に使ってください（詳細は`docs/14_apply_ocr_corrections_workflow.md`"
        "参照）。\n"
        "- このファイルはLLMへの出力を自動で取り込みません。LLMの回答を受け取ったら、"
        "`apply-llm-suggestions`でページ別の改善候補JSON・確認用レポートに構造化できます"
        "（`lesson_pages.json`への自動反映は行いません。詳細は"
        "`docs/15_llm_suggestion_candidates_workflow.md`参照）。もしくは`edit_plan_template.md`に"
        "採用判断を整理してください。\n\n"
        "  ```bash\n"
        "  python3 -m src.cli edit-plan-template --input output/editable/lesson_pages.json "
        "--output output/edit_plan_template.md\n"
        "  ```\n\n"
        "  その後、採用する内容だけを人間が`output/editable/lesson_pages.json`に反映し、"
        "`regenerate`で再出力してください（詳細は`docs/12_llm_review_apply_workflow.md`参照）。\n"
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

    依頼文・作業ルール・回答形式の説明は、`document.metadata.mode`（proofread/restructure/
    generate。それ以外は汎用レビュー扱い）に応じて切り替える。対象読者は
    `document.metadata.target_audience`が実質的に指定されている場合のみその値を使い、
    未指定の場合は特定の年代・属性を勝手に補完しない（詳細はモジュール冒頭のコメント参照）。

    `page_start`/`page_end`（`page_no`基準、両端含む）を指定すると、対象ページを絞り込める。
    将来的な自動分割・テンプレート分離に備え、セクションごとに関数を分けている。
    """
    title = document.metadata.project_title or "教材ブラッシュアップ設計書"
    mode = document.metadata.mode
    target_audience = document.metadata.target_audience
    sections = [
        f"# {title}：LLM手作業投入用ファイル",
        _format_purpose_section(),
        _format_request_section(mode),
        _format_rules_section(mode, target_audience),
        _format_response_format_section(mode),
        _format_overview_section(document),
        _format_pages_section(document, page_start, page_end),
        _format_notes_section(),
        _format_editing_template_section(),
    ]
    return "\n\n".join(sections) + "\n"
