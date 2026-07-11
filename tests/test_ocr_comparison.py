import html
import json
import re

from src import apple_vision_ocr, ocr_comparison


def _strip_tags_and_unescape(fragment: str) -> str:
    """テスト用ヘルパー: 差分HTML断片から`<mark>`等のタグだけを取り除き、元のテキストへ復元する
    （文字単位の差分は複数の`<mark>`片に分割されうるため、断片単位の完全一致ではなく、
    タグを除いた全体の内容が元の文字列と一致するかで検証する）。
    """
    without_tags = re.sub(r"<[^>]+>", "", fragment)
    return html.unescape(without_tags)


def _fake_unavailable(**kwargs):
    return apple_vision_ocr.AppleVisionResult(available=False, warnings=["not available in test"])


def _fake_available(text, *, duration=0.2):
    def _runner(*args, **kwargs):
        return apple_vision_ocr.AppleVisionResult(available=True, language="ja-JP", text=text, duration_seconds=duration)
    return _runner


def _availability_unavailable(*args, **kwargs):
    return apple_vision_ocr.AppleVisionAvailability(available=False, reason="テスト環境では利用不可")


def _availability_available(*args, **kwargs):
    return apple_vision_ocr.AppleVisionAvailability(available=True, reason="利用可能", helper_path="/fake/path")


_PAGES = [
    {"page_no": 1, "source_image": "assets/page_001.png", "lines": [{"text": "【タイトル】"}, {"text": "本文です"}]},
    {"page_no": 2, "source_image": "assets/page_002.png", "lines": [{"text": "【別ページ】"}, {"text": "内容"}]},
]


def _make_assets(tmp_path):
    from PIL import Image

    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    for name in ("page_001.png", "page_002.png"):
        Image.new("RGB", (40, 30), color=(200, 200, 200)).save(assets_dir / name)
    return assets_dir


# --- Apple Vision利用不可時のフォールバック挙動 -------------------------------------------------


def test_comparison_does_not_flag_all_pages_when_vision_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "check_apple_vision_availability", _availability_unavailable)
    assets_dir = _make_assets(tmp_path)

    summary = ocr_comparison.run_ocr_comparison_for_pages(
        _PAGES, assets_dir,
        tesseract_diagnostics=[
            {"page_no": 1, "score": 0.8, "quality": "ok", "duration_seconds": 1.0},
            {"page_no": 2, "score": 0.8, "quality": "ok", "duration_seconds": 1.0},
        ],
    )

    assert summary.vision_helper_available is False
    # Apple Visionが使えない場合、エンジン不一致を理由に全ページneeds_reviewにしない。
    assert summary.needs_review_pages == []
    assert summary.compared_pages == 0
    for page in summary.pages:
        assert page.vision_available is False
        assert page.needs_review is False


def test_comparison_still_uses_tesseract_own_quality_when_vision_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "check_apple_vision_availability", _availability_unavailable)
    assets_dir = _make_assets(tmp_path)

    summary = ocr_comparison.run_ocr_comparison_for_pages(
        _PAGES, assets_dir,
        tesseract_diagnostics=[
            {"page_no": 1, "score": 0.4, "quality": "needs_review", "duration_seconds": 1.0},
            {"page_no": 2, "score": 0.8, "quality": "ok", "duration_seconds": 1.0},
        ],
    )
    assert summary.needs_review_pages == [1]
    assert summary.tesseract_only_review_pages == [1]


# --- Apple Vision利用可能時の比較 ---------------------------------------------------------------


def test_comparison_flags_page_when_texts_diverge(tmp_path, monkeypatch):
    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "check_apple_vision_availability", _availability_available)
    monkeypatch.setattr(
        ocr_comparison.apple_vision_ocr, "run_apple_vision_ocr", _fake_available("まったく異なる内容のテキスト")
    )
    assets_dir = _make_assets(tmp_path)

    summary = ocr_comparison.run_ocr_comparison_for_pages(
        _PAGES, assets_dir,
        tesseract_diagnostics=[
            {"page_no": 1, "score": 0.8, "quality": "ok", "duration_seconds": 1.0},
            {"page_no": 2, "score": 0.8, "quality": "ok", "duration_seconds": 1.0},
        ],
    )
    assert summary.vision_helper_available is True
    assert summary.compared_pages == 2
    assert 1 in summary.needs_review_pages
    assert 1 in summary.vision_only_review_pages


def test_comparison_does_not_flag_page_when_texts_match(tmp_path, monkeypatch):
    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "check_apple_vision_availability", _availability_available)

    def _runner(image_path, **kwargs):
        # 画像ファイル名からページ内容を再現する簡易フェイク（page_001→タイトル、page_002→別ページ）。
        if "page_001" in str(image_path):
            return apple_vision_ocr.AppleVisionResult(available=True, text="【タイトル】\n本文です")
        return apple_vision_ocr.AppleVisionResult(available=True, text="【別ページ】\n内容")

    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "run_apple_vision_ocr", _runner)
    assets_dir = _make_assets(tmp_path)

    summary = ocr_comparison.run_ocr_comparison_for_pages(_PAGES, assets_dir)
    assert summary.needs_review_pages == []


# --- lesson_pages.jsonへの自動反映が無いこと -----------------------------------------------------


def test_comparison_never_touches_editable_lesson_pages(tmp_path, monkeypatch):
    """Apple Vision結果はいかなる場合もeditable/lesson_pages.json相当のデータへ書き込まれない
    （比較関数の戻り値・保存関数のいずれも、渡された`imported_pages`/lesson_pages構造を変更しない）。
    """
    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "check_apple_vision_availability", _availability_available)
    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "run_apple_vision_ocr", _fake_available("Vision側のテキスト"))
    assets_dir = _make_assets(tmp_path)

    pages_copy = json.loads(json.dumps(_PAGES))
    ocr_comparison.run_ocr_comparison_for_pages(pages_copy, assets_dir)

    # 入力（取り込み済みpages）自体が書き換えられていないこと。
    assert pages_copy == _PAGES


# --- 保存（output/ocr_comparison/） -------------------------------------------------------------


def test_write_comparison_outputs_creates_expected_file_structure(tmp_path, monkeypatch):
    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "check_apple_vision_availability", _availability_available)
    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "run_apple_vision_ocr", _fake_available("Vision側のテキスト"))
    assets_dir = _make_assets(tmp_path)

    summary = ocr_comparison.run_ocr_comparison_for_pages(_PAGES, assets_dir)
    output_dir = tmp_path / "output"
    paths = ocr_comparison.write_comparison_outputs(output_dir, summary)

    assert paths["summary_json"].exists()
    assert paths["summary_md"].exists()
    assert paths["review_html"].exists()
    assert (output_dir / "ocr_comparison" / "pages" / "page_001.json").exists()
    assert (output_dir / "ocr_comparison" / "pages" / "page_002.json").exists()

    summary_data = json.loads(paths["summary_json"].read_text(encoding="utf-8"))
    assert summary_data["total_pages"] == 2

    page_data = json.loads((output_dir / "ocr_comparison" / "pages" / "page_001.json").read_text(encoding="utf-8"))
    assert page_data["tesseract_text"] == "【タイトル】\n本文です"
    assert page_data["vision_text"] == "Vision側のテキスト"


def test_review_html_is_self_contained_and_references_local_assets(tmp_path, monkeypatch):
    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "check_apple_vision_availability", _availability_available)
    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "run_apple_vision_ocr", _fake_available("Vision側のテキスト"))
    assets_dir = _make_assets(tmp_path)

    summary = ocr_comparison.run_ocr_comparison_for_pages(_PAGES, assets_dir)
    html_text = ocr_comparison.render_comparison_review_html(summary)

    assert "http://" not in html_text
    assert "https://" not in html_text
    assert "<script src=" not in html_text
    assert "../assets/page_001.png" in html_text
    assert "Page 1" in html_text
    assert "Page 2" in html_text


def test_review_html_escapes_html_special_characters_in_ocr_text(tmp_path, monkeypatch):
    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "check_apple_vision_availability", _availability_available)
    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "run_apple_vision_ocr", _fake_available("<script>alert(1)</script>"))
    assets_dir = _make_assets(tmp_path)

    summary = ocr_comparison.run_ocr_comparison_for_pages(_PAGES, assets_dir)
    html_text = ocr_comparison.render_comparison_review_html(summary)

    assert "<script>alert(1)</script>" not in html_text
    assert "&lt;script&gt;" in html_text


def test_summary_markdown_notes_no_auto_adoption():
    from dataclasses import replace

    summary = ocr_comparison.ComparisonSummary(
        generated_at="2026-01-01T00:00:00+09:00", language="ja-JP", vision_helper_available=True,
        vision_unavailable_reason="", total_pages=0, compared_pages=0, needs_review_pages=[],
        tesseract_only_review_pages=[], vision_only_review_pages=[], both_engines_review_pages=[], pages=[],
    )
    markdown = ocr_comparison.render_comparison_summary_markdown(summary)
    assert "自動反映されません" in markdown
    assert "editable/lesson_pages.json" in markdown


# --- 文字単位の差分ハイライト（Phase 10.8） ------------------------------------------------------


def test_diff_identical_text_has_no_diff_tags():
    left_html, right_html = ocr_comparison._render_text_diff("同じ本文です", "同じ本文です")
    assert "<mark" not in left_html
    assert "<mark" not in right_html
    assert left_html == "同じ本文です"
    assert right_html == "同じ本文です"


def test_diff_character_replacement_uses_distinct_classes_per_side():
    left_html, right_html = ocr_comparison._render_text_diff("苦労したこと", "店労したこと")
    assert f'class="{ocr_comparison._DIFF_LEFT_REPLACE_CLASS}"' in left_html
    assert f'class="{ocr_comparison._DIFF_RIGHT_REPLACE_CLASS}"' in right_html
    assert ocr_comparison._DIFF_LEFT_REPLACE_CLASS != ocr_comparison._DIFF_RIGHT_REPLACE_CLASS
    assert "苦" in left_html
    assert "店" in right_html
    assert "労したこと" in left_html
    assert "労したこと" in right_html


def test_diff_tesseract_only_text_is_highlighted_on_left_only():
    left_html, right_html = ocr_comparison._render_text_diff("タイトル本文余分", "タイトル本文")
    assert f'class="{ocr_comparison._DIFF_LEFT_DELETE_CLASS}"' in left_html
    assert "<mark" not in right_html
    assert "余分" in left_html


def test_diff_vision_only_text_is_highlighted_on_right_only():
    left_html, right_html = ocr_comparison._render_text_diff("タイトル本文", "タイトル本文追加分")
    assert f'class="{ocr_comparison._DIFF_RIGHT_INSERT_CLASS}"' in right_html
    assert "<mark" not in left_html
    assert "追加分" in right_html


def test_diff_missing_line_is_visible_as_insert_only_on_vision_side():
    left = "本文1行目\n本文2行目"
    right = "本文1行目\n本文2行目\n※無断転載禁止（おとスタ）"
    left_html, right_html = ocr_comparison._render_text_diff(left, right)
    assert "※無断転載禁止（おとスタ）" in right_html
    assert f'class="{ocr_comparison._DIFF_RIGHT_INSERT_CLASS}"' in right_html
    assert "無断転載禁止" not in left_html.replace("\n", "")


def test_diff_both_empty_shows_placeholder_without_error():
    left_html, right_html = ocr_comparison._render_text_diff("", "")
    assert "OCRテキストなし" in left_html
    assert "OCRテキストなし" in right_html


def test_diff_left_empty_highlights_entire_right_side():
    left_html, right_html = ocr_comparison._render_text_diff("", "Apple Visionだけの本文")
    assert left_html == ""
    assert f'class="{ocr_comparison._DIFF_RIGHT_INSERT_CLASS}"' in right_html
    assert "Apple Visionだけの本文" in right_html


def test_diff_right_empty_highlights_entire_left_side():
    left_html, right_html = ocr_comparison._render_text_diff("Tesseractだけの本文", "")
    assert right_html == ""
    assert f'class="{ocr_comparison._DIFF_LEFT_DELETE_CLASS}"' in left_html
    assert "Tesseractだけの本文" in left_html


def test_diff_escapes_script_tags_without_breaking_structure():
    left_html, right_html = ocr_comparison._render_text_diff(
        "<script>alert(1)</script>", "normal text"
    )
    assert "<script>alert(1)</script>" not in left_html
    # 文字単位の差分により複数のmark片に分割されうるため、タグを除いた全体の内容で照合する。
    assert _strip_tags_and_unescape(left_html) == "<script>alert(1)</script>"


def test_diff_escapes_closing_span_and_ampersand_and_quotes():
    left_html, right_html = ocr_comparison._render_text_diff('</span>&"\'', "別の内容です")
    assert "</span>" not in left_html.replace("</mark>", "")
    assert "&lt;/span&gt;" in left_html
    assert "&amp;" in left_html
    assert "&quot;" in left_html or "&#x27;" in left_html or "&#39;" in left_html


def test_diff_does_not_apply_escaping_to_already_escaped_full_text():
    """先に元文字列をSequenceMatcherで分割してから断片ごとにエスケープする設計を確認する。
    `&`を含む一致部分でも、分割位置がエスケープ後の長さでずれない（前後の文字が欠落しない）。
    """
    left_html, right_html = ocr_comparison._render_text_diff("A&Bタイトル一致部分", "A&Bタイトル一致部分X")
    assert "一致部分" in left_html
    assert "一致部分" in right_html
    assert "A&amp;Bタイトル一致部分" in left_html


def test_diff_handles_unicode_circled_numbers_and_emoji_without_corruption():
    left = "⑩ここまでのメモ😀"
    right = "10ここまでのメモ😀"
    left_html, right_html = ocr_comparison._render_text_diff(left, right)
    assert "😀" in left_html
    assert "😀" in right_html
    assert "ここまでのメモ" in left_html
    assert "ここまでのメモ" in right_html


def test_diff_handles_long_strings_without_error():
    left = "同じ本文の繰り返しです。" * 500 + "Tesseract側の末尾"
    right = "同じ本文の繰り返しです。" * 500 + "Apple Vision側の末尾"
    left_html, right_html = ocr_comparison._render_text_diff(left, right)
    assert _strip_tags_and_unescape(left_html) == left
    assert _strip_tags_and_unescape(right_html) == right


def test_normalize_diff_line_endings_unifies_newlines_only():
    assert ocr_comparison._normalize_diff_line_endings("行1\r\n行2\r行3") == "行1\n行2\n行3"
    # 漢字・かな・句読点・数字・空白は変更しない。
    assert ocr_comparison._normalize_diff_line_endings("一貫したキャラ設定！70〜80%") == "一貫したキャラ設定！70〜80%"


# --- review.htmlへの統合確認 -----------------------------------------------------------------


def test_review_html_includes_diff_legend_and_diff_grid(tmp_path, monkeypatch):
    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "check_apple_vision_availability", _availability_available)
    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "run_apple_vision_ocr", _fake_available("苦労したことを書く"))
    assets_dir = _make_assets(tmp_path)

    summary = ocr_comparison.run_ocr_comparison_for_pages(_PAGES, assets_dir)
    html_text = ocr_comparison.render_comparison_review_html(summary)

    assert "diff-legend" in html_text
    assert "compare-grid" in html_text
    assert ocr_comparison._DIFF_LEFT_DELETE_CLASS in html_text or ocr_comparison._DIFF_LEFT_REPLACE_CLASS in html_text


def test_review_html_diff_view_is_still_self_contained(tmp_path, monkeypatch):
    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "check_apple_vision_availability", _availability_available)
    monkeypatch.setattr(
        ocr_comparison.apple_vision_ocr, "run_apple_vision_ocr", _fake_available("<script>evil()</script>まったく異なる内容")
    )
    assets_dir = _make_assets(tmp_path)

    summary = ocr_comparison.run_ocr_comparison_for_pages(_PAGES, assets_dir)
    html_text = ocr_comparison.render_comparison_review_html(summary)

    assert "http://" not in html_text
    assert "https://" not in html_text
    # OCR文字列内の"<script>evil()"という文字表現自体はJSONデータ内に無害なテキストとして
    # 残ってよい（新しいscript要素を開始しない）。安全性として意味があるのは、OCR由来の
    # "</script>"がエスケープされ、正規の<script>要素（ページデータ用・アプリロジック用の
    # 2個）だけが実際の閉じタグとして存在すること。
    assert html_text.count("</script>") == 2
    assert "../assets/page_001.png" in html_text


def test_review_html_diff_view_does_not_change_json_output_structure(tmp_path, monkeypatch):
    """差分HTML表示の追加が、summary.json・ページ別JSONのフィールド構成を変えていないことを確認する
    （既存のneeds_review判定・JSON形式を変更しない、という要求の直接検証）。"""
    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "check_apple_vision_availability", _availability_available)
    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "run_apple_vision_ocr", _fake_available("Vision側のテキスト"))
    assets_dir = _make_assets(tmp_path)

    summary = ocr_comparison.run_ocr_comparison_for_pages(_PAGES, assets_dir)
    output_dir = tmp_path / "output"
    paths = ocr_comparison.write_comparison_outputs(output_dir, summary)

    page_data = json.loads((output_dir / "ocr_comparison" / "pages" / "page_001.json").read_text(encoding="utf-8"))
    expected_keys = {
        "page_no", "source_image", "tesseract_text", "tesseract_available", "tesseract_duration_seconds",
        "tesseract_score", "tesseract_quality", "vision_text", "vision_available", "vision_warnings",
        "vision_duration_seconds", "metrics", "needs_review", "mismatch_reasons",
    }
    assert set(page_data.keys()) == expected_keys
    # 差分用のHTML断片はJSON側には含まれない（JSON生成にdiffは混入させない）。
    assert "<mark" not in json.dumps(page_data, ensure_ascii=False)


def test_review_html_diff_view_does_not_touch_editable_lesson_pages(tmp_path, monkeypatch):
    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "check_apple_vision_availability", _availability_available)
    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "run_apple_vision_ocr", _fake_available("Vision側のテキスト"))
    assets_dir = _make_assets(tmp_path)

    pages_copy = json.loads(json.dumps(_PAGES))
    ocr_comparison.run_ocr_comparison_for_pages(pages_copy, assets_dir)
    assert pages_copy == _PAGES


# --- 確定テキスト編集・採用判定・JSON書き出し（Phase 10.9） --------------------------------------


def _make_two_page_summary(tesseract_texts, vision_texts):
    pages = [
        ocr_comparison.PageComparison(
            page_no=no,
            source_image=f"assets/page_{no:03d}.jpeg",
            tesseract_text=tesseract_texts[i],
            tesseract_available=True,
            tesseract_duration_seconds=1.0,
            tesseract_score=0.7,
            tesseract_quality="ok",
            vision_text=vision_texts[i],
            vision_available=True,
            vision_warnings=[],
            vision_duration_seconds=0.3,
            metrics=None,
            needs_review=False,
            mismatch_reasons=[],
        )
        for i, no in enumerate((1, 2))
    ]
    return ocr_comparison.ComparisonSummary(
        generated_at="2026-01-01T00:00:00+09:00", language="ja-JP", vision_helper_available=True,
        vision_unavailable_reason="", total_pages=2, compared_pages=0, needs_review_pages=[],
        tesseract_only_review_pages=[], vision_only_review_pages=[], both_engines_review_pages=[], pages=pages,
    )


def test_review_html_tesseract_and_vision_panels_are_read_only():
    summary = _make_two_page_summary(["T本文1", "T本文2"], ["V本文1", "V本文2"])
    html_text = ocr_comparison.render_comparison_review_html(summary)
    # Tesseract/Apple Vision表示は<pre>（読み取り専用）のままで、<textarea>で囲まれていない。
    assert "<pre class=\"ocr-text diff-text\">" in html_text
    assert html_text.count("<textarea") == 2  # 確定テキスト欄（各ページ1つ）のみ


def test_review_html_has_copy_buttons_for_both_engines_per_page():
    summary = _make_two_page_summary(["T本文1", "T本文2"], ["V本文1", "V本文2"])
    html_text = ocr_comparison.render_comparison_review_html(summary)
    assert html_text.count('data-role="copy-tesseract"') == 2
    assert html_text.count('data-role="copy-vision"') == 2


def test_review_html_page_data_blob_contains_exact_plain_text_for_copy_buttons():
    summary = _make_two_page_summary(["Tesseractの全文です", "T2"], ["Apple Visionの全文です", "V2"])
    html_text = ocr_comparison.render_comparison_review_html(summary)
    match = re.search(
        r'<script type="application/json" id="ocr-review-page-data">(.*?)</script>', html_text, re.S
    )
    assert match is not None
    data = json.loads(match.group(1))
    assert data[0]["tesseractText"] == "Tesseractの全文です"
    assert data[0]["appleVisionText"] == "Apple Visionの全文です"


def test_review_html_adoption_radios_are_mutually_exclusive_per_page_via_shared_name():
    summary = _make_two_page_summary(["T1", "T2"], ["V1", "V2"])
    html_text = ocr_comparison.render_comparison_review_html(summary)
    # 同一ページ内のTesseract/Apple Vision採用ラジオは同じname（排他制御）、
    # ページが異なれば別のnameになる（他ページの選択状態に影響しない）。
    assert 'name="adopt-source-1"' in html_text
    assert 'name="adopt-source-2"' in html_text
    assert html_text.count('name="adopt-source-1"') == 2
    assert html_text.count('name="adopt-source-2"') == 2


def test_review_html_has_independent_source_review_and_completed_checkboxes():
    summary = _make_two_page_summary(["T1", "T2"], ["V1", "V2"])
    html_text = ocr_comparison.render_comparison_review_html(summary)
    assert html_text.count('data-role="requires-source-review"') == 2
    assert html_text.count('data-role="review-completed"') == 2


def test_review_html_has_export_and_reset_buttons():
    summary = _make_two_page_summary(["T1", "T2"], ["V1", "V2"])
    html_text = ocr_comparison.render_comparison_review_html(summary)
    assert 'id="ocr-review-export-btn"' in html_text
    assert 'id="ocr-review-reset-btn"' in html_text


def test_review_html_js_uses_local_storage_with_confirm_before_overwrite_and_reset():
    summary = _make_two_page_summary(["T1", "T2"], ["V1", "V2"])
    html_text = ocr_comparison.render_comparison_review_html(summary)
    assert "window.localStorage.setItem" in html_text
    assert "window.localStorage.getItem" in html_text
    assert "window.confirm(" in html_text  # コピー上書き確認・全リセット確認の両方で使用


def test_review_html_js_does_not_use_eval_or_function_constructor():
    summary = _make_two_page_summary(["T1", "T2"], ["V1", "V2"])
    html_text = ocr_comparison.render_comparison_review_html(summary)
    assert "eval(" not in html_text
    assert "new Function(" not in html_text


def test_review_html_export_json_field_names_match_spec():
    summary = _make_two_page_summary(["T1", "T2"], ["V1", "V2"])
    html_text = ocr_comparison.render_comparison_review_html(summary)
    for field in (
        "schema_version", "generated_at", "source", "page_no", "adopted_source", "adopted_text",
        "final_text", "tesseract_selected", "apple_vision_selected", "requires_source_review", "review_completed",
    ):
        assert field in html_text


def test_review_html_does_not_embed_absolute_paths_in_page_data():
    summary = _make_two_page_summary(["T1", "T2"], ["V1", "V2"])
    html_text = ocr_comparison.render_comparison_review_html(summary)
    match = re.search(
        r'<script type="application/json" id="ocr-review-page-data">(.*?)</script>', html_text, re.S
    )
    data = json.loads(match.group(1))
    for entry in data:
        assert set(entry.keys()) == {"pageNo", "tesseractText", "appleVisionText"}
        assert "/Users/" not in json.dumps(entry)
        assert not entry.get("sourceImagePath")


def test_review_html_handles_script_textarea_and_ampersand_in_ocr_text_safely():
    summary = _make_two_page_summary(
        ['<script>alert(1)</script>本文</textarea>&"\'', "T2"], ["V1", "V2"]
    )
    html_text = ocr_comparison.render_comparison_review_html(summary)
    # ページデータJSONとして正しくパースできる（構造が壊れていない）ことを確認する。
    match = re.search(
        r'<script type="application/json" id="ocr-review-page-data">(.*?)</script>', html_text, re.S
    )
    data = json.loads(match.group(1))
    assert data[0]["tesseractText"] == '<script>alert(1)</script>本文</textarea>&"\''
    # 実際に閉じられる<script>要素は2個（ページデータ用・アプリロジック用）だけで、
    # OCR文字列由来の"</script>"がその数へ紛れ込んでいない（安全にエスケープされている）。
    assert html_text.count("</script>") == 2
    # </textarea>はscript要素内では生テキストとして無害（HTMLパーサはscript要素内で
    # </scriptしか終端タグとみなさない）。テンプレート側の本物の<textarea>は
    # ページ数と同数（このテストでは2ページ）だけ存在する。
    assert html_text.count("<textarea") == 2


def test_review_html_still_self_contained_no_external_resources_with_new_ui():
    summary = _make_two_page_summary(["T1", "T2"], ["V1", "V2"])
    html_text = ocr_comparison.render_comparison_review_html(summary)
    assert "http://" not in html_text
    assert "https://" not in html_text
    assert "cdn." not in html_text


def test_review_html_diff_highlighting_still_present_alongside_new_ui():
    summary = _make_two_page_summary(["苦労したこと", "T2"], ["店労したこと", "V2"])
    html_text = ocr_comparison.render_comparison_review_html(summary)
    assert ocr_comparison._DIFF_LEFT_REPLACE_CLASS in html_text
    assert ocr_comparison._DIFF_RIGHT_REPLACE_CLASS in html_text
    assert "diff-legend" in html_text


def test_export_json_does_not_write_editable_lesson_pages_or_source_json(tmp_path, monkeypatch):
    """レビューJSON書き出し機能の追加が、既存の書き出し先（editable/lesson_pages.json・
    summary.json・ページ別JSON）を自動更新しないことを、write_comparison_outputs()の
    書き出しファイル一覧が変わっていないことで確認する。"""
    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "check_apple_vision_availability", _availability_available)
    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "run_apple_vision_ocr", _fake_available("Vision側のテキスト"))
    assets_dir = _make_assets(tmp_path)

    summary = ocr_comparison.run_ocr_comparison_for_pages(_PAGES, assets_dir)
    output_dir = tmp_path / "output"
    paths = ocr_comparison.write_comparison_outputs(output_dir, summary)

    assert set(paths.keys()) == {
        "summary_json", "summary_md", "review_html", "pages_dir",
        "claude_ocr_review_md", "claude_review_readme",
    }
    assert not (output_dir / "editable").exists()
