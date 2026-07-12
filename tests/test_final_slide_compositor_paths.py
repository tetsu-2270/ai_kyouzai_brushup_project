from __future__ import annotations

import json

import pytest
from PIL import Image

from src import final_image_package as fip
from src import final_image_renderer as fir
from src import final_slide_compositor as fsc
from src.image_renderer import resolve_font_path
from tests.test_final_slide_compositor import _prepare_package, _simple_page, _write_background

_FONT_PATH = resolve_font_path(None)


# --- relative_asset_path（相対パス算出の共通関数） ------------------------------------------------


def test_relative_asset_path_same_directory(tmp_path):
    (tmp_path / "image.png").write_bytes(b"fake")
    html_path = tmp_path / "page.html"
    rel = fsc.relative_asset_path(html_path, tmp_path / "image.png", allowed_root=tmp_path)
    assert rel == "image.png"


def test_relative_asset_path_one_level_up(tmp_path):
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (assets_dir / "image.png").write_bytes(b"fake")
    html_dir = tmp_path / "final_image_package"
    html_dir.mkdir()
    html_path = html_dir / "final_comparison.html"

    rel = fsc.relative_asset_path(html_path, assets_dir / "image.png", allowed_root=tmp_path)
    assert rel == "../assets/image.png"


def test_relative_asset_path_two_levels_up(tmp_path):
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (assets_dir / "image.png").write_bytes(b"fake")
    html_dir = tmp_path / "final_image_package" / "preview"
    html_dir.mkdir(parents=True)
    html_path = html_dir / "comparison.html"

    rel = fsc.relative_asset_path(html_path, assets_dir / "image.png", allowed_root=tmp_path)
    assert rel == "../../assets/image.png"


def test_relative_asset_path_child_directory(tmp_path):
    html_dir = tmp_path / "final_image_package"
    html_dir.mkdir()
    child_dir = html_dir / "preview"
    child_dir.mkdir()
    (child_dir / "image.png").write_bytes(b"fake")
    html_path = html_dir / "comparison.html"

    rel = fsc.relative_asset_path(html_path, child_dir / "image.png", allowed_root=tmp_path)
    assert rel == "preview/image.png"


def test_relative_asset_path_uses_posix_separators(tmp_path):
    assets_dir = tmp_path / "a" / "b"
    assets_dir.mkdir(parents=True)
    (assets_dir / "image.png").write_bytes(b"fake")
    html_dir = tmp_path / "c" / "d"
    html_dir.mkdir(parents=True)
    html_path = html_dir / "page.html"

    rel = fsc.relative_asset_path(html_path, assets_dir / "image.png", allowed_root=tmp_path)
    assert "\\" not in rel
    assert rel == "../../a/b/image.png"


def test_relative_asset_path_never_returns_absolute_path(tmp_path):
    (tmp_path / "image.png").write_bytes(b"fake")
    html_path = tmp_path / "sub" / "page.html"
    html_path.parent.mkdir()
    rel = fsc.relative_asset_path(html_path, tmp_path / "image.png", allowed_root=tmp_path)
    assert not rel.startswith("/")


def test_relative_asset_path_rejects_target_outside_allowed_root(tmp_path):
    outside_dir = tmp_path.parent / f"{tmp_path.name}_outside"
    outside_dir.mkdir(exist_ok=True)
    outside_file = outside_dir / "image.png"
    outside_file.write_bytes(b"fake")
    allowed_root = tmp_path / "output"
    allowed_root.mkdir()
    html_path = allowed_root / "page.html"

    with pytest.raises(ValueError, match="許可されたルート外"):
        fsc.relative_asset_path(html_path, outside_file, allowed_root=allowed_root)


def test_relative_asset_path_rejects_missing_file(tmp_path):
    html_path = tmp_path / "page.html"
    with pytest.raises(ValueError, match="見つかりません"):
        fsc.relative_asset_path(html_path, tmp_path / "no_such.png", allowed_root=tmp_path)


def test_relative_asset_path_rejects_directory_as_target(tmp_path):
    target_dir = tmp_path / "not_a_file"
    target_dir.mkdir()
    html_path = tmp_path / "page.html"
    with pytest.raises(ValueError, match="ファイルではありません"):
        fsc.relative_asset_path(html_path, target_dir, allowed_root=tmp_path)


# --- final_comparison.htmlの相対パス修正確認 -------------------------------------------------------


def test_final_comparison_html_uses_single_level_relative_paths(tmp_path):
    pages = [_simple_page(1), _simple_page(2)]
    document = _prepare_package(tmp_path, pages)
    _write_background(tmp_path)
    run = fsc.write_final_images(tmp_path, document, font_path=_FONT_PATH, run_ocr_check=False)
    paths = fsc.resolve_paths(tmp_path)
    page_specs = {
        p.page_no: json.loads((paths.pages_dir / f"page_{p.page_no:03d}.json").read_text(encoding="utf-8"))
        for p in document.pages
    }

    html_text = fsc.render_final_comparison_html(
        document, run.master_layout, page_specs, run, tmp_path, paths.final_comparison_html_path,
    )

    assert 'src="../assets/page_001.jpeg"' in html_text
    assert 'src="../rendered_brushup_preview/page_001.png"' in html_text
    assert 'src="../rendered_final/page_001.png"' in html_text
    # 誤ったパス（1階層上がりすぎ）が含まれていないことを確認する。
    assert "../../assets/" not in html_text
    assert "../../rendered_brushup_preview/" not in html_text
    assert "../../rendered_final/" not in html_text


def test_final_comparison_html_has_page_count_times_three_image_references(tmp_path):
    pages = [_simple_page(1), _simple_page(2), _simple_page(3)]
    document = _prepare_package(tmp_path, pages)
    _write_background(tmp_path)
    run = fsc.write_final_images(tmp_path, document, font_path=_FONT_PATH, run_ocr_check=False)
    paths = fsc.resolve_paths(tmp_path)
    page_specs = {
        p.page_no: json.loads((paths.pages_dir / f"page_{p.page_no:03d}.json").read_text(encoding="utf-8"))
        for p in document.pages
    }
    html_text = fsc.render_final_comparison_html(
        document, run.master_layout, page_specs, run, tmp_path, paths.final_comparison_html_path,
    )
    assert html_text.count("<img") == len(pages) * 3


def test_final_comparison_html_all_images_resolvable_and_pillow_readable(tmp_path):
    pages = [_simple_page(1), _simple_page(2)]
    document = _prepare_package(tmp_path, pages)
    _write_background(tmp_path)
    run = fsc.write_final_images(tmp_path, document, font_path=_FONT_PATH, run_ocr_check=False)
    paths = fsc.resolve_paths(tmp_path)
    page_specs = {
        p.page_no: json.loads((paths.pages_dir / f"page_{p.page_no:03d}.json").read_text(encoding="utf-8"))
        for p in document.pages
    }
    html_text = fsc.render_final_comparison_html(
        document, run.master_layout, page_specs, run, tmp_path, paths.final_comparison_html_path,
    )
    paths.final_comparison_html_path.write_text(html_text, encoding="utf-8")

    validation = fsc.validate_comparison_html_references(paths.final_comparison_html_path, tmp_path)
    assert validation["image_reference_count"] == len(pages) * 3
    assert validation["resolved_reference_count"] == len(pages) * 3
    assert validation["missing_reference_count"] == 0
    assert validation["broken_references"] == []
    assert validation["all_images_resolvable"] is True


def test_final_comparison_html_fails_when_preview_image_missing(tmp_path):
    pages = [_simple_page(1)]
    document = _prepare_package(tmp_path, pages)
    _write_background(tmp_path)
    run = fsc.write_final_images(tmp_path, document, font_path=_FONT_PATH, run_ocr_check=False)
    paths = fsc.resolve_paths(tmp_path)
    page_specs = {
        p.page_no: json.loads((paths.pages_dir / f"page_{p.page_no:03d}.json").read_text(encoding="utf-8"))
        for p in document.pages
    }
    # Phase 10.14プレビューを削除し、必須参照の欠落を発生させる。
    (paths.rendered_brushup_preview_dir / "page_001.png").unlink()

    with pytest.raises(ValueError, match="page_no=1, category=preview"):
        fsc.render_final_comparison_html(document, run.master_layout, page_specs, run, tmp_path, paths.final_comparison_html_path)


def test_final_comparison_html_fails_when_source_image_missing(tmp_path):
    pages = [_simple_page(1)]
    document = _prepare_package(tmp_path, pages)
    _write_background(tmp_path)
    run = fsc.write_final_images(tmp_path, document, font_path=_FONT_PATH, run_ocr_check=False)
    paths = fsc.resolve_paths(tmp_path)
    page_specs = {
        p.page_no: json.loads((paths.pages_dir / f"page_{p.page_no:03d}.json").read_text(encoding="utf-8"))
        for p in document.pages
    }
    (tmp_path / "assets" / "page_001.jpeg").unlink()

    with pytest.raises(ValueError, match="page_no=1, category=source"):
        fsc.render_final_comparison_html(document, run.master_layout, page_specs, run, tmp_path, paths.final_comparison_html_path)


def test_final_comparison_html_no_external_urls_or_file_scheme(tmp_path):
    pages = [_simple_page(1)]
    document = _prepare_package(tmp_path, pages)
    _write_background(tmp_path)
    run = fsc.write_final_images(tmp_path, document, font_path=_FONT_PATH, run_ocr_check=False)
    paths = fsc.resolve_paths(tmp_path)
    page_specs = {
        p.page_no: json.loads((paths.pages_dir / f"page_{p.page_no:03d}.json").read_text(encoding="utf-8"))
        for p in document.pages
    }
    html_text = fsc.render_final_comparison_html(
        document, run.master_layout, page_specs, run, tmp_path, paths.final_comparison_html_path,
    )
    assert "http://" not in html_text
    assert "https://" not in html_text
    assert "file://" not in html_text


# --- 任意のoutput-dir階層（深さを固定で仮定しない） ------------------------------------------------


def test_final_comparison_html_works_with_deeply_nested_output_dir(tmp_path):
    nested_output_dir = tmp_path / "a" / "b" / "c" / "output" / "ocr_engine_eval"
    nested_output_dir.mkdir(parents=True)
    pages = [_simple_page(1)]
    document = _prepare_package(nested_output_dir, pages)
    _write_background(nested_output_dir)
    run = fsc.write_final_images(nested_output_dir, document, font_path=_FONT_PATH, run_ocr_check=False)
    paths = fsc.resolve_paths(nested_output_dir)
    page_specs = {
        p.page_no: json.loads((paths.pages_dir / f"page_{p.page_no:03d}.json").read_text(encoding="utf-8"))
        for p in document.pages
    }
    html_text = fsc.render_final_comparison_html(
        document, run.master_layout, page_specs, run, nested_output_dir, paths.final_comparison_html_path,
    )
    paths.final_comparison_html_path.write_text(html_text, encoding="utf-8")

    assert 'src="../assets/page_001.jpeg"' in html_text
    validation = fsc.validate_comparison_html_references(paths.final_comparison_html_path, nested_output_dir)
    assert validation["all_images_resolvable"] is True


# --- 他の比較HTML監査（既存のロジックを流用して壊れていないことを回帰確認） -------------------------


def test_phase_10_14_preview_comparison_html_all_references_resolvable(tmp_path):
    pages = [_simple_page(1), _simple_page(2)]
    document = _prepare_package(tmp_path, pages)
    run = fir.write_final_image_package(tmp_path, document, font_path=_FONT_PATH)
    paths = fip.resolve_paths(tmp_path)
    assert paths.comparison_html_path.exists()

    validation = fsc.validate_comparison_html_references(paths.comparison_html_path, tmp_path)
    assert validation["all_images_resolvable"] is True
    assert validation["missing_reference_count"] == 0
