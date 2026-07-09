from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from .ocr_apply import load_correction_candidates
from .ocr_check import write_correction_candidates_json

# ocr-checkが生成したocr_correction_candidates.jsonのうち、条件に一致する明確な候補（既定では
# 高重要度・高確信度のreplace候補）だけをstatus: approvedに変更するモジュール。実際に
# lesson_pages.jsonへ反映するのはapply-ocr-corrections側の責務であり、このモジュールは
# statusを変更するだけで、editable/lesson_pages.jsonには一切触れない。
# 元のcandidates JSONファイルも直接上書きしない（別ファイルとして出力する）。
# 詳細はdocs/14_apply_ocr_corrections_workflow.md参照。

# 以下に該当する候補は、CLI引数の指定内容にかかわらず絶対に自動approvedにしない
# （安全設計の下限。ユーザーが誤って--action deleteのような指定をしても無効化する）。
_NEVER_APPROVE_ACTIONS = {"delete", "source_check"}
_NEVER_APPROVE_STATUSES = {"needs_source_check", "needs_human_review", "rejected", "approved"}
_NEVER_APPROVE_DETECTION_TYPES = {
    "incomplete_sentence",
    "source_check_required",
    "inferred_ocr_correction",
    "unusual_symbol",
    "garbled_latin",
    "ocr_noise_delete_candidate",
}

_REASON_LABELS = {
    "action_not_replaceable": "actionがreplace以外（delete/source_check）のため対象外",
    "detection_type_excluded": "detection_typeが自動approved対象外の種別のため",
    "status_not_approvable": "statusが元々approved対象にできない値のため",
    "status_not_proposed": "statusがproposedではないため",
    "suggested_missing": "suggestedが空のため",
    "original_missing": "originalが空のため",
    "action_mismatch": "actionが指定条件と一致しないため",
    "severity_mismatch": "severityが指定条件と一致しないため",
    "confidence_mismatch": "confidenceが指定条件と一致しないため",
    "detection_type_mismatch": "detection_typeが指定条件と一致しないため",
}

load_ocr_correction_candidates = load_correction_candidates
write_ocr_correction_candidates = write_correction_candidates_json


def evaluate_candidate_for_approval(
    candidate: dict[str, Any],
    *,
    severity: str | None = "high",
    action: str | None = "replace",
    confidence: str | None = "high",
    detection_type: str | None = None,
) -> str | None:
    """候補を自動approved対象にしてよいか判定する。approved可能ならNone、不可なら理由文字列を返す。

    まず絶対に自動approvedにしない条件（`action: delete`/`action: source_check`、
    `needs_source_check`/`needs_human_review`等のstatus、`incomplete_sentence`等の
    detection_type、`suggested`/`original`が空）をチェックし、これらはCLI引数の指定内容に
    かかわらず常に除外する。その後、`severity`/`action`/`confidence`/`detection_type`の
    指定条件（Noneの場合はそのfieldでは絞り込まない）に一致するかを確認する。
    """
    if candidate.get("action") in _NEVER_APPROVE_ACTIONS:
        return "action_not_replaceable"
    if candidate.get("detection_type") in _NEVER_APPROVE_DETECTION_TYPES:
        return "detection_type_excluded"
    if candidate.get("status") in _NEVER_APPROVE_STATUSES:
        return "status_not_approvable"
    if candidate.get("status") != "proposed":
        return "status_not_proposed"
    if not candidate.get("suggested"):
        return "suggested_missing"
    if not candidate.get("original"):
        return "original_missing"
    if action is not None and candidate.get("action") != action:
        return "action_mismatch"
    if severity is not None and candidate.get("severity") != severity:
        return "severity_mismatch"
    if confidence is not None and candidate.get("confidence") != confidence:
        return "confidence_mismatch"
    if detection_type is not None and candidate.get("detection_type") != detection_type:
        return "detection_type_mismatch"
    return None


def approve_ocr_candidates(
    candidates_data: dict[str, Any],
    *,
    severity: str | None = "high",
    action: str | None = "replace",
    confidence: str | None = "high",
    detection_type: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """条件に一致する安全な候補だけを`status: approved`に変更した新しいcandidates JSONを返す。

    入力の`candidates_data`は変更しない（`copy.deepcopy`した複製に対してのみ操作する）。
    戻り値は`(承認済みcandidates JSON, 結果サマリー)`。結果サマリーには`approved`/
    `not_approved`（未approved化候補に`not_approved_reason`を付与したもの）のリストと
    `input_count`を含む。
    """
    result_data = copy.deepcopy(candidates_data)
    candidates = result_data.get("candidates", [])
    approved: list[dict[str, Any]] = []
    not_approved: list[dict[str, Any]] = []

    for candidate in candidates:
        reason = evaluate_candidate_for_approval(
            candidate, severity=severity, action=action, confidence=confidence, detection_type=detection_type
        )
        if reason is None:
            candidate["status"] = "approved"
            approved.append(candidate)
        else:
            not_approved.append({**candidate, "not_approved_reason": reason})

    result_data["summary"] = dict(result_data.get("summary", {}))
    result_data["summary"]["approval"] = {
        "approved_by_command": True,
        "approved_count": len(approved),
        "criteria": {
            "severity": severity,
            "action": action,
            "confidence": confidence,
            "detection_type": detection_type,
        },
    }

    return result_data, {
        "approved": approved,
        "not_approved": not_approved,
        "input_count": len(candidates),
    }


# --- Markdownレポート -------------------------------------------------------------------


def _format_summary_section(
    result: dict[str, Any], *, input_path: str, output_path: str, dry_run: bool
) -> str:
    lines = [
        "## サマリー",
        "",
        f"- 入力候補数: {result['input_count']}",
        f"- approved化対象件数: {len(result['approved'])}",
        f"- 変更なし件数: {len(result['not_approved'])}",
        f"- 入力ファイル: `{input_path}`",
        f"- 出力ファイル: `{output_path}`" + ("（dry-runのため未生成）" if dry_run else ""),
    ]
    return "\n".join(lines)


def _format_approved_section(result: dict[str, Any]) -> str:
    approved = result["approved"]
    lines = ["## approved化した候補", ""]
    if not approved:
        lines.append("approved化した候補はありません。")
        return "\n".join(lines)
    lines.append("| candidate_id | Page | field | original | suggested | severity | action | confidence | detection_type |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for c in approved:
        lines.append(
            f"| {c['candidate_id']} | {c['page_no']} | {c['field']} | {c['original']} | "
            f"{c['suggested']} | {c['severity']} | {c['action']} | {c['confidence']} | {c['detection_type']} |"
        )
    return "\n".join(lines)


def _format_not_approved_section(result: dict[str, Any]) -> str:
    not_approved = result["not_approved"]
    lines = ["## approved化しなかった候補", ""]
    if not not_approved:
        lines.append("すべての候補がapproved化されました。")
        return "\n".join(lines)
    counts: dict[str, int] = {}
    for c in not_approved:
        counts[c["not_approved_reason"]] = counts.get(c["not_approved_reason"], 0) + 1
    for reason, count in sorted(counts.items(), key=lambda kv: -kv[1]):
        label = _REASON_LABELS.get(reason, reason)
        lines.append(f"- `{reason}`（{label}）: {count}件")
    return "\n".join(lines)


def _format_notes_section() -> str:
    return (
        "## 注意\n\n"
        "- `action: delete`は自動approved対象外です。\n"
        "- `status: needs_source_check`は自動approved対象外です。\n"
        "- `status: needs_human_review`は自動approved対象外です。\n"
        "- `source_check_required`/`inferred_ocr_correction`/`unusual_symbol`/`garbled_latin`/"
        "`incomplete_sentence`/`ocr_noise_delete_candidate`は自動approved対象外です。\n"
        "- これらの除外条件は、CLI引数の指定内容にかかわらず常に適用されます（安全設計の下限）。"
    )


def _format_apply_relationship_section() -> str:
    return (
        "## apply-ocr-correctionsとの関係\n\n"
        "`approve-ocr-candidates`は、candidates JSONの`status`を`approved`に変更するだけです。"
        "`editable/lesson_pages.json`への実際の反映は、既存の`apply-ocr-corrections`が行います。\n\n"
        "```bash\n"
        "python3 -m src.cli apply-ocr-corrections \\\n"
        "  --input output/editable/lesson_pages.json \\\n"
        "  --candidates output/ocr_correction_candidates.approved.json \\\n"
        "  --output output/editable/lesson_pages.ocr_fixed.json \\\n"
        "  --report output/ocr_apply_report.md\n"
        "```"
    )


def render_ocr_approval_report_markdown(
    result: dict[str, Any], *, input_path: str, output_path: str, dry_run: bool = False
) -> str:
    """`approve_ocr_candidates()`の結果からMarkdownレポート（`ocr_approval_report.md`）を生成する。"""
    sections = ["# OCR候補 approved化レポート"]
    if dry_run:
        sections.append(
            "> **dry-run実行のため、出力candidates JSON（`" + output_path + "`）は生成していません。**"
            "approved化予定の内容のみを以下に示します。"
        )
    sections += [
        _format_summary_section(result, input_path=input_path, output_path=output_path, dry_run=dry_run),
        _format_approved_section(result),
        _format_not_approved_section(result),
        _format_notes_section(),
        _format_apply_relationship_section(),
    ]
    return "\n\n".join(sections) + "\n"
