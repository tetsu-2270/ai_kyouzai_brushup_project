from __future__ import annotations

import json

import pytest

from src import content_brushup as cb
from src.lesson_pages import LessonDocument, LessonMetadata, LessonPage


def _page(page_no=1, **kwargs):
    defaults = dict(
        page_no=page_no, title=f"タイトル{page_no}", body=f": 本文{page_no}",
        summary=f"要約{page_no}", image_text="", layout_instruction=f"layout{page_no}",
        canva_prompt="", video_scene="", source_image=f"assets/page_{page_no:03d}.jpeg",
        notes=f"notes{page_no}", source_page_no=[page_no],
    )
    defaults.update(kwargs)
    return LessonPage(**defaults)


def _document(pages, **meta_kwargs):
    meta = LessonMetadata(mode="proofread", project_title="テスト教材", target_audience="初心者", tone="丁寧")
    for k, v in meta_kwargs.items():
        setattr(meta, k, v)
    return LessonDocument(metadata=meta, pages=pages)


def _write_lesson_pages(paths, document):
    from src.lesson_pages import lesson_document_to_dict

    paths.lesson_pages_path.parent.mkdir(parents=True, exist_ok=True)
    paths.lesson_pages_path.write_text(
        json.dumps(lesson_document_to_dict(document), ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _candidate(page_no=1, *, original, proposed, changes=None, risk_level="low", requires_human_review=False):
    return {
        "schema_version": 1, "page_no": page_no, "source_page_no": [page_no],
        "source_image": f"assets/page_{page_no:03d}.jpeg", "page_purpose": "test",
        "original": original, "proposed": proposed, "changes": changes or [],
        "preserved_facts": [], "risk_level": risk_level, "requires_human_review": requires_human_review,
        "review_reasons": [], "reviewed_by": "ai_work_agent", "reviewed_at": "2026-07-12T00:00:00+09:00",
    }


# --- スナップショット ------------------------------------------------------------------------


def test_build_snapshot_records_sha256_and_pages(tmp_path):
    document = _document([_page(1), _page(2)])
    paths = cb.resolve_paths(tmp_path)
    _write_lesson_pages(paths, document)

    snapshot = cb.build_snapshot(document, paths.lesson_pages_path)

    assert snapshot["source"] == "verified_ocr_lesson_pages"
    assert snapshot["source_sha256"] == cb.file_sha256(paths.lesson_pages_path)
    assert len(snapshot["pages"]) == 2
    assert snapshot["pages"][0]["title"] == "タイトル1"
    assert snapshot["pages"][0]["body"] == ": 本文1"


def test_check_snapshot_status_detects_new_matching_and_stale(tmp_path):
    document = _document([_page(1)])
    paths = cb.resolve_paths(tmp_path)
    _write_lesson_pages(paths, document)

    status_new = cb.check_snapshot_status(paths)
    assert status_new.exists is False

    cb.write_prepare_entry_points(paths, document)
    status_match = cb.check_snapshot_status(paths)
    assert status_match.exists is True
    assert status_match.stale is False

    # lesson_pages.jsonを書き換えるとスナップショットは古くなる。
    document2 = _document([_page(1, summary="変更後の要約")])
    _write_lesson_pages(paths, document2)
    status_stale = cb.check_snapshot_status(paths)
    assert status_stale.exists is True
    assert status_stale.stale is True


def test_write_prepare_entry_points_does_not_modify_lesson_pages(tmp_path):
    document = _document([_page(1)])
    paths = cb.resolve_paths(tmp_path)
    _write_lesson_pages(paths, document)
    before = paths.lesson_pages_path.read_text(encoding="utf-8")

    cb.write_prepare_entry_points(paths, document)

    after = paths.lesson_pages_path.read_text(encoding="utf-8")
    assert before == after


# --- 指示書生成 ------------------------------------------------------------------------------


def test_instructions_do_not_embed_body_text(tmp_path):
    document = _document([_page(1, title="固有タイトルXYZ", body=": 固有本文ABC")])
    text = cb.render_ai_content_brushup_instructions(document, tmp_path / "out", "deadbeef")
    assert "固有タイトルXYZ" not in text
    assert "固有本文ABC" not in text


def test_instructions_do_not_embed_absolute_path(tmp_path):
    document = _document([_page(1)])
    abs_dir = tmp_path / "out"
    text = cb.render_ai_content_brushup_instructions(document, abs_dir, "deadbeef")
    assert str(abs_dir) not in text


def test_instructions_state_ocr_confirmed_is_not_finished_prose(tmp_path):
    document = _document([_page(1)])
    text = cb.render_ai_content_brushup_instructions(document, tmp_path / "out", "deadbeef")
    assert "文章品質が" in text and "完成している" in text
    assert "ページ数" in text and "変更しない" in text or "変更しません" in text


def test_instructions_scale_independent_of_page_count(tmp_path):
    small = _document([_page(i) for i in range(1, 4)])
    large = _document([_page(i) for i in range(1, 138)])
    text_small = cb.render_ai_content_brushup_instructions(small, tmp_path / "out", "h")
    text_large = cb.render_ai_content_brushup_instructions(large, tmp_path / "out", "h")
    assert "対象ページ総数: 3" in text_small
    assert "対象ページ総数: 137" in text_large


def test_instructions_embed_snapshot_hash():
    document = _document([_page(1)])
    text = cb.render_ai_content_brushup_instructions(document, __import__("pathlib").Path("out"), "abc123hash")
    assert "abc123hash" in text


def test_render_content_brushup_readme_explains_snapshot_vs_proposed():
    text = cb.render_content_brushup_readme()
    assert "OCR確定原文" in text and "ブラッシュアップ済み本文" in text


# --- 候補JSON検証（正常系） --------------------------------------------------------------------


def _snapshot_page(page_no=1, **kwargs):
    defaults = {"page_no": page_no, "source_page_no": [page_no], "source_image": f"assets/page_{page_no:03d}.jpeg",
                "title": f"タイトル{page_no}", "body": f": 本文{page_no}", "summary": f"要約{page_no}"}
    defaults.update(kwargs)
    return defaults


def test_validate_candidate_page_accepts_valid_candidate():
    snap = _snapshot_page(1)
    candidate = _candidate(1, original={"title": "タイトル1", "body": ": 本文1", "summary": "要約1"},
                            proposed={"title": "タイトル1", "body": ": 改善本文1", "summary": "要約1"},
                            changes=[{"field": "body", "before": "本文1", "after": "改善本文1", "reason": "分かりやすく", "change_type": "clarify"}])
    errors = cb.validate_candidate_page(candidate, expected_page_no=1, snapshot_page=snap)
    assert errors == []


def test_validate_candidate_page_accepts_no_change_page():
    snap = _snapshot_page(1)
    candidate = _candidate(1, original={"title": "タイトル1", "body": ": 本文1", "summary": "要約1"},
                            proposed={"title": "タイトル1", "body": ": 本文1", "summary": "要約1"}, changes=[])
    errors = cb.validate_candidate_page(candidate, expected_page_no=1, snapshot_page=snap)
    assert errors == []


# --- 候補JSON検証（拒否系） --------------------------------------------------------------------


def test_validate_candidate_page_rejects_original_mismatch():
    snap = _snapshot_page(1)
    candidate = _candidate(1, original={"title": "改変済み", "body": ": 本文1", "summary": "要約1"},
                            proposed={"title": "タイトル1", "body": ": 本文1", "summary": "要約1"})
    errors = cb.validate_candidate_page(candidate, expected_page_no=1, snapshot_page=snap)
    assert any("original.title" in e for e in errors)


def test_validate_candidate_page_rejects_empty_proposed():
    snap = _snapshot_page(1)
    candidate = _candidate(1, original={"title": "タイトル1", "body": ": 本文1", "summary": "要約1"},
                            proposed={"title": "タイトル1", "body": "", "summary": "要約1"})
    errors = cb.validate_candidate_page(candidate, expected_page_no=1, snapshot_page=snap)
    assert any("proposed.body" in e for e in errors)


def test_validate_candidate_page_rejects_before_not_in_original():
    snap = _snapshot_page(1)
    candidate = _candidate(1, original={"title": "タイトル1", "body": ": 本文1", "summary": "要約1"},
                            proposed={"title": "タイトル1", "body": ": 改善本文1", "summary": "要約1"},
                            changes=[{"field": "body", "before": "存在しない文言", "after": "改善本文1", "reason": "r", "change_type": "clarify"}])
    errors = cb.validate_candidate_page(candidate, expected_page_no=1, snapshot_page=snap)
    assert any("before" in e for e in errors)


def test_validate_candidate_page_rejects_after_not_in_proposed():
    snap = _snapshot_page(1)
    candidate = _candidate(1, original={"title": "タイトル1", "body": ": 本文1", "summary": "要約1"},
                            proposed={"title": "タイトル1", "body": ": 改善本文1", "summary": "要約1"},
                            changes=[{"field": "body", "before": "本文1", "after": "存在しない文言", "reason": "r", "change_type": "clarify"}])
    errors = cb.validate_candidate_page(candidate, expected_page_no=1, snapshot_page=snap)
    assert any("after" in e for e in errors)


def test_validate_candidate_page_rejects_unknown_change_type():
    snap = _snapshot_page(1)
    candidate = _candidate(1, original={"title": "タイトル1", "body": ": 本文1", "summary": "要約1"},
                            proposed={"title": "タイトル1", "body": ": 改善本文1", "summary": "要約1"},
                            changes=[{"field": "body", "before": "本文1", "after": "改善本文1", "reason": "r", "change_type": "invented_type"}])
    errors = cb.validate_candidate_page(candidate, expected_page_no=1, snapshot_page=snap)
    assert any("change_type" in e for e in errors)


def test_validate_candidate_page_rejects_invalid_risk_level():
    snap = _snapshot_page(1)
    candidate = _candidate(1, original={"title": "タイトル1", "body": ": 本文1", "summary": "要約1"},
                            proposed={"title": "タイトル1", "body": ": 本文1", "summary": "要約1"}, risk_level="critical")
    errors = cb.validate_candidate_page(candidate, expected_page_no=1, snapshot_page=snap)
    assert any("risk_level" in e for e in errors)


def test_validate_candidate_page_rejects_high_risk_without_human_review():
    snap = _snapshot_page(1)
    candidate = _candidate(1, original={"title": "タイトル1", "body": ": 本文1", "summary": "要約1"},
                            proposed={"title": "タイトル1", "body": ": 本文1", "summary": "要約1"},
                            risk_level="high", requires_human_review=False)
    errors = cb.validate_candidate_page(candidate, expected_page_no=1, snapshot_page=snap)
    assert any("high" in e and "requires_human_review" in e for e in errors)


def test_validate_candidate_page_rejects_page_no_mismatch():
    snap = _snapshot_page(1)
    candidate = _candidate(2, original={"title": "タイトル1", "body": ": 本文1", "summary": "要約1"},
                            proposed={"title": "タイトル1", "body": ": 本文1", "summary": "要約1"})
    errors = cb.validate_candidate_page(candidate, expected_page_no=1, snapshot_page=snap)
    assert any("page_no" in e for e in errors)


def test_validate_candidate_page_rejects_source_image_mismatch():
    snap = _snapshot_page(1)
    candidate = _candidate(1, original={"title": "タイトル1", "body": ": 本文1", "summary": "要約1"},
                            proposed={"title": "タイトル1", "body": ": 本文1", "summary": "要約1"})
    candidate["source_image"] = "assets/wrong.jpeg"
    errors = cb.validate_candidate_page(candidate, expected_page_no=1, snapshot_page=snap)
    assert any("source_image" in e for e in errors)


# --- 集約JSON検証 ----------------------------------------------------------------------------


def test_validate_candidates_aggregate_accepts_consistent_data():
    candidates_data = {
        "schema_version": 1, "source": "ai_content_brushup", "source_snapshot_sha256": "hash1",
        "total_pages": 2, "completed_pages": 2, "requires_human_review_pages": [],
        "risk_counts": {"low": 2, "medium": 0, "high": 0},
        "pages": [{"page_no": 1}, {"page_no": 2}],
    }
    errors = cb.validate_candidates_aggregate(candidates_data, expected_page_numbers=[1, 2], expected_snapshot_sha256="hash1")
    assert errors == []


def test_validate_candidates_aggregate_rejects_snapshot_hash_mismatch():
    candidates_data = {
        "schema_version": 1, "source": "ai_content_brushup", "source_snapshot_sha256": "old_hash",
        "total_pages": 1, "completed_pages": 1, "requires_human_review_pages": [],
        "risk_counts": {"low": 1, "medium": 0, "high": 0}, "pages": [{"page_no": 1}],
    }
    errors = cb.validate_candidates_aggregate(candidates_data, expected_page_numbers=[1], expected_snapshot_sha256="new_hash")
    assert any("source_snapshot_sha256" in e for e in errors)


def test_validate_candidates_aggregate_rejects_duplicate_page_no():
    candidates_data = {
        "schema_version": 1, "source": "ai_content_brushup", "source_snapshot_sha256": "h",
        "total_pages": 2, "completed_pages": 2, "requires_human_review_pages": [],
        "risk_counts": {"low": 2, "medium": 0, "high": 0}, "pages": [{"page_no": 1}, {"page_no": 1}],
    }
    errors = cb.validate_candidates_aggregate(candidates_data, expected_page_numbers=[1, 2], expected_snapshot_sha256="h")
    assert any("重複" in e for e in errors)


def test_validate_candidates_aggregate_rejects_wrong_source():
    candidates_data = {
        "schema_version": 1, "source": "something_else", "source_snapshot_sha256": "h",
        "total_pages": 1, "completed_pages": 1, "requires_human_review_pages": [],
        "risk_counts": {"low": 1, "medium": 0, "high": 0}, "pages": [{"page_no": 1}],
    }
    errors = cb.validate_candidates_aggregate(candidates_data, expected_page_numbers=[1], expected_snapshot_sha256="h")
    assert any("source" in e for e in errors)


def test_validate_candidates_aggregate_rejects_risk_count_mismatch():
    candidates_data = {
        "schema_version": 1, "source": "ai_content_brushup", "source_snapshot_sha256": "h",
        "total_pages": 1, "completed_pages": 1, "requires_human_review_pages": [],
        "risk_counts": {"low": 5, "medium": 0, "high": 0}, "pages": [{"page_no": 1}],
    }
    errors = cb.validate_candidates_aggregate(candidates_data, expected_page_numbers=[1], expected_snapshot_sha256="h")
    assert any("risk_counts" in e for e in errors)


# --- 差分レンダリング（安全なエスケープ） ---------------------------------------------------------


def test_render_content_diff_escapes_html_and_marks_differences():
    original_html, proposed_html = cb.render_content_diff("<script>alert(1)</script>元の文章です", "改善された文章です")
    assert "<script>" not in original_html
    assert "&lt;script&gt;" in original_html
    assert "</script" not in proposed_html.replace("</script>", "")  # comparison.htmlに閉じタグ以外を含めない


def test_render_content_diff_handles_empty_strings():
    original_html, proposed_html = cb.render_content_diff("", "")
    assert "本文なし" in original_html


# --- review.html / review_summary.md ----------------------------------------------------------


def test_render_review_html_is_self_contained_and_shows_diff(tmp_path):
    document = _document([_page(1, title="タイトル1", body=": 元の本文", summary="要約1")])
    snapshot = cb.build_snapshot(document, tmp_path / "dummy") if False else {
        "source_sha256": "abc", "pages": [_snapshot_page(1, title="タイトル1", body=": 元の本文", summary="要約1")]
    }
    candidate_pages = {1: _candidate(1, original={"title": "タイトル1", "body": ": 元の本文", "summary": "要約1"},
                                      proposed={"title": "タイトル1", "body": ": 改善された本文", "summary": "要約1"},
                                      changes=[{"field": "body", "before": "元の本文", "after": "改善された本文", "reason": "分かりやすさ向上", "change_type": "clarify"}])}
    html_text = cb.render_review_html(document, snapshot, candidate_pages, tmp_path)
    assert "<!doctype html>" in html_text.lower()
    assert "http://" not in html_text and "https://" not in html_text
    assert "cdn." not in html_text.lower()
    assert "改善された本文" in html_text
    assert "OCR確定原文" in html_text and "変更されていません" in html_text


def test_render_review_summary_lists_next_command():
    document = _document([_page(1)])
    candidates_data = {
        "completed_pages": 1, "requires_human_review_pages": [], "risk_counts": {"low": 1, "medium": 0, "high": 0},
        "pages": [{"page_no": 1, "changes": [{"change_type": "clarify", "before": "a", "after": "b", "reason": "r"}]}],
    }
    summary = cb.render_review_summary_markdown(document, candidates_data, next_command="python3 -m src.cli apply-content-brushup --output-dir out --apply")
    assert "apply-content-brushup" in summary
    assert "Page 1" in summary
