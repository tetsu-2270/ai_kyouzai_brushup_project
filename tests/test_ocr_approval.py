from src.ocr_approval import approve_ocr_candidates, render_ocr_approval_report_markdown


def _candidate(**kwargs):
    defaults = dict(
        candidate_id="ocr-0001", page_no=1, page_index=0, field="body",
        original="一買", suggested="一貫", action="replace", severity="high",
        reason="test", detection_type="common_ocr_misread", source_page_no=[1], source_image="",
        confidence="high", requires_image_check=False, status="proposed", human_note="",
    )
    defaults.update(kwargs)
    return defaults


def _candidates_data(candidates):
    return {"version": 1, "source_file": "in.json", "candidates": candidates}


def test_high_severity_replace_high_confidence_proposed_is_approved():
    data = _candidates_data([_candidate()])
    result_data, result = approve_ocr_candidates(data)
    assert len(result["approved"]) == 1
    assert result_data["candidates"][0]["status"] == "approved"


def test_needs_source_check_is_not_approved():
    data = _candidates_data([_candidate(status="needs_source_check")])
    _, result = approve_ocr_candidates(data)
    assert result["approved"] == []
    assert result["not_approved"][0]["not_approved_reason"] == "status_not_approvable"


def test_needs_human_review_is_not_approved():
    data = _candidates_data([_candidate(status="needs_human_review")])
    _, result = approve_ocr_candidates(data)
    assert result["approved"] == []
    assert result["not_approved"][0]["not_approved_reason"] == "status_not_approvable"


def test_action_delete_is_not_approved():
    data = _candidates_data([_candidate(action="delete", status="needs_human_review", suggested=None)])
    _, result = approve_ocr_candidates(data)
    assert result["approved"] == []
    assert result["not_approved"][0]["not_approved_reason"] == "action_not_replaceable"


def test_action_delete_is_not_approved_even_if_criteria_requests_delete():
    """CLI引数でaction=deleteを指定しても、絶対に自動approvedにしないことを確認する。"""
    data = _candidates_data([_candidate(action="delete", status="needs_human_review", suggested=None)])
    _, result = approve_ocr_candidates(data, severity=None, action="delete", confidence=None)
    assert result["approved"] == []
    assert result["not_approved"][0]["not_approved_reason"] == "action_not_replaceable"


def test_action_source_check_is_not_approved():
    data = _candidates_data([_candidate(action="source_check", suggested=None)])
    _, result = approve_ocr_candidates(data)
    assert result["approved"] == []
    assert result["not_approved"][0]["not_approved_reason"] == "action_not_replaceable"


def test_missing_suggested_is_not_approved():
    data = _candidates_data([_candidate(suggested=None)])
    _, result = approve_ocr_candidates(data)
    assert result["approved"] == []
    assert result["not_approved"][0]["not_approved_reason"] == "suggested_missing"


def test_incomplete_sentence_is_not_approved():
    data = _candidates_data([_candidate(
        detection_type="incomplete_sentence", suggested=None, action="source_check",
    )])
    _, result = approve_ocr_candidates(data)
    assert result["approved"] == []
    assert result["not_approved"][0]["not_approved_reason"] in ("detection_type_excluded", "action_not_replaceable")


def test_inferred_ocr_correction_is_not_approved():
    data = _candidates_data([_candidate(
        detection_type="inferred_ocr_correction", status="needs_source_check", confidence="low",
    )])
    _, result = approve_ocr_candidates(data)
    assert result["approved"] == []
    assert result["not_approved"][0]["not_approved_reason"] in ("detection_type_excluded", "status_not_approvable")


def test_unusual_symbol_is_not_approved():
    data = _candidates_data([_candidate(
        detection_type="unusual_symbol", suggested=None, action="source_check",
    )])
    _, result = approve_ocr_candidates(data)
    assert result["approved"] == []
    assert result["not_approved"][0]["not_approved_reason"] in ("detection_type_excluded", "action_not_replaceable")


def test_garbled_latin_is_not_approved():
    data = _candidates_data([_candidate(
        detection_type="garbled_latin", suggested=None, action="delete", status="needs_human_review",
    )])
    _, result = approve_ocr_candidates(data)
    assert result["approved"] == []
    assert result["not_approved"][0]["not_approved_reason"] in ("detection_type_excluded", "action_not_replaceable")


def test_does_not_mutate_original_data():
    data = _candidates_data([_candidate()])
    approve_ocr_candidates(data)
    assert data["candidates"][0]["status"] == "proposed"


def test_summary_approval_includes_count_and_criteria():
    data = _candidates_data([_candidate(), _candidate(candidate_id="ocr-0002", status="needs_human_review", action="delete", suggested=None)])
    result_data, _ = approve_ocr_candidates(data, severity="high", action="replace", confidence="high")
    approval = result_data["summary"]["approval"]
    assert approval["approved_count"] == 1
    assert approval["criteria"] == {"severity": "high", "action": "replace", "confidence": "high", "detection_type": None}


def test_report_is_generated_with_expected_sections():
    data = _candidates_data([_candidate()])
    _, result = approve_ocr_candidates(data)
    text = render_ocr_approval_report_markdown(result, input_path="in.json", output_path="out.json")
    assert "サマリー" in text
    assert "approved化した候補" in text
    assert "approved化しなかった候補" in text
    assert "apply-ocr-correctionsとの関係" in text


def test_dry_run_report_notes_no_output_file_written():
    data = _candidates_data([_candidate()])
    _, result = approve_ocr_candidates(data)
    text = render_ocr_approval_report_markdown(result, input_path="in.json", output_path="out.json", dry_run=True)
    assert "dry-run" in text


def test_approved_candidates_json_can_be_applied_downstream():
    """approve後のJSONをapply-ocr-correctionsに渡すと、approvedのreplace候補のみ反映されることを確認する。"""
    from src.lesson_pages import LessonDocument, LessonMetadata, LessonPage
    from src.ocr_apply import apply_ocr_corrections

    document = LessonDocument(
        metadata=LessonMetadata(mode="proofread"),
        pages=[LessonPage(
            page_no=1, title="T", body="一買性のある文章とRSSが混入", summary="", image_text="",
            layout_instruction="", canva_prompt="", video_scene="", source_image="", notes="",
        )],
    )
    candidates_data = _candidates_data([
        _candidate(candidate_id="ocr-0001", original="一買", suggested="一貫"),
        _candidate(
            candidate_id="ocr-0002", original="RSS", suggested=None, action="delete",
            status="needs_human_review", detection_type="garbled_latin",
        ),
    ])
    approved_data, _ = approve_ocr_candidates(candidates_data)
    result = apply_ocr_corrections(document, approved_data)
    assert len(result["applied"]) == 1
    assert result["applied"][0]["original"] == "一買"
    assert result["document"].pages[0].body == "一貫性のある文章とRSSが混入"
