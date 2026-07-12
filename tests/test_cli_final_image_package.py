from __future__ import annotations

import json

import pytest
from PIL import Image

from src.cli import main
from src.image_brushup_design import resolve_paths as design_resolve_paths
from src.final_image_package import resolve_paths
from src.image_renderer import resolve_font_path
from tests.test_brushup_renderer import _design, _write_manifest_and_pages

_FONT_PATH = resolve_font_path(None)


def _write_lesson_pages(output_dir, pages: list[dict]) -> None:
    editable_dir = output_dir / "editable"
    editable_dir.mkdir(parents=True, exist_ok=True)
    document = {
        "metadata": {
            "project_title": "テスト教材", "mode": "proofread", "source_policy": "preserve_original",
            "target_audience": "テスト", "tone": "", "generated_at": "2026-07-12T00:00:00+09:00",
        },
        "pages": pages,
    }
    (editable_dir / "lesson_pages.json").write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")


def _lesson_page_dict(page_no: int, title: str, body: str, source_image: str) -> dict:
    return {
        "page_no": page_no, "source_page_no": [page_no], "role": "", "title": title, "body": body,
        "summary": title, "image_text": title, "layout_instruction": "", "canva_prompt": "",
        "video_scene": "", "source_image": source_image, "source_assets": [], "notes": "",
    }


def _write_asset(output_dir, page_no, size=(1706, 960)):
    assets_dir = output_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color=(240, 230, 210)).save(assets_dir / f"page_{page_no:03d}.jpeg")


def _prepare_fresh_design(output_dir, page_dicts):
    design_paths = design_resolve_paths(output_dir)
    designs = {p["page_no"]: _design(p["page_no"], source_image=p["source_image"]) for p in page_dicts}
    _write_manifest_and_pages(design_paths.design_dir, designs)


def _setup_full(output_dir, page_dicts):
    _write_lesson_pages(output_dir, page_dicts)
    for p in page_dicts:
        _write_asset(output_dir, p["page_no"])
    _prepare_fresh_design(output_dir, page_dicts)


def _run(monkeypatch, argv):
    monkeypatch.setattr("sys.argv", ["cli"] + argv)
    main()


def test_prepare_final_image_package_generates_full_package(tmp_path, monkeypatch, capsys):
    output_dir = tmp_path / "out"
    pages = [_lesson_page_dict(1, "タイトル1", "タイトル1\n本文1\n※無断転載禁止（おとスタ）", "assets/page_001.jpeg")]
    _setup_full(output_dir, pages)

    _run(monkeypatch, ["prepare-final-image-package", "--output-dir", str(output_dir), "--font-path", _FONT_PATH or ""])

    captured = capsys.readouterr()
    assert "FINAL_IMAGE_PACKAGE_PREPARE: passed" in captured.out
    assert "を読み、記載された手順を最後まで実行してください" in captured.out

    paths = resolve_paths(output_dir)
    assert paths.master_layout_path.exists()
    assert paths.instructions_path.exists()
    assert paths.package_manifest_path.exists()
    assert (paths.preview_dir / "page_001.png").exists()
    assert not (output_dir / "rendered_final").exists()


def test_prepare_final_image_package_requires_output_dir(monkeypatch):
    monkeypatch.setattr("sys.argv", ["cli", "prepare-final-image-package"])
    with pytest.raises(SystemExit):
        main()


def test_prepare_final_image_package_fails_cleanly_without_brushup_design(tmp_path, monkeypatch):
    output_dir = tmp_path / "out"
    pages = [_lesson_page_dict(1, "タイトル1", "タイトル1\n本文1\n※無断転載禁止（おとスタ）", "assets/page_001.jpeg")]
    _write_lesson_pages(output_dir, pages)
    _write_asset(output_dir, 1)
    # brushup_designを作らない。

    monkeypatch.setattr("sys.argv", ["cli", "prepare-final-image-package", "--output-dir", str(output_dir)])
    with pytest.raises(SystemExit):
        main()


def test_prepare_final_image_package_prints_common_canvas_and_card(tmp_path, monkeypatch, capsys):
    output_dir = tmp_path / "out"
    pages = [_lesson_page_dict(1, "タイトル1", "タイトル1\n本文1\n※無断転載禁止（おとスタ）", "assets/page_001.jpeg")]
    _setup_full(output_dir, pages)

    _run(monkeypatch, ["prepare-final-image-package", "--output-dir", str(output_dir)])

    captured = capsys.readouterr()
    assert "共通キャンバス: 1600x900" in captured.out
    assert "共通本文カード:" in captured.out
    assert "rendered_final/（完成画像）はこの工程ではまだ生成されていません" in captured.out
