from __future__ import annotations

import json

import pytest

from src import content_brushup as cb
from src import content_brushup_apply as cba
from src.lesson_pages import LessonDocument, LessonMetadata, LessonPage, lesson_document_to_dict


def _page(page_no=1, **kwargs):
    defaults = dict(
        page_no=page_no, title=f"タイトル{page_no}", body=f": 本文{page_no}",
        summary=f"要約{page_no}", image_text="", layout_instruction=f"layout{page_no}",
        canva_prompt="", video_scene="", source_image=f"assets/page_{page_no:03d}.jpeg",
        notes=f"notes{page_no}", source_page_no=[page_no],
    )
    defaults.update(kwargs)
    return LessonPage(**defaults)


def _document(pages):
    return LessonDocument(metadata=LessonMetadata(mode="proofread", project_title="テスト教材"), pages=pages)


def _write_lesson_pages(paths, document):
    paths.lesson_pages_path.parent.mkdir(parents=True, exist_ok=True)
    paths.lesson_pages_path.write_text(
        json.dumps(lesson_document_to_dict(document), ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _candidate(page_no, *, original, proposed, changes=None, risk_level="low", requires_human_review=False):
    return {
        "schema_version": 1, "page_no": page_no, "source_page_no": [page_no],
        "source_image": f"assets/page_{page_no:03d}.jpeg", "page_purpose": "test",
        "original": original, "proposed": proposed, "changes": changes or [],
        "preserved_facts": [], "risk_level": risk_level, "requires_human_review": requires_human_review,
        "review_reasons": [], "reviewed_by": "ai_work_agent", "reviewed_at": "2026-07-12T00:00:00+09:00",
    }


def build_fixture(paths, pages: list[dict]) -> dict:
    """`paths`配下に、prepare→AIエージェント役の候補作成、を模したフィクスチャ一式を作る。

    `pages`の各要素: {page_no, original_body(省略時はtitle等から自動), proposed_body, risk_level, requires_human_review}
    """
    lesson_pages = [
        _page(p["page_no"], title=p.get("title", f"タイトル{p['page_no']}"), body=p.get("original_body", f": 本文{p['page_no']}"),
              summary=p.get("summary", f"要約{p['page_no']}"))
        for p in pages
    ]
    document = _document(lesson_pages)
    _write_lesson_pages(paths, document)
    cb.write_prepare_entry_points(paths, document)
    snapshot = json.loads(paths.snapshot_path.read_text(encoding="utf-8"))

    paths.pages_dir.mkdir(parents=True, exist_ok=True)
    candidate_entries = []
    for p in pages:
        page_no = p["page_no"]
        original = {"title": p.get("title", f"タイトル{page_no}"), "body": p.get("original_body", f": 本文{page_no}"), "summary": p.get("summary", f"要約{page_no}")}
        proposed = {"title": p.get("title", f"タイトル{page_no}"), "body": p.get("proposed_body", original["body"]), "summary": p.get("summary", f"要約{page_no}")}
        changes = []
        if original["body"] != proposed["body"]:
            changes = [{"field": "body", "before": original["body"].lstrip(": "), "after": proposed["body"].lstrip(": "), "reason": "分かりやすさ向上", "change_type": "clarify"}]
        candidate = _candidate(page_no, original=original, proposed=proposed, changes=changes,
                                risk_level=p.get("risk_level", "low"), requires_human_review=p.get("requires_human_review", False))
        (paths.pages_dir / f"page_{page_no:03d}.json").write_text(json.dumps(candidate, ensure_ascii=False), encoding="utf-8")
        candidate_entries.append(candidate)

    risk_counts = {"low": 0, "medium": 0, "high": 0}
    for c in candidate_entries:
        risk_counts[c["risk_level"]] += 1

    progress = {
        "schema_version": 1, "total_pages": len(pages), "completed_pages": [p["page_no"] for p in pages],
        "requires_human_review_pages": [p["page_no"] for p in pages if p.get("requires_human_review")],
        "failed_pages": [], "remaining_pages": [], "updated_at": "2026-07-12T00:00:00+09:00",
    }
    paths.progress_path.write_text(json.dumps(progress, ensure_ascii=False), encoding="utf-8")

    candidates_data = {
        "schema_version": 1, "generated_at": "2026-07-12T00:00:00+09:00", "source": "ai_content_brushup",
        "source_snapshot_sha256": snapshot["source_sha256"], "total_pages": len(pages), "completed_pages": len(pages),
        "requires_human_review_pages": progress["requires_human_review_pages"], "risk_counts": risk_counts,
        "pages": candidate_entries,
    }
    paths.candidates_path.write_text(json.dumps(candidates_data, ensure_ascii=False), encoding="utf-8")
    return candidates_data


def _default_pages():
    return [
        {"page_no": 1, "original_body": ": 完璧を求めない", "proposed_body": ": 完璧を目指さず、まずは素直にやってみましょう"},
        {"page_no": 2, "original_body": ": 変更なしの本文", "proposed_body": ": 変更なしの本文"},
    ]


def _read_lesson_pages(paths) -> dict:
    return json.loads(paths.lesson_pages_path.read_text(encoding="utf-8"))


# --- parse_page_selection --------------------------------------------------------------------


def test_parse_page_selection_single_and_range():
    assert cba.parse_page_selection("1,4,7-9", list(range(1, 12))) == [1, 4, 7, 8, 9]


def test_parse_page_selection_rejects_nonexistent_page():
    with pytest.raises(ValueError):
        cba.parse_page_selection("99", [1, 2, 3])


# --- validate_and_plan: 正常系 --------------------------------------------------------------


def test_validate_and_plan_passes_and_detects_changed_and_unchanged_pages(tmp_path):
    paths = cb.resolve_paths(tmp_path)
    build_fixture(paths, _default_pages())

    plan = cba.validate_and_plan(paths)

    assert plan.passed is True
    assert plan.errors == []
    assert [p.page_no for p in plan.changed_pages] == [1]
    assert [p.page_no for p in plan.unchanged_pages] == [2]
    page1 = plan.changed_pages[0]
    assert "完璧を目指さず" in page1.after["body"]
    assert set(page1.changed_fields) >= {"body"}


def test_validate_and_plan_with_pages_filter(tmp_path):
    paths = cb.resolve_paths(tmp_path)
    build_fixture(paths, _default_pages())

    plan = cba.validate_and_plan(paths, pages_spec="1")

    assert plan.passed is True
    assert plan.target_pages == [1]


# --- validate_and_plan: 拒否系（全体停止方式） -------------------------------------------------


def test_validate_and_plan_rejects_whole_batch_when_one_page_is_high_risk(tmp_path):
    paths = cb.resolve_paths(tmp_path)
    pages = _default_pages()
    pages[1]["risk_level"] = "high"
    pages[1]["requires_human_review"] = True
    build_fixture(paths, pages)

    plan = cba.validate_and_plan(paths)

    assert plan.passed is False
    page2 = next(p for p in plan.pages if p.page_no == 2)
    assert not page2.reflectable
    assert any("high" in r for r in page2.reject_reasons)


def test_validate_and_plan_rejects_requires_human_review(tmp_path):
    paths = cb.resolve_paths(tmp_path)
    pages = _default_pages()
    pages[0]["requires_human_review"] = True
    build_fixture(paths, pages)

    plan = cba.validate_and_plan(paths)

    assert plan.passed is False
    page1 = next(p for p in plan.pages if p.page_no == 1)
    assert any("requires_human_review" in r for r in page1.reject_reasons)


def test_validate_and_plan_raises_on_missing_snapshot(tmp_path):
    paths = cb.resolve_paths(tmp_path)
    build_fixture(paths, _default_pages())
    paths.snapshot_path.unlink()

    with pytest.raises(cba.ContentBrushupInputError):
        cba.validate_and_plan(paths)


def test_validate_and_plan_raises_on_missing_candidates(tmp_path):
    paths = cb.resolve_paths(tmp_path)
    build_fixture(paths, _default_pages())
    paths.candidates_path.unlink()

    with pytest.raises(cba.ContentBrushupInputError):
        cba.validate_and_plan(paths)


def test_validate_and_plan_rejects_failed_pages_in_progress(tmp_path):
    paths = cb.resolve_paths(tmp_path)
    build_fixture(paths, _default_pages())
    progress = json.loads(paths.progress_path.read_text(encoding="utf-8"))
    progress["failed_pages"] = [2]
    paths.progress_path.write_text(json.dumps(progress, ensure_ascii=False), encoding="utf-8")

    plan = cba.validate_and_plan(paths)

    assert plan.passed is False
    assert any("failed_pages" in e for e in plan.errors)


def test_validate_and_plan_pages_spec_rejects_nonexistent_page(tmp_path):
    paths = cb.resolve_paths(tmp_path)
    build_fixture(paths, _default_pages())

    plan = cba.validate_and_plan(paths, pages_spec="99")
    assert plan.passed is False
    assert any("99" in e for e in plan.errors)


# --- apply_document ---------------------------------------------------------------------------


def test_apply_document_writes_backup_and_reflects_changes_and_recomputes_derived_fields(tmp_path):
    paths = cb.resolve_paths(tmp_path)
    build_fixture(paths, _default_pages())
    plan = cba.validate_and_plan(paths)

    result = cba.apply_document(plan, paths)

    assert result.wrote_changes is True
    assert result.backup_path is not None and result.backup_path.exists()

    updated = _read_lesson_pages(paths)
    page1 = next(p for p in updated["pages"] if p["page_no"] == 1)
    page2 = next(p for p in updated["pages"] if p["page_no"] == 2)
    assert "完璧を目指さず" in page1["body"]
    # image_text/canva_prompt/video_sceneが本文の変更に合わせて再計算されていること。
    assert "完璧を目指さず" in page1["image_text"]
    assert "完璧を目指さず" in page1["canva_prompt"]
    # 保持されるべき項目。
    assert page1["source_image"] == "assets/page_001.jpeg"
    assert page1["layout_instruction"] == "layout1"
    assert page1["notes"] == "notes1"
    assert page1["source_page_no"] == [1]
    assert page2["body"] == ": 変更なしの本文"


def test_apply_document_preserves_metadata(tmp_path):
    paths = cb.resolve_paths(tmp_path)
    build_fixture(paths, _default_pages())
    plan = cba.validate_and_plan(paths)

    cba.apply_document(plan, paths)

    updated = _read_lesson_pages(paths)
    assert updated["metadata"]["project_title"] == "テスト教材"


def test_apply_document_does_not_touch_snapshot(tmp_path):
    paths = cb.resolve_paths(tmp_path)
    build_fixture(paths, _default_pages())
    before_snapshot = paths.snapshot_path.read_text(encoding="utf-8")
    plan = cba.validate_and_plan(paths)

    cba.apply_document(plan, paths)

    after_snapshot = paths.snapshot_path.read_text(encoding="utf-8")
    assert before_snapshot == after_snapshot


def test_apply_document_is_idempotent_and_does_not_duplicate_backup(tmp_path):
    paths = cb.resolve_paths(tmp_path)
    build_fixture(paths, _default_pages())

    plan1 = cba.validate_and_plan(paths)
    result1 = cba.apply_document(plan1, paths)
    assert result1.wrote_changes is True

    plan2 = cba.validate_and_plan(paths)
    assert plan2.passed is True
    assert plan2.changed_pages == []
    result2 = cba.apply_document(plan2, paths)
    assert result2.wrote_changes is False
    assert result2.backup_path is None

    backups = list(paths.backups_dir.glob("*.json"))
    assert len(backups) == 1


def test_second_dry_run_after_apply_still_passes(tmp_path):
    """--apply成功後、lesson_pages.json全体のハッシュはスナップショット作成時から変わるが、
    フィールド単位の突き合わせにより2回目のdry-runも正常にpassする（冪等性）。"""
    paths = cb.resolve_paths(tmp_path)
    build_fixture(paths, _default_pages())
    plan1 = cba.validate_and_plan(paths)
    cba.apply_document(plan1, paths)

    plan2 = cba.validate_and_plan(paths)
    assert plan2.passed is True
    assert plan2.errors == []


def test_apply_document_raises_when_plan_not_passed(tmp_path):
    paths = cb.resolve_paths(tmp_path)
    pages = _default_pages()
    pages[0]["risk_level"] = "high"
    pages[0]["requires_human_review"] = True
    build_fixture(paths, pages)
    plan = cba.validate_and_plan(paths)
    assert plan.passed is False

    with pytest.raises(ValueError):
        cba.apply_document(plan, paths)

    updated = _read_lesson_pages(paths)
    assert updated["pages"][0]["body"] == ": 完璧を求めない"


def test_apply_document_result_loadable_by_existing_loader(tmp_path):
    from src.lesson_pages import lesson_document_from_dict

    paths = cb.resolve_paths(tmp_path)
    build_fixture(paths, _default_pages())
    plan = cba.validate_and_plan(paths)
    cba.apply_document(plan, paths)

    data = json.loads(paths.lesson_pages_path.read_text(encoding="utf-8"))
    document = lesson_document_from_dict(data)
    assert len(document.pages) == 2


# --- レポート・レビューHTML生成 -----------------------------------------------------------------


def test_write_apply_reports_dry_run_does_not_touch_lesson_pages(tmp_path):
    paths = cb.resolve_paths(tmp_path)
    build_fixture(paths, _default_pages())
    plan = cba.validate_and_plan(paths)

    before = _read_lesson_pages(paths)
    cba.write_apply_reports(plan, paths, mode="dry_run")
    after = _read_lesson_pages(paths)

    assert before == after
    assert (paths.content_dir / "apply_report.json").exists()
    assert (paths.content_dir / "apply_report.md").exists()
    assert paths.review_html_path.exists()
    assert paths.review_summary_path.exists()
    report_json = json.loads((paths.content_dir / "apply_report.json").read_text(encoding="utf-8"))
    assert report_json["passed"] is True
    assert not paths.backups_dir.exists()


def test_render_apply_report_markdown_mentions_next_apply_command_on_pass(tmp_path):
    paths = cb.resolve_paths(tmp_path)
    build_fixture(paths, _default_pages())
    plan = cba.validate_and_plan(paths)

    markdown = cba.render_apply_report_markdown(plan, mode="dry_run")
    assert "apply-content-brushup" in markdown
    assert "--apply" in markdown


def test_render_apply_report_markdown_suggests_prepare_image_brushup_after_apply(tmp_path):
    paths = cb.resolve_paths(tmp_path)
    build_fixture(paths, _default_pages())
    plan = cba.validate_and_plan(paths)
    result = cba.apply_document(plan, paths)

    markdown = cba.render_apply_report_markdown(plan, mode="apply", result=result)
    assert "prepare-image-brushup" in markdown
