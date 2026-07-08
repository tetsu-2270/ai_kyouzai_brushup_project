from src.lesson_pages import LessonDocument, LessonMetadata, LessonPage, build_lesson_document
from src.llm_handoff import render_llm_handoff_markdown
from src.models import project_from_dict


def _document(pages: list[dict]) -> LessonDocument:
    return build_lesson_document(project_from_dict({
        "project_title": "テスト教材",
        "target_reader": "テスター",
        "pages": pages,
    }))


def test_render_llm_handoff_markdown_includes_page_title():
    document = _document([{"page_no": 1, "title": "はじめに", "summary": "概要です", "lines": []}])
    text = render_llm_handoff_markdown(document)
    assert "はじめに" in text


def test_render_llm_handoff_markdown_includes_summary_and_body():
    document = _document([{
        "page_no": 1, "title": "P1", "summary": "これは概要です",
        "lines": [{"speaker": "講師", "text": "これは本文の台詞です"}],
    }])
    text = render_llm_handoff_markdown(document)
    assert "これは概要です" in text
    assert "これは本文の台詞です" in text


def test_render_llm_handoff_markdown_includes_constitution_phrase():
    document = _document([{"page_no": 1, "title": "P1", "summary": "", "lines": []}])
    text = render_llm_handoff_markdown(document)
    assert "ブラッシュアップであって、作り直しではない" in text


def test_render_llm_handoff_markdown_includes_multiple_pages():
    document = _document([
        {"page_no": 1, "title": "ページ1", "summary": "", "lines": []},
        {"page_no": 2, "title": "ページ2", "summary": "", "lines": []},
        {"page_no": 3, "title": "ページ3", "summary": "", "lines": []},
    ])
    text = render_llm_handoff_markdown(document)
    assert "ページ1" in text
    assert "ページ2" in text
    assert "ページ3" in text
    assert "### Page 1" in text
    assert "### Page 2" in text
    assert "### Page 3" in text


def test_render_llm_handoff_markdown_includes_source_page_no_when_present():
    """proofread由来の実データではsource_page_noが常に[page_no]で埋まる（build_lesson_document参照）。
    ここでは複数ページ由来（restructureのmerge等）を想定し、LessonPageを直接組み立てて確認する。
    """
    document = LessonDocument(
        metadata=LessonMetadata(),
        pages=[LessonPage(
            page_no=1, title="P1", body="", summary="", image_text="",
            layout_instruction="", canva_prompt="", video_scene="", source_image="", notes="",
            source_page_no=[3, 4],
        )],
    )
    text = render_llm_handoff_markdown(document)
    assert "source_page_no: 3, 4" in text


def test_render_llm_handoff_markdown_omits_source_page_no_when_absent():
    document = LessonDocument(
        metadata=LessonMetadata(),
        pages=[LessonPage(
            page_no=1, title="P1", body="", summary="", image_text="",
            layout_instruction="", canva_prompt="", video_scene="", source_image="", notes="",
            source_page_no=[],
        )],
    )
    text = render_llm_handoff_markdown(document)
    # 「7. 注意事項」に一般的な説明として"source_page_no"という語自体は出るため、
    # ページデータ側のフィールド行（"- source_page_no:"）が出ないことを確認する。
    assert "- source_page_no:" not in text


def test_render_llm_handoff_markdown_does_not_crash_on_missing_fields():
    """title/summary/body/source_image等が空でも例外を起こさず出力できることを確認する。"""
    document = LessonDocument(
        metadata=LessonMetadata(),
        pages=[LessonPage(
            page_no=1, title="", body="", summary="", image_text="",
            layout_instruction="", canva_prompt="", video_scene="", source_image="", notes="",
        )],
    )
    text = render_llm_handoff_markdown(document)
    assert "### Page 1" in text
    assert "(未設定)" in text


def test_render_llm_handoff_markdown_page_range_filters_pages():
    document = _document([
        {"page_no": 1, "title": "ページ1", "summary": "", "lines": []},
        {"page_no": 2, "title": "ページ2", "summary": "", "lines": []},
        {"page_no": 3, "title": "ページ3", "summary": "", "lines": []},
    ])
    text = render_llm_handoff_markdown(document, page_start=2, page_end=2)
    assert "### Page 2" in text
    assert "### Page 1" not in text
    assert "### Page 3" not in text


def test_render_llm_handoff_markdown_includes_response_format_template():
    document = _document([{"page_no": 1, "title": "P1", "summary": "", "lines": []}])
    text = render_llm_handoff_markdown(document)
    assert "教材全体の構成チェック" in text
    assert "ページ別改善案" in text
    assert "editable/lesson_pages.json 編集時の注意" in text
