import pytest

from src.parser import load_project


def test_load_project_reads_sample_json():
    project = load_project("examples/sample_pages.json")
    assert project.project_title == "教材ブラッシュアップ設計書 v1.0"
    assert [p.page_no for p in project.pages] == [1, 2]


def test_load_project_missing_file_raises_clear_error():
    with pytest.raises(FileNotFoundError, match="入力ファイルが見つかりません"):
        load_project("no_such_file.json")


def test_load_project_invalid_json_raises_clear_error(tmp_path):
    bad_file = tmp_path / "broken.json"
    bad_file.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(ValueError, match="JSONが不正です"):
        load_project(bad_file)
