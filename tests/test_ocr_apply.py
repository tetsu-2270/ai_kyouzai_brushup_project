from src.lesson_pages import LessonDocument, LessonMetadata, LessonPage
from src.ocr_apply import apply_ocr_corrections, render_ocr_apply_report_markdown


def _page(page_no=1, **kwargs):
    defaults = dict(
        page_no=page_no, title="", body="", summary="", image_text="",
        layout_instruction="", canva_prompt="", video_scene="", source_image="", notes="",
    )
    defaults.update(kwargs)
    return LessonPage(**defaults)


def _document(pages):
    return LessonDocument(metadata=LessonMetadata(mode="proofread"), pages=pages)


def _candidate(**kwargs):
    defaults = dict(
        candidate_id="ocr-0001", page_no=1, page_index=0, field="body",
        original="一買", suggested="一貫", severity="high", reason="test",
        detection_type="common_ocr_misread", source_page_no=[1], source_image="",
        confidence="high", requires_image_check=False, status="approved", human_note="",
    )
    defaults.update(kwargs)
    return defaults


def test_approved_candidate_is_applied():
    document = _document([_page(body="一買性のある文章です")])
    result = apply_ocr_corrections(document, {"candidates": [_candidate(status="approved")]})
    assert len(result["applied"]) == 1
    assert result["document"].pages[0].body == "一貫性のある文章です"


def test_proposed_candidate_is_not_applied():
    document = _document([_page(body="一買性のある文章です")])
    result = apply_ocr_corrections(document, {"candidates": [_candidate(status="proposed")]})
    assert result["applied"] == []
    assert result["skipped"][0]["skip_reason"] == "status_not_approved"
    assert result["document"].pages[0].body == "一買性のある文章です"


def test_rejected_candidate_is_not_applied():
    document = _document([_page(body="一買性のある文章です")])
    result = apply_ocr_corrections(document, {"candidates": [_candidate(status="rejected")]})
    assert result["applied"] == []
    assert result["skipped"][0]["skip_reason"] == "status_not_approved"


def test_needs_image_check_candidate_is_not_applied():
    document = _document([_page(body="一買性のある文章です")])
    result = apply_ocr_corrections(document, {"candidates": [_candidate(status="needs_image_check")]})
    assert result["applied"] == []
    assert result["skipped"][0]["skip_reason"] == "status_not_approved"


def test_null_suggested_candidate_is_not_applied():
    document = _document([_page(body="RSSが混入")])
    result = apply_ocr_corrections(
        document, {"candidates": [_candidate(field="body", original="RSS", suggested=None)]}
    )
    assert result["applied"] == []
    assert result["skipped"][0]["skip_reason"] == "suggested_missing"


def test_image_check_placeholder_suggested_is_not_applied():
    document = _document([_page(body="RSSが混入")])
    result = apply_ocr_corrections(
        document, {"candidates": [_candidate(field="body", original="RSS", suggested="(元画像確認)")]}
    )
    assert result["applied"] == []
    assert result["skipped"][0]["skip_reason"] == "suggested_requires_image_check"


def test_original_not_found_candidate_is_not_applied():
    document = _document([_page(body="通常の文章です")])
    result = apply_ocr_corrections(document, {"candidates": [_candidate(original="存在しない語句")]})
    assert result["applied"] == []
    assert result["skipped"][0]["skip_reason"] == "original_not_found"


def test_invalid_field_candidate_is_not_applied():
    document = _document([_page(role="intro")])
    result = apply_ocr_corrections(
        document, {"candidates": [_candidate(field="role", original="intro", suggested="x")]}
    )
    assert result["applied"] == []
    assert result["skipped"][0]["skip_reason"] == "invalid_field"


def test_invalid_page_index_candidate_is_not_applied():
    document = _document([_page(body="一買性のある文章です")])
    result = apply_ocr_corrections(
        document, {"candidates": [_candidate(page_index=99, page_no=99)]}
    )
    assert result["applied"] == []
    assert result["skipped"][0]["skip_reason"] == "page_not_found"


def test_layout_instruction_is_not_auto_applied():
    document = _document([_page(layout_instruction="assets: page_001.png")])
    result = apply_ocr_corrections(
        document,
        {"candidates": [_candidate(field="layout_instruction", original="assets", suggested="x")]},
    )
    assert result["applied"] == []
    assert result["skipped"][0]["skip_reason"] == "layout_instruction_skipped"


def test_all_editable_fields_are_applicable():
    document = _document([_page(
        title="一買タイトル", summary="一買概要", body="一買本文", notes="一買メモ",
    )])
    candidates = [
        _candidate(candidate_id=f"ocr-{i:04d}", field=field, original="一買", suggested="一貫")
        for i, field in enumerate(("title", "summary", "body", "notes"))
    ]
    result = apply_ocr_corrections(document, {"candidates": candidates})
    assert len(result["applied"]) == 4
    page = result["document"].pages[0]
    assert page.title == "一貫タイトル"
    assert page.summary == "一貫概要"
    assert page.body == "一貫本文"
    assert page.notes == "一貫メモ"


def test_replace_count_is_recorded():
    document = _document([_page(body="一買、一買、一買")])
    result = apply_ocr_corrections(document, {"candidates": [_candidate(original="一買", suggested="一貫")]})
    assert result["applied"][0]["replace_count"] == 3
    assert result["document"].pages[0].body == "一貫、一貫、一貫"


def test_skip_reason_is_recorded():
    document = _document([_page(body="通常の文章です")])
    result = apply_ocr_corrections(document, {"candidates": [_candidate(original="存在しない")]})
    assert result["skipped"][0]["skip_reason"] == "original_not_found"


def test_does_not_mutate_original_document():
    document = _document([_page(body="一買性のある文章です")])
    apply_ocr_corrections(document, {"candidates": [_candidate()]})
    assert document.pages[0].body == "一買性のある文章です"


def test_page_count_and_order_unchanged():
    document = _document([_page(page_no=1, body="a"), _page(page_no=2, body="一買"), _page(page_no=3, body="c")])
    result = apply_ocr_corrections(
        document, {"candidates": [_candidate(page_no=2, page_index=1, original="一買")]}
    )
    fixed = result["document"]
    assert len(fixed.pages) == 3
    assert [p.page_no for p in fixed.pages] == [1, 2, 3]


def test_source_metadata_unchanged():
    document = _document([_page(
        body="一買性のある文章です", source_page_no=[5], source_image="page_005.png",
        source_assets=["asset_a.png"],
    )])
    result = apply_ocr_corrections(document, {"candidates": [_candidate()]})
    page = result["document"].pages[0]
    assert page.source_page_no == [5]
    assert page.source_image == "page_005.png"
    assert page.source_assets == ["asset_a.png"]
    assert result["document"].metadata.mode == document.metadata.mode


def test_does_not_crash_on_missing_candidate_fields():
    document = _document([_page(body="通常の文章です")])
    incomplete_candidate = {"candidate_id": "ocr-broken"}
    result = apply_ocr_corrections(document, {"candidates": [incomplete_candidate]})
    assert result["applied"] == []
    assert result["skipped"][0]["skip_reason"] in ("status_not_approved", "unknown_status")


def test_unknown_status_is_recorded_distinctly():
    document = _document([_page(body="一買性のある文章です")])
    result = apply_ocr_corrections(document, {"candidates": [_candidate(status="something_else")]})
    assert result["skipped"][0]["skip_reason"] == "unknown_status"


# --- Markdownレポート -------------------------------------------------------------------


def test_report_includes_applied_and_skipped_sections():
    document = _document([_page(body="一買性のある文章です")])
    candidates_data = {
        "candidates": [
            _candidate(candidate_id="ocr-0001", status="approved"),
            _candidate(candidate_id="ocr-0002", status="proposed", original="別の語句"),
        ]
    }
    result = apply_ocr_corrections(document, candidates_data)
    text = render_ocr_apply_report_markdown(
        result, candidates_data,
        input_path="in.json", candidates_path="cand.json",
        output_path="out.json", report_path="report.md",
    )
    assert "反映された候補一覧" in text
    assert "ocr-0001" in text
    assert "反映されなかった候補一覧" in text
    assert "ocr-0002" in text
    assert "status_not_approved" in text


def test_report_includes_replace_count():
    document = _document([_page(body="一買、一買")])
    candidates_data = {"candidates": [_candidate(original="一買", suggested="一貫")]}
    result = apply_ocr_corrections(document, candidates_data)
    text = render_ocr_apply_report_markdown(
        result, candidates_data,
        input_path="in.json", candidates_path="cand.json",
        output_path="out.json", report_path="report.md",
    )
    assert "| ocr-0001 | 1 | body | 一買 | 一貫 | 2 |" in text


def test_report_dry_run_note():
    document = _document([_page(body="一買性のある文章です")])
    candidates_data = {"candidates": [_candidate()]}
    result = apply_ocr_corrections(document, candidates_data)
    text = render_ocr_apply_report_markdown(
        result, candidates_data,
        input_path="in.json", candidates_path="cand.json",
        output_path="out.json", report_path="report.md", dry_run=True,
    )
    assert "dry-run" in text


# --- 削除候補・推定修正候補・元画像確認必須候補の反映制御 -----------------------------------


def test_needs_source_check_status_is_not_applied():
    document = _document([_page(body="六坂載祭上と書いてある")])
    candidates_data = {"candidates": [_candidate(status="needs_source_check", original="六坂載祭上", suggested="※無断転載禁止")]}
    result = apply_ocr_corrections(document, candidates_data)
    assert result["applied"] == []
    assert result["skipped"][0]["skip_reason"] == "status_not_approved"


def test_needs_human_review_status_is_not_applied():
    document = _document([_page(body="RSSが混入")])
    candidates_data = {"candidates": [_candidate(status="needs_human_review", field="body", original="RSS", suggested=None, action="delete")]}
    result = apply_ocr_corrections(document, candidates_data)
    assert result["applied"] == []
    assert result["skipped"][0]["skip_reason"] == "status_not_approved"


def test_delete_action_is_not_applied_even_when_approved():
    """action: deleteは、approvedであっても今回は自動反映しないことを確認する。"""
    document = _document([_page(body="RSSが混入")])
    candidates_data = {"candidates": [_candidate(status="approved", field="body", original="RSS", suggested=None, action="delete")]}
    result = apply_ocr_corrections(document, candidates_data)
    assert result["applied"] == []
    assert result["skipped"][0]["skip_reason"] == "delete_action_not_supported"
    assert document.pages[0].body == "RSSが混入"


def test_report_shows_delete_action_not_supported_reason():
    document = _document([_page(body="RSSが混入")])
    candidates_data = {"candidates": [_candidate(status="approved", field="body", original="RSS", suggested=None, action="delete")]}
    result = apply_ocr_corrections(document, candidates_data)
    text = render_ocr_apply_report_markdown(
        result, candidates_data,
        input_path="in.json", candidates_path="cand.json",
        output_path="out.json", report_path="report.md",
    )
    assert "delete_action_not_supported" in text


def test_existing_approved_replace_candidate_still_applies_as_before():
    """action未指定（既存構造）のapproved置換候補は、従来通り反映されることを確認する。"""
    document = _document([_page(body="一買性のある文章です")])
    candidates_data = {"candidates": [_candidate(status="approved", original="一買", suggested="一貫")]}
    result = apply_ocr_corrections(document, candidates_data)
    assert len(result["applied"]) == 1
    assert result["document"].pages[0].body == "一貫性のある文章です"
