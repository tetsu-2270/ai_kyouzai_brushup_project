from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from .lesson_pages import LessonDocument, LessonPage, write_lesson_pages_json
from .parser import load_lesson_document

# ocr-checkが生成したocr_correction_candidates.jsonのうち、人間がstatus: approvedに変更した
# 候補だけをlesson_pages.jsonへ安全に反映するモジュール。OCR候補の自動承認・OCR再実行・
# 元ファイルの直接上書きは行わない（詳細はdocs/14_apply_ocr_corrections_workflow.md参照）。
#
# 反映対象fieldはtitle/summary/body/notesのみ。layout_instructionはOCR本文ではなく生成側の
# レイアウト指示・内部参照であるため、原則として自動反映の対象外とする（推奨方針。
# ocr_check.py側でもlayout_instructionはOCR崩れ検出の主対象から除外している）。

_APPLICABLE_FIELDS = ("title", "summary", "body", "notes")
_KNOWN_STATUSES = (
    "approved", "proposed", "rejected", "needs_image_check",
    "needs_source_check", "needs_human_review",
)
_IMAGE_CHECK_SUGGESTED_MARKERS = ("元画像確認",)

_SKIP_REASON_LABELS = {
    "status_not_approved": "statusがapprovedではない",
    "unknown_status": "statusが未知の値",
    "suggested_missing": "suggestedが空または未設定",
    "suggested_requires_image_check": "suggestedが元画像確認を示す値",
    "invalid_field": "fieldが反映対象外",
    "field_missing": "candidateにfieldが設定されていない",
    "page_not_found": "対象ページが見つからない",
    "original_not_found": "originalが対象field内に見つからない",
    "duplicate_or_already_applied": "同一candidate_idが重複している",
    "layout_instruction_skipped": "layout_instructionは自動反映対象外",
    "delete_action_not_supported": "action: deleteの反映は今回未対応",
}


def load_lesson_pages(path: str | Path) -> LessonDocument:
    """`lesson_pages.json`（editable配下等）を読み込む。`load_lesson_document`の薄いラッパー。"""
    return load_lesson_document(path)


def load_correction_candidates(path: str | Path) -> dict[str, Any]:
    """`ocr-check`が生成した`ocr_correction_candidates.json`を読み込む。"""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_lesson_pages(path: str | Path, document: LessonDocument) -> None:
    """補正済みの`LessonDocument`を新しいパスへ書き出す（`--input`の元ファイルは上書きしない）。"""
    write_lesson_pages_json(path, document)


def _classify_suggested(suggested: Any) -> str | None:
    """suggestedが反映に使える値かどうかを判定し、使えない場合はスキップ理由を返す。"""
    if suggested is None:
        return "suggested_missing"
    text = str(suggested).strip()
    if not text:
        return "suggested_missing"
    if text == "(元画像確認)" or any(marker in text for marker in _IMAGE_CHECK_SUGGESTED_MARKERS):
        return "suggested_requires_image_check"
    return None


def _find_page(document: LessonDocument, candidate: dict[str, Any]) -> LessonPage | None:
    page_index = candidate.get("page_index")
    page_no = candidate.get("page_no")
    if isinstance(page_index, int) and 0 <= page_index < len(document.pages):
        page = document.pages[page_index]
        if page_no is None or page.page_no == page_no:
            return page
    if page_no is not None:
        for page in document.pages:
            if page.page_no == page_no:
                return page
    return None


def should_apply_candidate(
    document: LessonDocument, candidate: dict[str, Any], applied_ids: set[str]
) -> tuple[LessonPage | None, str | None]:
    """候補を反映してよいか判定する。反映してよい場合は`(対象ページ, None)`、
    反映しない場合は`(None, スキップ理由)`を返す。

    反映条件（すべて満たす場合のみ反映）:
    status=approved / action が delete ではない（削除反映は今回未対応） / suggestedが実在し
    元画像確認系でない / fieldが反映対象（title/summary/body/notes。layout_instructionは
    対象外） / 対象ページが特定できる / original が対象field内に実在する。
    """
    candidate_id = candidate.get("candidate_id")
    if candidate_id and candidate_id in applied_ids:
        return None, "duplicate_or_already_applied"

    status = candidate.get("status")
    if status != "approved":
        if status in _KNOWN_STATUSES:
            return None, "status_not_approved"
        return None, "unknown_status"

    if candidate.get("action") == "delete":
        # 削除候補（ocr_check.pyのdetect_garbled_latin_sequences等）は、approvedであっても
        # 今回のバージョンでは自動反映しない（安全側の設計。将来的な対応候補）。
        return None, "delete_action_not_supported"

    field = candidate.get("field")
    if not field:
        return None, "field_missing"
    if field == "layout_instruction":
        return None, "layout_instruction_skipped"
    if field not in _APPLICABLE_FIELDS:
        return None, "invalid_field"

    suggested_reason = _classify_suggested(candidate.get("suggested"))
    if suggested_reason:
        return None, suggested_reason

    page = _find_page(document, candidate)
    if page is None:
        return None, "page_not_found"

    original = candidate.get("original")
    current_text = getattr(page, field, "") or ""
    if not original or original not in current_text:
        return None, "original_not_found"

    return page, None


def apply_candidate_to_page(page: LessonPage, candidate: dict[str, Any]) -> int:
    """`page`の対象fieldに含まれる`original`をすべて`suggested`へ置換し、置換回数を返す。

    同一field内に同じoriginalが複数回出現する場合も、対象field内の全一致を置換する
    （安全設計として、レポート側で置換回数を必ず記録する）。
    """
    field = candidate["field"]
    original = candidate["original"]
    suggested = str(candidate["suggested"])
    current_text = getattr(page, field, "") or ""
    replace_count = current_text.count(original)
    if replace_count:
        setattr(page, field, current_text.replace(original, suggested))
    return replace_count


def apply_ocr_corrections(document: LessonDocument, candidates_data: dict[str, Any]) -> dict[str, Any]:
    """`candidates_data`のうちapproved済みで反映条件を満たす候補だけを、`document`の複製へ反映する。

    `document`自体は変更しない（呼び出し側の`--input`ファイルを上書きしないための安全設計）。
    戻り値は補正後の`document`と、反映済み/未反映の候補一覧を含む。
    """
    result_document = copy.deepcopy(document)
    applied: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    applied_ids: set[str] = set()

    for candidate in candidates_data.get("candidates", []):
        page, reason = should_apply_candidate(result_document, candidate, applied_ids)
        if reason:
            skipped.append({**candidate, "skip_reason": reason})
            continue
        replace_count = apply_candidate_to_page(page, candidate)
        if replace_count == 0:
            skipped.append({**candidate, "skip_reason": "original_not_found"})
            continue
        if candidate.get("candidate_id"):
            applied_ids.add(candidate["candidate_id"])
        applied.append({**candidate, "replace_count": replace_count})

    return {
        "document": result_document,
        "applied": applied,
        "skipped": skipped,
    }


# --- Markdownレポート -------------------------------------------------------------------


def _format_purpose_section() -> str:
    return (
        "## 1. 目的\n\n"
        "このレポートは、`ocr-check`が生成した`ocr_correction_candidates.json`のうち、"
        "人間が`status: approved`に変更した候補だけを`lesson_pages.json`へ反映した結果を"
        "示すものです。`approved`以外の候補（`proposed`/`rejected`/`needs_image_check`/"
        "`needs_source_check`/`needs_human_review`等）は反映されません。"
    )


def _format_execution_conditions_section() -> str:
    return (
        "## 2. 実行条件\n\n"
        "以下をすべて満たす候補のみ反映しています。\n\n"
        "1. `status`が`approved`\n"
        "2. `action`が`delete`ではない（削除候補の反映は今回は未対応。安全側の設計として"
        "見送っています）\n"
        "3. `suggested`が存在し、空文字・`(元画像確認)`等の元画像確認を示す値ではない\n"
        "4. `field`が`title`/`summary`/`body`/`notes`のいずれか（`layout_instruction`は対象外）\n"
        "5. `page_index`または`page_no`から対象ページを特定できる\n"
        "6. 対象field内に`original`が実在する\n\n"
        "`layout_instruction`は生成側のレイアウト指示・内部参照でありOCR本文ではないため、"
        "今回は自動反映の対象外としています。"
    )


def _format_overall_summary_section(
    applied: list[dict[str, Any]],
    skipped: list[dict[str, Any]],
    candidates_data: dict[str, Any],
    input_path: str,
    candidates_path: str,
    output_path: str,
    report_path: str,
) -> str:
    all_candidates = candidates_data.get("candidates", [])
    approved_count = sum(1 for c in all_candidates if c.get("status") == "approved")
    skip_counts: dict[str, int] = {}
    for c in skipped:
        skip_counts[c["skip_reason"]] = skip_counts.get(c["skip_reason"], 0) + 1

    lines = [
        "## 3. 全体サマリー",
        "",
        f"- 入力lesson_pages: `{input_path}`",
        f"- 入力candidates: `{candidates_path}`",
        f"- 出力lesson_pages: `{output_path}`",
        f"- 出力report: `{report_path}`",
        f"- 候補総数: {len(all_candidates)}",
        f"- approved候補数: {approved_count}",
        f"- 反映成功件数: {len(applied)}",
        f"- 未反映件数: {len(skipped)}",
        f"- status不一致による未反映件数: {skip_counts.get('status_not_approved', 0) + skip_counts.get('unknown_status', 0)}",
        f"- suggestedなしによる未反映件数: {skip_counts.get('suggested_missing', 0) + skip_counts.get('suggested_requires_image_check', 0)}",
        f"- original未検出による未反映件数: {skip_counts.get('original_not_found', 0)}",
        f"- field不正による未反映件数: {skip_counts.get('invalid_field', 0) + skip_counts.get('field_missing', 0) + skip_counts.get('layout_instruction_skipped', 0)}",
        f"- page特定失敗による未反映件数: {skip_counts.get('page_not_found', 0)}",
        f"- action: deleteによる未反映件数: {skip_counts.get('delete_action_not_supported', 0)}",
    ]
    return "\n".join(lines)


def _format_applied_section(applied: list[dict[str, Any]]) -> str:
    lines = ["## 4. 反映された候補一覧", ""]
    if not applied:
        lines.append("反映された候補はありません。")
        return "\n".join(lines)
    lines.append("| candidate_id | Page | field | original | suggested | 置換回数 |")
    lines.append("|---|---|---|---|---|---|")
    for c in applied:
        lines.append(
            f"| {c['candidate_id']} | {c['page_no']} | {c['field']} | {c['original']} | "
            f"{c['suggested']} | {c['replace_count']} |"
        )
    return "\n".join(lines)


def _format_skipped_section(skipped: list[dict[str, Any]]) -> str:
    lines = ["## 5. 反映されなかった候補一覧", ""]
    if not skipped:
        lines.append("未反映の候補はありません。")
        return "\n".join(lines)
    lines.append("| candidate_id | Page | field | original | suggested | status | 未反映理由 |")
    lines.append("|---|---|---|---|---|---|---|")
    for c in skipped:
        candidate_id = c.get("candidate_id", "(不明)")
        page_no = c.get("page_no", "(不明)")
        field = c.get("field", "(不明)")
        original = c.get("original", "")
        suggested = c.get("suggested") or ""
        status = c.get("status", "(不明)")
        lines.append(
            f"| {candidate_id} | {page_no} | {field} | {original} | {suggested} | "
            f"{status} | {c['skip_reason']} |"
        )
    return "\n".join(lines)


def _format_skip_reason_summary_section(skipped: list[dict[str, Any]]) -> str:
    lines = ["## 6. 未反映理由別サマリー", ""]
    if not skipped:
        lines.append("未反映の候補はありません。")
        return "\n".join(lines)
    counts: dict[str, int] = {}
    for c in skipped:
        counts[c["skip_reason"]] = counts.get(c["skip_reason"], 0) + 1
    for reason, count in sorted(counts.items(), key=lambda kv: -kv[1]):
        label = _SKIP_REASON_LABELS.get(reason, reason)
        lines.append(f"- `{reason}`（{label}）: {count}件")
    return "\n".join(lines)


def _format_per_page_section(applied: list[dict[str, Any]], skipped: list[dict[str, Any]]) -> str:
    lines = ["## 7. ページ別反映結果", ""]
    page_nos = sorted({c.get("page_no") for c in applied + skipped if c.get("page_no") is not None})
    if not page_nos:
        lines.append("対象ページがありません。")
        return "\n".join(lines)
    for page_no in page_nos:
        page_applied = [c for c in applied if c.get("page_no") == page_no]
        page_skipped = [c for c in skipped if c.get("page_no") == page_no]
        changed_fields = sorted({c["field"] for c in page_applied})
        lines.append(f"### Page {page_no}")
        lines.append("")
        lines.append(f"- 反映成功: {len(page_applied)}")
        lines.append(f"- 未反映: {len(page_skipped)}")
        lines.append(f"- 変更field: {', '.join(changed_fields) if changed_fields else '(なし)'}")
        if any(c["skip_reason"] == "layout_instruction_skipped" for c in page_skipped):
            lines.append("- 注意: layout_instruction宛の候補があるため人間の確認を推奨します")
        lines.append("")
    return "\n".join(lines).rstrip()


def _format_per_field_section(applied: list[dict[str, Any]], skipped: list[dict[str, Any]]) -> str:
    lines = ["## 8. field別反映結果", ""]
    for field in ("title", "summary", "body", "notes", "layout_instruction"):
        applied_count = sum(1 for c in applied if c["field"] == field)
        skipped_count = sum(1 for c in skipped if c.get("field") == field)
        lines.append(f"- {field}: 反映{applied_count}件 / 未反映{skipped_count}件")
    return "\n".join(lines)


def _truncate_for_diff(text: str, around: str, width: int = 30) -> str:
    index = text.find(around)
    if index == -1:
        return text[:width * 2]
    start = max(0, index - width)
    end = min(len(text), index + len(around) + width)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return f"{prefix}{text[start:end]}{suffix}"


def _format_diff_notes_section(applied: list[dict[str, Any]]) -> str:
    lines = ["## 9. 差分確認用メモ", ""]
    if not applied:
        lines.append("反映された候補がないため、差分はありません。")
        return "\n".join(lines)
    for c in applied:
        before = _truncate_for_diff(c["original"], c["original"])
        after = c["suggested"]
        lines.append(f"candidate_id: {c['candidate_id']}")
        lines.append(f"Page: {c['page_no']}")
        lines.append(f"field: {c['field']}")
        lines.append(f"変更前: {before}")
        lines.append(f"変更後: {after}")
        lines.append(f"置換回数: {c['replace_count']}")
        lines.append("")
    return "\n".join(lines).rstrip()


def _format_next_commands_section(output_path: str) -> str:
    return (
        "## 10. 次に実行するコマンド例\n\n"
        "```bash\n"
        f"python3 -m src.cli llm-handoff --input {output_path} --output output/llm_handoff.md\n"
        f"python3 -m src.cli edit-plan-template --input {output_path} --output output/edit_plan_template.md\n"
        f"python3 -m src.cli regenerate --input {output_path} --output-dir output/regenerated\n"
        "```"
    )


def _format_notes_section() -> str:
    return (
        "## 11. 注意事項\n\n"
        "- このレポートは`ocr_correction_candidates.json`でstatusを`approved`にした候補のみを"
        "対象にしています。まだ判断していない候補（`proposed`）や、`rejected`/`needs_image_check`/"
        "`needs_source_check`/`needs_human_review`とした候補は反映されていません。\n"
        "- 削除候補（`action: delete`）は、`approved`にしても今回のバージョンでは反映されません"
        "（`delete_action_not_supported`）。本文から手動で削除するか、将来のバージョンでの対応を"
        "待ってください。\n"
        "- `layout_instruction`宛の候補は、statusに関わらず自動反映していません。必要であれば"
        "人間が直接確認・編集してください。\n"
        "- 元の`--input`ファイルは変更していません。補正後のファイルは別パス（`--output`）に"
        "出力されています。\n"
        "- 反映後は、このレポートの「反映された候補一覧」「差分確認用メモ」で内容を確認してから"
        "次工程（`llm-handoff`等）に進んでください。"
    )


def render_ocr_apply_report_markdown(
    result: dict[str, Any],
    candidates_data: dict[str, Any],
    *,
    input_path: str,
    candidates_path: str,
    output_path: str,
    report_path: str,
    dry_run: bool = False,
) -> str:
    """`apply_ocr_corrections()`の結果からMarkdownレポート（`ocr_apply_report.md`）を生成する。

    `dry_run=True`の場合、実際には出力lesson_pages JSONを生成していない旨をレポート冒頭に明記する。
    """
    applied = result["applied"]
    skipped = result["skipped"]
    sections = ["# OCR補正候補 反映結果レポート"]
    if dry_run:
        sections.append(
            "> **dry-run実行のため、出力lesson_pages（`" + output_path + "`）は生成していません。**"
            "反映予定の内容のみを以下に示します。"
        )
    sections += [
        _format_purpose_section(),
        _format_execution_conditions_section(),
        _format_overall_summary_section(
            applied, skipped, candidates_data, input_path, candidates_path, output_path, report_path
        ),
        _format_applied_section(applied),
        _format_skipped_section(skipped),
        _format_skip_reason_summary_section(skipped),
        _format_per_page_section(applied, skipped),
        _format_per_field_section(applied, skipped),
        _format_diff_notes_section(applied),
        _format_next_commands_section(output_path),
        _format_notes_section(),
    ]
    return "\n\n".join(sections) + "\n"
