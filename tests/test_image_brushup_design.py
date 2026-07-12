from __future__ import annotations

import pytest

from src.image_brushup_design import (
    check_manifest_freshness,
    format_page_number_ranges,
    lesson_pages_sha256,
    render_ai_image_brushup_instructions,
    render_design_readme,
    resolve_paths,
    validate_design_page,
    validate_manifest,
    write_design_entry_points,
)
from src.lesson_pages import LessonDocument, LessonMetadata, LessonPage


def _page(page_no=1, **kwargs):
    defaults = dict(
        page_no=page_no, title=f"タイトル{page_no}", body=f": 本文{page_no}", summary=f"要約{page_no}",
        image_text="", layout_instruction="", canva_prompt="", video_scene="",
        source_image=f"assets/page_{page_no:03d}.jpeg", notes="",
    )
    defaults.update(kwargs)
    return LessonPage(**defaults)


def _document(pages):
    return LessonDocument(metadata=LessonMetadata(mode="proofread"), pages=pages)


def _valid_design(page_no=1, source_image="assets/page_001.jpeg", **overrides):
    design = {
        "schema_version": 1,
        "page_no": page_no,
        "source_image": source_image,
        "canvas": {"width": 900, "height": 1200, "background_color": "#F8F7F2"},
        "design_intent": {"page_purpose": "test", "preserve": [], "improve": []},
        "theme": {
            "primary_color": "#2F6655", "secondary_color": "#E8F1EC", "accent_color": "#D9973D",
            "text_color": "#202522", "muted_text_color": "#6B746F",
        },
        "template": "title_body",
        "blocks": [
            {"id": "title", "type": "title", "source_field": "title",
             "style": {"font_size": 44, "font_weight": "bold", "alignment": "center", "color": "#202522",
                       "background_color": None, "padding": 20}},
            {"id": "body", "type": "body", "source_field": "body",
             "style": {"font_size": 28, "font_weight": "regular", "alignment": "left", "color": "#202522",
                       "background_color": "#FFFFFF", "padding": 32}},
        ],
        "footer": {"show_page_number": True, "show_source_notice": True},
        "review_notes": "", "designed_by": "ai_work_agent", "designed_at": "2026-07-12T00:00:00+09:00",
    }
    design.update(overrides)
    return design


# --- 指示書生成 ------------------------------------------------------------------------------


def test_format_page_number_ranges_compresses_consecutive():
    assert format_page_number_ranges([1, 2, 3, 5, 7, 8, 9]) == "1-3, 5, 7-9"


def test_instructions_include_page_count_and_final_goal(tmp_path):
    document = _document([_page(1), _page(2), _page(3)])
    text = render_ai_image_brushup_instructions(document, tmp_path / "out")
    assert "対象ページ総数: 3" in text
    assert "元教材画像" in text and "ブラッシュアップ済み教材画像を生成" in text


def test_instructions_do_not_embed_body_text(tmp_path):
    document = _document([_page(1, title="固有タイトルXYZ", body=": 固有本文ABC")])
    text = render_ai_image_brushup_instructions(document, tmp_path / "out")
    assert "固有タイトルXYZ" not in text
    assert "固有本文ABC" not in text


def test_instructions_do_not_embed_absolute_path(tmp_path):
    document = _document([_page(1)])
    abs_dir = tmp_path / "out"
    text = render_ai_image_brushup_instructions(document, abs_dir)
    assert str(abs_dir) not in text


def test_instructions_scale_independent_of_page_count(tmp_path):
    small = _document([_page(i) for i in range(1, 4)])
    large = _document([_page(i) for i in range(1, 138)])
    text_small = render_ai_image_brushup_instructions(small, tmp_path / "out")
    text_large = render_ai_image_brushup_instructions(large, tmp_path / "out")
    assert "対象ページ総数: 3" in text_small
    assert "対象ページ総数: 137" in text_large


def test_instructions_mention_source_field_duplication_prohibition():
    document = _document([_page(1)])
    text = render_ai_image_brushup_instructions(document, __import__("pathlib").Path("out"))
    assert "複製" in text
    assert "source_field" in text


def test_write_design_entry_points_creates_instructions_and_readme(tmp_path):
    document = _document([_page(1), _page(2)])
    output_dir = tmp_path / "out"
    written = write_design_entry_points(output_dir, document)
    assert written["instructions"].exists()
    assert written["readme"].exists()
    paths = resolve_paths(output_dir)
    assert not paths.manifest_path.exists()
    assert not paths.pages_dir.exists() or not list(paths.pages_dir.glob("*.json"))


def test_render_design_readme_mentions_no_body_duplication():
    text = render_design_readme()
    assert "複製" in text


# --- デザインJSON検証（正常系） ---------------------------------------------------------------


def test_validate_design_page_accepts_valid_design():
    validate_design_page(_valid_design(), expected_page_no=1, expected_source_image="assets/page_001.jpeg")


def test_validate_design_page_accepts_all_block_types():
    design = _valid_design(blocks=[
        {"id": "a", "type": "title", "source_field": "title", "style": {"font_size": 20, "padding": 10}},
        {"id": "b", "type": "summary", "source_field": "summary", "style": {"font_size": 20, "padding": 10}},
        {"id": "c", "type": "body", "source_field": "body", "style": {"font_size": 20, "padding": 10}},
        {"id": "d", "type": "note", "source_field": "body", "style": {"font_size": 20, "padding": 10}},
        {"id": "e", "type": "checklist", "source_field": "body", "style": {"font_size": 20, "padding": 10}},
        {"id": "f", "type": "steps", "source_field": "body", "style": {"font_size": 20, "padding": 10}},
        {"id": "g", "type": "quote", "source_field": "summary", "style": {"font_size": 20, "padding": 10}},
        {"id": "h", "type": "divider"},
        {"id": "i", "type": "spacer"},
    ])
    validate_design_page(design, expected_page_no=1, expected_source_image="assets/page_001.jpeg")


# --- デザインJSON検証（拒否系） ---------------------------------------------------------------


def test_validate_design_page_rejects_unknown_template():
    with pytest.raises(ValueError, match="template"):
        validate_design_page(
            _valid_design(template="made_up_template"), expected_page_no=1, expected_source_image="assets/page_001.jpeg"
        )


def test_validate_design_page_rejects_page_no_mismatch():
    with pytest.raises(ValueError, match="page_no"):
        validate_design_page(_valid_design(page_no=1), expected_page_no=2, expected_source_image="assets/page_001.jpeg")


def test_validate_design_page_rejects_duplicate_page_numbers_via_manifest():
    manifest = {
        "schema_version": 1,
        "pages": [
            {"page_no": 1, "design_file": "pages/page_001.json", "template": "title_body"},
            {"page_no": 1, "design_file": "pages/page_001b.json", "template": "title_body"},
        ],
    }
    errors = validate_manifest(manifest, expected_page_numbers=[1, 2])
    assert any("重複" in e for e in errors)
    assert any("欠落" in e for e in errors)


def test_validate_design_page_rejects_source_image_mismatch():
    with pytest.raises(ValueError, match="source_image"):
        validate_design_page(
            _valid_design(source_image="assets/wrong.jpeg"), expected_page_no=1,
            expected_source_image="assets/page_001.jpeg",
        )


def test_validate_design_page_rejects_absolute_path_source_image():
    with pytest.raises(ValueError):
        validate_design_page(
            _valid_design(source_image="/etc/passwd"), expected_page_no=1, expected_source_image="/etc/passwd",
        )


def test_validate_design_page_rejects_path_traversal_source_image():
    with pytest.raises(ValueError):
        validate_design_page(
            _valid_design(source_image="../../etc/passwd"), expected_page_no=1,
            expected_source_image="../../etc/passwd",
        )


def test_validate_design_page_rejects_arbitrary_code_embedding():
    design = _valid_design(blocks=[
        {"id": "x", "type": "body", "source_field": "body", "text": "<script>evil()</script>",
         "style": {"font_size": 20, "padding": 10}},
    ])
    with pytest.raises(ValueError, match="複製"):
        validate_design_page(design, expected_page_no=1, expected_source_image="assets/page_001.jpeg")


def test_validate_design_page_rejects_invalid_color_code():
    design = _valid_design()
    design["theme"]["primary_color"] = "red"
    with pytest.raises(ValueError, match="RRGGBB"):
        validate_design_page(design, expected_page_no=1, expected_source_image="assets/page_001.jpeg")


def test_validate_design_page_rejects_negative_font_size():
    design = _valid_design()
    design["blocks"][0]["style"]["font_size"] = -10
    with pytest.raises(ValueError, match="font_size"):
        validate_design_page(design, expected_page_no=1, expected_source_image="assets/page_001.jpeg")


def test_validate_design_page_rejects_canvas_out_of_range():
    design = _valid_design()
    design["canvas"]["width"] = 5
    with pytest.raises(ValueError, match="canvas"):
        validate_design_page(design, expected_page_no=1, expected_source_image="assets/page_001.jpeg")


def test_validate_design_page_rejects_nonexistent_source_field():
    design = _valid_design()
    design["blocks"][0]["source_field"] = "notes"
    with pytest.raises(ValueError, match="source_field"):
        validate_design_page(design, expected_page_no=1, expected_source_image="assets/page_001.jpeg")


def test_validate_design_page_rejects_unsupported_schema_version():
    design = _valid_design(schema_version=99)
    with pytest.raises(ValueError, match="schema_version"):
        validate_design_page(design, expected_page_no=1, expected_source_image="assets/page_001.jpeg")


def test_validate_design_page_rejects_missing_blocks():
    design = _valid_design(blocks=[])
    with pytest.raises(ValueError, match="blocks"):
        validate_design_page(design, expected_page_no=1, expected_source_image="assets/page_001.jpeg")


def test_validate_manifest_reports_missing_design_file_field():
    manifest = {"schema_version": 1, "pages": [{"page_no": 1, "template": "title_body"}]}
    errors = validate_manifest(manifest, expected_page_numbers=[1])
    assert any("design_file" in e for e in errors)


# --- lesson_pagesハッシュによる古いdesignの拒否（Phase 10.13連携） -----------------------------


def test_lesson_pages_sha256_matches_hashlib(tmp_path):
    import hashlib

    path = tmp_path / "lesson_pages.json"
    path.write_text('{"pages": []}', encoding="utf-8")
    assert lesson_pages_sha256(path) == hashlib.sha256(path.read_bytes()).hexdigest()


def test_check_manifest_freshness_accepts_matching_hash():
    manifest = {"source_lesson_pages_sha256": "abc123"}
    assert check_manifest_freshness(manifest, current_lesson_pages_sha256="abc123") is None


def test_check_manifest_freshness_rejects_mismatched_hash():
    manifest = {"source_lesson_pages_sha256": "old_hash"}
    error = check_manifest_freshness(manifest, current_lesson_pages_sha256="new_hash")
    assert error is not None
    assert "prepare-image-brushup" in error


def test_check_manifest_freshness_rejects_missing_field():
    manifest = {"schema_version": 1}
    error = check_manifest_freshness(manifest, current_lesson_pages_sha256="anything")
    assert error is not None


def test_render_ai_image_brushup_instructions_embeds_lesson_pages_hash(tmp_path):
    document = LessonDocument(
        metadata=LessonMetadata(mode="proofread"),
        pages=[LessonPage(page_no=1, title="t", body="b", summary="s", image_text="", layout_instruction="",
                           canva_prompt="", video_scene="", source_image="assets/page_001.jpeg", notes="")],
    )
    text = render_ai_image_brushup_instructions(document, tmp_path / "out", lesson_pages_sha256_value="deadbeef123")
    assert "deadbeef123" in text
    assert "source_lesson_pages_sha256" in text


def test_write_design_entry_points_embeds_actual_lesson_pages_hash(tmp_path):
    output_dir = tmp_path / "out"
    (output_dir / "editable").mkdir(parents=True)
    lesson_pages_path = output_dir / "editable" / "lesson_pages.json"
    lesson_pages_path.write_text('{"pages": []}', encoding="utf-8")
    document = LessonDocument(metadata=LessonMetadata(mode="proofread"), pages=[])

    write_design_entry_points(output_dir, document)

    expected_hash = lesson_pages_sha256(lesson_pages_path)
    instructions_text = (output_dir / "brushup_design" / "AI_IMAGE_BRUSHUP.md").read_text(encoding="utf-8")
    assert expected_hash in instructions_text
