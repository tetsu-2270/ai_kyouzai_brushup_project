from src.edit_plan import render_edit_plan_template_markdown
from src.lesson_pages import LessonDocument, LessonMetadata, LessonPage


def _document(mode: str, page_no: int = 1, title: str = "P1") -> LessonDocument:
    return LessonDocument(
        metadata=LessonMetadata(mode=mode),
        pages=[LessonPage(
            page_no=page_no, title=title, body="本文", summary="概要", image_text="",
            layout_instruction="", canva_prompt="", video_scene="", source_image="", notes="",
        )],
    )


def test_render_edit_plan_template_includes_page_title():
    document = _document("proofread", title="はじめに")
    text = render_edit_plan_template_markdown(document)
    assert "はじめに" in text


def test_render_edit_plan_template_includes_adoption_fields():
    document = _document("proofread")
    text = render_edit_plan_template_markdown(document)
    assert "採用判断：" in text
    assert "[ ] 採用する / [ ] 採用しない / [ ] 一部採用" in text
    assert "採用する改善内容：" in text
    assert "判断メモ：" in text


def test_render_edit_plan_template_includes_editable_fields_section():
    document = _document("proofread")
    text = render_edit_plan_template_markdown(document)
    assert "編集してよい項目" in text
    assert "`title`" in text
    assert "`summary`" in text
    assert "`body`" in text
    assert "`layout_instruction`" in text
    assert "`notes`" in text


def test_render_edit_plan_template_includes_non_editable_fields_section():
    document = _document("proofread")
    text = render_edit_plan_template_markdown(document)
    assert "通常編集しない項目" in text
    assert "`page_no`" in text
    assert "`role`" in text
    assert "`source_page_no`" in text
    assert "`source_image`" in text
    assert "`assets`" in text


def test_render_edit_plan_template_includes_regenerate_checklist():
    document = _document("proofread")
    text = render_edit_plan_template_markdown(document)
    assert "出力確認チェックリスト" in text
    assert "regenerate" in text
    assert "PDF / DOCX / Markdown / PNG" in text
    assert "人間が最終確認した" in text


def test_render_edit_plan_template_multiple_pages():
    document = LessonDocument(
        metadata=LessonMetadata(mode="proofread"),
        pages=[
            LessonPage(page_no=1, title="ページ1", body="", summary="", image_text="",
                       layout_instruction="", canva_prompt="", video_scene="", source_image="", notes=""),
            LessonPage(page_no=2, title="ページ2", body="", summary="", image_text="",
                       layout_instruction="", canva_prompt="", video_scene="", source_image="", notes=""),
        ],
    )
    text = render_edit_plan_template_markdown(document)
    assert "### Page 1" in text
    assert "### Page 2" in text


def test_render_edit_plan_template_does_not_crash_on_missing_fields():
    document = LessonDocument(
        metadata=LessonMetadata(mode="proofread"),
        pages=[LessonPage(
            page_no=1, title="", body="", summary="", image_text="",
            layout_instruction="", canva_prompt="", video_scene="", source_image="", notes="",
        )],
    )
    text = render_edit_plan_template_markdown(document)
    assert "### Page 1" in text


# --- mode別の注意文 ------------------------------------------------------------


def test_proofread_mode_avoids_structural_changes():
    document = _document("proofread")
    text = render_edit_plan_template_markdown(document)
    assert "ページの追加・削除・順序変更は原則行いません" in text
    assert "proofreadでは大きな構成変更を避ける" in text


def test_restructure_mode_allows_structural_reorganization_within_limits():
    document = _document("restructure")
    text = render_edit_plan_template_markdown(document)
    assert "ページの統合・分割・順序整理の提案があれば、採用を検討してよいです" in text
    assert "元資料の意図・雰囲気を大きく変える提案は採用しないでください" in text
    assert "restructureでは構成整理は許容するが、元資料から大きく逸脱しない" in text


def test_generate_mode_emphasizes_purpose_audience_tone_and_source_material():
    document = _document("generate")
    text = render_edit_plan_template_markdown(document)
    assert "目的・対象読者・トーンから外れる提案は採用しないでください" in text
    assert "generateでは目的・対象読者・トーン・元情報を守る" in text


def test_unknown_mode_does_not_raise():
    document = _document("some_custom_mode")
    text = render_edit_plan_template_markdown(document)  # 例外が起きないことが主な確認事項
    assert "modeが不明なため" in text
    assert "### Page 1" in text


def test_restructure_mode_mentions_role_reordering_caveat():
    document = _document("restructure")
    text = render_edit_plan_template_markdown(document)
    assert "restructureの場合の注意" in text
    assert "role" in text


def test_render_edit_plan_template_includes_ocr_check_checklist():
    document = _document("proofread")
    text = render_edit_plan_template_markdown(document)
    assert "ocr-check" in text
    assert "ocr_correction_candidates.json" in text
