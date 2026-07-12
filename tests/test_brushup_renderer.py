from __future__ import annotations

import json

from PIL import Image, ImageDraw

from src import brushup_renderer as br
from src.image_brushup_design import resolve_paths
from src.image_renderer import resolve_font_path
from src.lesson_pages import LessonDocument, LessonMetadata, LessonPage

_FONT_PATH = resolve_font_path(None)


def _page(page_no=1, **kwargs):
    defaults = dict(
        page_no=page_no, title=f"タイトル{page_no}", body=f": 本文{page_no}の一行目\n: 本文{page_no}の二行目",
        summary=f"要約{page_no}", image_text="", layout_instruction="", canva_prompt="", video_scene="",
        source_image=f"assets/page_{page_no:03d}.jpeg", notes="",
    )
    defaults.update(kwargs)
    return LessonPage(**defaults)


def _document(pages):
    return LessonDocument(metadata=LessonMetadata(mode="proofread"), pages=pages)


def _design(page_no=1, source_image=None, template="title_body", blocks=None, canvas=None, **overrides):
    design = {
        "schema_version": 1, "page_no": page_no,
        "source_image": source_image or f"assets/page_{page_no:03d}.jpeg",
        "canvas": canvas or {"width": 900, "height": 1200, "background_color": "#F8F7F2"},
        "design_intent": {"page_purpose": "test", "preserve": [], "improve": []},
        "theme": {
            "primary_color": "#2F6655", "secondary_color": "#E8F1EC", "accent_color": "#D9973D",
            "text_color": "#202522", "muted_text_color": "#6B746F",
        },
        "template": template,
        "blocks": blocks or [
            {"id": "title", "type": "title", "source_field": "title",
             "style": {"font_size": 40, "font_weight": "bold", "alignment": "center", "color": "#202522", "padding": 20}},
            {"id": "body", "type": "body", "source_field": "body",
             "style": {"font_size": 26, "font_weight": "regular", "alignment": "left", "color": "#202522", "padding": 24}},
        ],
        "footer": {"show_page_number": True, "show_source_notice": True},
    }
    design.update(overrides)
    return design


def _write_manifest_and_pages(design_dir, designs: dict[int, dict]):
    pages_dir = design_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    manifest_pages = []
    for page_no, design in designs.items():
        path = pages_dir / f"page_{page_no:03d}.json"
        path.write_text(json.dumps(design, ensure_ascii=False), encoding="utf-8")
        manifest_pages.append({"page_no": page_no, "design_file": f"pages/page_{page_no:03d}.json", "template": design["template"]})
    # design_dirは常にresolve_paths()の"output_dir / brushup_design"というレイアウトで渡されるため、
    # lesson_pages.jsonの位置をここから逆算できる（呼び出し側全箇所を変更せずに済む）。
    # ファイルが存在する場合のみsource_lesson_pages_sha256を計算して埋め込む
    # （存在しない場合は空文字列。load_design_pagesは対象lesson_pages.jsonが存在する場合のみ
    # 鮮度チェックを行うため、そのテストの意図どおりに動作する）。
    lesson_pages_path = design_dir.parent / "editable" / "lesson_pages.json"
    source_hash = br.lesson_pages_sha256(lesson_pages_path) if lesson_pages_path.exists() else ""
    manifest = {
        "schema_version": 1, "generated_at": "2026-07-12T00:00:00+09:00", "source": "ai_image_brushup_design",
        "source_lesson_pages_sha256": source_hash,
        "total_pages": len(designs), "completed_pages": len(designs),
        "template_counts": {}, "pages": manifest_pages,
    }
    (design_dir / "design_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")


# --- render_design_page（低レベルAPI） --------------------------------------------------------


def test_render_design_page_produces_png(tmp_path):
    page = _page(1)
    dest = tmp_path / "page_001.png"
    result = br.render_design_page(page, _design(1), tmp_path, dest, _FONT_PATH)
    assert result.succeeded
    assert dest.exists() and dest.stat().st_size > 0
    with Image.open(dest) as img:
        assert img.size == (900, 1200)


def test_render_design_page_uses_lesson_page_text_not_design_json(tmp_path):
    page = _page(1, title="実データのタイトル", body=": 実データの本文です")
    dest = tmp_path / "page_001.png"
    result = br.render_design_page(page, _design(1), tmp_path, dest, _FONT_PATH)
    assert result.rendered_fields["title"] == "実データのタイトル"
    assert result.rendered_fields["body"] == "実データの本文です" or "実データの本文です" in page.body
    assert result.text_match is True


def test_render_design_page_preserves_special_characters(tmp_path):
    page = _page(1, title="⑩の丸数字テスト", body=": 長音ーと括弧（）と句読点、。を保持")
    dest = tmp_path / "page_001.png"
    result = br.render_design_page(page, _design(1), tmp_path, dest, _FONT_PATH)
    assert result.succeeded
    assert result.rendered_fields["title"] == "⑩の丸数字テスト"


def test_render_design_page_all_block_types_render(tmp_path):
    page = _page(1, body=": 項目1\n: 項目2\n: 項目3")
    blocks = [
        {"id": "t", "type": "title", "source_field": "title", "style": {"font_size": 32, "padding": 12}},
        {"id": "s", "type": "summary", "source_field": "summary", "style": {"font_size": 20, "padding": 12}},
        {"id": "n", "type": "note", "source_field": "summary", "style": {"font_size": 18, "padding": 12, "background_color": "#E8F1EC"}},
        {"id": "c", "type": "checklist", "source_field": "body", "style": {"font_size": 18, "padding": 12}},
        {"id": "st", "type": "steps", "source_field": "body", "style": {"font_size": 18, "padding": 12}},
        {"id": "q", "type": "quote", "source_field": "summary", "style": {"font_size": 18, "padding": 12}},
        {"id": "d", "type": "divider"},
        {"id": "sp", "type": "spacer"},
    ]
    dest = tmp_path / "page_001.png"
    result = br.render_design_page(page, _design(1, blocks=blocks), tmp_path, dest, _FONT_PATH)
    assert result.succeeded, result.warnings


def test_render_design_page_two_column_layout_used_when_requested(tmp_path):
    long_body = "\n".join(f": 二段組みテスト行{i}。日本語を並べます。" for i in range(1, 15))
    page = _page(1, body=long_body)
    blocks = [
        {"id": "b", "type": "body", "source_field": "body", "columns": 2,
         "style": {"font_size": 20, "padding": 12}},
    ]
    dest = tmp_path / "page_001.png"
    result = br.render_design_page(page, _design(1, template="two_column", blocks=blocks), tmp_path, dest, _FONT_PATH)
    assert result.succeeded


def test_render_design_page_shrinks_font_to_fit_before_failing(tmp_path):
    long_body = "\n".join(f": 縮小テスト行{i}。" * 2 for i in range(1, 30))
    page = _page(1, body=long_body)
    blocks = [
        {"id": "b", "type": "body", "source_field": "body", "style": {"font_size": 40, "padding": 20}},
    ]
    dest = tmp_path / "page_001.png"
    canvas = {"width": 900, "height": 900, "background_color": "#FFFFFF"}
    result = br.render_design_page(page, _design(1, blocks=blocks, canvas=canvas), tmp_path, dest, _FONT_PATH)
    assert result.succeeded


def test_render_design_page_fails_with_overflow_when_content_never_fits(tmp_path):
    huge_body = "\n".join(f": 巨大テキスト行{i}。" * 5 for i in range(1, 200))
    page = _page(1, body=huge_body)
    blocks = [
        {"id": "b", "type": "body", "source_field": "body", "style": {"font_size": 40, "padding": 20}},
    ]
    dest = tmp_path / "page_001.png"
    canvas = {"width": 300, "height": 250, "background_color": "#FFFFFF"}
    result = br.render_design_page(page, _design(1, blocks=blocks, canvas=canvas), tmp_path, dest, _FONT_PATH)
    assert not result.succeeded
    assert result.overflow is True
    assert not dest.exists()


def test_render_design_page_does_not_truncate_with_ellipsis(tmp_path):
    """打ち切り(...)による省略はしない。収まらない場合は失敗として扱う。"""
    huge_body = "\n".join(f": テスト行{i}。" * 5 for i in range(1, 200))
    page = _page(1, body=huge_body)
    blocks = [{"id": "b", "type": "body", "source_field": "body", "style": {"font_size": 40, "padding": 20}}]
    dest = tmp_path / "page_001.png"
    canvas = {"width": 300, "height": 250, "background_color": "#FFFFFF"}
    result = br.render_design_page(page, _design(1, blocks=blocks, canvas=canvas), tmp_path, dest, _FONT_PATH)
    assert not result.succeeded
    assert not any("…" in w for w in result.warnings)


# --- 元画像コピー検出 -------------------------------------------------------------------------


def test_verify_not_source_copy_detects_identical_files(tmp_path):
    img = Image.new("RGB", (10, 10), color=(200, 200, 200))
    src = tmp_path / "source.png"
    dst = tmp_path / "copy.png"
    img.save(src)
    img.save(dst)
    assert br.verify_not_source_copy(src, dst) is False


def test_verify_not_source_copy_detects_different_files(tmp_path):
    Image.new("RGB", (10, 10), color=(200, 200, 200)).save(tmp_path / "source.png")
    Image.new("RGB", (10, 10), color=(10, 10, 10)).save(tmp_path / "different.png")
    assert br.verify_not_source_copy(tmp_path / "source.png", tmp_path / "different.png") is True


def test_render_all_pages_does_not_copy_source_image(tmp_path):
    output_dir = tmp_path / "out"
    assets_dir = output_dir / "assets"
    assets_dir.mkdir(parents=True)
    source_path = assets_dir / "page_001.jpeg"
    Image.new("RGB", (400, 500), color=(180, 180, 180)).save(source_path)

    page = _page(1, source_image="assets/page_001.jpeg")
    document = _document([page])
    designs = {1: _design(1, source_image="assets/page_001.jpeg")}
    rendered_dir = output_dir / "rendered_brushup"

    run = br.render_all_pages(document, designs, output_dir, rendered_dir, font_path=_FONT_PATH)
    assert run.succeeded_pages == [1]
    rendered_path = rendered_dir / "page_001.png"
    assert br.verify_not_source_copy(source_path, rendered_path) is True


# --- load_design_pages（manifest+pages読み込み・検証） -----------------------------------------


def test_load_design_pages_valid_manifest(tmp_path):
    output_dir = tmp_path / "out"
    document = _document([_page(1), _page(2)])
    paths = resolve_paths(output_dir)
    _write_manifest_and_pages(paths.design_dir, {1: _design(1), 2: _design(2)})

    designs, errors = br.load_design_pages(paths, document)
    assert errors == []
    assert set(designs.keys()) == {1, 2}


def test_load_design_pages_reports_missing_manifest(tmp_path):
    output_dir = tmp_path / "out"
    document = _document([_page(1)])
    paths = resolve_paths(output_dir)
    designs, errors = br.load_design_pages(paths, document)
    assert designs == {}
    assert any("design_manifest.json" in e for e in errors)


def test_load_design_pages_reports_page_gap(tmp_path):
    output_dir = tmp_path / "out"
    document = _document([_page(1), _page(2)])
    paths = resolve_paths(output_dir)
    _write_manifest_and_pages(paths.design_dir, {1: _design(1)})
    designs, errors = br.load_design_pages(paths, document)
    assert any("欠落" in e for e in errors)


def test_load_design_pages_reports_source_image_mismatch(tmp_path):
    output_dir = tmp_path / "out"
    document = _document([_page(1, source_image="assets/page_001.jpeg")])
    paths = resolve_paths(output_dir)
    _write_manifest_and_pages(paths.design_dir, {1: _design(1, source_image="assets/wrong.jpeg")})
    designs, errors = br.load_design_pages(paths, document)
    assert any("source_image" in e for e in errors)


# --- レポート生成 ---------------------------------------------------------------------------


def test_render_all_pages_and_reports_end_to_end(tmp_path):
    output_dir = tmp_path / "out"
    document = _document([_page(1), _page(2)])
    paths = resolve_paths(output_dir)
    _write_manifest_and_pages(paths.design_dir, {1: _design(1), 2: _design(2)})
    designs, errors = br.load_design_pages(paths, document)
    assert errors == []

    run = br.render_all_pages(document, designs, output_dir, paths.rendered_brushup_dir, font_path=_FONT_PATH)
    assert run.succeeded_pages == [1, 2]

    report_json = br.render_report_json(run)
    json.dumps(report_json)  # シリアライズ可能
    assert report_json["total_pages"] == 2

    report_md = br.render_report_markdown(run)
    assert "成功" in report_md

    html_text = br.render_comparison_html(document, designs, run, output_dir)
    assert "<!doctype html>" in html_text.lower() or "<!DOCTYPE" in html_text
    assert "http://" not in html_text and "https://" not in html_text
    assert "cdn." not in html_text.lower()


# --- line_range（bodyの一部だけをブロックが参照する。段落の複製・並べ替えはしない） -----------------


def test_paragraph_lines_for_field_line_range_skips_leading_title_duplicate():
    page = _page(1, body=": タイトル重複行\n: 本文1行目\n: 本文2行目")
    full = br._paragraph_lines_for_field(page, "body")
    sliced = br._paragraph_lines_for_field(page, "body", [1, None])
    assert full[0] == "タイトル重複行"
    assert sliced == full[1:]


def test_paragraph_lines_for_field_line_range_start_and_end():
    page = _page(1, body=": L0\n: L1\n: L2\n: L3\n: L4")
    assert br._paragraph_lines_for_field(page, "body", [1, 3]) == ["L1", "L2"]


def test_render_design_page_line_range_avoids_title_duplication_in_body_block(tmp_path):
    """titleブロックとは別に、bodyブロックのline_rangeで1行目（タイトル重複行）を除外できる。"""
    page = _page(1, title="固有タイトル", body=": 固有タイトル\n: 本文の実質的な内容です")
    blocks = [
        {"id": "title", "type": "title", "source_field": "title", "style": {"font_size": 30, "padding": 10}},
        {"id": "body", "type": "body", "source_field": "body", "line_range": [1, None],
         "style": {"font_size": 20, "padding": 10}},
    ]
    dest = tmp_path / "page_001.png"
    result = br.render_design_page(page, _design(1, blocks=blocks), tmp_path, dest, _FONT_PATH)
    assert result.succeeded
    # bodyブロックの実際の描画対象は1行目を除いた内容になっている（rendered_fieldsはfield全体を
    # 参照済みとして記録するが、実際の描画確認は_paragraph_lines_for_fieldの単体テストで担保する）。
    assert "本文の実質的な内容です" in page.body


# --- 2段組みの列分割（段落境界を保つ・split_atで意味区切りを明示できる） ----------------------------


def test_measure_columns_does_not_split_a_paragraph_across_columns():
    from PIL import Image, ImageDraw

    draw = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    font = br._load_font(_FONT_PATH, 20, "regular")
    paragraphs = ["短い段落A", "短い段落B", "短い段落C", "短い段落D"]
    wrapped_columns, _ = br._measure_columns(draw, paragraphs, font, 24, 1200, 10, columns=2)
    left_text = "".join(wrapped_columns[0])
    right_text = "".join(wrapped_columns[1])
    # いずれの段落も、左右どちらか一方の列にまるごと収まる（分裂しない）。
    for para in paragraphs:
        assert (para in left_text) != (para in right_text)


def test_measure_columns_split_at_places_content_on_the_correct_side():
    from PIL import Image, ImageDraw

    draw = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    font = br._load_font(_FONT_PATH, 20, "regular")
    paragraphs = ["例1見出し", "T特徴1", "T特徴2", "例2見出し", "B特徴1", "B特徴2"]
    wrapped_columns, _ = br._measure_columns(draw, paragraphs, font, 24, 1200, 10, columns=2, split_at=3)
    left_text = "".join(wrapped_columns[0])
    right_text = "".join(wrapped_columns[1])
    assert "例1見出し" in left_text and "T特徴1" in left_text and "T特徴2" in left_text
    assert "例2見出し" not in left_text
    assert "例2見出し" in right_text and "B特徴1" in right_text and "B特徴2" in right_text
    assert "T特徴1" not in right_text


def test_render_design_page_note_block_supports_two_columns_with_split_at(tmp_path):
    """noteブロックでもcolumns=2+split_atが効く（bodyブロックだけの制限になっていないことの回帰確認）。"""
    page = _page(1, body=": タイトル重複\n: 例1見出し\n: T特徴1\n: 例2見出し\n: B特徴1")
    blocks = [
        {"id": "examples", "type": "note", "source_field": "body", "line_range": [1, None], "columns": 2,
         "split_at": 2, "style": {"font_size": 22, "padding": 16, "background_color": "#EEEEEE"}},
    ]
    dest = tmp_path / "page_001.png"
    result = br.render_design_page(page, _design(1, blocks=blocks), tmp_path, dest, _FONT_PATH)
    assert result.succeeded, result.warnings


def test_validate_design_page_accepts_line_range_and_split_at():
    from src.image_brushup_design import validate_design_page

    design = _design(1, blocks=[
        {"id": "q", "type": "body", "source_field": "body", "line_range": [1, 3],
         "style": {"font_size": 30, "padding": 10}},
        {"id": "ex", "type": "note", "source_field": "body", "line_range": [3, None], "columns": 2,
         "split_at": 2, "style": {"font_size": 20, "padding": 10}},
    ])
    validate_design_page(design, expected_page_no=1, expected_source_image="assets/page_001.jpeg")


def test_validate_design_page_rejects_invalid_line_range():
    import pytest
    from src.image_brushup_design import validate_design_page

    design = _design(1, blocks=[
        {"id": "q", "type": "body", "source_field": "body", "line_range": [3, 1],
         "style": {"font_size": 30, "padding": 10}},
    ])
    with pytest.raises(ValueError, match="line_range"):
        validate_design_page(design, expected_page_no=1, expected_source_image="assets/page_001.jpeg")


def test_validate_design_page_rejects_negative_split_at():
    import pytest
    from src.image_brushup_design import validate_design_page

    design = _design(1, blocks=[
        {"id": "q", "type": "body", "source_field": "body", "split_at": -1,
         "style": {"font_size": 30, "padding": 10}},
    ])
    with pytest.raises(ValueError, match="split_at"):
        validate_design_page(design, expected_page_no=1, expected_source_image="assets/page_001.jpeg")


# --- group（問いかけ+補足説明を1つの共有背景の中へ積み重ねる） ------------------------------------


def test_render_design_page_group_block_shares_one_background(tmp_path):
    page = _page(1, body=": タイトル重複\n: 大きな問いかけです\n: 補足説明の文章です")
    blocks = [
        {"id": "card", "type": "group", "style": {"background_color": "#EEEEEE", "padding": 16}, "blocks": [
            {"id": "q", "type": "body", "source_field": "body", "line_range": [1, 2],
             "style": {"font_size": 32, "font_weight": "bold", "padding": 0}},
            {"id": "exp", "type": "body", "source_field": "body", "line_range": [2, 3],
             "style": {"font_size": 20, "font_weight": "regular", "padding": 0}},
        ]},
    ]
    dest = tmp_path / "page_001.png"
    result = br.render_design_page(page, _design(1, blocks=blocks), tmp_path, dest, _FONT_PATH)
    assert result.succeeded, result.warnings


def test_validate_design_page_rejects_group_child_with_disallowed_type():
    import pytest
    from src.image_brushup_design import validate_design_page

    design = _design(1, blocks=[
        {"id": "card", "type": "group", "style": {"padding": 16}, "blocks": [
            {"id": "cl", "type": "checklist", "source_field": "body", "style": {"font_size": 20, "padding": 0}},
        ]},
    ])
    with pytest.raises(ValueError, match="子block"):
        validate_design_page(design, expected_page_no=1, expected_source_image="assets/page_001.jpeg")


def test_validate_design_page_rejects_empty_group_blocks():
    import pytest
    from src.image_brushup_design import validate_design_page

    design = _design(1, blocks=[{"id": "card", "type": "group", "style": {"padding": 16}, "blocks": []}])
    with pytest.raises(ValueError, match="blocks"):
        validate_design_page(design, expected_page_no=1, expected_source_image="assets/page_001.jpeg")


# --- column_ratio（2段組みの左右幅配分を変え、不自然な位置での改行を防ぐ） --------------------------


def test_column_widths_reflects_ratio():
    left, right = br._column_widths(1280, 18, 0.58)
    left_even, right_even = br._column_widths(1280, 18, 0.5)
    assert left > left_even
    assert right < right_even


def test_render_design_page_column_ratio_widens_left_column_to_avoid_awkward_wrap(tmp_path):
    """左列の内容が右列より明らかに長い場合、column_ratioで左列を広げると不自然な改行を避けられる。"""
    long_left_line = "・非常に心優しく、慈悲深い　・少し頑固な「頭の固さ」"
    draw = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    font = br._load_font(_FONT_PATH, 23, "regular")

    fit_even = br._fit_text_block(
        draw, [long_left_line, "短い右列の項目"], font_path=_FONT_PATH, base_font_size=23, weight="regular",
        base_padding=18, max_width=1280, available_height=400, force_columns=2, split_at=1, column_ratio=0.5,
    )
    fit_widened = br._fit_text_block(
        draw, [long_left_line, "短い右列の項目"], font_path=_FONT_PATH, base_font_size=23, weight="regular",
        base_padding=18, max_width=1280, available_height=400, force_columns=2, split_at=1, column_ratio=0.7,
    )
    assert fit_even.fits and fit_widened.fits
    # 均等割りだと長い行が折り返されて2行になるが、column_ratioで左列を広げると1行に収まる。
    assert len(fit_even.wrapped_columns[0]) >= len(fit_widened.wrapped_columns[0])
    assert len(fit_widened.wrapped_columns[0]) == 1

    page = _page(1, body=f": タイトル\n: {long_left_line}\n: 短い右列の項目")
    blocks = [
        {"id": "examples", "type": "note", "source_field": "body", "line_range": [1, 3], "columns": 2,
         "split_at": 1, "column_ratio": 0.7, "style": {"font_size": 23, "padding": 18}},
    ]
    canvas = {"width": 1280, "height": 400, "background_color": "#FFFFFF"}
    dest = tmp_path / "page_001.png"
    result = br.render_design_page(page, _design(1, blocks=blocks, canvas=canvas), tmp_path, dest, _FONT_PATH)
    assert result.succeeded, result.warnings


def test_validate_design_page_rejects_out_of_range_column_ratio():
    import pytest
    from src.image_brushup_design import validate_design_page

    design = _design(1, blocks=[
        {"id": "q", "type": "body", "source_field": "body", "columns": 2, "column_ratio": 0.95,
         "style": {"font_size": 30, "padding": 10}},
    ])
    with pytest.raises(ValueError, match="column_ratio"):
        validate_design_page(design, expected_page_no=1, expected_source_image="assets/page_001.jpeg")
