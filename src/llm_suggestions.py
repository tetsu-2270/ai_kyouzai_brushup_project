from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .lesson_pages import LessonDocument
from .parser import load_lesson_document

# ChatGPT/Claude等（当面の手作業検証用の製品）から返ってきた教材改善案Markdown
# （llm-handoffが依頼した回答形式）を読み込み、ページごとの改善候補として構造化するモジュール。
# lesson_pages.jsonへの自動反映・LLM改善案の自動採用は行わない（すべての候補はstatus: proposed
# で出力され、人間が採用判断してから将来のapply-approved-llm-suggestions（未実装）で反映する
# 想定）。詳細はdocs/15_llm_suggestion_candidates_workflow.md参照。

_FIELD_ORDER = ("title", "summary", "body", "notes")
_SUGGESTION_KEY_BY_FIELD = {
    "title": "title_suggestion",
    "summary": "summary_suggestion",
    "body": "body_suggestion",
    "notes": "notes_suggestion",
}

_LABEL_ALIASES: dict[str, tuple[str, ...]] = {
    "issue": ("現状の問題点", "現状問題", "問題点"),
    "policy": ("改善方針",),
    "title_suggestion": ("title改善案", "title案", "タイトル改善案", "タイトル案"),
    "summary_suggestion": ("summary改善案", "summary案", "概要改善案", "概要案"),
    "body_suggestion": ("body改善案", "body案", "本文改善案", "本文案"),
    "notes_suggestion": ("notes改善案", "メモ改善案"),
    "caution": ("注意点", "注意"),
}

_NO_CHANGE_PHRASES = (
    "変更なし", "現状維持", "そのままでよい", "そのままで良い", "修正不要", "特になし", "なし",
)

_COMMENT_ONLY_LENGTH_THRESHOLD = 120

_PAGE_HEADING_RE = re.compile(
    r"^#{0,6}\s*(?:Page\s*0*(\d+)|ページ\s*0*(\d+))\b.*$", re.IGNORECASE | re.MULTILINE
)
_ANY_HEADING_RE = re.compile(r"^(#{1,6})\s*(.+?)\s*$", re.MULTILINE)
_LABEL_LINE_RE = re.compile(r"^[\-\*・]?\s*(?P<label>[^\n：:]{1,20}?)\s*[：:]\s*(?P<rest>.*)$", re.MULTILINE)


def load_lesson_pages(path: str | Path) -> LessonDocument:
    """`lesson_pages.json`（editable配下・OCR補正済み等）を読み込む。"""
    return load_lesson_document(path)


def load_llm_suggestions_markdown(path: str | Path) -> str:
    """ChatGPT/Claude等の回答Markdownを読み込む。"""
    return Path(path).read_text(encoding="utf-8")


def _normalize_label(text: str) -> str:
    return re.sub(r"[\s　]+", "", text or "").lower()


def _match_label_field(label_text: str) -> str | None:
    normalized = _normalize_label(label_text)
    if not normalized:
        return None
    for field_key, aliases in _LABEL_ALIASES.items():
        for alias in aliases:
            if _normalize_label(alias) == normalized:
                return field_key
    return None


def _sections_by_heading(markdown_text: str) -> list[dict[str, Any]]:
    matches = list(_ANY_HEADING_RE.finditer(markdown_text))
    sections = []
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown_text)
        sections.append({
            "level": len(match.group(1)),
            "title": match.group(2).strip(),
            "body": markdown_text[start:end].strip(),
        })
    return sections


def extract_overall_review(markdown_text: str) -> dict[str, str]:
    """「全体評価」「大きく直す必要がある点」「直しすぎない方がよい点」「編集時の注意」を抽出する。"""
    result = {"overall_evaluation": "", "major_points": "", "keep_as_is_points": "", "editing_notes": ""}
    for section in _sections_by_heading(markdown_text):
        normalized_title = _normalize_label(section["title"])
        if _normalize_label("全体評価") in normalized_title:
            result["overall_evaluation"] = section["body"]
        elif _normalize_label("大きく直す必要がある点") in normalized_title:
            result["major_points"] = section["body"]
        elif _normalize_label("直しすぎない方がよい点") in normalized_title:
            result["keep_as_is_points"] = section["body"]
        elif "編集時の注意" in normalized_title:
            result["editing_notes"] = section["body"]
    return result


def extract_page_suggestion_blocks(markdown_text: str) -> list[dict[str, Any]]:
    """「## Page 1: タイトル」等の表記揺れに対応してページ別改善案ブロックを抽出する。

    対応する表記例: `## Page 1: タイトル` / `## Page 1` / `### Page 1: タイトル` /
    `Page 1: タイトル`（見出し記号なし）/ `## ページ1` / `## Page1` / `## Page 01`。
    """
    page_matches = list(_PAGE_HEADING_RE.finditer(markdown_text))
    level1_positions = [m.start() for m in _ANY_HEADING_RE.finditer(markdown_text) if len(m.group(1)) == 1]
    blocks = []
    for i, match in enumerate(page_matches):
        page_no_str = match.group(1) or match.group(2)
        try:
            page_no = int(page_no_str)
        except (TypeError, ValueError):
            continue
        start = match.end()
        end_candidates = []
        if i + 1 < len(page_matches):
            end_candidates.append(page_matches[i + 1].start())
        end_candidates += [pos for pos in level1_positions if pos > match.start()]
        end = min(end_candidates) if end_candidates else len(markdown_text)
        block_text = markdown_text[start:end].strip()
        blocks.append({"page_no": page_no, "block_text": block_text})
    return blocks


def parse_page_suggestion_block(block_text: str) -> dict[str, str]:
    """ページ別改善案ブロックから、issue/policy/各field改善案/cautionを抽出する。

    「現状の問題点：」等の認識できたラベル行だけを区切りとして扱うため、改善案本文の中に
    コロンを含む行があっても誤って区切ってしまわない。抽出できなかった項目は空文字になる。
    """
    matches = list(_LABEL_LINE_RE.finditer(block_text))
    boundaries = []
    for match in matches:
        field_key = _match_label_field(match.group("label"))
        if field_key:
            boundaries.append({"field": field_key, "value_start": match.start("rest"), "line_start": match.start()})

    values: dict[str, list[str]] = {key: [] for key in _LABEL_ALIASES}
    for i, boundary in enumerate(boundaries):
        end = boundaries[i + 1]["line_start"] if i + 1 < len(boundaries) else len(block_text)
        value = block_text[boundary["value_start"]:end].strip()
        values[boundary["field"]].append(value)

    return {field: "\n".join(v).strip() for field, v in values.items()}


def parse_llm_suggestions(markdown_text: str) -> dict[str, Any]:
    """LLM回答Markdown全体を解析し、全体評価・ページ別改善案・パース警告を返す。"""
    overall_review = extract_overall_review(markdown_text)
    page_blocks = extract_page_suggestion_blocks(markdown_text)
    warnings: list[dict[str, Any]] = []
    pages = []
    for block in page_blocks:
        page_no = block["page_no"]
        parsed = parse_page_suggestion_block(block["block_text"])
        pages.append({"page_no": page_no, "raw_block": block["block_text"], **parsed})
        if not any(parsed[key] for key in ("title_suggestion", "summary_suggestion", "body_suggestion", "notes_suggestion")):
            warnings.append({
                "page_no": page_no,
                "warning_type": "no_suggestions_found",
                "message": f"Page {page_no}: title/summary/body/notesいずれの改善案も抽出できませんでした",
            })

    if not page_blocks:
        warnings.append({
            "page_no": None,
            "warning_type": "page_block_not_found",
            "message": "ページ別改善案のブロックが見つかりませんでした",
        })

    return {"overall_review": overall_review, "pages": pages, "warnings": warnings}


def _is_no_change(text: str) -> bool:
    normalized = _normalize_label(text)
    if not normalized:
        return True
    return normalized in {_normalize_label(phrase) for phrase in _NO_CHANGE_PHRASES}


def build_llm_suggestion_candidates(
    document: LessonDocument,
    parsed_suggestions: dict[str, Any],
    *,
    source_lesson_pages: str = "",
    source_suggestions: str = "",
) -> dict[str, Any]:
    """`parse_llm_suggestions()`の結果とlesson_pages.jsonから、`llm_suggestion_candidates.json`
    相当の構造化データを組み立てる。

    候補生成対象fieldはtitle/summary/body/notes（source_page_no/source_image/assets/
    layout_instructionは元資料対応・確認用として参照するのみで、改善候補の対象にしない）。
    「変更なし」「現状維持」等の改善案は候補化しない。すべての候補はstatus: proposedで生成し、
    自動反映は行わない（採用判断は人間が行う）。
    """
    page_by_no = {page.page_no: (index, page) for index, page in enumerate(document.pages)}
    candidates: list[dict[str, Any]] = []
    warnings = list(parsed_suggestions.get("warnings", []))

    for page_data in parsed_suggestions.get("pages", []):
        page_no = page_data["page_no"]
        lookup = page_by_no.get(page_no)
        if lookup is None:
            warnings.append({
                "page_no": page_no,
                "warning_type": "page_not_found_in_lesson_pages",
                "message": f"Page {page_no}はlesson_pages.json内に見つかりませんでした",
            })
            continue
        page_index, page = lookup

        for field in _FIELD_ORDER:
            suggested = page_data.get(_SUGGESTION_KEY_BY_FIELD[field], "")
            if _is_no_change(suggested):
                continue
            if len(suggested) > _COMMENT_ONLY_LENGTH_THRESHOLD:
                warnings.append({
                    "page_no": page_no,
                    "warning_type": "suggestion_looks_like_comment_only",
                    "message": f"Page {page_no}の{field}改善案が長文のため、置換案ではなく説明文の可能性があります",
                })
            candidate_id = f"llm-{len(candidates) + 1:04d}"
            candidates.append({
                "candidate_id": candidate_id,
                "page_no": page_no,
                "page_index": page_index,
                "field": field,
                "original": getattr(page, field, "") or "",
                "suggested": suggested,
                "issue": page_data.get("issue", ""),
                "policy": page_data.get("policy", ""),
                "caution": page_data.get("caution", ""),
                "source_page_no": list(page.source_page_no) if page.source_page_no else [],
                "source_image": page.source_image or "",
                "status": "proposed",
                "human_note": "",
                "raw_block": page_data.get("raw_block", ""),
            })

    by_field = {"title": 0, "summary": 0, "body": 0, "notes": 0}
    for candidate in candidates:
        by_field[candidate["field"]] += 1
    pages_with_suggestions = len({c["page_no"] for c in candidates})

    return {
        "version": "1.0",
        "source_lesson_pages": source_lesson_pages,
        "source_suggestions": source_suggestions,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "mode": "llm_suggestions",
        "summary": {
            "total_pages": len(document.pages),
            "pages_with_suggestions": pages_with_suggestions,
            "total_candidates": len(candidates),
            "title_candidates": by_field["title"],
            "summary_candidates": by_field["summary"],
            "body_candidates": by_field["body"],
            "notes_candidates": by_field["notes"],
            "warnings": len(warnings),
        },
        "overall_review": parsed_suggestions.get("overall_review", {}),
        "candidates": candidates,
        "parse_warnings": warnings,
    }


def write_llm_suggestion_candidates_json(path: str | Path, candidates_data: dict[str, Any]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(candidates_data, ensure_ascii=False, indent=2), encoding="utf-8")


# --- Markdownレポート -------------------------------------------------------------------


def _format_purpose_section() -> str:
    return (
        "## 1. 目的\n\n"
        "このレポートは、ChatGPT/Claude等から返ってきた教材改善案（`llm-handoff`で依頼した"
        "回答Markdown）を、ページ・項目ごとの改善候補として構造化した結果を示すものです。\n\n"
        "**この機能はLLM改善案を自動で`lesson_pages.json`へ反映しません。** あくまで人間が"
        "採用判断しやすい形に整理するだけです。"
    )


def _format_usage_section(candidates_output: str) -> str:
    return (
        "## 2. 使い方\n\n"
        "1. `llm_suggestion_candidates.json`を開き、候補ごとに`status`を確認する。\n"
        "2. 採用する候補は`status`を`approved`に変更する。\n"
        "3. 採用しない候補は`rejected`、元資料確認が必要な候補は`needs_source_check`にする。\n"
        "4. 判断メモは`human_note`に記入する。\n"
        f"5. 現時点では、`{candidates_output}`を見ながら人間が`lesson_pages.json`を編集する"
        "（将来的な自動反映は`docs/15_llm_suggestion_candidates_workflow.md`参照）。"
    )


def _format_overall_summary_section(
    document: LessonDocument,
    candidates_data: dict[str, Any],
    *,
    lesson_pages_path: str,
    suggestions_path: str,
    candidates_output: str,
    report_path: str,
) -> str:
    summary = candidates_data["summary"]
    lines = [
        "## 3. 全体サマリー",
        "",
        f"- 入力lesson_pages: `{lesson_pages_path}`",
        f"- 入力suggestions: `{suggestions_path}`",
        f"- 出力candidates: `{candidates_output}`",
        f"- 出力report: `{report_path}`",
        f"- ページ数: {summary['total_pages']}",
        f"- 改善案が見つかったページ数: {summary['pages_with_suggestions']}",
        f"- 候補総数: {summary['total_candidates']}",
        f"- title候補数: {summary['title_candidates']}",
        f"- summary候補数: {summary['summary_candidates']}",
        f"- body候補数: {summary['body_candidates']}",
        f"- notes候補数: {summary['notes_candidates']}",
        f"- parse_warnings件数: {summary['warnings']}",
    ]
    return "\n".join(lines)


def _format_overall_review_section(candidates_data: dict[str, Any]) -> str:
    review = candidates_data.get("overall_review", {})
    lines = ["## 4. 教材全体へのLLM評価"]
    lines.append("### 全体評価\n\n" + (review.get("overall_evaluation") or "(抽出できませんでした)"))
    lines.append("### 大きく直す必要がある点\n\n" + (review.get("major_points") or "(抽出できませんでした)"))
    lines.append("### 直しすぎない方がよい点\n\n" + (review.get("keep_as_is_points") or "(抽出できませんでした)"))
    lines.append("### editable/lesson_pages.json 編集時の注意（LLM側の記述）\n\n" + (review.get("editing_notes") or "(抽出できませんでした)"))
    return "\n\n".join(lines)


def _format_per_page_section(document: LessonDocument, candidates_data: dict[str, Any]) -> str:
    candidates = candidates_data["candidates"]
    header = "## 5. ページ別改善候補一覧"
    page_nos = sorted({c["page_no"] for c in candidates})
    if not page_nos:
        return f"{header}\n\n改善候補は見つかりませんでした。"

    page_by_no = {p.page_no: p for p in document.pages}
    blocks = []
    for page_no in page_nos:
        page = page_by_no.get(page_no)
        page_candidates = [c for c in candidates if c["page_no"] == page_no]
        by_field = {c["field"]: c for c in page_candidates}
        lines = [f"### Page {page_no}: {page.title if page else '(不明)'}", ""]
        if page:
            lines.append(f"- source_page_no: {', '.join(str(v) for v in page.source_page_no) or '(なし)'}")
            lines.append(f"- source_image: {page.source_image or '(なし)'}")
        issue = next((c["issue"] for c in page_candidates if c["issue"]), "")
        policy = next((c["policy"] for c in page_candidates if c["policy"]), "")
        caution = next((c["caution"] for c in page_candidates if c["caution"]), "")
        lines.append(f"- 現状の問題点: {issue or '(なし)'}")
        lines.append(f"- 改善方針: {policy or '(なし)'}")
        lines.append(f"- title候補: {by_field['title']['suggested'] if 'title' in by_field else '(なし)'}")
        lines.append(f"- summary候補: {by_field['summary']['suggested'] if 'summary' in by_field else '(なし)'}")
        lines.append(f"- body候補: {by_field['body']['suggested'] if 'body' in by_field else '(なし)'}")
        lines.append(f"- 注意点: {caution or '(なし)'}")
        lines.append(f"- 候補ID: {', '.join(c['candidate_id'] for c in page_candidates)}")
        blocks.append("\n".join(lines))
    return f"{header}\n\n" + "\n\n".join(blocks)


def _format_per_field_table_section(candidates_data: dict[str, Any]) -> str:
    candidates = candidates_data["candidates"]
    lines = ["## 6. field別候補一覧", ""]
    if not candidates:
        lines.append("候補はありません。")
        return "\n".join(lines)
    lines.append("| candidate_id | Page | field | original | suggested | status |")
    lines.append("|---|---|---|---|---|---|")
    for c in candidates:
        lines.append(f"| {c['candidate_id']} | {c['page_no']} | {c['field']} | {c['original']} | {c['suggested']} | {c['status']} |")
    return "\n".join(lines)


def _format_parse_warnings_section(candidates_data: dict[str, Any]) -> str:
    warnings = candidates_data.get("parse_warnings", [])
    lines = ["## 7. parse_warnings", ""]
    if not warnings:
        lines.append("警告はありません。")
        return "\n".join(lines)
    lines.append("| page_no | warning_type | message |")
    lines.append("|---|---|---|")
    for w in warnings:
        lines.append(f"| {w.get('page_no', '(不明)')} | {w['warning_type']} | {w['message']} |")
    return "\n".join(lines)


def _format_adoption_memo_section() -> str:
    return (
        "## 8. 採用判断メモ\n\n"
        "- 採用する候補は`status`を`approved`に変更してください。\n"
        "- 採用しない候補は`status`を`rejected`に変更してください。\n"
        "- 元資料確認が必要な候補は`status`を`needs_source_check`にしてください。\n"
        "- 判断理由や気づいた点は`human_note`に書いてください。\n"
        "- `needs_human_review`は、内容の妥当性そのものを人間が確認すべき候補に使ってください"
        "（`caution`や`parse_warnings`に注意点が出ている候補が該当します）。"
    )


def _format_next_commands_section(lesson_pages_path: str, candidates_output: str) -> str:
    return (
        "## 9. 次に実行するコマンド例\n\n"
        "現時点では、このJSONを見ながら人間が`lesson_pages.json`を編集してください。\n\n"
        "```text\n"
        "TODO（未実装。将来的な反映コマンドの案）:\n"
        f"python3 -m src.cli apply-approved-llm-suggestions --input {lesson_pages_path} "
        f"--candidates {candidates_output} --output output/editable/lesson_pages.llm_fixed.json "
        "--report output/llm_apply_report.md\n"
        "```"
    )


def _format_notes_section() -> str:
    return (
        "## 10. 注意事項\n\n"
        "- この機能はLLM改善案を自動で`lesson_pages.json`へ反映しません。すべての候補は"
        "`status: proposed`で生成されます。\n"
        "- LLM回答のMarkdown形式には表記揺れが起こり得ます。想定外の見出し・ラベル表記は"
        "抽出できず、`parse_warnings`に記録されます。抽出漏れがないか、レポートと元のLLM回答を"
        "見比べて確認してください。\n"
        "- `source_page_no`/`source_image`/`assets`/`layout_instruction`は改善候補の対象に"
        "していません（元資料対応・確認用の参照情報です）。\n"
        "- OCR崩れが残っている場合は、先に`ocr-check`/`apply-ocr-corrections`でOCR補正済みの"
        "`lesson_pages.ocr_fixed.json`を作成し、それを`--lesson-pages`に使ってください。"
    )


def render_llm_suggestion_report_markdown(
    document: LessonDocument,
    candidates_data: dict[str, Any],
    *,
    lesson_pages_path: str,
    suggestions_path: str,
    candidates_output: str,
    report_path: str,
) -> str:
    """`build_llm_suggestion_candidates()`の結果からMarkdownレポート（`llm_suggestion_report.md`）
    を生成する。
    """
    title = document.metadata.project_title or "教材ブラッシュアップ設計書"
    sections = [
        f"# {title}：LLM改善案 構造化候補レポート",
        _format_purpose_section(),
        _format_usage_section(candidates_output),
        _format_overall_summary_section(
            document, candidates_data,
            lesson_pages_path=lesson_pages_path, suggestions_path=suggestions_path,
            candidates_output=candidates_output, report_path=report_path,
        ),
        _format_overall_review_section(candidates_data),
        _format_per_page_section(document, candidates_data),
        _format_per_field_table_section(candidates_data),
        _format_parse_warnings_section(candidates_data),
        _format_adoption_memo_section(),
        _format_next_commands_section(lesson_pages_path, candidates_output),
        _format_notes_section(),
    ]
    return "\n\n".join(sections) + "\n"
