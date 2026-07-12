from __future__ import annotations

import json

import pytest
from PIL import Image

from src import final_image_package as fip
from src import final_image_renderer as fir
from src import final_slide_compositor as fsc
from src.image_renderer import resolve_font_path
from src.lesson_pages import write_lesson_pages_json
from tests.test_final_image_renderer import _prepare_fresh_brushup_design, _setup, _write_asset
from tests.test_brushup_renderer import _document, _page

_FONT_PATH = resolve_font_path(None)


def _prepare_package(tmp_path, pages):
    """Phase 10.14までの前提（brushup_design・MASTER_LAYOUT・pages/text）を揃える。"""
    document = _setup(tmp_path, pages)
    fir.write_final_image_package(tmp_path, document, font_path=_FONT_PATH)
    return document


def _write_background(tmp_path, size=(1600, 900), color=(240, 220, 200)):
    paths = fsc.resolve_paths(tmp_path)
    paths.rendered_final_dir.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color=color).save(paths.default_background_path)
    return paths.default_background_path


def _simple_page(page_no=1, **kwargs):
    kwargs.setdefault("title", f"タイトル{page_no}")
    kwargs.setdefault("body", f": タイトル{page_no}\n: 本文{page_no}の一行目\n: ※無断転載禁止（おとスタ）")
    return _page(page_no, **kwargs)


# --- write_final_images（一括実行・正常系） -------------------------------------------------------


def test_write_final_images_generates_all_pages(tmp_path):
    pages = [_simple_page(1), _simple_page(2)]
    document = _prepare_package(tmp_path, pages)
    _write_background(tmp_path)

    run = fsc.write_final_images(tmp_path, document, font_path=_FONT_PATH, run_ocr_check=False)

    assert run.failed_pages == []
    assert run.succeeded_pages == [1, 2]
    paths = fsc.resolve_paths(tmp_path)
    for page_no in (1, 2):
        out = paths.rendered_final_dir / f"page_{page_no:03d}.png"
        assert out.exists()
        with Image.open(out) as img:
            assert img.size == (1600, 900)


def test_write_final_images_is_idempotent(tmp_path):
    pages = [_simple_page(1)]
    document = _prepare_package(tmp_path, pages)
    _write_background(tmp_path)

    run1 = fsc.write_final_images(tmp_path, document, font_path=_FONT_PATH, run_ocr_check=False)
    run2 = fsc.write_final_images(tmp_path, document, font_path=_FONT_PATH, run_ocr_check=False)

    assert run1.succeeded_pages == run2.succeeded_pages == [1]
    paths = fsc.resolve_paths(tmp_path)
    img1_bytes = (paths.rendered_final_dir / "page_001.png").read_bytes()
    assert img1_bytes  # 再実行後も存在し、空ではない


def test_write_final_images_does_not_modify_protected_inputs(tmp_path):
    pages = [_simple_page(1)]
    document = _prepare_package(tmp_path, pages)
    bg_path = _write_background(tmp_path)

    lesson_pages_path = tmp_path / "editable" / "lesson_pages.json"
    asset_path = tmp_path / "assets" / "page_001.jpeg"
    master_layout_path = fip.resolve_paths(tmp_path).master_layout_path
    before_lesson = lesson_pages_path.read_bytes()
    before_asset = asset_path.read_bytes()
    before_bg = bg_path.read_bytes()
    before_master = master_layout_path.read_bytes()

    fsc.write_final_images(tmp_path, document, font_path=_FONT_PATH, run_ocr_check=False)

    assert lesson_pages_path.read_bytes() == before_lesson
    assert asset_path.read_bytes() == before_asset
    assert bg_path.read_bytes() == before_bg
    assert master_layout_path.read_bytes() == before_master


def test_write_final_images_all_pages_share_identical_content_card(tmp_path):
    pages = [
        _simple_page(1, body=": T\n: 短い\n: ※無断転載禁止（おとスタ）"),
        _simple_page(2, body=": T\n" + "\n".join(f": 行{i}" for i in range(9)) + "\n: ※無断転載禁止（おとスタ）"),
    ]
    document = _prepare_package(tmp_path, pages)
    _write_background(tmp_path)
    run = fsc.write_final_images(tmp_path, document, font_path=_FONT_PATH, run_ocr_check=False)
    assert run.failed_pages == []

    paths = fsc.resolve_paths(tmp_path)
    sizes = set()
    for page_no in (1, 2):
        with Image.open(paths.rendered_final_dir / f"page_{page_no:03d}.png") as img:
            sizes.add(img.size)
    assert len(sizes) == 1


def test_write_final_images_renders_two_column_page(tmp_path):
    body = (
        ": T\n: 導入\n: ※実在の人物などを参考にするのも◎\n: 例1）キャラA\n: ・特徴1\n: ・特徴2\n"
        ": 例2）キャラB\n: ・特徴3\n: ・特徴4\n: ※無断転載禁止（おとスタ）"
    )
    pages = [_simple_page(1, body=body)]
    document = _prepare_package(tmp_path, pages)
    _write_background(tmp_path)
    run = fsc.write_final_images(tmp_path, document, font_path=_FONT_PATH, run_ocr_check=False)

    assert run.failed_pages == []
    paths = fsc.resolve_paths(tmp_path)
    spec = json.loads((paths.pages_dir / "page_001.json").read_text(encoding="utf-8"))
    assert spec["content_layout"]["type"] == "two_column"


def test_write_final_images_renders_circled_numbers_and_long_vowel_marks(tmp_path):
    pages = [_simple_page(1, title="①キャラー設定", body=": ①キャラー設定\n: ①〜⑩の項目\n: ※無断転載禁止（おとスタ）")]
    document = _prepare_package(tmp_path, pages)
    _write_background(tmp_path)
    run = fsc.write_final_images(tmp_path, document, font_path=_FONT_PATH, run_ocr_check=False)
    assert run.failed_pages == []


# --- 入力検証（拒否系） ------------------------------------------------------------------------


def test_write_final_images_rejects_missing_background(tmp_path):
    pages = [_simple_page(1)]
    document = _prepare_package(tmp_path, pages)
    # 背景を書き込まない。

    with pytest.raises(ValueError, match="背景画像が見つかりません"):
        fsc.write_final_images(tmp_path, document, font_path=_FONT_PATH, run_ocr_check=False)


def test_write_final_images_rejects_wrong_background_size(tmp_path):
    pages = [_simple_page(1)]
    document = _prepare_package(tmp_path, pages)
    _write_background(tmp_path, size=(800, 600))

    with pytest.raises(ValueError, match="サイズ"):
        fsc.write_final_images(tmp_path, document, font_path=_FONT_PATH, run_ocr_check=False)


def test_write_final_images_rejects_transparent_background(tmp_path):
    pages = [_simple_page(1)]
    document = _prepare_package(tmp_path, pages)
    paths = fsc.resolve_paths(tmp_path)
    paths.rendered_final_dir.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (1600, 900), color=(240, 220, 200, 128)).save(paths.default_background_path)

    with pytest.raises(ValueError, match="透明度"):
        fsc.write_final_images(tmp_path, document, font_path=_FONT_PATH, run_ocr_check=False)


def test_write_final_images_rejects_missing_master_layout(tmp_path):
    pages = [_simple_page(1)]
    document = _document(pages)
    write_lesson_pages_json(tmp_path / "editable" / "lesson_pages.json", document)
    _write_asset(tmp_path, 1)
    _write_background(tmp_path)
    # prepare-final-image-packageを実行しない（MASTER_LAYOUT.json不在）。

    with pytest.raises(ValueError, match="MASTER_LAYOUT.json"):
        fsc.write_final_images(tmp_path, document, font_path=_FONT_PATH, run_ocr_check=False)


def test_write_final_images_rejects_missing_package_manifest(tmp_path):
    pages = [_simple_page(1)]
    document = _prepare_package(tmp_path, pages)
    _write_background(tmp_path)
    fip.resolve_paths(tmp_path).package_manifest_path.unlink()

    with pytest.raises(ValueError, match="package_manifest.json"):
        fsc.write_final_images(tmp_path, document, font_path=_FONT_PATH, run_ocr_check=False)


def test_write_final_images_rejects_stale_lesson_pages(tmp_path):
    pages = [_simple_page(1)]
    document = _prepare_package(tmp_path, pages)
    _write_background(tmp_path)

    # 本文ブラッシュアップ後、final_image_packageを再生成しないまま本文を書き換える。
    pages[0].body = pages[0].body + "\n: 追記"
    write_lesson_pages_json(tmp_path / "editable" / "lesson_pages.json", _document(pages))

    loaded = fsc.load_and_validate(tmp_path, _document(pages), font_path=_FONT_PATH)
    assert loaded.errors
    assert any("lesson_pages.json" in e for e in loaded.errors)


def test_write_final_images_rejects_missing_page_spec(tmp_path):
    pages = [_simple_page(1), _simple_page(2)]
    document = _prepare_package(tmp_path, pages)
    _write_background(tmp_path)
    fsc.resolve_paths(tmp_path).pages_dir.joinpath("page_002.json").unlink()

    with pytest.raises(ValueError, match="page_no=2"):
        fsc.write_final_images(tmp_path, document, font_path=_FONT_PATH, run_ocr_check=False)


def test_write_final_images_rejects_extra_page_spec_not_in_lesson_pages(tmp_path):
    pages = [_simple_page(1)]
    document = _prepare_package(tmp_path, pages)
    _write_background(tmp_path)
    paths = fsc.resolve_paths(tmp_path)
    # page_002.jsonという余分なファイルを紛れ込ませる（lesson_pages.jsonにpage_no=2は存在しない）。
    (paths.pages_dir / "page_002.json").write_text((paths.pages_dir / "page_001.json").read_text(encoding="utf-8"), encoding="utf-8")

    with pytest.raises(ValueError, match="存在しないページ仕様"):
        fsc.write_final_images(tmp_path, document, font_path=_FONT_PATH, run_ocr_check=False)


def test_write_final_images_rejects_text_snapshot_mismatch(tmp_path):
    pages = [_simple_page(1)]
    document = _prepare_package(tmp_path, pages)
    _write_background(tmp_path)
    paths = fsc.resolve_paths(tmp_path)
    text_path = paths.text_dir / "page_001.json"
    data = json.loads(text_path.read_text(encoding="utf-8"))
    data["title"] = "改変されたタイトル"
    text_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="page_no=1"):
        fsc.write_final_images(tmp_path, document, font_path=_FONT_PATH, run_ocr_check=False)


def test_write_final_images_rejects_font_not_found(tmp_path):
    pages = [_simple_page(1)]
    document = _prepare_package(tmp_path, pages)
    _write_background(tmp_path)

    with pytest.raises(ValueError, match="フォント"):
        fsc.write_final_images(tmp_path, document, font_path=str(tmp_path / "no_such_font.ttf"))


# --- オーバーフロー（省略・切り詰めをせず失敗させる） -------------------------------------------------


def test_write_final_images_fails_without_truncation_when_body_impossibly_long(tmp_path):
    long_body = ": T\n" + "\n".join(f": 非常に長い本文行その{i}。" * 20 for i in range(60)) + "\n: ※無断転載禁止（おとスタ）"
    pages = [_simple_page(1, body=long_body)]
    document = _prepare_package(tmp_path, pages)
    _write_background(tmp_path)

    run = fsc.write_final_images(tmp_path, document, font_path=_FONT_PATH, run_ocr_check=False)
    assert run.failed_pages == [1]
    result = run.pages[0]
    assert result.overflow is True
    assert result.truncated is False
    assert result.succeeded is False


# --- source_text_match / notice派生ロジック --------------------------------------------------------


def test_derive_notice_text_prefers_explicit_notice_field():
    snapshot = {"notice": "※既定の注記", "body": "本文"}
    assert fsc._derive_notice_text(snapshot) == "※既定の注記"


def test_derive_notice_text_falls_back_to_trailing_body_line_with_empty_speaker_prefix():
    # 実データと同じ「話者が空文字列の生行(': ※...')」を模した本文スナップショット。
    snapshot = {"notice": "", "body": ": タイトル\n: 本文一行目\n: ※無断転載禁止（おとスタ）"}
    assert fsc._derive_notice_text(snapshot) == "※無断転載禁止（おとスタ）"


def test_derive_notice_text_returns_empty_when_no_notice_present():
    snapshot = {"notice": "", "body": ": タイトル\n: 本文一行目"}
    assert fsc._derive_notice_text(snapshot) == ""


def test_write_final_images_reports_source_text_match_and_no_truncation(tmp_path):
    pages = [_simple_page(1)]
    document = _prepare_package(tmp_path, pages)
    _write_background(tmp_path)

    run = fsc.write_final_images(tmp_path, document, font_path=_FONT_PATH, run_ocr_check=False)
    for r in run.pages:
        assert r.source_text_match is True
        assert r.truncated is False
        assert r.visual["all_regions_visually_rendered"] is True


# --- レポート/比較HTML -------------------------------------------------------------------------


def test_render_final_render_report_json_matches_run(tmp_path):
    pages = [_simple_page(1)]
    document = _prepare_package(tmp_path, pages)
    _write_background(tmp_path)
    run = fsc.write_final_images(tmp_path, document, font_path=_FONT_PATH, run_ocr_check=False)

    report = fsc.render_final_render_report_json(run)
    assert report["succeeded_pages"] == [1]
    assert report["pages"][0]["source_text_match"] is True
    assert report["pages"][0]["overflow"] is False
    assert report["pages"][0]["truncated"] is False
    assert report["pages"][0]["all_regions_visually_rendered"] is True
    assert report["pages"][0]["title_visually_rendered"] is True
    assert report["pages"][0]["body_visually_rendered"] is True


def test_final_comparison_html_is_self_contained(tmp_path):
    pages = [_simple_page(1)]
    document = _prepare_package(tmp_path, pages)
    _write_background(tmp_path)
    run = fsc.write_final_images(tmp_path, document, font_path=_FONT_PATH, run_ocr_check=False)
    paths = fsc.resolve_paths(tmp_path)
    page_specs = {1: json.loads((paths.pages_dir / "page_001.json").read_text(encoding="utf-8"))}

    html_text = fsc.render_final_comparison_html(
        document, run.master_layout, page_specs, run, tmp_path, paths.final_comparison_html_path,
    )
    assert "http://" not in html_text
    assert "https://" not in html_text
    assert "source_text_match" in html_text
    assert "title bbox" in html_text
