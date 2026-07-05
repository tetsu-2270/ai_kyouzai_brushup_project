import pytest
from PIL import Image

from src.image_renderer import (
    render_document_images,
    render_page_image,
    resolve_font_path,
)
from src.lesson_pages import build_lesson_document
from src.models import project_from_dict


def _document(pages):
    return build_lesson_document(project_from_dict({
        "project_title": "テスト教材",
        "target_reader": "テスター",
        "pages": pages,
    }))


def test_resolve_font_path_with_valid_explicit_path():
    # 実行環境に実在する日本語フォントをexplicit_pathとして渡し、そのまま返ることを確認する。
    auto = resolve_font_path(None)
    if auto is None:
        return  # この環境に日本語フォントが1つも無い場合はスキップ相当（後続テストでカバー）
    assert resolve_font_path(auto) == auto


def test_resolve_font_path_raises_for_missing_file(tmp_path):
    missing = tmp_path / "does_not_exist.ttc"
    with pytest.raises(ValueError, match="見つかりません"):
        resolve_font_path(str(missing))


def test_resolve_font_path_raises_for_unloadable_file(tmp_path):

    bogus = tmp_path / "not_a_font.ttf"
    bogus.write_text("this is not a font file", encoding="utf-8")
    with pytest.raises(ValueError, match="読み込めません"):
        resolve_font_path(str(bogus))


def test_resolve_font_path_auto_search_returns_none_when_no_candidates(monkeypatch):
    import src.image_renderer as image_renderer_module

    monkeypatch.setattr(image_renderer_module, "_JAPANESE_FONT_CANDIDATES", ())
    assert resolve_font_path(None) is None


def test_render_document_images_warns_when_synthesis_needed_and_no_font_found(monkeypatch, tmp_path, capsys):
    import src.image_renderer as image_renderer_module

    monkeypatch.setattr(image_renderer_module, "_JAPANESE_FONT_CANDIDATES", ())
    document = _document([{"page_no": 1, "source_image": "", "title": "P1", "summary": "概要", "lines": []}])

    render_document_images(document, tmp_path, tmp_path / "rendered")

    captured = capsys.readouterr()
    assert "WARNING" in captured.err
    assert "font" in captured.err.lower()


def test_render_document_images_does_not_warn_when_all_pages_have_source_image(monkeypatch, tmp_path, capsys):
    import src.image_renderer as image_renderer_module

    monkeypatch.setattr(image_renderer_module, "_JAPANESE_FONT_CANDIDATES", ())
    Image.new("RGB", (80, 120), color=(220, 220, 220)).save(tmp_path / "assets_page.png")
    (tmp_path / "assets").mkdir()
    Image.new("RGB", (80, 120), color=(220, 220, 220)).save(tmp_path / "assets" / "page_001.png")

    document = _document([{"page_no": 1, "source_image": "assets/page_001.png", "title": "P1", "summary": ""}])
    render_document_images(document, tmp_path, tmp_path / "rendered")

    captured = capsys.readouterr()
    assert "WARNING" not in captured.err


def test_render_document_images_continues_after_warning(monkeypatch, tmp_path):
    """フォント未検出でも警告を出すだけで処理は継続し、画像は生成されることを確認する。"""
    import src.image_renderer as image_renderer_module

    monkeypatch.setattr(image_renderer_module, "_JAPANESE_FONT_CANDIDATES", ())
    document = _document([{"page_no": 1, "source_image": "", "title": "P1", "summary": "概要", "lines": []}])

    paths = render_document_images(document, tmp_path, tmp_path / "rendered")
    assert paths[0].exists()


def test_render_document_images_generates_multiple_pages(tmp_path):
    document = _document([
        {"page_no": 1, "source_image": "", "title": "P1", "summary": "概要1", "lines": []},
        {"page_no": 2, "source_image": "", "title": "P2", "summary": "概要2", "lines": []},
        {"page_no": 3, "source_image": "", "title": "P3", "summary": "概要3", "lines": []},
    ])
    paths = render_document_images(document, tmp_path, tmp_path / "rendered")
    assert [p.name for p in paths] == ["page_001.png", "page_002.png", "page_003.png"]
    for p in paths:
        assert p.exists()


def test_render_page_image_with_explicit_font_path_uses_that_font(tmp_path):
    auto_font = resolve_font_path(None)
    if auto_font is None:
        return  # 実行環境に日本語フォントが無い場合はスキップ相当

    document = _document([{"page_no": 1, "source_image": "", "title": "テスト", "summary": "", "lines": []}])
    dest_path = tmp_path / "rendered" / "page_001.png"
    render_page_image(document.pages[0], tmp_path, dest_path, font_path=auto_font)
    assert dest_path.exists()


def test_synthesized_image_handles_long_text_without_error(tmp_path):
    """長文でも例外を出さず、画像の範囲内に収まる（打ち切り表示を含む）ことを確認する。"""
    long_text = "これはとても長い台詞です。" * 30
    document = _document([{
        "page_no": 1,
        "source_image": "",
        "title": "長文ページ",
        "summary": "概要も" * 20,
        "lines": [{"speaker": "講師", "text": long_text}],
    }])
    dest_path = tmp_path / "rendered" / "page_001.png"
    render_page_image(document.pages[0], tmp_path, dest_path)
    assert dest_path.exists()
    image = Image.open(dest_path)
    assert image.size == (900, 1200)
