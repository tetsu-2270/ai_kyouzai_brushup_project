from src.models import project_from_dict


def test_pages_are_sorted_by_page_no_regardless_of_input_order():
    project = project_from_dict({
        "pages": [
            {"page_no": 3, "source_image": "c.png", "title": "P3", "summary": ""},
            {"page_no": 1, "source_image": "a.png", "title": "P1", "summary": ""},
            {"page_no": 2, "source_image": "b.png", "title": "P2", "summary": ""},
        ],
    })
    assert [p.page_no for p in project.pages] == [1, 2, 3]
