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


def _document_with_metadata(mode: str, target_audience: str, page_no: int = 1) -> LessonDocument:
    return LessonDocument(
        metadata=LessonMetadata(mode=mode, target_audience=target_audience),
        pages=[LessonPage(
            page_no=page_no, title="P1", body="本文", summary="概要", image_text="",
            layout_instruction="", canva_prompt="", video_scene="", source_image="", notes="",
        )],
    )


# --- target_audienceの扱い（固定文言にしない） ---------------------------------------


def test_render_llm_handoff_markdown_shows_target_audience_value_when_specified():
    """target_audienceが実質指定されている場合、その値がそのまま生成Markdownに出ることを確認する。"""
    document = _document_with_metadata("proofread", "50〜60代の受講者")
    text = render_llm_handoff_markdown(document)
    assert "50〜60代の受講者" in text
    assert "対象読者「50〜60代の受講者」" in text


def test_render_llm_handoff_markdown_uses_arbitrary_target_audience_value():
    """target_audienceには特定の年代・属性に限らず、任意の値がそのまま反映されることを確認する
    （プログラムの根幹が特定ジャンル・属性に依存しないことの確認）。"""
    document = _document_with_metadata("proofread", "海外向けビジネス文書の読み手")
    text = render_llm_handoff_markdown(document)
    assert "海外向けビジネス文書の読み手" in text


def test_render_llm_handoff_markdown_does_not_hardcode_age_group_when_unspecified():
    """target_audienceが未指定（システム既定値のまま）の場合、「50〜60代」等の年代・属性を
    勝手に補完しないことを確認する。"""
    document = _document_with_metadata("proofread", "教材制作者")  # システム既定のプレースホルダ
    text = render_llm_handoff_markdown(document)
    assert "50〜60代" not in text
    assert "受講者" not in text
    assert "想定読者が明示されていないため" in text


def test_render_llm_handoff_markdown_does_not_hardcode_age_group_for_empty_target_audience():
    document = LessonDocument(
        metadata=LessonMetadata(mode="proofread", target_audience=""),
        pages=[LessonPage(
            page_no=1, title="P1", body="", summary="", image_text="",
            layout_instruction="", canva_prompt="", video_scene="", source_image="", notes="",
        )],
    )
    text = render_llm_handoff_markdown(document)
    assert "50〜60代" not in text


def test_readme_and_docs_do_not_hardcode_age_group():
    """READMEやdocsが、llm-handoffの一般仕様として特定年代（50〜60代等）に固定した説明を
    していないことを確認する（例示であればよいが、一般仕様としては書かない）。"""
    from pathlib import Path

    repo_root = Path(__file__).resolve().parent.parent
    readme_text = (repo_root / "README.md").read_text(encoding="utf-8")
    # READMEのllm-handoff節自体には年代の言及が無いことを確認する。
    llm_handoff_section = readme_text.split("### LLM手作業投入用ファイルを生成")[1].split("###")[0]
    assert "50〜60代" not in llm_handoff_section
    assert "60代" not in llm_handoff_section


# --- mode別の依頼文・作業ルール切り替え ------------------------------------------------


def test_proofread_mode_shows_constitution_as_strong_rule():
    document = _document_with_metadata("proofread", "教材制作者")
    text = render_llm_handoff_markdown(document)
    assert "憲法第1条" in text
    assert "ブラッシュアップであって、作り直しではない" in text
    assert "大きな構成変更" in text  # proofreadでは大きな構成変更を提案しない旨が入る


def test_restructure_mode_shows_constitution_but_allows_structural_reorganization():
    document = _document_with_metadata("restructure", "教材制作者")
    text = render_llm_handoff_markdown(document)
    assert "憲法第1条" in text
    assert "ブラッシュアップであって、作り直しではない" in text
    assert "構成整理は許容する" in text
    assert "統合・分割・順序整理" in text


def test_generate_mode_does_not_fix_constitution_as_top_rule():
    """generateモードでは「ブラッシュアップであって、作り直しではない」を最重要ルールとして
    固定表示しないことを確認する。"""
    document = _document_with_metadata("generate", "教材制作者")
    text = render_llm_handoff_markdown(document)
    assert "憲法第1条" not in text


def test_generate_mode_emphasizes_purpose_audience_tone_and_source_material():
    """generateモードでは目的・対象読者・トーン・元情報を守ることが重視されることを確認する。"""
    document = _document_with_metadata("generate", "教材制作者")
    text = render_llm_handoff_markdown(document)
    assert "目的・対象読者・トーンを守る" in text
    assert "元情報にない断定や根拠のない内容の追加は避ける" in text


def test_generate_mode_allows_additional_explanations():
    document = _document_with_metadata("generate", "教材制作者")
    text = render_llm_handoff_markdown(document)
    assert "説明補足" in text
    assert "ページ構成案の追加は許容する" in text


def test_unknown_mode_does_not_raise_and_uses_generic_review_wording():
    """mode不明でもエラーにならず、汎用的なレビュー扱いの文言になることを確認する。"""
    document = _document_with_metadata("some_custom_mode", "教材制作者")
    text = render_llm_handoff_markdown(document)  # 例外が起きないことそのものが主な確認事項
    assert "modeが不明なため" in text
    assert "過度な作り替えは避ける" in text
    # proofread専用・generate専用の強い固定文言は出さない。
    assert "憲法第1条" not in text


def test_unknown_mode_still_includes_page_data():
    document = _document_with_metadata("", "教材制作者", page_no=5)
    text = render_llm_handoff_markdown(document)
    assert "### Page 5" in text
