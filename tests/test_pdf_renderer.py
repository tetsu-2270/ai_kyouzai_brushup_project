from reportlab.platypus import ListFlowable, Paragraph

from src.lesson_pages import build_lesson_document
from src.models import project_from_dict
from src.pdf_renderer import render_pdf, write_pdf


def _collect_paragraph_texts(flowables) -> list[str]:
    texts = []
    for item in flowables:
        if isinstance(item, Paragraph):
            texts.append(item.text)
        elif isinstance(item, ListFlowable):
            for li_indenter in item._content:
                texts.extend(_collect_paragraph_texts([li_indenter._flowable]))
    return texts


def _document():
    return build_lesson_document(project_from_dict({
        "project_title": "テスト教材",
        "target_reader": "テスター",
        "pages": [
            {
                "page_no": 1,
                "source_image": "a.png",
                "title": "P1",
                "summary": "概要文",
                "lines": [{"speaker": "まじょこ", "text": "こんにちは"}],
            }
        ],
    }))


def test_render_pdf_story_contains_expected_content():
    story = render_pdf(_document())
    texts = _collect_paragraph_texts(story)

    assert "テスト教材" in texts
    assert any("Page 1: P1" in t for t in texts)
    assert "概要文" in texts
    assert "まじょこ: こんにちは" in texts


def test_write_pdf_creates_valid_pdf_file(tmp_path):
    output_path = tmp_path / "nested" / "brushup.pdf"
    write_pdf(output_path, _document())

    assert output_path.exists()
    assert output_path.read_bytes()[:5] == b"%PDF-"


def test_render_pdf_story_does_not_expose_source_page_no_or_role():
    document = _document()
    document.pages[0].source_page_no = [1, 2]
    document.pages[0].role = "explanation"

    texts = _collect_paragraph_texts(render_pdf(document))
    joined_text = "\n".join(texts)

    assert "source_page_no" not in joined_text
    assert "explanation" not in joined_text
