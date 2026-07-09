import json

import pytest

from src.ocr_patterns import (
    OcrPatternConfigError,
    default_ocr_patterns,
    get_allowed_words,
    get_delete_candidates,
    get_high_confidence_replacements,
    get_inferred_candidates,
    get_source_check_required,
    load_ocr_patterns,
    merge_ocr_patterns,
    patterns_summary,
)


def test_default_ocr_patterns_has_all_sections():
    patterns = default_ocr_patterns()
    for key in (
        "high_confidence_replacements", "delete_candidates", "inferred_candidates",
        "source_check_required", "allowed_words",
    ):
        assert key in patterns


def test_load_ocr_patterns_without_external_file_uses_defaults(tmp_path):
    """config/ocr_patterns.jsonが無くても既存デフォルトで動くことを確認する。"""
    patterns, meta = load_ocr_patterns(tmp_path / "does_not_exist.json")
    assert meta["load_status"] == "default_only"
    assert patterns == default_ocr_patterns()


def test_load_ocr_patterns_reads_external_file(tmp_path):
    external_path = tmp_path / "patterns.json"
    external_path.write_text(json.dumps({"high_confidence_replacements": {"新誤字": "新正字"}}), encoding="utf-8")
    patterns, meta = load_ocr_patterns(external_path)
    assert meta["load_status"] == "loaded"
    assert str(external_path) == meta["external_path"]
    assert get_high_confidence_replacements(patterns)["新誤字"] == ("新正字", "high")


def test_external_high_confidence_replacement_overrides_default(tmp_path):
    """外部辞書が同じkeyを持つ場合に上書きできることを確認する。"""
    external_path = tmp_path / "patterns.json"
    external_path.write_text(json.dumps({"high_confidence_replacements": {"一買": "上書き結果"}}), encoding="utf-8")
    patterns, _ = load_ocr_patterns(external_path)
    assert get_high_confidence_replacements(patterns)["一買"][0] == "上書き結果"
    # 上書きされていない既存デフォルトは維持される
    assert get_high_confidence_replacements(patterns)["共通説識"][0] == "共通認識"


def test_external_delete_candidates_are_added(tmp_path):
    external_path = tmp_path / "patterns.json"
    external_path.write_text(json.dumps({"delete_candidates": ["ZZZ"]}), encoding="utf-8")
    patterns, _ = load_ocr_patterns(external_path)
    assert "ZZZ" in get_delete_candidates(patterns)
    assert "ae" in get_delete_candidates(patterns)  # 既存デフォルトも維持される


def test_external_inferred_candidates_are_added(tmp_path):
    external_path = tmp_path / "patterns.json"
    external_path.write_text(
        json.dumps({"inferred_candidates": {"新崩れ": {"suggested": "新推定", "confidence": "medium"}}}),
        encoding="utf-8",
    )
    patterns, _ = load_ocr_patterns(external_path)
    inferred = get_inferred_candidates(patterns)
    assert inferred["新崩れ"]["suggested"] == "新推定"
    assert inferred["新崩れ"]["confidence"] == "medium"
    assert "時 9ま1よう" in inferred  # 既存デフォルトも維持される


def test_external_source_check_required_are_added(tmp_path):
    external_path = tmp_path / "patterns.json"
    external_path.write_text(json.dumps({"source_check_required": ["新元画像確認語句"]}), encoding="utf-8")
    patterns, _ = load_ocr_patterns(external_path)
    required = get_source_check_required(patterns)
    assert "新元画像確認語句" in required
    assert "マチオロウーざん" in required


def test_external_allowed_words_are_added(tmp_path):
    external_path = tmp_path / "patterns.json"
    external_path.write_text(json.dumps({"allowed_words": ["MyBrand"]}), encoding="utf-8")
    patterns, _ = load_ocr_patterns(external_path)
    allowed = get_allowed_words(patterns)
    assert "mybrand" in allowed
    assert "api" in allowed  # 既存デフォルトも維持される


def test_allowed_words_merge_is_case_insensitive_deduped():
    default_patterns = default_ocr_patterns()
    merged = merge_ocr_patterns(default_patterns, {"allowed_words": ["API", "Instagram"]})
    # デフォルトに既に含まれる語（大文字小文字違い）は重複しない
    lowered = [w.lower() for w in merged["allowed_words"]]
    assert lowered.count("api") == 1
    assert lowered.count("instagram") == 1


def test_invalid_json_raises_clear_error(tmp_path):
    bad_path = tmp_path / "bad.json"
    bad_path.write_text("{ not valid json", encoding="utf-8")
    with pytest.raises(OcrPatternConfigError) as excinfo:
        load_ocr_patterns(bad_path)
    assert str(bad_path) in str(excinfo.value)


def test_patterns_summary_counts():
    summary = patterns_summary(default_ocr_patterns())
    assert summary["high_confidence_replacements"] > 0
    assert summary["delete_candidates"] > 0
    assert summary["inferred_candidates"] > 0
    assert summary["source_check_required"] > 0
    assert summary["allowed_words"] > 0
