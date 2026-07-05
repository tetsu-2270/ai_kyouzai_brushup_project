import pytest

from src.models import project_from_dict


def base_page(**overrides):
    page = {"page_no": 1, "source_image": "a.png", "title": "P1", "summary": "概要"}
    page.update(overrides)
    return page


def test_missing_page_no_raises_clear_error():
    with pytest.raises(ValueError, match="page_no が指定されていません"):
        project_from_dict({"pages": [{"title": "P1"}]})


def test_non_integer_page_no_raises_clear_error():
    with pytest.raises(ValueError, match="page_no は整数で指定してください"):
        project_from_dict({"pages": [base_page(page_no="abc")]})


def test_duplicate_page_no_raises_clear_error():
    with pytest.raises(ValueError, match="page_no が重複しています"):
        project_from_dict({"pages": [base_page(page_no=1), base_page(page_no=1)]})


def test_pages_not_a_list_raises_clear_error():
    with pytest.raises(ValueError, match="pages はリスト形式で指定してください"):
        project_from_dict({"pages": {"page_no": 1}})


def test_invalid_line_keys_raise_clear_error():
    page = base_page(lines=[{"speaker": "まじょこ", "text": "こんにちは", "unknown": "x"}])
    with pytest.raises(ValueError, match="speaker と text のみ指定できます"):
        project_from_dict({"pages": [page]})


def test_invalid_canva_keys_raise_clear_error():
    page = base_page(canva={"layout_type": "縦長", "unknown": "x"})
    with pytest.raises(ValueError, match="layout_type/main_visual/notes のみ指定できます"):
        project_from_dict({"pages": [page]})


def test_improvement_points_not_a_list_raises_clear_error():
    page = base_page(improvement_points="文字量を減らす")
    with pytest.raises(ValueError, match="improvement_points はリスト形式で指定してください"):
        project_from_dict({"pages": [page]})


def test_lines_not_a_list_raises_clear_error():
    page = base_page(lines={"speaker": "まじょこ", "text": "こんにちは"})
    with pytest.raises(ValueError, match="lines はリスト形式で指定してください"):
        project_from_dict({"pages": [page]})


def test_line_speaker_not_a_string_raises_clear_error():
    page = base_page(lines=[{"speaker": 123, "text": "こんにちは"}])
    with pytest.raises(ValueError, match=r"lines\[0\]\.speaker は文字列で指定してください"):
        project_from_dict({"pages": [page]})


def test_line_text_not_a_string_raises_clear_error():
    page = base_page(lines=[{"speaker": "まじょこ", "text": 123}])
    with pytest.raises(ValueError, match=r"lines\[0\]\.text は文字列で指定してください"):
        project_from_dict({"pages": [page]})


def test_improvement_point_not_a_string_raises_clear_error():
    page = base_page(improvement_points=["OK", 123])
    with pytest.raises(ValueError, match=r"improvement_points\[1\] は文字列で指定してください"):
        project_from_dict({"pages": [page]})


def test_source_image_absolute_path_raises_clear_error():
    page = base_page(source_image="/etc/passwd")
    with pytest.raises(ValueError, match="絶対パスや親ディレクトリ参照"):
        project_from_dict({"pages": [page]})


def test_source_image_parent_traversal_raises_clear_error():
    page = base_page(source_image="../../etc/passwd")
    with pytest.raises(ValueError, match="絶対パスや親ディレクトリ参照"):
        project_from_dict({"pages": [page]})


def test_source_image_windows_absolute_path_raises_clear_error():
    page = base_page(source_image="C:\\Windows\\system.ini")
    with pytest.raises(ValueError, match="絶対パスや親ディレクトリ参照"):
        project_from_dict({"pages": [page]})


def test_source_image_not_a_string_raises_clear_error():
    page = base_page(source_image=123)
    with pytest.raises(ValueError, match="source_image は文字列で指定してください"):
        project_from_dict({"pages": [page]})


def test_valid_project_still_parses():
    project = project_from_dict({"pages": [base_page()]})
    assert project.pages[0].page_no == 1
