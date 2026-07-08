from __future__ import annotations

from .lesson_pages import LessonDocument, LessonPage

# LLM（ChatGPT/Claude等、当面の手作業検証用の製品）の回答をそのまま
# editable/lesson_pages.jsonへ反映するのではなく、いったん「採用判断シート」に
# 整理してから人間が手編集する運用を支援するモジュール。LLM出力の自動取り込みは行わない。
# 詳細はdocs/12_llm_review_apply_workflow.md、プロジェクト方針はREADME.md
# 「プロジェクト方針：外部API非依存・ローカルLLM移行前提」参照。
#
# llm_handoff.pyと同様、特定の教材・特定の年代/属性・特定ジャンルに依存しない汎用設計とする。

_EDITABLE_FIELDS = ("title", "summary", "body", "layout_instruction", "notes")


def _format_purpose_section() -> str:
    return (
        "## 1. 目的\n\n"
        "このファイルは、ChatGPT/Claude等から返ってきた改善案を、そのまま"
        "`editable/lesson_pages.json`へ反映するのではなく、いったん**採用判断を整理するため**の"
        "テンプレートです。LLMの回答を読みながら、ページごとに「採用する／採用しない／一部採用」を"
        "記入し、採用する内容を明確にしてから`editable/lesson_pages.json`を編集してください。"
    )


def _format_usage_section() -> str:
    return (
        "## 2. 使い方\n\n"
        "1. `llm-handoff`で生成したMarkdownをChatGPT/Claude等へ貼り付け、改善案を受け取る。\n"
        "2. 改善案を読みながら、このファイルのページ別「採用判断」欄にチェックを入れ、"
        "「採用する改善内容」欄に採用する文面を書き写す。\n"
        "3. このファイルを見ながら、`output/editable/lesson_pages.json`の該当ページを人間が手編集する。\n"
        "4. `regenerate`で完成outputを作り直す。\n"
        "5. 末尾の「出力確認チェックリスト」で結果を確認する。"
    )


def _mode_policy_text(mode: str) -> str:
    if mode == "proofread":
        return (
            "- 誤字脱字・分かりにくさ・説明不足の改善が中心です。\n"
            "- ページの追加・削除・順序変更は原則行いません。\n"
            "- `title`/`summary`/`body`の軽微な改善を中心に採用を検討してください。"
        )
    if mode == "restructure":
        return (
            "- ページの統合・分割・順序整理の提案があれば、採用を検討してよいです。\n"
            "- ただし、元資料の意図・雰囲気を大きく変える提案は採用しないでください。\n"
            "- `source_page_no`/`source_image`との対応が壊れないよう注意してください。"
        )
    if mode == "generate":
        return (
            "- 新規生成寄りのモードのため、必要な説明補足やページ構成案の追加は採用を検討してよいです。\n"
            "- ただし、元情報にない断定や根拠のない内容の追加は採用しないでください。\n"
            "- 目的・対象読者・トーンから外れる提案は採用しないでください。"
        )
    return (
        "- modeが不明なため、汎用的な判断基準として扱ってください。\n"
        "- 元資料の意図を尊重し、過度な作り替えとなる提案は採用しないでください。"
    )


def _mode_page_note(mode: str) -> str:
    if mode == "proofread":
        return "proofreadでは大きな構成変更を避ける"
    if mode == "restructure":
        return "restructureでは構成整理は許容するが、元資料から大きく逸脱しない"
    if mode == "generate":
        return "generateでは目的・対象読者・トーン・元情報を守る"
    return "元資料の意図を尊重し、過度な作り替えは避ける"


def _format_adoption_rules_section(mode: str) -> str:
    return (
        "## 3. 採用判断ルール\n\n"
        f"このデータのmodeは`{mode}`です。以下の方針を目安に採用・不採用を判断してください。\n\n"
        f"{_mode_policy_text(mode)}\n\n"
        "共通の判断基準:\n\n"
        "- 元資料にない断定・誇張表現を含む提案は採用しない。\n"
        "- 提案の意図が分からない場合は、いったん保留にして元資料を確認する。\n"
        "- 迷った場合は、採用しない方を選ぶ（改善は次の反復でも行える）。"
    )


def _format_editable_fields_section() -> str:
    editable_list = "\n".join(f"- `{field}`" for field in _EDITABLE_FIELDS)
    return (
        "## 4. 編集してよい項目\n\n"
        f"{editable_list}\n\n"
        "これらは`editable/lesson_pages.json`の各ページで、採用した改善案を反映してよい項目です。"
    )


def _format_non_editable_fields_section(mode: str) -> str:
    non_editable_list = "\n".join(
        f"- `{field}`"
        for field in ("page_no", "role", "source_page_no", "source_image", "assets", "generated_at", "metadata", "project設定")
    )
    text = (
        "## 5. 通常編集しない項目\n\n"
        f"{non_editable_list}\n\n"
        "これらは元資料との対応関係や内部管理に使う情報です。書き換えると元資料とのつながりが"
        "分からなくなったり、再生成時に不整合が起きたりするため、通常は編集しないでください。"
    )
    if mode == "restructure":
        text += (
            "\n\n**restructureの場合の注意**: 構成整理のために`role`やページ順の見直しが必要になる"
            "場合があります。その場合も、直接編集する前に人間が慎重に判断し、"
            "`source_page_no`との対応が壊れていないか確認してください。"
        )
    return text


def _format_regenerate_flow_section() -> str:
    return (
        "## 6. regenerateまでの流れ\n\n"
        "```text\n"
        "edit_plan_template.md の採用判断を見ながら\n"
        "↓\n"
        "output/editable/lesson_pages.json を人間が手編集する\n"
        "↓\n"
        "python3 -m src.cli regenerate --input output/editable/lesson_pages.json --output-format all\n"
        "↓\n"
        "出力確認チェックリストで確認する\n"
        "```"
    )


def _format_page_section(page: LessonPage, mode: str) -> str:
    lines = [f"### Page {page.page_no}", "", "現在の情報："]
    lines.append(f"- page_no: {page.page_no}")
    if page.role:
        lines.append(f"- role: {page.role}")
    if page.source_page_no:
        lines.append(f"- source_page_no: {', '.join(str(v) for v in page.source_page_no)}")
    lines.append(f"- title: {page.title or '(未設定)'}")
    lines.append(f"- summary: {page.summary or '(未設定)'}")
    lines.append("")
    lines.append("採用判断：")
    for field in _EDITABLE_FIELDS:
        lines.append(f"- {field}: [ ] 採用する / [ ] 採用しない / [ ] 一部採用")
    lines.append("")
    lines.append("採用する改善内容：")
    for field in _EDITABLE_FIELDS:
        lines.append(f"- {field}: ")
    lines.append("")
    lines.append("判断メモ：")
    lines.append("- 採用理由：")
    lines.append("- 採用しない理由：")
    lines.append("- 元資料確認が必要な点：")
    lines.append("")
    lines.append("編集時の注意：")
    lines.append("- source_page_no / source_image / assets は通常変更しない")
    lines.append("- 元資料にない断定を追加しない")
    lines.append(f"- {_mode_page_note(mode)}")
    return "\n".join(lines)


def _format_pages_section(document: LessonDocument) -> str:
    header = "## 7. ページ別の採用判断欄"
    if not document.pages:
        return f"{header}\n\n（対象ページがありません。）"
    mode = document.metadata.mode
    body = "\n\n".join(_format_page_section(page, mode) for page in document.pages)
    return f"{header}\n\n{body}"


def _format_checklist_section() -> str:
    return (
        "## 8. 出力確認チェックリスト\n\n"
        "`regenerate`実行後、以下を確認してください。\n\n"
        "- [ ] `regenerate`がエラーなく完了した\n"
        "- [ ] PDF / DOCX / Markdown / PNG等が生成された\n"
        "- [ ] 変更したtitle / summary / bodyが出力に反映されている\n"
        "- [ ] 元資料との対応関係が壊れていない\n"
        "- [ ] source_page_no / source_imageが意図せず変わっていない\n"
        "- [ ] 誇張表現や元資料にない断定が増えていない\n"
        "- [ ] ページ数が意図せず変わっていない\n"
        "- [ ] レイアウトが大きく崩れていない\n"
        "- [ ] 人間が最終確認した"
    )


def _format_ocr_check_section() -> str:
    return (
        "## 9. OCR確認チェック\n\n"
        "文章改善とOCR崩れの修正を混同しないよう、以下も確認してください"
        "（詳細は`docs/13_ocr_quality_check_workflow.md`参照）。\n\n"
        "- [ ] `ocr-check`でOCR崩れ候補・修正候補を確認した\n"
        "- [ ] 高重要度のOCR候補を確認した\n"
        "- [ ] `ocr_correction_candidates.json`を確認した\n"
        "- [ ] 元画像確認が必要な箇所を確認した\n"
        "- [ ] OCR補正と文章改善を混同していない"
    )


def render_edit_plan_template_markdown(document: LessonDocument) -> str:
    """editable/lesson_pages.json相当の正データから、LLM改善案の採用判断シート
    （edit_plan_template.md）を生成する。

    ChatGPT/Claude等から返ってきた改善案を、そのまま`editable/lesson_pages.json`へ
    反映するのではなく、いったんこのシートで「採用する／採用しない／一部採用」を人間が
    整理してから手編集する運用を支援する（LLM出力の自動取り込み・自動マージは行わない）。

    依頼文・注意事項は`document.metadata.mode`（proofread/restructure/generate。
    それ以外は汎用レビュー扱い）に応じて切り替える（llm_handoff.pyと同じ設計方針）。
    """
    title = document.metadata.project_title or "教材ブラッシュアップ設計書"
    mode = document.metadata.mode
    sections = [
        f"# {title}：採用判断シート（edit plan）",
        _format_purpose_section(),
        _format_usage_section(),
        _format_adoption_rules_section(mode),
        _format_editable_fields_section(),
        _format_non_editable_fields_section(mode),
        _format_regenerate_flow_section(),
        _format_pages_section(document),
        _format_checklist_section(),
        _format_ocr_check_section(),
    ]
    return "\n\n".join(sections) + "\n"
