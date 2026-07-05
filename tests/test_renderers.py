from src.canva_renderer import render_canva_design
from src.lesson_pages import build_lesson_document
from src.models import project_from_dict
from src.renderer import render_brushup


def test_render_brushup_contains_title():
    document = build_lesson_document(project_from_dict({
        "project_title": "テスト教材",
        "target_reader": "テスター",
        "pages": [{"page_no": 1, "source_image": "a.png", "title": "P1", "summary": "概要"}],
    }))
    assert "# テスト教材" in render_brushup(document)


def test_render_canva_contains_prompt():
    document = build_lesson_document(project_from_dict({
        "project_title": "テスト教材",
        "target_reader": "テスター",
        "pages": [{"page_no": 1, "source_image": "a.png", "title": "P1", "summary": "概要"}],
    }))
    assert "Canva AI投入用プロンプト" in render_canva_design(document)


def test_render_shows_fallback_for_unset_fields():
    document = build_lesson_document(project_from_dict({
        "pages": [{"page_no": 1, "source_image": "a.png", "title": "", "summary": "", "lines": []}],
    }))
    brushup = render_brushup(document)
    canva = render_canva_design(document)

    assert "### 概要\n未設定" in brushup
    assert "### 本文\n未設定" in brushup
    assert "### 画像内テキスト\n未設定" in canva
    assert "### レイアウト指示\n未設定" in canva


# --- canva_design.md表示時のlayout_instructionクリーニング -----------------------


def _document_with_layout_instruction(main_visual: str):
    return build_lesson_document(project_from_dict({
        "project_title": "テスト教材",
        "target_reader": "テスター",
        "pages": [
            {
                "page_no": 1,
                "source_image": "a.png",
                "title": "P1",
                "summary": "概要",
                "lines": [{"speaker": "講師", "text": "本文"}],
                "canva": {"main_visual": main_visual},
            }
        ],
    }))


def test_canva_design_removes_heading_markup_from_layout_instruction():
    for value in ("# 見出し", "## 見出し", "### 見出し"):
        canva = render_canva_design(_document_with_layout_instruction(value))
        assert f"### レイアウト指示\n{value}" not in canva
        assert "### レイアウト指示\n見出し" in canva


def test_canva_design_removes_bullet_markup_from_layout_instruction():
    for value in ("- やさしい配色", "* やさしい配色"):
        canva = render_canva_design(_document_with_layout_instruction(value))
        assert f"### レイアウト指示\n{value}" not in canva
        assert "### レイアウト指示\nやさしい配色" in canva


def test_canva_design_keeps_hashtag_in_layout_instruction():
    document = _document_with_layout_instruction("#AI初心者向けデザイン")
    canva = render_canva_design(document)
    assert "#AI初心者向けデザイン" in canva


def test_canva_design_keeps_mid_text_symbols_in_layout_instruction():
    document = _document_with_layout_instruction("見本 file-name.md を参考に、文中の-はそのまま")
    canva = render_canva_design(document)
    assert "見本 file-name.md を参考に、文中の-はそのまま" in canva


def test_canva_design_cleaning_does_not_mutate_lesson_pages_layout_instruction():
    document = _document_with_layout_instruction("# 見出し")

    render_canva_design(document)

    assert document.pages[0].layout_instruction == "# 見出し"


def test_canva_design_cleaning_does_not_affect_canva_prompt_or_video_scene():
    document = _document_with_layout_instruction("# 見出し")

    render_canva_design(document)

    assert "レイアウト: # 見出し" in document.pages[0].canva_prompt
    assert "ビジュアル: # 見出し" in document.pages[0].video_scene


def test_canva_design_cleaning_does_not_affect_brushup_or_scenario():
    from src.scenario_renderer import build_scene_data

    document = _document_with_layout_instruction("# 見出し")

    brushup = render_brushup(document)
    render_canva_design(document)
    scene_data = build_scene_data(document)

    assert "# 見出し" not in brushup  # brushupはlayout_instructionを参照しないため、そもそも出現しない
    assert scene_data["scenes"][0]["visual_prompt"] == "# 見出し"


# --- brushup.md/canva_design.md表示時のsummaryクリーニング -----------------------


def _document_with_summary(summary: str, lines=None):
    return build_lesson_document(project_from_dict({
        "project_title": "テスト教材",
        "target_reader": "テスター",
        "pages": [
            {
                "page_no": 1,
                "source_image": "a.png",
                "title": "P1",
                "summary": summary,
                "lines": lines if lines is not None else [{"speaker": "講師", "text": "本文"}],
            }
        ],
    }))


def test_brushup_and_canva_design_remove_heading_markup_from_summary():
    for value in ("# 見出し", "## 見出し", "### 見出し"):
        document = _document_with_summary(value)
        brushup = render_brushup(document)
        canva = render_canva_design(document)

        assert f"### 概要\n{value}" not in brushup
        assert "### 概要\n見出し" in brushup
        assert f"### 概要\n{value}" not in canva
        assert "### 概要\n見出し" in canva


def test_brushup_and_canva_design_remove_bullet_markup_from_summary():
    for value in ("- 箇条書き", "* 箇条書き"):
        document = _document_with_summary(value)
        brushup = render_brushup(document)
        canva = render_canva_design(document)

        assert f"### 概要\n{value}" not in brushup
        assert "### 概要\n箇条書き" in brushup
        assert f"### 概要\n{value}" not in canva
        assert "### 概要\n箇条書き" in canva


def test_canva_design_image_text_fallback_removes_markup_when_body_is_empty():
    """bodyが空でimage_textがsummaryにフォールバックする場合も、
    canva_design.mdの「### 画像内テキスト」でMarkdown記法が混入しないこと。"""
    document = _document_with_summary("# 見出し", lines=[])

    canva = render_canva_design(document)

    assert "### 画像内テキスト\n# 見出し" not in canva
    assert "### 画像内テキスト\n見出し" in canva
    # lesson_pages.json側のimage_text自体は変更されない
    assert document.pages[0].image_text == "# 見出し"


def test_summary_cleaning_keeps_hashtag():
    document = _document_with_summary("#AI初心者向け教材")
    brushup = render_brushup(document)
    canva = render_canva_design(document)

    assert "#AI初心者向け教材" in brushup
    assert "#AI初心者向け教材" in canva


def test_summary_cleaning_keeps_mid_text_symbols_and_urls():
    value = "詳細は file-name.md や https://example.com/a-b を参照。文中の-はそのまま"
    document = _document_with_summary(value)
    brushup = render_brushup(document)
    canva = render_canva_design(document)

    assert value in brushup
    assert value in canva


def test_summary_cleaning_does_not_mutate_lesson_pages_summary():
    document = _document_with_summary("# 見出し")

    render_brushup(document)
    render_canva_design(document)

    assert document.pages[0].summary == "# 見出し"


def test_summary_cleaning_does_not_affect_non_markdown_outputs():
    from docx import Document as DocxDocument

    from src.docx_renderer import render_docx
    from src.pdf_renderer import render_pdf
    from src.scenario_renderer import build_scenario_data

    document = _document_with_summary("# 見出し")

    # canva_prompt/video_sceneは元のsummaryをそのまま埋め込む
    render_canva_design(document)
    assert "概要: # 見出し" in document.pages[0].canva_prompt

    # DOCXは生の"#"がそのまま段落テキストとして入る（Markdownとして解釈されないため対象外）
    docx_texts = [p.text for p in render_docx(document).paragraphs]
    assert "# 見出し" in docx_texts

    # PDFも同様に生のテキストとしてそのまま入る
    from reportlab.platypus import Paragraph
    pdf_texts = [f.text for f in render_pdf(document) if isinstance(f, Paragraph)]
    assert "# 見出し" in pdf_texts

    # scenario出力はsummaryを使わないため無関係（bodyのみ影響）
    scenario_data = build_scenario_data(document)
    assert all("# 見出し" not in scene["text"] for scene in scenario_data["scenes"])


def test_canva_design_shows_source_image_for_imported_page():
    document = build_lesson_document(project_from_dict({
        "project_title": "テスト教材",
        "target_reader": "テスター",
        "pages": [{"page_no": 1, "source_image": "assets/page_001.png", "title": "P1", "summary": "概要"}],
    }))
    canva = render_canva_design(document)
    assert "元画像: assets/page_001.png" in canva


def test_canva_design_shows_source_assets_when_present():
    document = build_lesson_document(project_from_dict({
        "project_title": "テスト教材",
        "target_reader": "テスター",
        "pages": [{
            "page_no": 1,
            "source_image": "assets/slide_001_1.png",
            "source_assets": ["assets/slide_001_2.png", "assets/slide_001_3.png"],
            "title": "P1",
            "summary": "概要",
        }],
    }))
    canva = render_canva_design(document)
    assert "参考画像: assets/slide_001_2.png, assets/slide_001_3.png" in canva


def test_canva_design_omits_source_image_line_when_not_set():
    document = build_lesson_document(project_from_dict({
        "project_title": "テスト教材",
        "target_reader": "テスター",
        "pages": [{"page_no": 1, "source_image": "", "title": "P1", "summary": "概要"}],
    }))
    canva = render_canva_design(document)
    assert "元画像:" not in canva
    assert "参考画像:" not in canva


def test_all_renderers_do_not_fail_when_source_image_and_source_assets_are_empty():
    """新規構築(generateモード)相当のsource_image/source_assets空ページで、
    全renderer(Markdown/DOCX/PDF/scenario/review-report)が例外を出さないことを確認する。"""
    from src.docx_renderer import render_docx
    from src.lesson_pages import render_review_report
    from src.pdf_renderer import render_pdf
    from src.scenario_renderer import build_scenario_data, build_scene_data, render_scenario_markdown, render_voicevox_text

    document = build_lesson_document(project_from_dict({
        "project_title": "新規構築テスト教材",
        "target_reader": "テスター",
        "pages": [{
            "page_no": 1,
            "source_image": "",
            "title": "P1",
            "summary": "概要",
            "lines": [{"speaker": "講師", "text": "本文"}],
        }],
    }))

    # 例外が出ないことそのものがテストの主眼（戻り値の型・非空であることだけ軽く確認する）。
    assert render_brushup(document)
    canva_text = render_canva_design(document)
    assert "元画像:" not in canva_text
    assert "参考画像:" not in canva_text
    assert render_docx(document) is not None
    assert render_pdf(document) is not None
    assert render_review_report(document)
    assert build_scenario_data(document) is not None
    assert render_scenario_markdown(document) is not None
    assert render_voicevox_text(document) is not None
    assert build_scene_data(document) is not None
