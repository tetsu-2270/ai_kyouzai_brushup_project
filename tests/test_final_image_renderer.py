from __future__ import annotations

import json

from PIL import Image

from src import final_image_package as fip
from src import final_image_renderer as fir
from src.image_brushup_design import resolve_paths as design_resolve_paths
from src.image_renderer import resolve_font_path
from src.lesson_pages import write_lesson_pages_json
from tests.test_brushup_renderer import _design, _document, _page, _write_manifest_and_pages

_FONT_PATH = resolve_font_path(None)


def _write_asset(output_dir, page_no, size=(1706, 960)):
    assets_dir = output_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color=(240, 230, 210)).save(assets_dir / f"page_{page_no:03d}.jpeg")


def _prepare_fresh_brushup_design(output_dir, document):
    """final_image_renderer.write_final_image_packageの前提（Phase 10.12デザインの新鮮さ）を満たす。"""
    design_paths = design_resolve_paths(output_dir)
    designs = {p.page_no: _design(p.page_no, source_image=p.source_image) for p in document.pages}
    _write_manifest_and_pages(design_paths.design_dir, designs)


def _setup(tmp_path, pages, body_overrides=None):
    document = _document(pages)
    write_lesson_pages_json(tmp_path / "editable" / "lesson_pages.json", document)
    for p in pages:
        _write_asset(tmp_path, p.page_no)
    _prepare_fresh_brushup_design(tmp_path, document)
    return document


# --- render_page_preview（単一ページ） ----------------------------------------------------------


def test_render_page_preview_succeeds_for_simple_page(tmp_path):
    page = _page(1, title="T", body="T\n本文の1行目\n※無断転載禁止（おとスタ）")
    document = _setup(tmp_path, [page])
    master_layout = fip.build_master_layout(document, tmp_path, tmp_path / "editable" / "lesson_pages.json")
    spec = fip.build_page_spec(page, master_layout["source_lesson_pages_sha256"], _FONT_PATH)

    image, warnings, overflow = fir.render_page_preview(page, spec, master_layout, _FONT_PATH)

    assert image is not None
    assert overflow is False
    assert image.size == (1600, 900)


def test_render_page_preview_fails_without_truncation_when_body_impossibly_long(tmp_path):
    page = _page(1, title="T", body="T\n" + "非常に長い本文行。" * 400 + "\n※無断転載禁止（おとスタ）")
    document = _setup(tmp_path, [page])
    master_layout = fip.build_master_layout(document, tmp_path, tmp_path / "editable" / "lesson_pages.json")
    spec = fip.build_page_spec(page, master_layout["source_lesson_pages_sha256"], _FONT_PATH)

    image, warnings, overflow = fir.render_page_preview(page, spec, master_layout, _FONT_PATH)

    assert image is None
    assert overflow is True
    assert warnings


# --- 全ページ共通のカード寸法（deck-wide uniformity） -------------------------------------------


def test_content_card_size_is_identical_for_sparse_and_dense_pages(tmp_path):
    sparse = _page(1, title="短", body="短\n短い一行\n※無断転載禁止（おとスタ）")
    dense = _page(2, title="長", body="長\n" + "\n".join(f"本文行{i}" for i in range(12)) + "\n※無断転載禁止（おとスタ）")
    document = _setup(tmp_path, [sparse, dense])
    master_layout = fip.build_master_layout(document, tmp_path, tmp_path / "editable" / "lesson_pages.json")

    spec_sparse = fip.build_page_spec(sparse, master_layout["source_lesson_pages_sha256"], _FONT_PATH)
    spec_dense = fip.build_page_spec(dense, master_layout["source_lesson_pages_sha256"], _FONT_PATH)

    image_sparse, _, overflow_sparse = fir.render_page_preview(sparse, spec_sparse, master_layout, _FONT_PATH)
    image_dense, _, overflow_dense = fir.render_page_preview(dense, spec_dense, master_layout, _FONT_PATH)

    assert overflow_sparse is False and overflow_dense is False
    # 両ページとも同じキャンバスサイズ（=カード外形が内容量で変わっていない）。
    assert image_sparse.size == image_dense.size == (1600, 900)
    assert spec_sparse["content_layout"]["vertical_alignment"] != "top" or spec_dense["content_layout"]["vertical_alignment"] == "top"


# --- write_final_image_package（一括実行） -------------------------------------------------------


def test_write_final_image_package_generates_all_expected_files(tmp_path):
    pages = [_page(1), _page(2)]
    document = _setup(tmp_path, pages)

    run = fir.write_final_image_package(tmp_path, document, font_path=_FONT_PATH)

    assert run.failed_pages == []
    assert run.succeeded_pages == [1, 2]

    paths = fip.resolve_paths(tmp_path)
    assert paths.master_layout_path.exists()
    assert paths.instructions_path.exists()
    assert paths.readme_path.exists()
    assert paths.package_manifest_path.exists()
    assert paths.asset_manifest_path.exists()
    assert paths.master_background_prompt_path.exists()
    assert paths.master_guides_path.exists()
    assert paths.comparison_html_path.exists()
    for page_no in (1, 2):
        assert (paths.pages_dir / f"page_{page_no:03d}.json").exists()
        assert (paths.text_dir / f"page_{page_no:03d}.json").exists()
        assert (paths.prompts_dir / f"page_{page_no:03d}.md").exists()
        assert (paths.preview_dir / f"page_{page_no:03d}.png").exists()
        assert (paths.rendered_brushup_preview_dir / f"page_{page_no:03d}.png").exists()


def test_write_final_image_package_never_creates_rendered_final(tmp_path):
    document = _setup(tmp_path, [_page(1)])
    fir.write_final_image_package(tmp_path, document, font_path=_FONT_PATH)
    assert not (tmp_path / "rendered_final").exists()


def test_write_final_image_package_does_not_modify_source_image_or_lesson_pages(tmp_path):
    document = _setup(tmp_path, [_page(1)])
    lesson_pages_path = tmp_path / "editable" / "lesson_pages.json"
    asset_path = tmp_path / "assets" / "page_001.jpeg"
    before_lesson = lesson_pages_path.read_bytes()
    before_asset = asset_path.read_bytes()

    fir.write_final_image_package(tmp_path, document, font_path=_FONT_PATH)

    assert lesson_pages_path.read_bytes() == before_lesson
    assert asset_path.read_bytes() == before_asset


def test_write_final_image_package_all_pages_share_identical_content_card(tmp_path):
    pages = [_page(1, body="T\n短い\n※無断転載禁止（おとスタ）"), _page(2, body="T\n" + "\n".join(f"行{i}" for i in range(9)) + "\n※無断転載禁止（おとスタ）")]
    document = _setup(tmp_path, pages)
    run = fir.write_final_image_package(tmp_path, document, font_path=_FONT_PATH)
    assert run.failed_pages == []

    paths = fip.resolve_paths(tmp_path)
    manifest = json.loads(paths.package_manifest_path.read_text(encoding="utf-8"))
    card = manifest["content_card"]
    for page_no in (1, 2):
        spec = json.loads((paths.pages_dir / f"page_{page_no:03d}.json").read_text(encoding="utf-8"))
        master_layout = json.loads(paths.master_layout_path.read_text(encoding="utf-8"))
        assert master_layout["regions"]["content_card"]["x"] == card["x"]
        assert master_layout["regions"]["content_card"]["width"] == card["width"]
        assert spec["master_layout"] == master_layout["master_id"]


def test_write_final_image_package_supports_arbitrary_page_counts(tmp_path):
    pages = [_page(i, body=f"T{i}\n本文{i}\n※無断転載禁止（おとスタ）") for i in range(1, 8)]
    document = _setup(tmp_path, pages)
    run = fir.write_final_image_package(tmp_path, document, font_path=_FONT_PATH)
    assert run.total_pages == 7
    assert run.succeeded_pages == list(range(1, 8))


def test_write_final_image_package_rejects_stale_brushup_design(tmp_path):
    pages = [_page(1)]
    document = _document(pages)
    write_lesson_pages_json(tmp_path / "editable" / "lesson_pages.json", document)
    _write_asset(tmp_path, 1)
    # brushup_designを作らない（=デザインが揃っていない状態）。
    try:
        fir.write_final_image_package(tmp_path, document, font_path=_FONT_PATH)
        assert False, "should have raised"
    except ValueError as e:
        assert "brushup_design" in str(e) or "デザイン" in str(e)


def test_write_final_image_package_rejects_design_manifest_with_stale_lesson_pages_hash(tmp_path):
    pages = [_page(1)]
    document = _document(pages)
    write_lesson_pages_json(tmp_path / "editable" / "lesson_pages.json", document)
    _write_asset(tmp_path, 1)
    design_paths = design_resolve_paths(tmp_path)
    _write_manifest_and_pages(design_paths.design_dir, {1: _design(1, source_image=pages[0].source_image)})
    # lesson_pages.jsonを後から書き換え、manifestのハッシュを古くする。
    pages[0].body = pages[0].body + "\n追記"
    write_lesson_pages_json(tmp_path / "editable" / "lesson_pages.json", _document(pages))

    try:
        fir.write_final_image_package(tmp_path, document, font_path=_FONT_PATH)
        assert False, "should have raised"
    except ValueError:
        pass


# --- master_guides / comparison.html ------------------------------------------------------------


def test_render_master_guides_matches_canvas_size(tmp_path):
    pages = [_page(1)]
    document = _setup(tmp_path, pages)
    master_layout = fip.build_master_layout(document, tmp_path, tmp_path / "editable" / "lesson_pages.json")
    image = fir.render_master_guides(master_layout, _FONT_PATH)
    assert image.size == (master_layout["canvas"]["width"], master_layout["canvas"]["height"])


def test_comparison_html_is_self_contained_with_no_external_references(tmp_path):
    document = _setup(tmp_path, [_page(1)])
    run = fir.write_final_image_package(tmp_path, document, font_path=_FONT_PATH)
    paths = fip.resolve_paths(tmp_path)
    html_text = paths.comparison_html_path.read_text(encoding="utf-8")
    assert "http://" not in html_text
    assert "https://" not in html_text
    assert "本文カード" in html_text
