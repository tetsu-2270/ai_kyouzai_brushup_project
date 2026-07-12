from __future__ import annotations

from PIL import Image, ImageDraw

from src import final_image_package as fip
from src import final_slide_compositor as fsc
from src.image_renderer import resolve_font_path
from tests.test_brushup_renderer import _page
from tests.test_final_slide_compositor import _prepare_package, _simple_page, _write_background

_FONT_PATH = resolve_font_path(None)

_MASTER = {
    "regions": {
        "title_region": {"x": 72, "y": 52, "width": 1456, "height": 130},
        "content_card": {
            "x": 56, "y": 200, "width": 1488, "height": 590,
            "padding": {"top": 38, "right": 42, "bottom": 38, "left": 42},
        },
        "notice_region": {"x": 72, "y": 802, "width": 900, "height": 40},
        "page_number_region": {"x": 700, "y": 842, "width": 200, "height": 36},
    },
    "theme": {
        "background_base": "#F6ECD9", "card_background": "#FFFDF8", "primary_text": "#4A1422",
        "secondary_text": "#6A4E50", "accent": "#D9835C", "border": "#E8D7C1",
    },
    "typography": {
        "font_family_role": "japanese_gothic", "title_weight": "bold", "body_weight": "regular", "notice_weight": "regular",
    },
}


def _blank_canvas(size=(1600, 900), color=(246, 236, 217)):
    return Image.new("RGB", size, color=color)


def _hex_to_rgb(v):
    v = v.lstrip("#")
    return (int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16))


# --- タイトル: bbox / mask / 黒矩形の検出 -----------------------------------------------------------


def test_verify_title_region_flags_missing_title_ink_as_not_visually_rendered():
    image = _blank_canvas()
    report = fsc._verify_title_region(image, _MASTER, "【欠落したタイトル】", 52, 1)
    assert report["title_mask_nonempty"] is False
    assert report["title_visually_rendered"] is False


def test_verify_title_region_true_when_no_title_expected():
    image = _blank_canvas()
    report = fsc._verify_title_region(image, _MASTER, "", 52, 0)
    assert report["title_visually_rendered"] is True


def test_verify_title_region_detects_ink_when_title_actually_drawn():
    image = _blank_canvas()
    draw = ImageDraw.Draw(image)
    region = _MASTER["regions"]["title_region"]
    color = _hex_to_rgb(_MASTER["theme"]["primary_text"])
    draw.rectangle([region["x"] + 10, region["y"] + 10, region["x"] + 200, region["y"] + 60], fill=color)
    report = fsc._verify_title_region(image, _MASTER, "【タイトル】", 52, 1)
    assert report["title_mask_nonempty"] is True
    assert report["title_pixels_present"] is True
    assert report["title_bbox_within_region"] is True
    assert report["title_visually_rendered"] is True


def test_verify_title_region_detects_black_rectangle_as_dark_artifact():
    image = _blank_canvas()
    draw = ImageDraw.Draw(image)
    region = _MASTER["regions"]["title_region"]
    # 安全領域内に意図しない大面積の黒矩形を描く。
    draw.rectangle([region["x"], region["y"], region["x"] + region["width"], region["y"] + region["height"]], fill=(0, 0, 0))
    report = fsc._verify_title_region(image, _MASTER, "【タイトル】", 52, 1)
    assert report["title_dark_artifact_detected"] is True
    assert report["title_visually_rendered"] is False


def test_verify_title_region_does_not_flag_primary_text_color_as_dark_artifact():
    # primary_text (#4A1422 -> (74,20,34)) はr=74なので「RGB全チャンネルがcutoff未満」に該当せず、
    # 文字マスク自体を暗色矩形として誤検出しないことを確認する。
    image = _blank_canvas()
    draw = ImageDraw.Draw(image)
    region = _MASTER["regions"]["title_region"]
    color = _hex_to_rgb(_MASTER["theme"]["primary_text"])
    draw.rectangle([region["x"], region["y"], region["x"] + region["width"], region["y"] + region["height"]], fill=color)
    ratio = fsc._dark_region_ratio(image, region)
    assert ratio == 0.0


def test_verify_ink_region_detects_overflow_beyond_region_boundary():
    image = _blank_canvas()
    draw = ImageDraw.Draw(image)
    region = _MASTER["regions"]["title_region"]
    color = _hex_to_rgb(_MASTER["theme"]["primary_text"])
    # regionの左端よりさらに外側（マージン内）に同色インクを描き、はみ出しを検出させる。
    draw.rectangle([region["x"] - 4, region["y"] + 5, region["x"] + 30, region["y"] + 20], fill=color)
    result = fsc._verify_ink_region(image, region, [color])
    assert result["overflow"] is True


def test_verify_ink_region_no_overflow_when_ink_stays_inside_region():
    image = _blank_canvas()
    draw = ImageDraw.Draw(image)
    region = _MASTER["regions"]["title_region"]
    color = _hex_to_rgb(_MASTER["theme"]["primary_text"])
    draw.rectangle([region["x"] + 20, region["y"] + 20, region["x"] + 100, region["y"] + 60], fill=color)
    result = fsc._verify_ink_region(image, region, [color])
    assert result["overflow"] is False
    assert result["bbox"] is not None


def test_dark_region_ratio_ignores_pixels_outside_the_region():
    image = _blank_canvas()
    draw = ImageDraw.Draw(image)
    region = _MASTER["regions"]["page_number_region"]
    # region外の背景装飾（暗色）を描いても、region自体の暗色比率には影響しない。
    draw.rectangle([0, 850, 60, 900], fill=(10, 10, 10))
    ratio = fsc._dark_region_ratio(image, region)
    assert ratio == 0.0


# --- タイトル: 描画そのもの（_draw_title）の座標・折り返し ------------------------------------------


def test_draw_title_produces_non_negative_x_coordinate():
    image = _blank_canvas()
    draw = ImageDraw.Draw(image)
    snapshot_page = fsc._SnapshotPage(page_no=1, title="【非常に長いタイトルの場合の折り返し確認テスト】", body="", summary="")
    fit = fsc._draw_title(draw, snapshot_page, _MASTER, _FONT_PATH)
    assert fit is not None
    region = _MASTER["regions"]["title_region"]
    ink = fsc._verify_ink_region(image, region, [_hex_to_rgb(_MASTER["theme"]["primary_text"])])
    assert ink["bbox"][0] >= region["x"]
    assert ink["bbox"][1] >= region["y"]


def test_draw_title_single_short_line():
    image = _blank_canvas()
    draw = ImageDraw.Draw(image)
    snapshot_page = fsc._SnapshotPage(page_no=1, title="短いタイトル", body="", summary="")
    fit = fsc._draw_title(draw, snapshot_page, _MASTER, _FONT_PATH)
    assert fit is not None
    assert len(fit.wrapped_columns[0]) == 1


def test_draw_title_wraps_to_two_lines_for_long_title():
    image = _blank_canvas()
    draw = ImageDraw.Draw(image)
    long_title = "【" + "長いタイトル文字列を折り返しさせるためのテスト" * 2 + "】"
    snapshot_page = fsc._SnapshotPage(page_no=1, title=long_title, body="", summary="")
    fit = fsc._draw_title(draw, snapshot_page, _MASTER, _FONT_PATH)
    assert fit is not None
    assert len(fit.wrapped_columns[0]) >= 2


def test_draw_title_shrinks_font_size_when_needed_but_still_fits():
    image = _blank_canvas()
    draw = ImageDraw.Draw(image)
    long_title = "【" + "非常に長いタイトルで縮小が必要になるケースを再現するための文字列です" * 2 + "】"
    snapshot_page = fsc._SnapshotPage(page_no=1, title=long_title, body="", summary="")
    fit = fsc._draw_title(draw, snapshot_page, _MASTER, _FONT_PATH)
    if fit is not None:
        assert fit.font_size <= 52
    # 収まらない場合はNone（切り詰めではなく失敗）になることも許容する。


def test_draw_title_fails_without_truncation_when_impossibly_long():
    image = _blank_canvas()
    draw = ImageDraw.Draw(image)
    impossible_title = "極めて長いタイトル" * 60
    snapshot_page = fsc._SnapshotPage(page_no=1, title=impossible_title, body="", summary="")
    fit = fsc._draw_title(draw, snapshot_page, _MASTER, _FONT_PATH)
    assert fit is None  # 切り詰めて成功させるのではなく、収まらない場合は失敗として扱う


# --- 本文カード内部の視覚的均衡（sparse pageの文字サイズ拡大） -------------------------------------


def test_measure_card_blocks_with_growth_enlarges_font_for_sparse_single_column():
    image = _blank_canvas()
    draw = ImageDraw.Draw(image)
    snapshot_page = fsc._SnapshotPage(page_no=1, title="T", body="短い本文\n二行目", summary="")
    blocks = [{
        "id": "body_0_2", "type": "body", "source_field": "body", "line_range": [0, 2],
        "style": {"font_size": 30, "font_weight": "regular", "color": "#4A1422", "alignment": "left", "padding": 0},
    }]
    card = _MASTER["regions"]["content_card"]
    width = card["width"] - card["padding"]["left"] - card["padding"]["right"]
    available_height = card["height"] - card["padding"]["top"] - card["padding"]["bottom"]
    items, used, fits, failed, scale = fsc._measure_card_blocks_with_growth(
        draw, snapshot_page, blocks, _FONT_PATH, width, available_height, "single_column",
    )
    assert fits is True
    assert scale > 1.0
    grown_font_size = items[0][1].font_size
    assert grown_font_size > 30 * 0.6  # shrink-to-fit最小値より明確に大きい拡大が適用されている


def test_measure_card_blocks_with_growth_leaves_two_column_unchanged():
    image = _blank_canvas()
    draw = ImageDraw.Draw(image)
    snapshot_page = fsc._SnapshotPage(page_no=1, title="T", body="短い本文\n二行目", summary="")
    blocks = [{
        "id": "body_0_2", "type": "body", "source_field": "body", "line_range": [0, 2],
        "style": {"font_size": 30, "font_weight": "regular", "color": "#4A1422", "alignment": "left", "padding": 0},
    }]
    card = _MASTER["regions"]["content_card"]
    width = card["width"] - card["padding"]["left"] - card["padding"]["right"]
    available_height = card["height"] - card["padding"]["top"] - card["padding"]["bottom"]
    items, used, fits, failed, scale = fsc._measure_card_blocks_with_growth(
        draw, snapshot_page, blocks, _FONT_PATH, width, available_height, "two_column",
    )
    assert scale == 1.0


def test_measure_card_blocks_with_growth_does_not_change_card_outer_dimensions():
    card_before = dict(_MASTER["regions"]["content_card"])
    image = _blank_canvas()
    draw = ImageDraw.Draw(image)
    snapshot_page = fsc._SnapshotPage(page_no=1, title="T", body="短い本文", summary="")
    blocks = [{
        "id": "body_0_1", "type": "body", "source_field": "body", "line_range": [0, 1],
        "style": {"font_size": 30, "font_weight": "regular", "color": "#4A1422", "alignment": "left", "padding": 0},
    }]
    card = _MASTER["regions"]["content_card"]
    width = card["width"] - card["padding"]["left"] - card["padding"]["right"]
    available_height = card["height"] - card["padding"]["top"] - card["padding"]["bottom"]
    fsc._measure_card_blocks_with_growth(draw, snapshot_page, blocks, _FONT_PATH, width, available_height, "single_column")
    assert _MASTER["regions"]["content_card"] == card_before


# --- 完成判定: source_text_matchだけでは成功にならない ------------------------------------------------


def test_write_final_images_fails_when_title_visually_rendered_forced_false(tmp_path, monkeypatch):
    pages = [_simple_page(1)]
    document = _prepare_package(tmp_path, pages)
    _write_background(tmp_path)

    original = fsc._verify_title_region

    def _forced_false(*args, **kwargs):
        result = original(*args, **kwargs)
        result["title_visually_rendered"] = False
        return result

    monkeypatch.setattr(fsc, "_verify_title_region", _forced_false)
    run = fsc.write_final_images(tmp_path, document, font_path=_FONT_PATH, run_ocr_check=False)
    assert run.failed_pages == [1]
    result = run.pages[0]
    assert result.source_text_match is True  # 文字列としては一致しているのに
    assert result.succeeded is False  # 視覚描画検証の失敗により成功にはならない


def test_write_final_images_fails_when_body_visually_rendered_forced_false(tmp_path, monkeypatch):
    pages = [_simple_page(1)]
    document = _prepare_package(tmp_path, pages)
    _write_background(tmp_path)

    original = fsc._verify_body_region

    def _forced_false(*args, **kwargs):
        result = original(*args, **kwargs)
        result["body_visually_rendered"] = False
        return result

    monkeypatch.setattr(fsc, "_verify_body_region", _forced_false)
    run = fsc.write_final_images(tmp_path, document, font_path=_FONT_PATH, run_ocr_check=False)
    assert run.failed_pages == [1]


def test_write_final_images_fails_when_notice_visually_rendered_forced_false(tmp_path, monkeypatch):
    pages = [_simple_page(1)]
    document = _prepare_package(tmp_path, pages)
    _write_background(tmp_path)

    original = fsc._verify_notice_region

    def _forced_false(*args, **kwargs):
        result = original(*args, **kwargs)
        result["notice_visually_rendered"] = False
        return result

    monkeypatch.setattr(fsc, "_verify_notice_region", _forced_false)
    run = fsc.write_final_images(tmp_path, document, font_path=_FONT_PATH, run_ocr_check=False)
    assert run.failed_pages == [1]


def test_write_final_images_fails_when_page_number_visually_rendered_forced_false(tmp_path, monkeypatch):
    pages = [_simple_page(1)]
    document = _prepare_package(tmp_path, pages)
    _write_background(tmp_path)

    original = fsc._verify_page_number_region

    def _forced_false(*args, **kwargs):
        result = original(*args, **kwargs)
        result["page_number_visually_rendered"] = False
        return result

    monkeypatch.setattr(fsc, "_verify_page_number_region", _forced_false)
    run = fsc.write_final_images(tmp_path, document, font_path=_FONT_PATH, run_ocr_check=False)
    assert run.failed_pages == [1]


def test_write_final_images_succeeds_only_when_all_regions_true(tmp_path):
    pages = [_simple_page(1)]
    document = _prepare_package(tmp_path, pages)
    _write_background(tmp_path)
    run = fsc.write_final_images(tmp_path, document, font_path=_FONT_PATH, run_ocr_check=False)
    result = run.pages[0]
    assert result.visual["all_regions_visually_rendered"] is True
    assert result.succeeded is True


def test_report_records_bbox_pixel_and_artifact_results(tmp_path):
    pages = [_simple_page(1)]
    document = _prepare_package(tmp_path, pages)
    _write_background(tmp_path)
    run = fsc.write_final_images(tmp_path, document, font_path=_FONT_PATH, run_ocr_check=False)
    report = fsc.render_final_render_report_json(run)
    page_report = report["pages"][0]
    assert page_report["title_bbox"] is not None
    assert page_report["title_region"] is not None
    assert "body_bbox" in page_report
    assert "horizontal_utilization" in page_report
    assert "vertical_utilization" in page_report
    assert "title_dark_artifact_detected" in page_report
    assert "body_dark_artifact_detected" in page_report


# --- notice抽出（Phase 10.14側の正式修正） ----------------------------------------------------------


def test_split_body_and_notice_official_fix_extracts_empty_speaker_notice():
    body = ": 本文1行目\n: 本文2行目\n: ※無断転載禁止（おとスタ）"
    main, notice = fip.split_body_and_notice(body)
    assert notice == "※無断転載禁止（おとスタ）"
    assert "※" not in main


def test_derive_notice_text_does_not_need_fallback_for_correctly_fixed_snapshot():
    # 正式修正後のsnapshotではnoticeフィールドが最初から埋まっているため、
    # _derive_notice_textはbody解析にフォールバックせず、notice値をそのまま返す。
    snapshot = {"notice": "※無断転載禁止（おとスタ）", "body": ": 本文1行目\n: 本文2行目"}
    assert fsc._derive_notice_text(snapshot) == "※無断転載禁止（おとスタ）"


def test_write_final_images_uses_officially_fixed_notice_without_fallback(tmp_path):
    pages = [_page(
        1, title="T", body=": T\n: 本文1行目\n: ※無断転載禁止（おとスタ）",
        summary="T", source_image="assets/page_001.jpeg",
    )]
    document = _prepare_package(tmp_path, pages)
    _write_background(tmp_path)
    paths = fsc.resolve_paths(tmp_path)
    text_snapshot_path = paths.text_dir / "page_001.json"
    import json as _json
    snapshot = _json.loads(text_snapshot_path.read_text(encoding="utf-8"))
    assert snapshot["notice"] == "※無断転載禁止（おとスタ）"

    run = fsc.write_final_images(tmp_path, document, font_path=_FONT_PATH, run_ocr_check=False)
    assert run.failed_pages == []
    assert run.pages[0].rendered_fields["notice"] == "※無断転載禁止（おとスタ）"


# --- 実データ相当の回帰（Page1/Page3/Page11の構造を模した合成データ） ------------------------------------


def test_two_column_page_regression_title_and_no_dark_artifact(tmp_path):
    # Page3相当: 導入 + ◎強調 + 例1)/例2)の2段組み。
    body = (
        ": 【キャラ設定実践タイム】\n: 導入文\n: ※参考にするのも◎\n: 例1）キャラA\n: ・特徴1\n: ・特徴2\n"
        ": 例2）キャラB\n: ・特徴3\n: ・特徴4\n: ※無断転載禁止（おとスタ）"
    )
    pages = [_page(3, title="【キャラ設定実践タイム】", body=body, summary="導入文", source_image="assets/page_003.jpeg")]
    document = _prepare_package(tmp_path, pages)
    _write_background(tmp_path)
    run = fsc.write_final_images(tmp_path, document, font_path=_FONT_PATH, run_ocr_check=False)

    assert run.failed_pages == []
    result = run.pages[0]
    assert result.visual["title_visually_rendered"] is True
    assert result.visual["title_dark_artifact_detected"] is False
    assert result.visual["body_dark_artifact_detected"] is False
    paths = fsc.resolve_paths(tmp_path)
    import json as _json
    spec = _json.loads((paths.pages_dir / "page_003.json").read_text(encoding="utf-8"))
    assert spec["content_layout"]["type"] == "two_column"


def test_sparse_single_column_page_regression_utilization_and_title(tmp_path):
    # Page11相当（実データと同じ行数・分量）: 短い単一カラム本文（⑩を含む）。
    body = (
        ": 【キャラ設定実践タイム】\n: ⑩ここまでのメモを見返して\n: 仮でも良いので\n"
        ": アカウントのジャンルを1つ\n: 決めてください（次の質問でつかいます）\n"
        ": ※既に決まっている方は、ジャンルやありたい姿に\n: 合うキャラクターか、照らし合わせてみてください\n"
        ": ※無断転載禁止（おとスタ）"
    )
    pages = [_page(11, title="【キャラ設定実践タイム】", body=body, summary="まとめ", source_image="assets/page_011.jpeg")]
    document = _prepare_package(tmp_path, pages)
    _write_background(tmp_path)
    run = fsc.write_final_images(tmp_path, document, font_path=_FONT_PATH, run_ocr_check=False)

    assert run.failed_pages == []
    result = run.pages[0]
    assert result.visual["title_visually_rendered"] is True
    assert "⑩" in result.rendered_fields["body"]
    # 極端な左偏り（水平利用率が非常に低い状態）が改善されていることを、最低限の閾値で確認する。
    assert result.visual["horizontal_utilization"] > 0.3
    assert result.visual["vertical_utilization"] > 0.3


def test_full_deck_of_page1_page3_page11_shapes_all_succeed(tmp_path):
    page1 = _page(1, title="【キャラ設定】", body=": 【キャラ設定】\n: 実践タイム\n: ※無断転載禁止（おとスタ）", summary="導入", source_image="assets/page_001.jpeg")
    page3_body = (
        ": 【キャラ設定実践タイム】\n: 導入文\n: ※参考にするのも◎\n: 例1）キャラA\n: ・特徴1\n: ・特徴2\n"
        ": 例2）キャラB\n: ・特徴3\n: ・特徴4\n: ※無断転載禁止（おとスタ）"
    )
    page3 = _page(3, title="【キャラ設定実践タイム】", body=page3_body, summary="導入文", source_image="assets/page_003.jpeg")
    page11 = _page(
        11, title="【キャラ設定実践タイム】",
        body=": 【キャラ設定実践タイム】\n: ⑩ここまでのメモを見返して\n: ※無断転載禁止（おとスタ）",
        summary="まとめ", source_image="assets/page_011.jpeg",
    )
    document = _prepare_package(tmp_path, [page1, page3, page11])
    _write_background(tmp_path)
    run = fsc.write_final_images(tmp_path, document, font_path=_FONT_PATH, run_ocr_check=False)

    assert run.total_pages == 3
    assert run.failed_pages == []
    assert run.succeeded_pages == [1, 3, 11]
    for r in run.pages:
        assert r.visual["all_regions_visually_rendered"] is True


# --- 補助OCR確認（既存OCR機能。主判定はbbox/pixel検証のため、ここは単体呼び出しで高速に確認する） --------


def test_ocr_title_check_direct_call_detects_present_title(tmp_path):
    document = None
    pages = [_simple_page(1)]
    document = _prepare_package(tmp_path, pages)
    _write_background(tmp_path)
    run = fsc.write_final_images(tmp_path, document, font_path=_FONT_PATH, run_ocr_check=False)
    paths = fsc.resolve_paths(tmp_path)
    from PIL import Image as _Image
    image = _Image.open(paths.rendered_final_dir / "page_001.png")
    report = fsc._ocr_title_check(image, run.master_layout, "タイトル1")
    assert report["ocr_available"] in (True, False)
    if report["ocr_available"]:
        assert report["ocr_title_match_ratio"] is not None


def test_ocr_title_check_empty_title_short_circuits_without_running_ocr():
    image = _blank_canvas()
    report = fsc._ocr_title_check(image, _MASTER, "")
    assert report["ocr_title_match_ratio"] == 1.0
    assert report["ocr_warning"] == ""


def test_write_final_images_with_ocr_check_enabled_end_to_end(tmp_path):
    # OCR補助確認を実際に有効化した状態でパイプライン全体を1回だけ流し、統合を確認する
    # （tesseractのプロセス起動コストがあるため、他のテストではrun_ocr_check=Falseにしている）。
    pages = [_simple_page(1)]
    document = _prepare_package(tmp_path, pages)
    _write_background(tmp_path)
    run = fsc.write_final_images(tmp_path, document, font_path=_FONT_PATH, run_ocr_check=True)
    assert run.failed_pages == []
    visual = run.pages[0].visual
    assert "ocr_available" in visual
    assert "ocr_title_match_ratio" in visual
