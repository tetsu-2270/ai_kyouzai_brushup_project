from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .lesson_pages import LessonDocument, LessonPage

# OCR結果の品質（誤認識・文字化け・不自然な表記）を、llm-handoffでLLMへ投入する前に
# システム側で検出・分類し、修正候補を人間が判断しやすい形で提示するモジュール。
# OCRエンジンの再実行・自動修正・editable/lesson_pages.jsonへの自動反映は行わない
# （将来のapply-ocr-corrections相当の機能に備え、補正候補は構造化JSONとして出力する）。
# 詳細はdocs/13_ocr_quality_check_workflow.md参照。

_SCAN_FIELDS = ("title", "summary", "body", "notes", "layout_instruction")

_SEVERITY_LABELS = {"high": "高", "medium": "中", "low": "低"}

# --- 1. よくあるOCR誤認識辞書（検出のみ・自動置換はしない） ------------------------------

_OCR_MISREAD_DICTIONARY = {
    "一買": "一貫",
    "アウトブット": "アウトプット",
    "右労": "苦労",
    "革細": "些細",
    "実貴": "実践",
    "共通説識": "共通認識",
    "人帳面": "几帳面",
    "叱嘘激励": "叱咤激励",
    "全1 1問": "全11問",
    "1 つ": "1つ",
}


def detect_common_ocr_misreads(text: str) -> list[dict[str, Any]]:
    """OCR誤認識辞書（`_OCR_MISREAD_DICTIONARY`）に一致する語句を検出する。

    辞書は将来拡張しやすいよう、この関数の外側にモジュールレベル定数として定義している。
    """
    if not text:
        return []
    candidates = []
    for wrong, correct in _OCR_MISREAD_DICTIONARY.items():
        if wrong in text:
            candidates.append({
                "original": wrong,
                "suggested": correct,
                "severity": "high",
                "reason": f"OCR誤認識辞書に一致します（{wrong} → {correct}）",
                "detection_type": "common_ocr_misread",
                "requires_image_check": False,
            })
    return candidates


# --- 2. 意味不明な英字・記号列（過検出しすぎないための許可語リスト付き） --------------------

_LATIN_RUN_RE = re.compile(r"[A-Za-z]+(?:[ \t]+[A-Za-z]+)*")

_LATIN_ALLOWLIST = {
    "url", "sns", "instagram", "canva", "gamma", "chatgpt", "claude",
    "pdf", "docx", "pptx", "png", "jpg", "jpeg", "csv", "json", "html",
    "ai", "llm", "ocr", "ok", "ng", "id", "web", "seo", "qr", "pc",
    "youtube", "line", "wifi", "wi-fi", "no", "cm", "kg", "app",
}


def detect_garbled_latin_sequences(text: str) -> list[dict[str, Any]]:
    """日本語教材本文として不自然な英字の並びを「疑わしい候補」として検出する。

    URL/SNS/Instagram/Canva/PDF等の意図的な英語表記を誤検出しないよう、`_LATIN_ALLOWLIST`に
    一致する語句のみで構成される部分は対象外にする。1文字トークンは列挙記号等と区別できない
    ため対象外とし、2文字以上のトークンを持つ並びのみ検出する。完全な判定は難しいため、
    多少の過検出は許容し「要確認候補」として扱う。
    """
    if not text:
        return []
    candidates = []
    for match in _LATIN_RUN_RE.finditer(text):
        run = match.group(0)
        tokens = [t for t in run.split() if len(t) >= 2]
        if not tokens:
            continue
        if all(t.lower() in _LATIN_ALLOWLIST for t in tokens):
            continue
        candidates.append({
            "original": run,
            "suggested": None,
            "severity": "medium",
            "reason": "日本語教材本文として不自然な英字列の可能性があります",
            "detection_type": "garbled_latin",
            "requires_image_check": True,
        })
    return candidates


# --- 3. 不自然な記号・番号崩れ -----------------------------------------------------------

_UNUSUAL_SYMBOL_PATTERNS = (
    re.compile(r"[(（][①-⑳]"),
    re.compile(r"[〈<][①-⑳]"),
    re.compile(r"[①-⑳]{2,}"),
    re.compile(r"\\{1,}"),
    re.compile(r"[|｜]{2,}"),
    re.compile(r"[!-/:-@\[-`{-~]{4,}"),
)


def detect_unusual_symbols(text: str) -> list[dict[str, Any]]:
    """不自然な括弧の始まり・番号崩れ・バックスラッシュ装飾・記号の連続等を検出する。"""
    if not text:
        return []
    candidates = []
    for pattern in _UNUSUAL_SYMBOL_PATTERNS:
        for match in pattern.finditer(text):
            candidates.append({
                "original": match.group(0),
                "suggested": None,
                "severity": "medium",
                "reason": "不自然な記号・番号の並びの可能性があります",
                "detection_type": "unusual_symbol",
                "requires_image_check": True,
            })
    return candidates


# --- 4. 文が途中で切れていそうな箇所 ------------------------------------------------------

_INCOMPLETE_ENDINGS = (
    "たら", "ので", "ため", "けれど", "けど", "が、", "と、", "は、", "も、", "し、", "て、",
)
_SENTENCE_END_CHARS = "。！？」』）.!?"


def detect_incomplete_sentences(text: str) -> list[dict[str, Any]]:
    """文末が助詞・接続詞で終わっている等、文が途中で切れている可能性がある行を検出する。

    過検出してもよい前提のため、句点等で終わっていない行のうち、典型的な未完パターンに
    一致するものを候補として出す。
    """
    if not text:
        return []
    candidates = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped[-1] in _SENTENCE_END_CHARS:
            continue
        for ending in _INCOMPLETE_ENDINGS:
            if stripped.endswith(ending):
                candidates.append({
                    "original": stripped,
                    "suggested": None,
                    "severity": "high",
                    "reason": "文が途中で切れている可能性があります",
                    "detection_type": "incomplete_sentence",
                    "requires_image_check": True,
                })
                break
    return candidates


# --- 5. 数字と日本語の間の不自然な空白（日本語として不自然な箇所の一種） ----------------------

_NUMBER_JAPANESE_SPACING_RE = re.compile(
    r"(?:(?<=[ぁ-んァ-ヶ一-龯])[ 　]+(?=[0-9])|(?<=[0-9])[ 　]+(?=[ぁ-んァ-ヶ一-龯]))"
)


def detect_suspicious_tokens(text: str) -> list[dict[str, Any]]:
    """数字と日本語の間の不自然な空白など、ルールベースで検出できる範囲の不自然な表記を検出する。

    完全な自然言語判定は行わない（ルールベースでできる範囲にとどめる）。
    """
    if not text:
        return []
    candidates = []
    for match in _NUMBER_JAPANESE_SPACING_RE.finditer(text):
        start = max(0, match.start() - 5)
        end = min(len(text), match.end() + 5)
        snippet = text[start:end].strip()
        candidates.append({
            "original": snippet,
            "suggested": None,
            "severity": "low",
            "reason": "数字と日本語の間に不自然な空白がある可能性があります",
            "detection_type": "spacing",
            "requires_image_check": False,
        })
    return candidates


_DETECTORS = (
    detect_common_ocr_misreads,
    detect_garbled_latin_sequences,
    detect_unusual_symbols,
    detect_incomplete_sentences,
    detect_suspicious_tokens,
)


def analyze_page_ocr_quality(page: LessonPage) -> list[dict[str, Any]]:
    """ページ1件分のOCR品質を検出する。フィールドごとに全検出器を適用する。"""
    candidates = []
    for field in _SCAN_FIELDS:
        text = getattr(page, field, "") or ""
        if not text:
            continue
        for detector in _DETECTORS:
            for raw in detector(text):
                raw = dict(raw)
                raw["field"] = field
                candidates.append(raw)
    return candidates


def build_correction_candidate(
    page: LessonPage, page_index: int, raw: dict[str, Any], candidate_id: str
) -> dict[str, Any]:
    """検出結果(raw)とページ情報から、`ocr_correction_candidates.json`の候補1件分を組み立てる。

    `confidence`は現段階では`severity`と同等の値を使う（要件上、難しければ同等でよいとされている）。
    """
    return {
        "candidate_id": candidate_id,
        "page_no": page.page_no,
        "page_index": page_index,
        "field": raw["field"],
        "original": raw["original"],
        "suggested": raw.get("suggested"),
        "severity": raw["severity"],
        "reason": raw["reason"],
        "detection_type": raw["detection_type"],
        "source_page_no": list(page.source_page_no) if page.source_page_no else [],
        "source_image": page.source_image or "",
        "confidence": raw["severity"],
        "requires_image_check": bool(raw.get("requires_image_check", False)),
        "status": "proposed",
        "human_note": "",
    }


def build_ocr_correction_candidates(document: LessonDocument, source_file: str = "") -> dict[str, Any]:
    """教材全体のOCR補正候補データ（`ocr_correction_candidates.json`相当の構造）を組み立てる。

    今回は自動反映を行わない。将来的に`status`を`approved`等に変更したうえで、
    `apply-ocr-corrections`（未実装）のような機能で`editable/lesson_pages.json`へ
    反映できるようにするための構造化データとして出力する。
    """
    candidates: list[dict[str, Any]] = []
    counts = {"high": 0, "medium": 0, "low": 0}
    for page_index, page in enumerate(document.pages):
        for raw in analyze_page_ocr_quality(page):
            candidate_id = f"ocr-{len(candidates) + 1:04d}"
            candidate = build_correction_candidate(page, page_index, raw, candidate_id)
            candidates.append(candidate)
            counts[candidate["severity"]] = counts.get(candidate["severity"], 0) + 1

    return {
        "version": 1,
        "source_file": source_file,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "mode": document.metadata.mode,
        "summary": {
            "total_pages": len(document.pages),
            "total_candidates": len(candidates),
            "high": counts["high"],
            "medium": counts["medium"],
            "low": counts["low"],
        },
        "candidates": candidates,
    }


def write_correction_candidates_json(data: dict[str, Any], path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# --- Markdownレポート -------------------------------------------------------------------


def _format_purpose_section() -> str:
    return (
        "## 1. 目的\n\n"
        "このレポートは、`llm-handoff`でChatGPT/Claude等へ教材改善を依頼する**前**に、"
        "OCR結果に含まれる誤認識・文字化け・意味不明な文字列・不自然な表記の可能性がある箇所を"
        "システム側で検出し、修正候補・要確認箇所・重要度を整理するためのものです。\n\n"
        "OCR崩れが多いままLLMへ投入すると、LLMの回答が教材改善ではなくOCR誤字の指摘中心になって"
        "しまうことがあります。先にこのレポートで候補を確認しておくことで、`llm-handoff`後の"
        "改善案がより教材内容に集中しやすくなります。"
    )


def _format_usage_section() -> str:
    return (
        "## 2. 使い方\n\n"
        "```bash\n"
        "python3 -m src.cli ocr-check --input output/editable/lesson_pages.json "
        "--output output/ocr_check_report.md "
        "--candidates-output output/ocr_correction_candidates.json\n"
        "```\n\n"
        "1. 本レポート（`ocr_check_report.md`）で、検出された候補・重要度・修正案を確認する。\n"
        "2. `ocr_correction_candidates.json`で、将来の反映に使える構造化データを確認する。\n"
        "3. 高重要度の候補から優先して、採用・不採用・元画像確認を判断する。\n"
        "4. 判断結果をもとに、必要な箇所を人間が`output/editable/lesson_pages.json`に反映する。\n"
        "5. OCR補正が済んだら`llm-handoff`でLLM投入用Markdownを作成する。"
    )


def _format_overall_summary_section(document: LessonDocument, candidates: list[dict[str, Any]], candidates_output: str) -> str:
    pages_with_candidates = {c["page_no"] for c in candidates}
    pages_requiring_image_check = {c["page_no"] for c in candidates if c.get("requires_image_check")}
    by_type: dict[str, int] = {}
    for c in candidates:
        by_type[c["detection_type"]] = by_type.get(c["detection_type"], 0) + 1
    high = sum(1 for c in candidates if c["severity"] == "high")
    medium = sum(1 for c in candidates if c["severity"] == "medium")
    low = sum(1 for c in candidates if c["severity"] == "low")

    lines = [
        "## 3. 全体サマリー",
        "",
        f"- ページ数: {len(document.pages)}",
        f"- OCR確認対象ページ数: {len(document.pages)}",
        f"- 要確認ページ数: {len(pages_with_candidates)}",
        f"- 検出された疑わしい語句・候補の総数: {len(candidates)}",
        f"- 意味不明な英字・記号列の件数: {by_type.get('garbled_latin', 0)}",
        f"- よくあるOCR誤認識候補の件数: {by_type.get('common_ocr_misread', 0)}",
        f"- 未完の可能性がある文の件数: {by_type.get('incomplete_sentence', 0)}",
        f"- 不自然な記号・番号の件数: {by_type.get('unusual_symbol', 0)}",
        f"- 高重要度の件数: {high}",
        f"- 中重要度の件数: {medium}",
        f"- 低重要度の件数: {low}",
        f"- 元画像確認が必要そうなページ数: {len(pages_requiring_image_check)}",
        f"- 補正候補JSONの出力先: `{candidates_output}`",
    ]
    return "\n".join(lines)


def _format_detection_summary_section(candidates: list[dict[str, Any]]) -> str:
    by_type: dict[str, int] = {}
    for c in candidates:
        by_type[c["detection_type"]] = by_type.get(c["detection_type"], 0) + 1
    type_labels = {
        "common_ocr_misread": "よくあるOCR誤認識候補",
        "garbled_latin": "意味不明な英字・記号列",
        "unusual_symbol": "不自然な記号・番号崩れ",
        "incomplete_sentence": "未完の可能性がある文",
        "spacing": "数字と日本語の不自然な空白",
    }
    lines = ["## 4. システム検出結果サマリー", ""]
    if not candidates:
        lines.append("検出された候補はありませんでした。")
        return "\n".join(lines)
    for detection_type, count in sorted(by_type.items(), key=lambda kv: -kv[1]):
        label = type_labels.get(detection_type, detection_type)
        lines.append(f"- {label}（`{detection_type}`）: {count}件")
    return "\n".join(lines)


def _format_severity_section(candidates: list[dict[str, Any]]) -> str:
    lines = ["## 5. 重要度別の要確認候補一覧", ""]
    for severity in ("high", "medium", "low"):
        label = _SEVERITY_LABELS[severity]
        matched = [c for c in candidates if c["severity"] == severity]
        lines.append(f"### 重要度：{label}（{len(matched)}件）")
        lines.append("")
        if not matched:
            lines.append("（該当なし）")
        else:
            for c in matched:
                suggested = c["suggested"] or "(元画像確認)"
                lines.append(
                    f"- `{c['candidate_id']}` Page {c['page_no']} / {c['field']}: "
                    f"「{c['original']}」→「{suggested}」（{c['reason']}）"
                )
        lines.append("")
    return "\n".join(lines).rstrip()


def _format_flagged_pages_section(document: LessonDocument, candidates: list[dict[str, Any]]) -> str:
    pages_with_candidates = sorted({c["page_no"] for c in candidates})
    lines = ["## 6. OCR崩れの可能性があるページ一覧", ""]
    if not pages_with_candidates:
        lines.append("OCR崩れの可能性がある候補は検出されませんでした。")
        return "\n".join(lines)
    page_by_no = {p.page_no: p for p in document.pages}
    for page_no in pages_with_candidates:
        page = page_by_no.get(page_no)
        title = page.title if page and page.title else "(未設定)"
        count = sum(1 for c in candidates if c["page_no"] == page_no)
        lines.append(f"- Page {page_no}（{title}）: {count}件")
    return "\n".join(lines)


def _format_page_detail(page: LessonPage, candidates: list[dict[str, Any]]) -> str:
    page_candidates = [c for c in candidates if c["page_no"] == page.page_no]
    high = sum(1 for c in page_candidates if c["severity"] == "high")
    medium = sum(1 for c in page_candidates if c["severity"] == "medium")
    low = sum(1 for c in page_candidates if c["severity"] == "low")
    by_type: dict[str, int] = {}
    for c in page_candidates:
        by_type[c["detection_type"]] = by_type.get(c["detection_type"], 0) + 1
    image_check_count = sum(1 for c in page_candidates if c.get("requires_image_check"))

    lines = [f"### Page {page.page_no}: {page.title or '(未設定)'}", "", "基本情報："]
    lines.append(f"- page_no: {page.page_no}")
    if page.role:
        lines.append(f"- role: {page.role}")
    if page.source_page_no:
        lines.append(f"- source_page_no: {', '.join(str(v) for v in page.source_page_no)}")
    if page.source_image:
        lines.append(f"- source_image: {page.source_image}")
    lines.append(f"- title: {page.title or '(未設定)'}")
    lines.append("")
    lines.append("検出結果：")
    lines.append(f"- 高重要度: {high}")
    lines.append(f"- 中重要度: {medium}")
    lines.append(f"- 低重要度: {low}")
    lines.append(f"- 疑わしい語句: {len(page_candidates)}")
    lines.append(f"- 意味不明な英字・記号列: {by_type.get('garbled_latin', 0)}")
    lines.append(f"- OCR誤認識候補: {by_type.get('common_ocr_misread', 0)}")
    lines.append(f"- 未完の可能性がある文: {by_type.get('incomplete_sentence', 0)}")
    lines.append(f"- 不自然な記号・番号: {by_type.get('unusual_symbol', 0)}")
    lines.append(f"- 元画像確認が必要そうな箇所: {image_check_count}")
    lines.append("")
    lines.append("修正候補：")
    if not page_candidates:
        lines.append("（該当なし）")
    else:
        for c in page_candidates:
            lines.append(f"- candidate_id：{c['candidate_id']}")
            lines.append(f"  - 検出語句：{c['original']}")
            lines.append(f"  - 対象項目：{c['field']}")
            lines.append(f"  - 修正候補：{c['suggested'] or '(元画像確認)'}")
            lines.append(f"  - 重要度：{_SEVERITY_LABELS[c['severity']]}")
            lines.append(f"  - 理由：{c['reason']}")
            lines.append(f"  - 元画像確認：{'必要' if c.get('requires_image_check') else '不要'}")
            lines.append("  - 人間の判断：[ ] 採用 / [ ] 不採用 / [ ] 元画像確認")
    lines.append("")
    lines.append("修正メモ欄：")
    lines.append("- 採用する修正：")
    lines.append("- 採用しない修正：")
    lines.append("- 元画像で確認すること：")
    lines.append("- lesson_pages.jsonで修正する項目：")
    return "\n".join(lines)


def _format_pages_detail_section(document: LessonDocument, candidates: list[dict[str, Any]]) -> str:
    header = "## 7. ページ別の確認結果"
    if not document.pages:
        return f"{header}\n\n（対象ページがありません。）"
    body = "\n\n".join(_format_page_detail(page, candidates) for page in document.pages)
    return f"{header}\n\n{body}"


def _format_common_misreads_section(candidates: list[dict[str, Any]]) -> str:
    matched = [c for c in candidates if c["detection_type"] == "common_ocr_misread"]
    lines = ["## 8. よくあるOCR誤認識候補", ""]
    if not matched:
        lines.append("OCR誤認識辞書に一致する候補は検出されませんでした。")
        return "\n".join(lines)
    lines.append("| candidate_id | Page | 検出語句 | 修正候補 |")
    lines.append("|---|---|---|---|")
    for c in matched:
        lines.append(f"| {c['candidate_id']} | {c['page_no']} | {c['original']} | {c['suggested']} |")
    return "\n".join(lines)


def _format_correction_candidates_section(candidates: list[dict[str, Any]]) -> str:
    lines = ["## 9. 修正候補", ""]
    if not candidates:
        lines.append("修正候補はありません。")
        return "\n".join(lines)
    lines.append("| candidate_id | Page | 項目 | 検出語句 | 修正候補 | 重要度 |")
    lines.append("|---|---|---|---|---|---|")
    for c in candidates:
        suggested = c["suggested"] or "(元画像確認)"
        lines.append(
            f"| {c['candidate_id']} | {c['page_no']} | {c['field']} | {c['original']} | "
            f"{suggested} | {_SEVERITY_LABELS[c['severity']]} |"
        )
    return "\n".join(lines)


def _format_image_check_section(candidates: list[dict[str, Any]]) -> str:
    matched = [c for c in candidates if c.get("requires_image_check")]
    lines = ["## 10. 元画像確認が必要そうな箇所", ""]
    if not matched:
        lines.append("元画像確認が必要そうな候補はありませんでした。")
        return "\n".join(lines)
    for c in matched:
        lines.append(f"- `{c['candidate_id']}` Page {c['page_no']} / {c['field']}: 「{c['original']}」（{c['reason']}）")
    return "\n".join(lines)


def _format_human_judgment_section() -> str:
    return (
        "## 11. 人間が最終判断すべき箇所\n\n"
        "- 修正候補（`suggested`）が空、または「元画像確認」となっている候補は、システム側では"
        "断定していません。元画像と照らし合わせて人間が判断してください。\n"
        "- 検出は「疑わしい候補」ベースであり、過検出（実際には問題ない箇所を候補として出す）も"
        "起こり得ます。文脈から見て問題がなければ、不採用としてください。\n"
        "- 意味不明な英字・記号列（`garbled_latin`）は、意図的な英語表記の可能性もあるため、"
        "文脈を見て判断してください。\n"
        "- 数字・日付・地名・固有名詞に関わる候補は、内容の正確性に直結するため特に慎重に判断して"
        "ください。"
    )


def _format_candidates_json_usage_section(candidates_output: str) -> str:
    return (
        "## 12. 補正候補JSONの使い方\n\n"
        f"`{candidates_output}`は、システムが検出した補正候補の構造化データです。\n\n"
        "- 今回はこのJSONを使った自動反映は行いません。\n"
        "- 人間が各候補を確認し、採用・不採用・元画像確認のいずれかを判断してください。\n"
        "- 候補1件ごとに`page_no`/`page_index`/`field`/`original`/`suggested`/`severity`/`reason`/"
        "`status`等を持っています。\n"
        "- `status`の初期値は`proposed`です。将来的に`approved`/`rejected`/`needs_image_check`等へ"
        "拡張し、`apply-ocr-corrections`（未実装）のような機能で`editable/lesson_pages.json`へ"
        "反映できるようにする想定です。\n"
        "- 現段階では、このJSONは「将来の自動反映に備えた候補データ」として扱ってください。"
    )


def _format_correction_workflow_section() -> str:
    return (
        "## 13. 修正作業の進め方\n\n"
        "- このレポートは、システムがOCR崩れ候補と修正候補を検出するためのものです。自動修正は"
        "行いません。\n"
        "- 人間は、検出された候補を「採用」「不採用」「元画像確認」に振り分けてください。\n"
        "- 修正する場合は、現段階では`output/editable/lesson_pages.json`の`title`/`summary`/"
        "`body`/`notes`/`layout_instruction`を人間が確認して反映してください。\n"
        "- `source_page_no`/`source_image`/`assets`は通常編集しないでください。\n"
        "- 将来的には、`ocr_correction_candidates.json`をもとに、採用済み候補をシステムが反映"
        "できるようにする想定です（今回は未実装）。\n"
        "- OCR補正を先に行うと、`llm-handoff`実行後のLLMの回答が教材改善に集中しやすくなります。"
        "先にOCR補正を行わないと、LLM回答が誤字修正の指摘中心になりやすい点に注意してください。"
    )


def _format_pre_llm_handoff_checklist_section() -> str:
    return (
        "## 14. llm-handoffへ進む前のチェックリスト\n\n"
        "- [ ] 高重要度の候補をすべて確認した\n"
        "- [ ] よくあるOCR誤認識候補（8節）を確認した\n"
        "- [ ] 元画像確認が必要そうな箇所（10節）を確認した\n"
        "- [ ] 明らかな誤字は`editable/lesson_pages.json`に反映した（または反映不要と判断した）\n"
        "- [ ] `ocr_correction_candidates.json`の内容を一通り確認した\n"
        "- [ ] OCR補正と文章改善（`llm-handoff`側の作業）を混同していない"
    )


def render_ocr_check_report_markdown(
    document: LessonDocument, candidates_data: dict[str, Any], candidates_output: str = "output/ocr_correction_candidates.json"
) -> str:
    """OCR品質チェックレポート（`ocr_check_report.md`）を生成する。

    `candidates_data`は`build_ocr_correction_candidates()`が返す構造化データ。
    """
    title = document.metadata.project_title or "教材ブラッシュアップ設計書"
    candidates = candidates_data.get("candidates", [])
    sections = [
        f"# {title}：OCR品質チェックレポート",
        _format_purpose_section(),
        _format_usage_section(),
        _format_overall_summary_section(document, candidates, candidates_output),
        _format_detection_summary_section(candidates),
        _format_severity_section(candidates),
        _format_flagged_pages_section(document, candidates),
        _format_pages_detail_section(document, candidates),
        _format_common_misreads_section(candidates),
        _format_correction_candidates_section(candidates),
        _format_image_check_section(candidates),
        _format_human_judgment_section(),
        _format_candidates_json_usage_section(candidates_output),
        _format_correction_workflow_section(),
        _format_pre_llm_handoff_checklist_section(),
    ]
    return "\n\n".join(sections) + "\n"
