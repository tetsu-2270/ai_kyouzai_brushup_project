import json

import pytest
from PIL import Image

from src.import_source import import_images, import_source
from src.models import project_from_dict


def _make_image(path, size=(80, 120)):
    Image.new("RGB", size, color=(220, 220, 220)).save(path)


def test_import_images_assigns_page_no_in_filename_order(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    # わざと逆順・非連番のファイル名で作成し、ファイル名昇順に並び替わることを確認する。
    for name in ("page_003.png", "page_001.png", "page_002.png"):
        _make_image(source_dir / name)

    assets_dir = tmp_path / "assets"
    result = import_source(source_dir, assets_dir)

    page_nos = [page["page_no"] for page in result["pages"]]
    assert page_nos == [1, 2, 3]
    titles_or_names = [page["source_image"] for page in result["pages"]]
    assert titles_or_names == ["assets/page_001.png", "assets/page_002.png", "assets/page_003.png"]


def test_import_images_copies_original_files_into_assets_dir(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    _make_image(source_dir / "photo.jpg")

    assets_dir = tmp_path / "output" / "assets"
    result = import_source(source_dir, assets_dir)

    source_image = result["pages"][0]["source_image"]
    assert source_image == "assets/page_001.jpg"
    copied_path = assets_dir / "page_001.jpg"
    assert copied_path.exists()
    assert copied_path.read_bytes() == (source_dir / "photo.jpg").read_bytes()


def test_import_images_single_file_input(tmp_path):
    image_path = tmp_path / "single.png"
    _make_image(image_path)

    assets_dir = tmp_path / "assets"
    result = import_source(image_path, assets_dir)

    assert len(result["pages"]) == 1
    assert result["pages"][0]["source_image"] == "assets/page_001.png"


def test_import_images_result_is_compatible_with_lesson_pages_input(tmp_path):
    """import_sourceの戻り値が、そのままlesson-pagesの--input(pages形式)として使えることを確認する。"""
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    _make_image(source_dir / "page_001.png")
    _make_image(source_dir / "page_002.png")

    assets_dir = tmp_path / "assets"
    result = import_source(source_dir, assets_dir)

    project = project_from_dict(result)
    assert len(project.pages) == 2
    assert project.pages[0].page_no == 1
    assert project.pages[0].source_image == "assets/page_001.png"


def test_import_images_missing_directory_raises_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="取り込み元が見つかりません"):
        import_source(tmp_path / "does_not_exist", tmp_path / "assets")


def test_import_images_empty_directory_raises_clear_error(tmp_path):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    with pytest.raises(ValueError, match="画像ファイル"):
        import_source(empty_dir, tmp_path / "assets")


def test_import_source_unsupported_extension_raises_clear_error(tmp_path):
    unsupported = tmp_path / "note.txt"
    unsupported.write_text("hello", encoding="utf-8")
    with pytest.raises(ValueError, match="対応していない形式"):
        import_source(unsupported, tmp_path / "assets")


def test_import_source_legacy_ppt_raises_clear_error(tmp_path):
    legacy = tmp_path / "old.ppt"
    legacy.write_bytes(b"dummy")
    with pytest.raises(ValueError, match=r"\.ppt"):
        import_source(legacy, tmp_path / "assets")


def test_import_images_ocr_failure_falls_back_gracefully(tmp_path, monkeypatch):
    """tesseract本体が無い環境でも、OCRに失敗した扱いで空文字にフォールバックし、取り込み自体は成立する。"""
    import src.import_source as import_source_module

    monkeypatch.setattr(import_source_module, "_try_ocr", lambda image_path: "")

    source_dir = tmp_path / "source"
    source_dir.mkdir()
    _make_image(source_dir / "page_001.png")

    result = import_source(source_dir, tmp_path / "assets")
    page = result["pages"][0]
    assert page["lines"] == []
    assert page["source_image"] == "assets/page_001.png"
    assert "OCR" in page["canva"]["notes"]


def test_import_images_preserves_ocr_text_when_available(tmp_path, monkeypatch):
    import src.import_source as import_source_module

    monkeypatch.setattr(import_source_module, "_try_ocr", lambda image_path: "1行目のテキスト\n2行目のテキスト")

    source_dir = tmp_path / "source"
    source_dir.mkdir()
    _make_image(source_dir / "page_001.png")

    result = import_source(source_dir, tmp_path / "assets")
    page = result["pages"][0]
    assert page["lines"] == [
        {"speaker": "", "text": "1行目のテキスト"},
        {"speaker": "", "text": "2行目のテキスト"},
    ]
    assert page["title"] == "1行目のテキスト"
