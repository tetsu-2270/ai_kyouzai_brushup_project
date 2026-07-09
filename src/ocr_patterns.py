from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# OCR崩れ検出・修正候補生成に使う辞書（誤認識辞書・削除候補・推定修正候補・元画像確認必須候補・
# 許可語）を外部JSON（既定: config/ocr_patterns.json）から読み込み、組み込みデフォルトと安全に
# マージするモジュール。外部ファイルが無くても組み込みデフォルトでocr-checkは従来通り動く。
# 実データから見つかった新しいOCR崩れパターンを、コードを触らずに育てられるようにするための
# 仕組み（詳細はdocs/13_ocr_quality_check_workflow.md参照）。

DEFAULT_OCR_PATTERNS_PATH = "config/ocr_patterns.json"

_PATTERN_KEYS = (
    "high_confidence_replacements",
    "delete_candidates",
    "inferred_candidates",
    "source_check_required",
    "allowed_words",
)

# --- 組み込みデフォルト（config/ocr_patterns.jsonが無くてもこれで動く） -----------------------

_DEFAULT_HIGH_CONFIDENCE_REPLACEMENTS: dict[str, Any] = {
    "一買": "一貫",
    "アウトブット": "アウトプット",
    "右労": "苦労",
    "革細": "些細",
    "実貴": "実践",
    "共通説識": "共通認識",
    "人帳面": "几帳面",
    "叱嘘激励": "叱咤激励",
    "全1 1問": "全11問",
    "全1 1 問": "全11問",
    "有崩す": "崩す",
    "生んな経験": "そんな経験",
    "どいう": "という",
    "ベネフィット計理想の未来": "ベネフィット＝理想の未来",
    # 「1 つ」→「1つ」は内容を大きく損なわない軽微な誤認識のため、重要度を下げる
    # （オブジェクト形式で個別にseverityを指定できる）。
    "1 つ": {"suggested": "1つ", "severity": "low"},
}

_DEFAULT_DELETE_CANDIDATES: list[str] = ["ae", "BQ", "Ps", "RSS"]

_DEFAULT_INFERRED_CANDIDATES: dict[str, dict[str, str]] = {
    "時 9ま1よう": {
        "suggested": "決めましょう",
        "confidence": "low",
        "status": "needs_source_check",
        "human_note": "推定修正候補。元画像確認推奨。",
    },
    "六坂載祭上": {
        "suggested": "※無断転載禁止",
        "confidence": "low",
        "status": "needs_source_check",
        "human_note": "定型文のOCR崩れの可能性。元画像確認推奨。",
    },
}

_DEFAULT_SOURCE_CHECK_REQUIRED: list[str] = [
    "マチオロウーざん",
    "ERRh se rel Cee oe",
    "SAAT こコ全わった",
]

_DEFAULT_ALLOWED_WORDS: list[str] = [
    "url", "sns", "instagram", "canva", "gamma", "chatgpt", "claude",
    "pdf", "docx", "pptx", "png", "jpg", "jpeg", "webp", "csv", "json", "html", "md", "api",
    "ai", "llm", "ocr", "ok", "ng", "id", "web", "seo", "qr", "pc",
    "youtube", "line", "wifi", "wi-fi", "no", "cm", "kg", "app",
    # システム内部の参照語・レイアウト指示由来の語句（OCR崩れではないため許可語として扱う）
    "assets", "page", "image", "images", "source_image", "source_assets",
    "rendered", "output", "input", "editable", "layout", "instruction",
]


def default_ocr_patterns() -> dict[str, Any]:
    """組み込みデフォルトのOCRパターン辞書を返す。`config/ocr_patterns.json`が無くても、
    これだけで`ocr-check`は従来通り動く。
    """
    return {
        "version": "1.0",
        "high_confidence_replacements": dict(_DEFAULT_HIGH_CONFIDENCE_REPLACEMENTS),
        "delete_candidates": list(_DEFAULT_DELETE_CANDIDATES),
        "inferred_candidates": {key: dict(value) for key, value in _DEFAULT_INFERRED_CANDIDATES.items()},
        "source_check_required": list(_DEFAULT_SOURCE_CHECK_REQUIRED),
        "allowed_words": list(_DEFAULT_ALLOWED_WORDS),
    }


class OcrPatternConfigError(ValueError):
    """`config/ocr_patterns.json`が存在するがJSONとして不正な場合に送出する。"""


def normalize_ocr_patterns(patterns: dict[str, Any] | None) -> dict[str, Any]:
    """5分類すべてのキーが揃った辞書に整形する（一部のキーだけを指定した外部辞書も許容する）。"""
    patterns = patterns or {}
    return {
        "version": patterns.get("version", "1.0"),
        "high_confidence_replacements": dict(patterns.get("high_confidence_replacements") or {}),
        "delete_candidates": list(patterns.get("delete_candidates") or []),
        "inferred_candidates": dict(patterns.get("inferred_candidates") or {}),
        "source_check_required": list(patterns.get("source_check_required") or []),
        "allowed_words": list(patterns.get("allowed_words") or []),
    }


def _read_external_patterns(path: str | Path) -> dict[str, Any] | None:
    file_path = Path(path)
    if not file_path.exists():
        return None
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise OcrPatternConfigError(f"OCR pattern config is invalid: {path}") from exc
    if not isinstance(data, dict):
        raise OcrPatternConfigError(f"OCR pattern config is invalid: {path}")
    return normalize_ocr_patterns(data)


def _merge_lists(base: list[Any], extra: list[Any], *, case_insensitive: bool = False) -> list[Any]:
    seen: set[Any] = set()
    result: list[Any] = []
    for item in list(base) + list(extra):
        key = item.lower() if case_insensitive and isinstance(item, str) else item
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def merge_ocr_patterns(default_patterns: dict[str, Any], external_patterns: dict[str, Any] | None) -> dict[str, Any]:
    """組み込みデフォルトと外部辞書を安全にマージする。

    - `high_confidence_replacements`/`inferred_candidates`: dict merge。外部辞書が同じkeyを
      持つ場合は外部辞書を優先する。
    - `delete_candidates`/`source_check_required`: list merge・重複排除（大文字小文字は区別する。
      日本語の文字列比較のため）。
    - `allowed_words`: list merge・重複排除（大文字小文字を区別しない）。
    """
    if not external_patterns:
        return normalize_ocr_patterns(default_patterns)

    default_patterns = normalize_ocr_patterns(default_patterns)
    external_patterns = normalize_ocr_patterns(external_patterns)

    return {
        "version": external_patterns.get("version") or default_patterns.get("version", "1.0"),
        "high_confidence_replacements": {
            **default_patterns["high_confidence_replacements"],
            **external_patterns["high_confidence_replacements"],
        },
        "delete_candidates": _merge_lists(
            default_patterns["delete_candidates"], external_patterns["delete_candidates"]
        ),
        "inferred_candidates": {
            **default_patterns["inferred_candidates"],
            **external_patterns["inferred_candidates"],
        },
        "source_check_required": _merge_lists(
            default_patterns["source_check_required"], external_patterns["source_check_required"]
        ),
        "allowed_words": _merge_lists(
            default_patterns["allowed_words"], external_patterns["allowed_words"], case_insensitive=True
        ),
    }


def load_ocr_patterns(path: str | Path | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    """OCRパターン辞書を読み込む。`path`省略時は`config/ocr_patterns.json`を見に行く。

    戻り値は`(マージ済みpatterns, メタ情報)`。メタ情報には`external_path`（参照したパス）と
    `load_status`（`"loaded"`: 外部辞書を読み込みマージした / `"default_only"`: 外部辞書が
    存在せず組み込みデフォルトのみ使用）を含む。外部ファイルが存在するがJSONとして不正な場合は
    `OcrPatternConfigError`を送出する（分かりやすいメッセージ付き）。
    """
    resolved_path = str(path) if path is not None else DEFAULT_OCR_PATTERNS_PATH
    defaults = default_ocr_patterns()
    external = _read_external_patterns(resolved_path)
    if external is None:
        return defaults, {"external_path": resolved_path, "load_status": "default_only"}
    merged = merge_ocr_patterns(defaults, external)
    return merged, {"external_path": resolved_path, "load_status": "loaded"}


# --- アクセサ（正規化した形で各分類を取り出す） -----------------------------------------------


def get_high_confidence_replacements(patterns: dict[str, Any]) -> dict[str, tuple[str, str]]:
    """`{誤認識文字列: (修正候補, 重要度)}`の正規化済み辞書を返す。

    値が単純な文字列の場合は重要度`high`を補う。オブジェクト形式（`{"suggested": ..., "severity": ...}`）
    の場合はそれぞれの値を使う。
    """
    result: dict[str, tuple[str, str]] = {}
    for wrong, value in patterns.get("high_confidence_replacements", {}).items():
        if isinstance(value, dict):
            result[wrong] = (value.get("suggested", ""), value.get("severity", "high"))
        else:
            result[wrong] = (str(value), "high")
    return result


def get_delete_candidates(patterns: dict[str, Any]) -> list[str]:
    return list(patterns.get("delete_candidates", []))


def get_inferred_candidates(patterns: dict[str, Any]) -> dict[str, dict[str, str]]:
    """`{OCR崩れ文字列: {suggested, confidence, status, human_note}}`の正規化済み辞書を返す。"""
    result: dict[str, dict[str, str]] = {}
    for wrong, value in patterns.get("inferred_candidates", {}).items():
        if isinstance(value, dict):
            result[wrong] = {
                "suggested": value.get("suggested", ""),
                "confidence": value.get("confidence", "low"),
                "status": value.get("status", "needs_source_check"),
                "human_note": value.get("human_note", "推定修正候補。元画像確認推奨。"),
            }
        else:
            result[wrong] = {
                "suggested": str(value),
                "confidence": "low",
                "status": "needs_source_check",
                "human_note": "推定修正候補。元画像確認推奨。",
            }
    return result


def get_source_check_required(patterns: dict[str, Any]) -> list[str]:
    return list(patterns.get("source_check_required", []))


def get_allowed_words(patterns: dict[str, Any]) -> set[str]:
    return {word.lower() for word in patterns.get("allowed_words", [])}


def patterns_summary(patterns: dict[str, Any]) -> dict[str, int]:
    """レポート・candidates JSONに出す件数サマリーを返す。"""
    return {
        "high_confidence_replacements": len(patterns.get("high_confidence_replacements", {})),
        "delete_candidates": len(patterns.get("delete_candidates", [])),
        "inferred_candidates": len(patterns.get("inferred_candidates", {})),
        "source_check_required": len(patterns.get("source_check_required", [])),
        "allowed_words": len(patterns.get("allowed_words", [])),
    }
