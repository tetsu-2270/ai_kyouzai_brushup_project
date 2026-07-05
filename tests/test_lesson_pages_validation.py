import pytest

from src.lesson_pages import lesson_document_from_dict

_STRING_FIELDS = (
    "title",
    "body",
    "summary",
    "image_text",
    "layout_instruction",
    "canva_prompt",
    "video_scene",
    "source_image",
    "notes",
)


def _valid_page() -> dict:
    return {
        "page_no": 1,
        "title": "P1",
        "body": "状況説明者: こんにちは",
        "summary": "概要",
        "image_text": "画像内テキスト",
        "layout_instruction": "中央配置",
        "canva_prompt": "プロンプト",
        "video_scene": "シーン説明",
        "source_image": "a.png",
        "notes": "補足",
    }


@pytest.mark.parametrize("field_name", _STRING_FIELDS)
def test_lesson_page_field_must_be_string(field_name):
    page = _valid_page()
    page[field_name] = 123

    with pytest.raises(ValueError, match=f"{field_name} は文字列で指定してください"):
        lesson_document_from_dict({"pages": [page]})


def test_lesson_page_with_all_valid_strings_parses():
    document = lesson_document_from_dict({"pages": [_valid_page()]})
    assert document.pages[0].title == "P1"
