from src.lesson_pages import LessonDocument, LessonMetadata, LessonPage
from src.ocr_check import (
    build_ocr_correction_candidates,
    detect_common_ocr_misreads,
    detect_garbled_latin_sequences,
    detect_incomplete_sentences,
    detect_suspicious_tokens,
    detect_unusual_symbols,
    render_ocr_check_report_markdown,
)


def _document(pages: list[LessonPage], mode: str = "proofread") -> LessonDocument:
    return LessonDocument(metadata=LessonMetadata(mode=mode), pages=pages)


def _page(page_no: int = 1, **kwargs) -> LessonPage:
    defaults = dict(
        page_no=page_no, title="", body="", summary="", image_text="",
        layout_instruction="", canva_prompt="", video_scene="", source_image="", notes="",
    )
    defaults.update(kwargs)
    return LessonPage(**defaults)


# --- 検出器の単体テスト ----------------------------------------------------------------


def test_detect_common_ocr_misreads_finds_known_dictionary_entries():
    candidates = detect_common_ocr_misreads("一買性を大事にする。アウトブットが重要。")
    detected = {c["original"] for c in candidates}
    assert "一買" in detected
    assert "アウトブット" in detected
    misread = next(c for c in candidates if c["original"] == "一買")
    assert misread["suggested"] == "一貫"
    assert misread["severity"] == "high"


def test_detect_garbled_latin_sequences_flags_noise():
    candidates = detect_garbled_latin_sequences("RSS ERRh se rel Cee oe がありました")
    assert len(candidates) >= 1
    assert candidates[0]["detection_type"] == "garbled_latin"


def test_detect_garbled_latin_sequences_does_not_flag_allowed_terms():
    text = "OK、AIとLLM、OCRの技術を使い、InstagramにPDFやDOCXをアップロードします。URLはSNSで共有します。"
    candidates = detect_garbled_latin_sequences(text)
    assert candidates == []


def test_detect_unusual_symbols_flags_broken_numbering():
    candidates = detect_unusual_symbols("(⑤番目の項目について説明します")
    assert any(c["detection_type"] == "unusual_symbol" for c in candidates)


def test_detect_incomplete_sentences_flags_dangling_ending():
    candidates = detect_incomplete_sentences("※もし何も思い浮かばなかったら")
    assert len(candidates) == 1
    assert candidates[0]["detection_type"] == "incomplete_sentence"


def test_detect_incomplete_sentences_does_not_flag_completed_sentence():
    candidates = detect_incomplete_sentences("これは完結した文章です。")
    assert candidates == []


def test_detect_suspicious_tokens_flags_number_japanese_spacing():
    candidates = detect_suspicious_tokens("全部で 11問あります")
    assert any(c["detection_type"] == "spacing" for c in candidates)


# --- analyze/build のテスト -------------------------------------------------------------


def test_build_ocr_correction_candidates_includes_required_fields():
    document = _document([_page(page_no=3, title="一買性のある教材", source_page_no=[5], source_image="p5.png")])
    data = build_ocr_correction_candidates(document, source_file="test.json")
    assert data["candidates"], "候補が生成されていること"
    candidate = data["candidates"][0]
    for key in ("candidate_id", "page_no", "page_index", "field", "original", "suggested", "severity", "reason", "status"):
        assert key in candidate
    assert candidate["page_no"] == 3
    assert candidate["status"] == "proposed"
    assert candidate["field"] == "title"


def test_build_ocr_correction_candidates_severity_counts():
    document = _document([_page(title="一買性のある教材")])
    data = build_ocr_correction_candidates(document)
    assert data["summary"]["total_candidates"] >= 1
    assert data["summary"]["high"] >= 1


def test_build_ocr_correction_candidates_does_not_crash_on_missing_fields():
    document = _document([_page(page_no=1)])  # 全フィールド空
    data = build_ocr_correction_candidates(document)
    assert data["summary"]["total_candidates"] == 0
    assert data["candidates"] == []


def test_build_ocr_correction_candidates_avoids_false_positives_for_allowed_terms():
    document = _document([_page(body="OK、AI、LLM、OCR、Instagram、PDF、DOCXを使います。")])
    data = build_ocr_correction_candidates(document)
    assert data["summary"]["total_candidates"] == 0


# --- Markdownレポートのテスト ------------------------------------------------------------


def test_render_ocr_check_report_includes_overall_summary():
    document = _document([_page(title="一買性のある教材")])
    data = build_ocr_correction_candidates(document)
    text = render_ocr_check_report_markdown(document, data)
    assert "全体サマリー" in text
    assert "ページ数: 1" in text


def test_render_ocr_check_report_includes_detection_summary():
    document = _document([_page(title="一買性のある教材")])
    data = build_ocr_correction_candidates(document)
    text = render_ocr_check_report_markdown(document, data)
    assert "システム検出結果サマリー" in text
    assert "よくあるOCR誤認識候補" in text


def test_render_ocr_check_report_includes_per_page_detail():
    document = _document([
        _page(page_no=1, title="ページ1"),
        _page(page_no=2, title="ページ2"),
    ])
    data = build_ocr_correction_candidates(document)
    text = render_ocr_check_report_markdown(document, data)
    assert "### Page 1: ページ1" in text
    assert "### Page 2: ページ2" in text


def test_render_ocr_check_report_includes_correction_candidates_table():
    document = _document([_page(title="一買性のある教材")])
    data = build_ocr_correction_candidates(document)
    text = render_ocr_check_report_markdown(document, data)
    assert "## 9. 修正候補" in text
    assert "一買" in text
    assert "一貫" in text


def test_render_ocr_check_report_includes_severity_labels():
    document = _document([_page(title="一買性のある教材")])
    data = build_ocr_correction_candidates(document)
    text = render_ocr_check_report_markdown(document, data)
    assert "重要度：高" in text


def test_render_ocr_check_report_does_not_crash_on_missing_fields():
    document = _document([_page(page_no=1)])
    data = build_ocr_correction_candidates(document)
    text = render_ocr_check_report_markdown(document, data)
    assert "### Page 1" in text
    assert "候補はありません" in text or "該当なし" in text


def test_render_ocr_check_report_mentions_candidates_json_path():
    document = _document([_page(title="P1")])
    data = build_ocr_correction_candidates(document)
    text = render_ocr_check_report_markdown(document, data, candidates_output="output/custom_candidates.json")
    assert "output/custom_candidates.json" in text
