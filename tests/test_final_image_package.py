from __future__ import annotations

from PIL import Image

from src import final_image_package as fip
from tests.test_brushup_renderer import _document, _page

_FONT_PATH = None


def _write_asset(output_dir, page_no, size=(1706, 960)):
    assets_dir = output_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    path = assets_dir / f"page_{page_no:03d}.jpeg"
    Image.new("RGB", size, color=(240, 230, 210)).save(path)
    return path


# --- キャンバス正規化 -------------------------------------------------------------------------


def test_analyze_canvas_size_normalizes_16_9_sources_to_1600x900(tmp_path):
    pages = [_page(1), _page(2)]
    for p in pages:
        _write_asset(tmp_path, p.page_no)
    document = _document(pages)

    info = fip.analyze_canvas_size(document, tmp_path)

    assert info["canvas"] == {"width": 1600, "height": 900}
    assert info["standard_ratio"] == "16:9"


def test_analyze_canvas_size_normalizes_4_3_sources(tmp_path):
    pages = [_page(1)]
    _write_asset(tmp_path, 1, size=(1200, 900))
    document = _document(pages)

    info = fip.analyze_canvas_size(document, tmp_path)

    assert info["canvas"] == {"width": 1600, "height": 1200}
    assert info["standard_ratio"] == "4:3"


def test_analyze_canvas_size_falls_back_when_no_images_found(tmp_path):
    document = _document([_page(1, source_image="")])
    info = fip.analyze_canvas_size(document, tmp_path)
    assert info["canvas"] == {"width": 1600, "height": 900}
    assert info["warnings"]


# --- マスターレイアウト -----------------------------------------------------------------------


def _write_lesson_pages(output_dir, document):
    from src.lesson_pages import write_lesson_pages_json

    write_lesson_pages_json(output_dir / "editable" / "lesson_pages.json", document)


def test_build_master_layout_is_identical_regardless_of_page_content_length(tmp_path):
    pages = [_page(1, body=": 短い"), _page(2, body=": " + "長い本文。" * 40)]
    for p in pages:
        _write_asset(tmp_path, p.page_no)
    document = _document(pages)
    _write_lesson_pages(tmp_path, document)

    master_layout = fip.build_master_layout(document, tmp_path, tmp_path / "editable" / "lesson_pages.json")

    assert master_layout["master_id"] == fip.MASTER_ID
    assert master_layout["canvas"] == {"width": 1600, "height": 900, "background_color": master_layout["theme"]["background_base"]}
    card = master_layout["regions"]["content_card"]
    assert (card["x"], card["y"], card["width"], card["height"]) == (56, 200, 1488, 590)
    assert "source_lesson_pages_sha256" in master_layout


def test_build_master_layout_scales_regions_for_non_baseline_canvas(tmp_path):
    pages = [_page(1)]
    _write_asset(tmp_path, 1, size=(1200, 900))  # 4:3 -> canvas 1600x1200
    document = _document(pages)
    _write_lesson_pages(tmp_path, document)

    master_layout = fip.build_master_layout(document, tmp_path, tmp_path / "editable" / "lesson_pages.json")

    assert master_layout["canvas"]["width"] == 1600
    assert master_layout["canvas"]["height"] == 1200
    # 高さ方向は1200/900倍にスケールされているはず(content_cardのy,heightが基準値と異なる)。
    card = master_layout["regions"]["content_card"]
    assert card["y"] != 200
    assert card["height"] != 590


def test_check_master_layout_freshness_detects_missing_hash():
    assert fip.check_master_layout_freshness({}, current_lesson_pages_sha256="abc") is not None


def test_check_master_layout_freshness_detects_mismatch():
    err = fip.check_master_layout_freshness(
        {"source_lesson_pages_sha256": "old"}, current_lesson_pages_sha256="new"
    )
    assert err is not None


def test_check_master_layout_freshness_passes_when_matching():
    err = fip.check_master_layout_freshness(
        {"source_lesson_pages_sha256": "same"}, current_lesson_pages_sha256="same"
    )
    assert err is None


# --- 本文の区分（notice/emphasis/2段組み検出） --------------------------------------------------


def test_analyze_page_text_detects_notice_line_and_skips_title_duplicate_line():
    page = _page(1, title="タイトル1", body="タイトル1\n本文の1行目\n本文の2行目\n※無断転載禁止（おとスタ）")
    layout = fip.analyze_page_text(page)
    assert layout.content_start == 1
    assert layout.has_notice is True
    assert layout.content_end == 3  # 0=title dup, 1,2=content, 3=notice


def test_analyze_page_text_detects_circle_emphasis_marker():
    page = _page(1, title="T", body="T\n参考にするのも◎\n通常の行")
    layout = fip.analyze_page_text(page)
    assert layout.emphasis_indices == [1]


def test_analyze_page_text_detects_two_column_markers_and_splits_correctly():
    body = "T\n導入\n例1）キャラA\n・特徴1\n・特徴2\n例2）キャラB\n・特徴3\n※無断転載禁止（おとスタ）"
    page = _page(1, title="T", body=body)
    layout = fip.analyze_page_text(page)
    assert layout.two_column_range is not None
    start, end = layout.two_column_range
    assert start == 2  # 例1）の段落index
    assert layout.two_column_split_at == 5  # 例2）の段落index
    assert end == layout.content_end


def test_analyze_page_text_no_two_column_when_only_one_marker():
    body = "T\n例1）キャラA\n・特徴1\n※無断転載禁止（おとスタ）"
    page = _page(1, title="T", body=body)
    layout = fip.analyze_page_text(page)
    assert layout.two_column_range is None


def test_split_body_and_notice_preserves_content_and_extracts_last_notice_line():
    body = "本文1行目\n本文2行目\n※無断転載禁止（おとスタ）"
    main, notice = fip.split_body_and_notice(body)
    assert main == "本文1行目\n本文2行目"
    assert notice == "※無断転載禁止（おとスタ）"


def test_split_body_and_notice_returns_full_body_when_no_notice_line():
    body = "本文1行目\n本文2行目"
    main, notice = fip.split_body_and_notice(body)
    assert main == body
    assert notice == ""


def test_split_body_and_notice_detects_notice_on_empty_speaker_prefixed_line():
    # 実データと同じ「話者が空文字列の生行(': ※...')」形式。空話者の区切り文字だけで
    # 判定すると検出できないバグ（実データ11ページで発生していた）の回帰テスト。
    body = ": 本文1行目\n: 本文2行目\n: ※無断転載禁止（おとスタ）"
    main, notice = fip.split_body_and_notice(body)
    assert main == ": 本文1行目\n: 本文2行目"
    assert notice == "※無断転載禁止（おとスタ）"


# --- ページ仕様生成 ---------------------------------------------------------------------------


def test_build_page_spec_single_column_segments_emphasis_into_separate_blocks():
    body = "T\n導入行\n参考にするのも◎\n補足行\n※無断転載禁止（おとスタ）"
    page = _page(1, title="T", body=body)
    spec = fip.build_page_spec(page, "hash123", _FONT_PATH)

    assert spec["content_layout"]["type"] == "single_column"
    assert spec["master_layout"] == fip.MASTER_ID
    assert spec["source_lesson_pages_sha256"] == "hash123"
    block_types = [b["style"]["font_weight"] for b in spec["content_layout"]["blocks"]]
    assert "bold" in block_types  # 強調ブロックが分離されている
    assert spec["notice"]["line_range"] == [4, None]


def test_build_page_spec_two_column_page_produces_single_columns_block():
    body = "T\n導入\n例1）キャラA\n・特徴1\n例2）キャラB\n・特徴2\n※無断転載禁止（おとスタ）"
    page = _page(1, title="T", body=body)
    spec = fip.build_page_spec(page, "hash123", _FONT_PATH)

    assert spec["content_layout"]["type"] == "two_column"
    columns_blocks = [b for b in spec["content_layout"]["blocks"] if b.get("columns") == 2]
    assert len(columns_blocks) == 1
    assert 0.35 <= columns_blocks[0]["column_ratio"] <= 0.65


def test_build_page_spec_emphasis_matches_are_real_substrings_of_body():
    body = "T\n参考にするのも◎\n※無断転載禁止（おとスタ）"
    page = _page(1, title="T", body=body)
    spec = fip.build_page_spec(page, "hash", _FONT_PATH)
    for rule in spec["emphasis"]:
        assert rule["match"] in getattr(page, rule["source"])


# --- 検証 ---------------------------------------------------------------------------------


def _valid_master_layout(sha="hash123"):
    return {
        "master_id": fip.MASTER_ID, "source_lesson_pages_sha256": sha,
        "regions": {
            "title_region": {}, "content_card": {}, "notice_region": {}, "page_number_region": {},
        },
    }


def test_validate_page_spec_accepts_generated_spec():
    page = _page(1, title="T", body="T\n本文\n※無断転載禁止（おとスタ）")
    master_layout = _valid_master_layout()
    spec = fip.build_page_spec(page, "hash123", _FONT_PATH)
    errors = fip.validate_page_spec(
        spec, expected_page_no=1, expected_source_image=page.source_image, master_layout=master_layout, lesson_page=page,
    )
    assert errors == []


def test_validate_page_spec_rejects_wrong_page_no():
    page = _page(1, title="T", body="T\n本文\n※無断転載禁止（おとスタ）")
    spec = fip.build_page_spec(page, "hash123", _FONT_PATH)
    errors = fip.validate_page_spec(
        spec, expected_page_no=2, expected_source_image=page.source_image, master_layout=_valid_master_layout(), lesson_page=page,
    )
    assert any("page_no" in e for e in errors)


def test_validate_page_spec_rejects_stale_lesson_pages_hash():
    page = _page(1, title="T", body="T\n本文\n※無断転載禁止（おとスタ）")
    spec = fip.build_page_spec(page, "old_hash", _FONT_PATH)
    errors = fip.validate_page_spec(
        spec, expected_page_no=1, expected_source_image=page.source_image,
        master_layout=_valid_master_layout(sha="new_hash"), lesson_page=page,
    )
    assert any("source_lesson_pages_sha256" in e for e in errors)


def test_validate_page_spec_rejects_emphasis_match_not_found_in_current_body():
    page = _page(1, title="T", body="T\n本文\n※無断転載禁止（おとスタ）")
    spec = fip.build_page_spec(page, "hash123", _FONT_PATH)
    spec["emphasis"].append({"source": "body", "match": "存在しない一節", "style": "strong"})
    errors = fip.validate_page_spec(
        spec, expected_page_no=1, expected_source_image=page.source_image, master_layout=_valid_master_layout(), lesson_page=page,
    )
    assert any("emphasis" in e for e in errors)


def test_validate_page_spec_rejects_master_coordinate_override_attempt():
    page = _page(1, title="T", body="T\n本文\n※無断転載禁止（おとスタ）")
    spec = fip.build_page_spec(page, "hash123", _FONT_PATH)
    spec["content_layout"]["content_card"] = {"x": 0, "y": 0, "width": 10, "height": 10}
    errors = fip.validate_page_spec(
        spec, expected_page_no=1, expected_source_image=page.source_image, master_layout=_valid_master_layout(), lesson_page=page,
    )
    assert any("content_card" in e for e in errors)


def test_validate_page_spec_rejects_body_text_embedded_directly():
    page = _page(1, title="T", body="T\n本文\n※無断転載禁止（おとスタ）")
    spec = fip.build_page_spec(page, "hash123", _FONT_PATH)
    spec["content_layout"]["blocks"][0]["text"] = "複製した本文"
    errors = fip.validate_page_spec(
        spec, expected_page_no=1, expected_source_image=page.source_image, master_layout=_valid_master_layout(), lesson_page=page,
    )
    assert any("複製" in e for e in errors)


def test_validate_text_snapshot_accepts_matching_snapshot():
    page = _page(1, title="T", body="T\n本文\n※無断転載禁止（おとスタ）", summary="要約")
    snapshot = fip.build_text_snapshot(page, "hash123")
    errors = fip.validate_text_snapshot(snapshot, expected_page_no=1, lesson_page=page, lesson_pages_sha256_value="hash123")
    assert errors == []


def test_validate_text_snapshot_rejects_body_mismatch():
    page = _page(1, title="T", body="T\n本文\n※無断転載禁止（おとスタ）")
    snapshot = fip.build_text_snapshot(page, "hash123")
    snapshot["body"] = "改変された本文"
    errors = fip.validate_text_snapshot(snapshot, expected_page_no=1, lesson_page=page, lesson_pages_sha256_value="hash123")
    assert any("body" in e for e in errors)


def test_validate_master_layout_requires_all_regions():
    errors = fip.validate_master_layout({"schema_version": 1, "master_id": fip.MASTER_ID, "regions": {}}, expected_page_numbers=[1])
    assert len(errors) >= 4


def test_validate_master_layout_accepts_well_formed_layout():
    ml = _valid_master_layout()
    ml["schema_version"] = 1
    errors = fip.validate_master_layout(ml, expected_page_numbers=[1])
    assert errors == []


# --- asset_manifest / package_manifest ---------------------------------------------------------


def test_build_asset_manifest_includes_sha256_and_dimensions(tmp_path):
    _write_asset(tmp_path, 1)
    document = _document([_page(1)])
    manifest = fip.build_asset_manifest(document, tmp_path)
    assert manifest["assets"][0]["width"] == 1706
    assert manifest["assets"][0]["height"] == 960
    assert len(manifest["assets"][0]["sha256"]) == 64


def test_build_package_manifest_reports_identical_content_card_across_pages(tmp_path):
    pages = [_page(1), _page(2)]
    for p in pages:
        _write_asset(tmp_path, p.page_no)
    document = _document(pages)
    _write_lesson_pages(tmp_path, document)
    master_layout = fip.build_master_layout(document, tmp_path, tmp_path / "editable" / "lesson_pages.json")
    manifest = fip.build_package_manifest(document, master_layout, [{"page_no": 1}, {"page_no": 2}])
    assert manifest["total_pages"] == 2
    assert manifest["completed_pages"] == 2
    assert manifest["content_card"] == {
        "x": master_layout["regions"]["content_card"]["x"], "y": master_layout["regions"]["content_card"]["y"],
        "width": master_layout["regions"]["content_card"]["width"], "height": master_layout["regions"]["content_card"]["height"],
    }
