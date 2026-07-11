import json

from src import apple_vision_ocr, ocr_comparison


def _fake_unavailable(**kwargs):
    return apple_vision_ocr.AppleVisionResult(available=False, warnings=["not available in test"])


def _fake_available(text, *, duration=0.2):
    def _runner(*args, **kwargs):
        return apple_vision_ocr.AppleVisionResult(available=True, language="ja-JP", text=text, duration_seconds=duration)
    return _runner


def _availability_unavailable(*args, **kwargs):
    return apple_vision_ocr.AppleVisionAvailability(available=False, reason="テスト環境では利用不可")


def _availability_available(*args, **kwargs):
    return apple_vision_ocr.AppleVisionAvailability(available=True, reason="利用可能", helper_path="/fake/path")


_PAGES = [
    {"page_no": 1, "source_image": "assets/page_001.png", "lines": [{"text": "【タイトル】"}, {"text": "本文です"}]},
    {"page_no": 2, "source_image": "assets/page_002.png", "lines": [{"text": "【別ページ】"}, {"text": "内容"}]},
]


def _make_assets(tmp_path):
    from PIL import Image

    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    for name in ("page_001.png", "page_002.png"):
        Image.new("RGB", (40, 30), color=(200, 200, 200)).save(assets_dir / name)
    return assets_dir


# --- Apple Vision利用不可時のフォールバック挙動 -------------------------------------------------


def test_comparison_does_not_flag_all_pages_when_vision_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "check_apple_vision_availability", _availability_unavailable)
    assets_dir = _make_assets(tmp_path)

    summary = ocr_comparison.run_ocr_comparison_for_pages(
        _PAGES, assets_dir,
        tesseract_diagnostics=[
            {"page_no": 1, "score": 0.8, "quality": "ok", "duration_seconds": 1.0},
            {"page_no": 2, "score": 0.8, "quality": "ok", "duration_seconds": 1.0},
        ],
    )

    assert summary.vision_helper_available is False
    # Apple Visionが使えない場合、エンジン不一致を理由に全ページneeds_reviewにしない。
    assert summary.needs_review_pages == []
    assert summary.compared_pages == 0
    for page in summary.pages:
        assert page.vision_available is False
        assert page.needs_review is False


def test_comparison_still_uses_tesseract_own_quality_when_vision_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "check_apple_vision_availability", _availability_unavailable)
    assets_dir = _make_assets(tmp_path)

    summary = ocr_comparison.run_ocr_comparison_for_pages(
        _PAGES, assets_dir,
        tesseract_diagnostics=[
            {"page_no": 1, "score": 0.4, "quality": "needs_review", "duration_seconds": 1.0},
            {"page_no": 2, "score": 0.8, "quality": "ok", "duration_seconds": 1.0},
        ],
    )
    assert summary.needs_review_pages == [1]
    assert summary.tesseract_only_review_pages == [1]


# --- Apple Vision利用可能時の比較 ---------------------------------------------------------------


def test_comparison_flags_page_when_texts_diverge(tmp_path, monkeypatch):
    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "check_apple_vision_availability", _availability_available)
    monkeypatch.setattr(
        ocr_comparison.apple_vision_ocr, "run_apple_vision_ocr", _fake_available("まったく異なる内容のテキスト")
    )
    assets_dir = _make_assets(tmp_path)

    summary = ocr_comparison.run_ocr_comparison_for_pages(
        _PAGES, assets_dir,
        tesseract_diagnostics=[
            {"page_no": 1, "score": 0.8, "quality": "ok", "duration_seconds": 1.0},
            {"page_no": 2, "score": 0.8, "quality": "ok", "duration_seconds": 1.0},
        ],
    )
    assert summary.vision_helper_available is True
    assert summary.compared_pages == 2
    assert 1 in summary.needs_review_pages
    assert 1 in summary.vision_only_review_pages


def test_comparison_does_not_flag_page_when_texts_match(tmp_path, monkeypatch):
    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "check_apple_vision_availability", _availability_available)

    def _runner(image_path, **kwargs):
        # 画像ファイル名からページ内容を再現する簡易フェイク（page_001→タイトル、page_002→別ページ）。
        if "page_001" in str(image_path):
            return apple_vision_ocr.AppleVisionResult(available=True, text="【タイトル】\n本文です")
        return apple_vision_ocr.AppleVisionResult(available=True, text="【別ページ】\n内容")

    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "run_apple_vision_ocr", _runner)
    assets_dir = _make_assets(tmp_path)

    summary = ocr_comparison.run_ocr_comparison_for_pages(_PAGES, assets_dir)
    assert summary.needs_review_pages == []


# --- lesson_pages.jsonへの自動反映が無いこと -----------------------------------------------------


def test_comparison_never_touches_editable_lesson_pages(tmp_path, monkeypatch):
    """Apple Vision結果はいかなる場合もeditable/lesson_pages.json相当のデータへ書き込まれない
    （比較関数の戻り値・保存関数のいずれも、渡された`imported_pages`/lesson_pages構造を変更しない）。
    """
    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "check_apple_vision_availability", _availability_available)
    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "run_apple_vision_ocr", _fake_available("Vision側のテキスト"))
    assets_dir = _make_assets(tmp_path)

    pages_copy = json.loads(json.dumps(_PAGES))
    ocr_comparison.run_ocr_comparison_for_pages(pages_copy, assets_dir)

    # 入力（取り込み済みpages）自体が書き換えられていないこと。
    assert pages_copy == _PAGES


# --- 保存（output/ocr_comparison/） -------------------------------------------------------------


def test_write_comparison_outputs_creates_expected_file_structure(tmp_path, monkeypatch):
    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "check_apple_vision_availability", _availability_available)
    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "run_apple_vision_ocr", _fake_available("Vision側のテキスト"))
    assets_dir = _make_assets(tmp_path)

    summary = ocr_comparison.run_ocr_comparison_for_pages(_PAGES, assets_dir)
    output_dir = tmp_path / "output"
    paths = ocr_comparison.write_comparison_outputs(output_dir, summary)

    assert paths["summary_json"].exists()
    assert paths["summary_md"].exists()
    assert paths["review_html"].exists()
    assert (output_dir / "ocr_comparison" / "pages" / "page_001.json").exists()
    assert (output_dir / "ocr_comparison" / "pages" / "page_002.json").exists()

    summary_data = json.loads(paths["summary_json"].read_text(encoding="utf-8"))
    assert summary_data["total_pages"] == 2

    page_data = json.loads((output_dir / "ocr_comparison" / "pages" / "page_001.json").read_text(encoding="utf-8"))
    assert page_data["tesseract_text"] == "【タイトル】\n本文です"
    assert page_data["vision_text"] == "Vision側のテキスト"


def test_review_html_is_self_contained_and_references_local_assets(tmp_path, monkeypatch):
    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "check_apple_vision_availability", _availability_available)
    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "run_apple_vision_ocr", _fake_available("Vision側のテキスト"))
    assets_dir = _make_assets(tmp_path)

    summary = ocr_comparison.run_ocr_comparison_for_pages(_PAGES, assets_dir)
    html_text = ocr_comparison.render_comparison_review_html(summary)

    assert "http://" not in html_text
    assert "https://" not in html_text
    assert "<script src=" not in html_text
    assert "../assets/page_001.png" in html_text
    assert "Page 1" in html_text
    assert "Page 2" in html_text


def test_review_html_escapes_html_special_characters_in_ocr_text(tmp_path, monkeypatch):
    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "check_apple_vision_availability", _availability_available)
    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "run_apple_vision_ocr", _fake_available("<script>alert(1)</script>"))
    assets_dir = _make_assets(tmp_path)

    summary = ocr_comparison.run_ocr_comparison_for_pages(_PAGES, assets_dir)
    html_text = ocr_comparison.render_comparison_review_html(summary)

    assert "<script>alert(1)</script>" not in html_text
    assert "&lt;script&gt;" in html_text


def test_summary_markdown_notes_no_auto_adoption():
    from dataclasses import replace

    summary = ocr_comparison.ComparisonSummary(
        generated_at="2026-01-01T00:00:00+09:00", language="ja-JP", vision_helper_available=True,
        vision_unavailable_reason="", total_pages=0, compared_pages=0, needs_review_pages=[],
        tesseract_only_review_pages=[], vision_only_review_pages=[], both_engines_review_pages=[], pages=[],
    )
    markdown = ocr_comparison.render_comparison_summary_markdown(summary)
    assert "自動反映されません" in markdown
    assert "editable/lesson_pages.json" in markdown
