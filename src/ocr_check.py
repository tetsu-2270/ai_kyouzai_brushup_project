from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .lesson_pages import LessonDocument, LessonPage
from .ocr_patterns import (
    default_ocr_patterns,
    get_allowed_words,
    get_delete_candidates,
    get_high_confidence_replacements,
    get_inferred_candidates,
    get_source_check_required,
    patterns_summary,
)

# OCR結果の品質（誤認識・文字化け・不自然な表記）を、llm-handoffでLLMへ投入する前に
# システム側で検出・分類し、修正候補を人間が判断しやすい形で提示するモジュール。
# OCRエンジンの再実行・自動修正・editable/lesson_pages.jsonへの自動反映は行わない
# （将来のapply-ocr-corrections相当の機能に備え、補正候補は構造化JSONとして出力する）。
#
# 検出に使う辞書（誤認識辞書・削除候補・推定修正候補・元画像確認必須候補・許可語）は
# src/ocr_patterns.pyが管理する。組み込みデフォルトに加え、config/ocr_patterns.jsonが
# あればマージして使う（コードを変更せずに辞書を育てられるようにするための設計）。
# 詳細はdocs/13_ocr_quality_check_workflow.md参照。

# 全検出器を適用するフィールド（OCR本文として扱う）。
_FULL_SCAN_FIELDS = ("title", "summary", "body", "notes")
# layout_instructionはレイアウト指示・内部参照（assets/page等）が入ることがあり、OCR本文
# ではないため、辞書一致（common_ocr_misread）のみ適用する（garbled_latin等の対象外にする）。
_DICTIONARY_ONLY_SCAN_FIELDS = ("layout_instruction",)

_SEVERITY_LABELS = {"high": "高", "medium": "中", "low": "低"}


# --- 1. よくあるOCR誤認識辞書（検出のみ・自動置換はしない） ------------------------------


def detect_common_ocr_misreads(text: str, patterns: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """OCR誤認識辞書（`high_confidence_replacements`）に一致する語句を検出する（high confidence correction）。

    辞書は`src/ocr_patterns.py`が管理し、組み込みデフォルトに`config/ocr_patterns.json`を
    マージした`patterns`を受け取る（省略時は組み込みデフォルトのみ使用）。
    """
    if not text:
        return []
    patterns = patterns or default_ocr_patterns()
    candidates = []
    for wrong, (correct, severity) in get_high_confidence_replacements(patterns).items():
        if wrong in text:
            candidates.append({
                "original": wrong,
                "suggested": correct,
                "severity": severity,
                "reason": f"OCR誤認識辞書に一致します（{wrong} → {correct}）",
                "detection_type": "common_ocr_misread",
                "requires_image_check": False,
                "action": "replace",
                "confidence": severity,
                "status": "proposed",
            })
    return candidates


def detect_inferred_ocr_corrections(text: str, patterns: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """OCR崩れであることは明確だが、復元に推測が入る候補（inferred correction candidate）を検出する。

    辞書一致による検出のみで、断定的な自動反映は行わない前提。`status: needs_source_check`・
    `confidence: low`で提示し、`apply-ocr-corrections`では`approved`にならない限り反映されない。
    """
    if not text:
        return []
    patterns = patterns or default_ocr_patterns()
    candidates = []
    for wrong, info in get_inferred_candidates(patterns).items():
        if wrong in text:
            correct = info["suggested"]
            candidates.append({
                "original": wrong,
                "suggested": correct,
                "severity": "medium",
                "reason": f"OCR崩れの可能性が高く、推定修正候補です（{wrong} → {correct}）",
                "detection_type": "inferred_ocr_correction",
                "requires_image_check": True,
                "action": "replace",
                "confidence": info["confidence"],
                "status": info["status"],
                "human_note": info["human_note"],
            })
    return candidates


def detect_source_check_required_phrases(text: str, patterns: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """OCR崩れであることは明確だが、正しい復元が難しい候補（source check required）を検出する。

    `suggested`を断定せず、`status: needs_source_check`で元画像確認が必要な候補として提示する。
    """
    if not text:
        return []
    patterns = patterns or default_ocr_patterns()
    candidates = []
    for phrase in get_source_check_required(patterns):
        if phrase in text:
            candidates.append({
                "original": phrase,
                "suggested": None,
                "severity": "medium",
                "reason": "OCR崩れの可能性が高いですが、正しい復元が難しいため元画像の確認が必要です",
                "detection_type": "source_check_required",
                "requires_image_check": True,
                "action": "source_check",
                "confidence": "low",
                "status": "needs_source_check",
                "human_note": "元画像確認推奨。",
            })
    return candidates


# --- 2. 意味不明な英字・記号列（過検出しすぎないための許可語リスト付き） --------------------

_LATIN_RUN_RE = re.compile(r"[A-Za-z]+(?:[ \t]+[A-Za-z]+)*")

_DELETE_CANDIDATE_REASON = "日本語教材本文として不自然な英字列であり、削除候補です"
_DELETE_CANDIDATE_HUMAN_NOTE = "OCRノイズの可能性が高いため、削除候補。元画像確認推奨。"


def _build_deletion_candidate(original: str, detection_type: str) -> dict[str, Any]:
    return {
        "original": original,
        "suggested": None,
        "severity": "medium",
        "reason": _DELETE_CANDIDATE_REASON,
        "detection_type": detection_type,
        "requires_image_check": True,
        "action": "delete",
        "confidence": "medium",
        "status": "needs_human_review",
        "human_note": _DELETE_CANDIDATE_HUMAN_NOTE,
    }


def detect_garbled_latin_sequences(text: str, patterns: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """日本語教材本文として不自然な英字の並びを「削除候補（deletion candidate）」として検出する。

    URL/SNS/Instagram/Canva/PDF/API等の意図的な英語表記を誤検出しないよう、`allowed_words`に
    一致する語句のみで構成される部分は対象外にする。1文字トークンは列挙記号等と区別できない
    ため対象外とし、2文字以上のトークンを持つ並びのみ検出する。`source_check_required`に
    該当する箇所は`detect_source_check_required_phrases`側の分類に譲り、ここでは扱わない
    （固有名詞・URLの可能性がある語句を過検出しすぎないよう、断定的な削除候補ではなく
    「削除候補（要人間確認）」として提示し、自動反映はしない）。

    上記の正規表現ベースの検出に加え、`delete_candidates`（config/ocr_patterns.json等で
    育てられる明示的な削除候補リスト）に一致する語句も検出する（正規表現側で既に検出済みの
    箇所は重複させない）。
    """
    if not text:
        return []
    patterns = patterns or default_ocr_patterns()
    allowed_words = get_allowed_words(patterns)
    source_check_phrases = get_source_check_required(patterns)

    candidates = []
    seen_originals: set[str] = set()
    for match in _LATIN_RUN_RE.finditer(text):
        run = match.group(0)
        tokens = [t for t in run.split() if len(t) >= 2]
        if not tokens:
            continue
        if all(t.lower() in allowed_words for t in tokens):
            continue
        if run in source_check_phrases:
            continue
        candidates.append(_build_deletion_candidate(run, "garbled_latin"))
        seen_originals.add(run)

    for phrase in get_delete_candidates(patterns):
        if phrase in seen_originals:
            continue
        if phrase.lower() in allowed_words:
            continue
        if phrase in text:
            candidates.append(_build_deletion_candidate(phrase, "ocr_noise_delete_candidate"))
            seen_originals.add(phrase)

    return candidates


# --- 3. 不自然な記号・番号崩れ -----------------------------------------------------------

_UNUSUAL_SYMBOL_PATTERNS = (
    re.compile(r"[(（][①-⑳]"),
    re.compile(r"[〈<][①-⑳]"),
    re.compile(r"[①-⑳]{2,}"),
    re.compile(r"\\{1,}"),
    re.compile(r"[|｜]{2,}"),
    re.compile(r"[!-/:-@\[-`{-~]{4,}"),
    # 半角括弧で始まり全角括弧で終わる（またはその逆）、崩れた括弧の組み合わせ
    re.compile(r"[\[(][^\]\)\[(【「『]{0,20}[】」』]"),
    re.compile(r"[【「『][^【「『\]\)]{0,20}[\])]"),
)


def detect_unusual_symbols(text: str, patterns: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """不自然な括弧の始まり・番号崩れ・バックスラッシュ装飾・記号の連続等を検出する。

    `patterns`は他の検出器との呼び出し規約を揃えるための引数で、この検出器では使用しない。
    """
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


# --- タイトル専用の検出（短い記号混じり・特殊記号の混入等） -------------------------------

_TITLE_STRAY_SYMBOL_RE = re.compile(r"[|｜°@]")


def detect_title_anomalies(title: str) -> list[dict[str, Any]]:
    """タイトル特有の崩れ（`|`/`°`/`@`等の不自然な記号混入）を検出する。

    英字列・辞書一致・括弧崩れは他の検出器（`detect_garbled_latin_sequences`/
    `detect_common_ocr_misreads`/`detect_unusual_symbols`）がtitleにも適用されるため、
    ここでは他の検出器がカバーしない記号混入のみを扱う。
    """
    if not title:
        return []
    candidates = []
    if _TITLE_STRAY_SYMBOL_RE.search(title):
        candidates.append({
            "original": title,
            "suggested": None,
            "severity": "medium",
            "reason": "タイトルに不自然な記号が含まれている可能性があります",
            "detection_type": "unusual_symbol",
            "requires_image_check": True,
        })
    return candidates


# --- 4. 文が途中で切れていそうな箇所 ------------------------------------------------------

_INCOMPLETE_ENDINGS = (
    "たら", "ので", "ため", "けれど", "けど", "が、", "と、", "は、", "も、", "し、", "て、",
)
_SENTENCE_END_CHARS = "。！？」』）.!?"


def detect_incomplete_sentences(text: str, patterns: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """文末が助詞・接続詞で終わっている等、文が途中で切れている可能性がある行を検出する。

    行単位ではなく、フィールド末尾（最後の非空行）だけを判定対象にする。次に続く行がある
    場合は「文が途中で切れている」のではなく単に改行を挟んで文が続いているだけのことが多い
    ため（例:「〜ので\nミュートを解除してください」）、誤検出を避けるためフィールドの
    最後の行のみを見る。過検出してもよい前提のため、それでも典型的な未完パターンに一致する
    ものは候補として出す。`patterns`は呼び出し規約を揃えるための引数で使用しない。
    """
    if not text:
        return []
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return []
    last_line = lines[-1]
    if last_line[-1] in _SENTENCE_END_CHARS:
        return []
    for ending in _INCOMPLETE_ENDINGS:
        if last_line.endswith(ending):
            return [{
                "original": last_line,
                "suggested": None,
                "severity": "high",
                "reason": "文が途中で切れている可能性があります",
                "detection_type": "incomplete_sentence",
                "requires_image_check": True,
            }]
    return []


# --- 5. 数字と日本語の間の不自然な空白（日本語として不自然な箇所の一種） ----------------------

_NUMBER_JAPANESE_SPACING_RE = re.compile(
    r"(?:(?<=[ぁ-んァ-ヶ一-龯])[ 　]+(?=[0-9])|(?<=[0-9])[ 　]+(?=[ぁ-んァ-ヶ一-龯]))"
)

# 「9ま1よう」のように、数字と短いかな・カタカナが2回以上タイトに交互する並び。
# 「3人」「5月」のような通常の数え方は1回の交互出現に留まるため誤検出しにくい。
_GARBLED_NUMBER_KANA_RE = re.compile(r"(?:[0-9]+[ぁ-んァ-ヶ]{1,3}){2,}[0-9]*")

# 「7 / 1」のような日付・分数風の表記。誤って断定的に修正しないよう元画像確認候補にする。
_DATE_LIKE_RE = re.compile(r"[0-9]{1,4}[ 　]*/[ 　]*[0-9]{1,4}")


def _matches_dictionary_entry(snippet: str, patterns: dict[str, Any]) -> bool:
    return any(key in snippet for key in get_high_confidence_replacements(patterns))


def detect_suspicious_tokens(text: str, patterns: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """数字と日本語が絡む不自然な表記を、ルールベースでできる範囲で検出する。

    - 数字とかな・カタカナがタイトに交互する並び（OCR崩れの可能性が高い）
    - 日付・分数のような数字/数字表記（誤修正を避けるため元画像確認候補にする）
    - 数字と日本語の間の単純な空白（軽微な表記ゆれ。辞書一致箇所とは重複させない）

    完全な自然言語判定は行わない（ルールベースでできる範囲にとどめる）。
    """
    if not text:
        return []
    patterns = patterns or default_ocr_patterns()
    candidates = []

    for match in _GARBLED_NUMBER_KANA_RE.finditer(text):
        span = match.group(0)
        if _matches_dictionary_entry(span, patterns):
            continue
        candidates.append({
            "original": span,
            "suggested": None,
            "severity": "medium",
            "reason": "数字と日本語が不自然に混在しており、OCR崩れの可能性があります",
            "detection_type": "spacing",
            "requires_image_check": True,
        })

    for match in _DATE_LIKE_RE.finditer(text):
        candidates.append({
            "original": match.group(0),
            "suggested": None,
            "severity": "medium",
            "reason": "日付や数値表記の可能性があり、誤修正を避けるため元画像で確認してください",
            "detection_type": "spacing",
            "requires_image_check": True,
        })

    for match in _NUMBER_JAPANESE_SPACING_RE.finditer(text):
        start = max(0, match.start() - 5)
        end = min(len(text), match.end() + 5)
        snippet = text[start:end].strip()
        if _matches_dictionary_entry(snippet, patterns):
            continue
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
    detect_inferred_ocr_corrections,
    detect_source_check_required_phrases,
    detect_garbled_latin_sequences,
    detect_unusual_symbols,
    detect_incomplete_sentences,
    detect_suspicious_tokens,
)


def analyze_page_ocr_quality(page: LessonPage, patterns: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """ページ1件分のOCR品質を検出する。

    `title`/`summary`/`body`/`notes`にはOCR本文として全検出器を適用する。`layout_instruction`は
    レイアウト指示・内部参照（`assets`/`page`等）が入ることがありOCR本文ではないため、
    辞書一致（`detect_common_ocr_misreads`）のみを適用する。`title`にはさらに、他の検出器が
    カバーしない記号混入を`detect_title_anomalies`で追加検出する。

    `patterns`（`src/ocr_patterns.py`の`load_ocr_patterns()`が返す辞書）を省略した場合は
    組み込みデフォルトのみを使用する。
    """
    patterns = patterns or default_ocr_patterns()
    candidates = []
    for field in _FULL_SCAN_FIELDS:
        text = getattr(page, field, "") or ""
        if not text:
            continue
        for detector in _DETECTORS:
            for raw in detector(text, patterns):
                raw = dict(raw)
                raw["field"] = field
                candidates.append(raw)
        if field == "title":
            for raw in detect_title_anomalies(text):
                raw = dict(raw)
                raw["field"] = field
                candidates.append(raw)

    for field in _DICTIONARY_ONLY_SCAN_FIELDS:
        text = getattr(page, field, "") or ""
        if not text:
            continue
        for raw in detect_common_ocr_misreads(text, patterns):
            raw = dict(raw)
            raw["field"] = field
            candidates.append(raw)
    return candidates


def build_correction_candidate(
    page: LessonPage, page_index: int, raw: dict[str, Any], candidate_id: str
) -> dict[str, Any]:
    """検出結果(raw)とページ情報から、`ocr_correction_candidates.json`の候補1件分を組み立てる。

    `action`/`confidence`/`status`/`human_note`は、検出器がrawで明示していればそれを使い、
    明示していない既存検出器（unusual_symbol/incomplete_sentence/spacing等）については
    後方互換のため以下の既定値にフォールバックする。
    - `action`: `suggested`があれば`replace`、なければ`source_check`
    - `confidence`: `severity`と同値
    - `status`: `proposed`
    - `human_note`: 空文字
    """
    suggested = raw.get("suggested")
    default_action = "replace" if suggested else "source_check"
    return {
        "candidate_id": candidate_id,
        "page_no": page.page_no,
        "page_index": page_index,
        "field": raw["field"],
        "original": raw["original"],
        "suggested": suggested,
        "action": raw.get("action", default_action),
        "severity": raw["severity"],
        "reason": raw["reason"],
        "detection_type": raw["detection_type"],
        "source_page_no": list(page.source_page_no) if page.source_page_no else [],
        "source_image": page.source_image or "",
        "confidence": raw.get("confidence", raw["severity"]),
        "requires_image_check": bool(raw.get("requires_image_check", False)),
        "status": raw.get("status", "proposed"),
        "human_note": raw.get("human_note", ""),
    }


def build_ocr_correction_candidates(
    document: LessonDocument,
    source_file: str = "",
    patterns: dict[str, Any] | None = None,
    patterns_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """教材全体のOCR補正候補データ（`ocr_correction_candidates.json`相当の構造）を組み立てる。

    今回は自動反映を行わない。将来的に`status`を`approved`等に変更したうえで、
    `apply-ocr-corrections`のような機能で`editable/lesson_pages.json`へ反映できるように
    するための構造化データとして出力する。

    `patterns`（`ocr_patterns.load_ocr_patterns()`の戻り値）を省略した場合は組み込み
    デフォルトのみを使用する。`patterns_meta`は`summary.patterns`に出す読み込み情報
    （`external_path`/`load_status`）。
    """
    patterns = patterns or default_ocr_patterns()
    patterns_meta = patterns_meta or {
        "external_path": "config/ocr_patterns.json",
        "load_status": "default_only",
    }

    candidates: list[dict[str, Any]] = []
    counts = {"high": 0, "medium": 0, "low": 0}
    for page_index, page in enumerate(document.pages):
        for raw in analyze_page_ocr_quality(page, patterns):
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
        "patterns": {
            "external_path": patterns_meta.get("external_path"),
            "load_status": patterns_meta.get("load_status"),
            **patterns_summary(patterns),
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


def _pages_requiring_image_check(candidates: list[dict[str, Any]]) -> set[int]:
    """元画像確認が必要そうなページ番号の集合を返す。

    layout_instruction由来の候補（辞書一致のみ・requires_image_check=False）は対象にならない
    が、将来の検出器追加に備えて明示的にfieldでも除外しておく。
    """
    return {
        c["page_no"]
        for c in candidates
        if c.get("requires_image_check") and c["field"] != "layout_instruction"
    }


def _format_overall_summary_section(document: LessonDocument, candidates: list[dict[str, Any]], candidates_output: str) -> str:
    pages_with_candidates = {c["page_no"] for c in candidates}
    pages_requiring_image_check = _pages_requiring_image_check(candidates)
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
        "inferred_ocr_correction": "推定修正候補",
        "source_check_required": "元画像確認が必須の候補",
        "garbled_latin": "意味不明な英字・記号列（削除候補）",
        "ocr_noise_delete_candidate": "外部辞書由来の削除候補",
        "unusual_symbol": "不自然な記号・番号崩れ",
        "incomplete_sentence": "未完の可能性がある文",
        "spacing": "数字と日本語の不自然な空白",
    }
    lines = ["## 4. システム検出結果サマリー", ""]
    if not candidates:
        lines.append("検出された候補はありませんでした。")
    else:
        for detection_type, count in sorted(by_type.items(), key=lambda kv: -kv[1]):
            label = type_labels.get(detection_type, detection_type)
            lines.append(f"- {label}（`{detection_type}`）: {count}件")
    lines.append("")
    lines.append(
        "`layout_instruction`はレイアウト指示・内部参照（`assets`/`page`等）が含まれるため、"
        "OCR崩れ候補の主対象からは除外し、辞書一致（8節）のみ確認しています。"
        "まずは高重要度の候補（5節）から確認することをおすすめします。"
    )
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

    high_confidence = [c for c in candidates if c["detection_type"] == "common_ocr_misread" and c["status"] == "proposed"]
    deletion = [c for c in candidates if c.get("action") == "delete"]
    inferred = [c for c in candidates if c["detection_type"] == "inferred_ocr_correction"]
    source_check = [c for c in candidates if c["detection_type"] == "source_check_required"]

    lines.append("### 分類別の件数")
    lines.append("")
    lines.append(f"- high confidence correction（`common_ocr_misread`・status: proposed）: {len(high_confidence)}件")
    lines.append(f"- deletion candidate（`action: delete`）: {len(deletion)}件")
    lines.append(f"- inferred correction candidate（`inferred_ocr_correction`）: {len(inferred)}件")
    lines.append(f"- source check required（`source_check_required`）: {len(source_check)}件")
    lines.append("")
    lines.append(
        "削除候補・推定修正候補・元画像確認が必須の候補は、いずれも`status`が`approved`に"
        "ならない限り`apply-ocr-corrections`で反映されません。特に削除候補（`action: delete`）は、"
        "`approved`にしても今回のバージョンでは自動反映されません（詳細は"
        "`docs/14_apply_ocr_corrections_workflow.md`参照）。"
    )
    lines.append("")
    lines.append("### 候補一覧")
    lines.append("")
    lines.append("| candidate_id | Page | field | original | suggested | action | status | confidence | reason | human_note |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for c in candidates:
        suggested = c["suggested"] or "(未設定)"
        human_note = c.get("human_note") or ""
        lines.append(
            f"| {c['candidate_id']} | {c['page_no']} | {c['field']} | {c['original']} | "
            f"{suggested} | {c['action']} | {c['status']} | {c['confidence']} | {c['reason']} | {human_note} |"
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
        "- 削除候補（`action: delete`）は、本文からノイズとして削除した方が自然だとシステムが"
        "判断した候補です。ただし固有名詞・URLの可能性もゼロではないため、削除前に文脈を確認して"
        "ください。\n"
        "- 推定修正候補（`inferred_ocr_correction`）は、`suggested`に修正案が入っていても"
        "断定はできません。元画像を確認したうえで採用可否を判断してください。\n"
        "- 元画像確認が必須の候補（`source_check_required`）は、正しい復元が難しいため`suggested`が"
        "空のままのことがあります。必ず元画像を確認してください。\n"
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
        "- 人間が各候補を確認し、`status`を`approved`/`rejected`/`needs_source_check`/"
        "`needs_human_review`のいずれかに変更してください。\n"
        "- 候補1件ごとに`page_no`/`page_index`/`field`/`original`/`suggested`/`action`"
        "（`replace`/`delete`/`source_check`）/`severity`/`confidence`/`reason`/`status`/"
        "`human_note`等を持っています。\n"
        "- `status`の初期値は、high confidence correctionは`proposed`、削除候補は"
        "`needs_human_review`、推定修正候補・元画像確認が必須の候補は`needs_source_check`です。\n"
        "- `apply-ocr-corrections`は`status: approved`の候補だけを反映します"
        "（`action: delete`は`approved`にしても今回は反映されません。詳細は"
        "`docs/14_apply_ocr_corrections_workflow.md`参照）。\n"
        "- 現段階では、このJSONは「将来の自動反映に備えた候補データ」として扱ってください。"
    )


def _format_correction_workflow_section() -> str:
    return (
        "## 13. 修正作業の進め方\n\n"
        "- このレポートは、システムがOCR崩れ候補と修正候補を検出するためのものです。自動修正は"
        "行いません。\n"
        "- 人間は、検出された候補の`status`を`approved`（採用）/`rejected`（不採用）/"
        "`needs_source_check`（元資料確認）/`needs_human_review`（内容確認）に振り分けてください。\n"
        "- `approved`にした候補は`apply-ocr-corrections`で`lesson_pages.json`へ反映できます"
        "（`action: delete`の候補は今回は反映対象外です）。\n"
        "- `source_page_no`/`source_image`/`assets`は通常編集しないでください。\n"
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


def _format_ocr_patterns_section(candidates_data: dict[str, Any]) -> str:
    info = candidates_data.get("patterns") or {}
    load_status = info.get("load_status", "default_only")
    lines = [
        "## 15. 使用したOCRパターン辞書",
        "",
        f"- 外部辞書: `{info.get('external_path', 'config/ocr_patterns.json')}`",
        f"- 読み込み結果: {load_status}",
        f"- high_confidence_replacements: {info.get('high_confidence_replacements', 0)}件",
        f"- delete_candidates: {info.get('delete_candidates', 0)}件",
        f"- inferred_candidates: {info.get('inferred_candidates', 0)}件",
        f"- source_check_required: {info.get('source_check_required', 0)}件",
        f"- allowed_words: {info.get('allowed_words', 0)}件",
        "",
    ]
    if load_status == "loaded":
        lines.append(
            "外部辞書が読み込まれ、組み込みデフォルトとマージされています。"
            "辞書の育て方は`docs/13_ocr_quality_check_workflow.md`を参照してください。"
        )
    else:
        lines.append(
            "外部辞書（`config/ocr_patterns.json`）が見つからなかったため、組み込みデフォルトの"
            "みを使用しています。"
        )
    return "\n".join(lines)


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
        _format_ocr_patterns_section(candidates_data),
    ]
    return "\n\n".join(sections) + "\n"
