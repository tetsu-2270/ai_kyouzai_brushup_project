from __future__ import annotations

import json

import pytest
from PIL import Image

from src.cli import main
from src.image_brushup_design import resolve_paths
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


def _lesson_page_dict(page_no: int, title: str, body: str, source_image: str = "") -> dict:
    return {
        "page_no": page_no, "source_page_no": [page_no], "role": "", "title": title, "body": body,
        "summary": title, "image_text": title, "layout_instruction": "", "canva_prompt": "",
        "video_scene": "", "source_image": source_image, "source_assets": [], "notes": "",
    }


def _run(monkeypatch, argv):
    monkeypatch.setattr("sys.argv", ["cli"] + argv)
    main()


# --- prepare-image-brushup --------------------------------------------------------------------


def test_prepare_image_brushup_generates_instructions_and_readme(tmp_path, monkeypatch, capsys):
    output_dir = tmp_path / "out"
    _write_lesson_pages(output_dir, [_lesson_page_dict(1, "タイトル1", ": 本文1")])

    _run(monkeypatch, ["prepare-image-brushup", "--output-dir", str(output_dir)])

    captured = capsys.readouterr()
    assert "IMAGE_BRUSHUP_PREPARE: passed" in captured.out
    paths = resolve_paths(output_dir)
    assert paths.instructions_path.exists()
    assert paths.readme_path.exists()
    assert not paths.manifest_path.exists()


def test_prepare_image_brushup_prints_copyable_instruction_line(tmp_path, monkeypatch, capsys):
    output_dir = tmp_path / "out"
    _write_lesson_pages(output_dir, [_lesson_page_dict(1, "タイトル1", ": 本文1")])
    _run(monkeypatch, ["prepare-image-brushup", "--output-dir", str(output_dir)])
    captured = capsys.readouterr()
    assert "を読み、記載された手順を最後まで実行してください" in captured.out
    assert str(tmp_path) not in captured.out


def test_prepare_image_brushup_requires_output_dir(monkeypatch):
    monkeypatch.setattr("sys.argv", ["cli", "prepare-image-brushup"])
    with pytest.raises(SystemExit):
        main()


# --- render-brushup ----------------------------------------------------------------------------


def test_render_brushup_fails_cleanly_without_designs(tmp_path, monkeypatch):
    output_dir = tmp_path / "out"
    _write_lesson_pages(output_dir, [_lesson_page_dict(1, "タイトル1", ": 本文1")])
    monkeypatch.setattr("sys.argv", ["cli", "render-brushup", "--output-dir", str(output_dir)])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code != 0


def test_render_brushup_generates_images_and_reports(tmp_path, monkeypatch, capsys):
    output_dir = tmp_path / "out"
    assets_dir = output_dir / "assets"
    assets_dir.mkdir(parents=True)
    Image.new("RGB", (400, 500), color=(180, 180, 180)).save(assets_dir / "page_001.jpeg")
    _write_lesson_pages(output_dir, [_lesson_page_dict(1, "実データタイトル", ": 実データ本文です", "assets/page_001.jpeg")])

    paths = resolve_paths(output_dir)
    _write_manifest_and_pages(paths.design_dir, {1: _design(1, source_image="assets/page_001.jpeg")})

    _run(monkeypatch, ["render-brushup", "--output-dir", str(output_dir), "--font-path", _FONT_PATH])

    captured = capsys.readouterr()
    assert "IMAGE_BRUSHUP_RENDER: passed" in captured.out
    assert (paths.rendered_brushup_dir / "page_001.png").exists()
    assert paths.render_report_json_path.exists()
    assert paths.render_report_md_path.exists()
    assert paths.comparison_html_path.exists()

    report = json.loads(paths.render_report_json_path.read_text(encoding="utf-8"))
    assert report["pages"][0]["rendered_fields"]["title"] == "実データタイトル"

    # 既存のrendered/には一切書き込まれない。
    assert not (output_dir / "rendered").exists()
    # 元画像は変更されない。
    with Image.open(assets_dir / "page_001.jpeg") as img:
        assert img.size == (400, 500)


def test_render_brushup_fails_when_page_overflows(tmp_path, monkeypatch):
    output_dir = tmp_path / "out"
    huge_body = "\n".join(f": オーバーフローテスト行{i}。" * 5 for i in range(1, 200))
    _write_lesson_pages(output_dir, [_lesson_page_dict(1, "タイトル", huge_body, "assets/page_001.jpeg")])
    paths = resolve_paths(output_dir)
    blocks = [{"id": "b", "type": "body", "source_field": "body", "style": {"font_size": 40, "padding": 20}}]
    tiny_canvas = {"width": 300, "height": 250, "background_color": "#FFFFFF"}
    _write_manifest_and_pages(paths.design_dir, {1: _design(1, blocks=blocks, canvas=tiny_canvas)})

    monkeypatch.setattr("sys.argv", ["cli", "render-brushup", "--output-dir", str(output_dir)])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code != 0

    report = json.loads(paths.render_report_json_path.read_text(encoding="utf-8"))
    assert report["failed_pages"] == [1]


def test_render_brushup_does_not_modify_lesson_pages(tmp_path, monkeypatch):
    output_dir = tmp_path / "out"
    _write_lesson_pages(output_dir, [_lesson_page_dict(1, "タイトル1", ": 本文1", "assets/page_001.jpeg")])
    paths = resolve_paths(output_dir)
    _write_manifest_and_pages(paths.design_dir, {1: _design(1)})
    before = (output_dir / "editable" / "lesson_pages.json").read_text(encoding="utf-8")

    _run(monkeypatch, ["render-brushup", "--output-dir", str(output_dir), "--font-path", _FONT_PATH])

    after = (output_dir / "editable" / "lesson_pages.json").read_text(encoding="utf-8")
    assert before == after


def test_render_brushup_rejects_manifest_with_stale_lesson_pages_hash(tmp_path, monkeypatch, capsys):
    """本文ブラッシュアップ等でlesson_pages.jsonが更新された後、古いdesign_manifest.jsonの
    ままrender-brushupを実行すると拒否される（Phase 10.13連携）。"""
    output_dir = tmp_path / "out"
    _write_lesson_pages(output_dir, [_lesson_page_dict(1, "タイトル1", ": 本文1", "assets/page_001.jpeg")])
    paths = resolve_paths(output_dir)
    _write_manifest_and_pages(paths.design_dir, {1: _design(1)})

    # design_manifest.json作成後にlesson_pages.jsonの内容が変わった状況を再現する。
    _write_lesson_pages(output_dir, [_lesson_page_dict(1, "更新後のタイトル", ": 更新後の本文", "assets/page_001.jpeg")])

    monkeypatch.setattr("sys.argv", ["cli", "render-brushup", "--output-dir", str(output_dir)])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code != 0

    captured = capsys.readouterr()
    assert "prepare-image-brushup" in captured.err
    assert not (paths.rendered_brushup_dir / "page_001.png").exists()
