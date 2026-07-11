import json
import platform
import shutil
import subprocess

import pytest

from src import ocr_comparison

# review.htmlに埋め込む採用判定ロジック（resolvePageAdoption等）はDOM・localStorageに依存しない
# 純粋関数として分離してある（src/ocr_comparison.py の_REVIEW_JS_PURE）。この開発環境には
# Xcode本体・Node.jsが無いため、macOS標準搭載のJavaScriptCore（`osascript -l JavaScript`）で
# 実際にこのJSコードを実行して検証する。macOS以外・osascriptが無い環境ではスキップする。
pytestmark = pytest.mark.skipif(
    platform.system() != "Darwin" or shutil.which("osascript") is None,
    reason="osascript(-l JavaScript、JavaScriptCore)が無い環境ではJS側のテストを実行できない",
)


def _run_js(expression: str) -> str:
    script = ocr_comparison._REVIEW_JS_PURE + "\n" + expression
    completed = subprocess.run(
        ["osascript", "-l", "JavaScript"], input=script, capture_output=True, text=True, timeout=15
    )
    assert completed.returncode == 0, f"stderr: {completed.stderr}"
    return completed.stdout.strip()


def _resolve(state: dict) -> dict:
    expr = f"JSON.stringify(resolvePageAdoption({json.dumps(state, ensure_ascii=False)}))"
    return json.loads(_run_js(expr))


# --- resolvePageAdoption（採用優先順位） --------------------------------------------------------


def test_js_resolve_adoption_prefers_edited_when_final_text_present():
    result = _resolve({"finalText": "編集済み本文", "tesseractSelected": False, "appleVisionSelected": True})
    assert result["adoptedSource"] == "edited"
    assert result["adoptedText"] == "編集済み本文"
    assert result["error"] is None


def test_js_resolve_adoption_falls_back_to_tesseract_when_final_text_empty():
    result = _resolve(
        {"finalText": "", "tesseractSelected": True, "appleVisionSelected": False, "tesseractText": "T本文"}
    )
    assert result["adoptedSource"] == "tesseract"
    assert result["adoptedText"] == "T本文"


def test_js_resolve_adoption_falls_back_to_apple_vision_when_final_text_empty():
    result = _resolve({"finalText": "", "appleVisionSelected": True, "appleVisionText": "V本文"})
    assert result["adoptedSource"] == "apple_vision"
    assert result["adoptedText"] == "V本文"


def test_js_resolve_adoption_unresolved_when_nothing_selected():
    result = _resolve({"finalText": ""})
    assert result["adoptedSource"] == "unresolved"
    assert result["adoptedText"] == ""
    assert result["warning"] is None


def test_js_resolve_adoption_whitespace_only_final_text_is_treated_as_empty():
    result = _resolve({"finalText": "   \n  ", "tesseractSelected": True, "tesseractText": "T"})
    assert result["adoptedSource"] == "tesseract"


def test_js_resolve_adoption_both_selected_without_final_text_is_error():
    result = _resolve({"finalText": "", "tesseractSelected": True, "appleVisionSelected": True})
    assert result["adoptedSource"] == "error"
    assert result["error"] is not None


def test_js_resolve_adoption_both_selected_with_final_text_prefers_edited_and_warns():
    result = _resolve({"finalText": "編集済み", "tesseractSelected": True, "appleVisionSelected": True})
    assert result["adoptedSource"] == "edited"
    assert result["adoptedText"] == "編集済み"
    assert result["error"] is None
    assert result["warning"] is not None


def test_js_resolve_adoption_review_completed_but_unresolved_warns():
    result = _resolve({"finalText": "", "reviewCompleted": True})
    assert result["adoptedSource"] == "unresolved"
    assert result["warning"] is not None


def test_js_resolve_adoption_review_completed_with_resolved_source_has_no_warning():
    result = _resolve({"finalText": "", "tesseractSelected": True, "tesseractText": "T", "reviewCompleted": True})
    assert result["adoptedSource"] == "tesseract"
    assert result["warning"] is None


# --- simpleHash / buildMaterialId / buildStorageKey（保存キーの一意性） -----------------------------


def test_js_simple_hash_is_deterministic():
    a = _run_js('simpleHash("assets/page_001.jpeg")')
    b = _run_js('simpleHash("assets/page_001.jpeg")')
    assert a == b


def test_js_simple_hash_differs_for_different_input():
    a = _run_js('simpleHash("materialA")')
    b = _run_js('simpleHash("materialB")')
    assert a != b


def test_js_build_material_id_differs_for_different_page_sets():
    a = _run_js('buildMaterialId([{sourceImage:"assets/page_001.jpeg"}])')
    b = _run_js('buildMaterialId([{sourceImage:"assets/other_001.jpeg"}])')
    assert a != b


def test_js_build_material_id_same_for_same_page_set():
    a = _run_js('buildMaterialId([{sourceImage:"assets/page_001.jpeg"},{sourceImage:"assets/page_002.jpeg"}])')
    b = _run_js('buildMaterialId([{sourceImage:"assets/page_001.jpeg"},{sourceImage:"assets/page_002.jpeg"}])')
    assert a == b


def test_js_build_storage_key_includes_material_id_and_page_number():
    key = _run_js('buildStorageKey("abc123", 4)')
    assert "abc123" in key
    assert "4" in key


def test_js_build_storage_key_distinct_per_page():
    key1 = _run_js('buildStorageKey("abc123", 1)')
    key2 = _run_js('buildStorageKey("abc123", 2)')
    assert key1 != key2


def test_js_build_storage_key_distinct_per_material():
    key1 = _run_js('buildStorageKey("materialA", 1)')
    key2 = _run_js('buildStorageKey("materialB", 1)')
    assert key1 != key2
