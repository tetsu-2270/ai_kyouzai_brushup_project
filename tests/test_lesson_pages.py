import json
import re

from src.canva_renderer import render_canva_design
from src.lesson_pages import (
    build_lesson_document,
    lesson_document_from_dict,
    project_from_lesson_document,
    write_lesson_pages_json,
)
from src.models import DialogueLine, project_from_dict
from src.parser import load_lesson_document, load_project
from src.renderer import render_brushup

_PAGE_HEADING_RE = re.compile(r"^## Page (\d+): (.*)$", flags=re.MULTILINE)

_LESSON_PAGES_FIELDS = (
    "page_no", "title", "body", "summary", "image_text",
    "layout_instruction", "canva_prompt", "video_scene", "source_image", "notes",
)


def _document():
    project = project_from_dict({
        "project_title": "テスト教材",
        "target_reader": "テスター",
        "pages": [
            {
                "page_no": 1,
                "source_image": "a.png",
                "title": "P1",
                "summary": "概要1",
                "lines": [{"speaker": "まじょこ", "text": "こんにちは"}],
                "canva": {"main_visual": "中央配置", "notes": "余白広め"},
            },
            {
                "page_no": 2,
                "source_image": "b.png",
                "title": "P2",
                "summary": "",
                "lines": [],
            },
        ],
    })
    return build_lesson_document(project)


def _page_headings(markdown: str) -> list[tuple[int, str]]:
    return [(int(no), title) for no, title in _PAGE_HEADING_RE.findall(markdown)]


def test_write_lesson_pages_json_creates_file_with_required_fields(tmp_path):
    document = _document()
    output_path = tmp_path / "lesson_pages.json"

    write_lesson_pages_json(output_path, document)

    assert output_path.exists()
    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert len(data["pages"]) == 2
    for page in data["pages"]:
        for field_name in _LESSON_PAGES_FIELDS:
            assert field_name in page


def test_lesson_pages_count_matches_brushup_md_pages():
    document = _document()
    brushup_pages = _page_headings(render_brushup(document))
    assert len(brushup_pages) == len(document.pages)


def test_lesson_pages_count_matches_canva_design_pages():
    document = _document()
    canva_pages = _page_headings(render_canva_design(document))
    assert len(canva_pages) == len(document.pages)


def test_brushup_and_canva_design_page_numbers_match():
    document = _document()
    brushup_page_nos = [no for no, _ in _page_headings(render_brushup(document))]
    canva_page_nos = [no for no, _ in _page_headings(render_canva_design(document))]
    assert brushup_page_nos == canva_page_nos


def test_brushup_title_reflected_in_canva_design():
    document = _document()
    brushup_titles = dict(_page_headings(render_brushup(document)))
    canva_titles = dict(_page_headings(render_canva_design(document)))
    assert brushup_titles == canva_titles


def test_summary_or_image_text_never_both_empty():
    document = _document()
    for page in document.pages:
        assert page.summary or page.image_text


def test_load_lesson_document_reads_written_lesson_pages_json(tmp_path):
    document = _document()
    output_path = tmp_path / "lesson_pages.json"
    write_lesson_pages_json(output_path, document)

    reloaded = load_lesson_document(output_path)

    assert reloaded.project_title == document.project_title
    assert [p.page_no for p in reloaded.pages] == [p.page_no for p in document.pages]
    assert [p.title for p in reloaded.pages] == [p.title for p in document.pages]


def test_editing_body_regenerates_image_text_and_canva_prompt():
    data = {
        "pages": [
            {
                "page_no": 1,
                "title": "P1",
                "body": "まじょこ: 古い台詞",
                "summary": "概要",
                "image_text": "古いimage_text（手動で書き換えても無視される）",
                "layout_instruction": "中央配置",
                "canva_prompt": "古いcanva_prompt",
                "video_scene": "古いvideo_scene",
                "source_image": "a.png",
                "notes": "",
            }
        ],
    }
    document = lesson_document_from_dict(data)
    page = document.pages[0]

    assert page.image_text == "古い台詞"
    assert "古い台詞" in page.canva_prompt
    assert "古いimage_text" not in page.image_text


def test_project_from_lesson_document_converts_body_back_to_lines():
    document = _document()
    project = project_from_lesson_document(document)

    assert [p.page_no for p in project.pages] == [p.page_no for p in document.pages]
    assert project.pages[0].title == "P1"
    assert project.pages[0].lines == [DialogueLine(speaker="まじょこ", text="こんにちは")]
    assert project.pages[0].improvement_points == []
    assert project.pages[0].canva.main_visual == "中央配置"
    assert project.pages[0].canva.notes == "余白広め"


def test_load_project_accepts_lesson_pages_format(tmp_path):
    document = _document()
    lesson_pages_path = tmp_path / "lesson_pages.json"
    write_lesson_pages_json(lesson_pages_path, document)

    project = load_project(lesson_pages_path)

    assert [p.page_no for p in project.pages] == [p.page_no for p in document.pages]
    assert project.pages[0].lines == [DialogueLine(speaker="まじょこ", text="こんにちは")]
