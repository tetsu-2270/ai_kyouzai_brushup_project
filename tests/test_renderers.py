from src.models import project_from_dict
from src.renderer import render_brushup
from src.canva_renderer import render_canva_design


def test_render_brushup_contains_title():
    project = project_from_dict({
        "project_title": "テスト教材",
        "target_reader": "テスター",
        "pages": [{"page_no": 1, "source_image": "a.png", "title": "P1", "summary": "概要"}],
    })
    assert "# テスト教材" in render_brushup(project)


def test_render_canva_contains_prompt():
    project = project_from_dict({
        "project_title": "テスト教材",
        "target_reader": "テスター",
        "pages": [{"page_no": 1, "source_image": "a.png", "title": "P1", "summary": "概要"}],
    })
    assert "Canva AI投入用プロンプト" in render_canva_design(project)
