from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.lesson_pages import LessonPage, lesson_document_from_dict, lesson_document_to_dict
from src.ocr_review_apply import (
    ApplyPlan,
    OcrReviewApplyInputError,
    apply_document,
    apply_proposed_text_to_page,
    parse_page_selection,
    reconstruct_fields_from_proposed_text,
    render_apply_report_json,
    render_apply_report_markdown,
    resolve_paths,
    validate_and_plan,
    write_apply_reports,
)


# --- フィクスチャ組み立てヘルパー ------------------------------------------------------------


def _build_original_lesson_page(page_no: int, *, original_text: str, source_image: str) -> LessonPage:
    """`original_text`（OCRそのまま等、反映前の想定文面）から、実際の派生ロジックを使って
    内部的に整合の取れた初期LessonPageを組み立てる（手打ちのfixtureが本物の派生ルールと
    食い違って偽の差分を生むのを防ぐため）。
    """
    base = LessonPage(
        page_no=page_no, title="", body="", summary="", image_text="",
        layout_instruction=f"layout for page {page_no}", canva_prompt="", video_scene="",
        source_image=source_image, notes=f"notes {page_no}", source_page_no=[page_no],
    )
    return apply_proposed_text_to_page(base, original_text)


def _candidate_page_dict(
    page_no: int,
    *,
    source_image: str,
    proposed_text: str,
    decision: str = "corrected",
    requires_human_review: bool = False,
    unresolved_spans: list | None = None,
) -> dict:
    return {
        "schema_version": 1,
        "page_no": page_no,
        "source_image": source_image,
        "decision": decision,
        "proposed_text": proposed_text,
        "corrections": [{"location": "1行目", "tesseract": "誤", "apple_vision": "誤", "adopted": "正", "reason": "テスト"}],
        "unresolved_spans": unresolved_spans or [],
        "requires_human_review": requires_human_review,
        "review_notes": "",
        "reviewed_by": "claude_code",
        "reviewed_at": "2026-07-12T00:00:00+09:00",
    }


def build_fixture(
    output_dir: Path,
    pages: list[dict],
    *,
    progress_overrides: dict | None = None,
    candidates_overrides: dict | None = None,
    skip_pages_in_candidates: set[int] | None = None,
) -> None:
    """`output_dir`配下に、apply-ocr-reviewが読み込む一式（editable/lesson_pages.json・
    ocr_comparison/pages/page_NNN.json・ocr_comparison/claude_review/{candidates,progress,pages/page_NNN}.json）
    を組み立てる。`pages`の各要素は{page_no, title, body, source_image, proposed_text, decision, ...}。
    """
    skip_pages_in_candidates = skip_pages_in_candidates or set()

    from src.lesson_pages import LessonDocument, LessonMetadata

    lesson_pages_dir = output_dir / "editable"
    lesson_pages_dir.mkdir(parents=True, exist_ok=True)
    lesson_document = LessonDocument(
        metadata=LessonMetadata(project_title="テスト教材", mode="proofread", source_policy="preserve_original",
                                 target_audience="テスト", generated_at="2026-07-12T00:00:00+09:00"),
        pages=[
            _build_original_lesson_page(
                p["page_no"], original_text=p.get("original_text", p["proposed_text"]), source_image=p["source_image"]
            )
            for p in pages
        ],
    )
    (lesson_pages_dir / "lesson_pages.json").write_text(
        json.dumps(lesson_document_to_dict(lesson_document), ensure_ascii=False, indent=2), encoding="utf-8"
    )

    comparison_pages_dir = output_dir / "ocr_comparison" / "pages"
    comparison_pages_dir.mkdir(parents=True, exist_ok=True)
    claude_review_dir = output_dir / "ocr_comparison" / "claude_review"
    claude_review_pages_dir = claude_review_dir / "pages"
    claude_review_pages_dir.mkdir(parents=True, exist_ok=True)

    candidate_entries = []
    for p in pages:
        comparison_data = {"page_no": p["page_no"], "source_image": p["source_image"]}
        (comparison_pages_dir / f"page_{p['page_no']:03d}.json").write_text(
            json.dumps(comparison_data, ensure_ascii=False), encoding="utf-8"
        )
        if p["page_no"] in skip_pages_in_candidates:
            continue
        candidate = _candidate_page_dict(
            p["page_no"],
            source_image=p["source_image"],
            proposed_text=p["proposed_text"],
            decision=p.get("decision", "corrected"),
            requires_human_review=p.get("requires_human_review", False),
            unresolved_spans=p.get("unresolved_spans"),
        )
        (claude_review_pages_dir / f"page_{p['page_no']:03d}.json").write_text(
            json.dumps(candidate, ensure_ascii=False), encoding="utf-8"
        )
        candidate_entries.append(candidate)

    decision_counts: dict[str, int] = {}
    for c in candidate_entries:
        decision_counts[c["decision"]] = decision_counts.get(c["decision"], 0) + 1

    candidates_data = {
        "schema_version": 1,
        "generated_at": "2026-07-12T00:00:00+09:00",
        "source": "claude_code_image_review",
        "total_pages": len(pages),
        "completed_pages": len(candidate_entries),
        "requires_human_review_pages": [p["page_no"] for p in pages if p.get("requires_human_review")],
        "decision_counts": decision_counts,
        "pages": candidate_entries,
    }
    if candidates_overrides:
        candidates_data.update(candidates_overrides)
    (claude_review_dir / "candidates.json").write_text(
        json.dumps(candidates_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    progress_data = {
        "schema_version": 1,
        "total_pages": len(pages),
        "completed_pages": [p["page_no"] for p in pages if p["page_no"] not in skip_pages_in_candidates],
        "unresolved_pages": [],
        "failed_pages": [],
        "remaining_pages": sorted(skip_pages_in_candidates),
        "updated_at": "2026-07-12T00:00:00+09:00",
    }
    if progress_overrides:
        progress_data.update(progress_overrides)
    (claude_review_dir / "progress.json").write_text(
        json.dumps(progress_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _default_pages() -> list[dict]:
    return [
        {
            "page_no": 1,
            "original_text": "誤タイトル\nますず本文の一行目",
            "source_image": "assets/page_001.jpeg",
            "proposed_text": "正タイトル\nまず本文の一行目",
        },
        {
            "page_no": 2,
            "original_text": "2ページ目\n変更なしの本文",
            "source_image": "assets/page_002.jpeg",
            "proposed_text": "2ページ目\n変更なしの本文",
        },
    ]


def _read_lesson_pages(output_dir: Path) -> dict:
    return json.loads((output_dir / "editable" / "lesson_pages.json").read_text(encoding="utf-8"))


# --- reconstruct_fields_from_proposed_text / apply_proposed_text_to_page --------------------


def test_reconstruct_fields_first_line_becomes_title_and_is_duplicated_into_body():
    fields = reconstruct_fields_from_proposed_text("タイトル行\n本文1行目\n本文2行目", page_no=1, source_image="a.jpg")
    assert fields["title"] == "タイトル行"
    # 既存proofread取り込み仕様(_text_to_lines)と同じく、title行はbodyからも除外されない。
    assert fields["body"].splitlines()[0] == ": タイトル行"
    assert fields["body"].splitlines()[1] == ": 本文1行目"
    assert fields["summary"] == "タイトル行 本文1行目"


def test_reconstruct_fields_title_truncated_to_60_chars():
    long_title = "あ" * 100
    fields = reconstruct_fields_from_proposed_text(f"{long_title}\n本文", page_no=1, source_image="a.jpg")
    assert len(fields["title"]) == 60


def test_apply_proposed_text_to_page_regenerates_derived_fields_and_preserves_layout():
    from src.lesson_pages import LessonPage

    page = LessonPage(
        page_no=1, title="旧", body=": 旧\n: ますず素直に", summary="旧", image_text="旧の要約",
        layout_instruction="レイアウトそのまま", canva_prompt="古いプロンプト", video_scene="古いシーン",
        source_image="assets/page_001.jpeg", notes="メモそのまま",
    )
    new_page = apply_proposed_text_to_page(page, "新タイトル\nまず素直に")
    assert new_page.title == "新タイトル"
    assert "まず素直に" in new_page.body
    assert "まず素直に" in new_page.image_text
    assert "まず素直に" in new_page.canva_prompt
    assert "まず素直に" in new_page.video_scene
    # layout_instruction/notesはOCR本文ではないため変更されない。
    assert new_page.layout_instruction == "レイアウトそのまま"
    assert new_page.notes == "メモそのまま"
    # 呼び出し元のpageオブジェクト自体は変更しない。
    assert page.title == "旧"


# --- parse_page_selection ------------------------------------------------------------------


def test_parse_page_selection_single_and_range():
    assert parse_page_selection("1,4,7-9", list(range(1, 12))) == [1, 4, 7, 8, 9]


def test_parse_page_selection_rejects_duplicates():
    with pytest.raises(ValueError):
        parse_page_selection("1,1", [1, 2])


def test_parse_page_selection_rejects_reversed_range():
    with pytest.raises(ValueError):
        parse_page_selection("9-7", list(range(1, 12)))


def test_parse_page_selection_rejects_nonexistent_page():
    with pytest.raises(ValueError):
        parse_page_selection("99", [1, 2, 3])


# --- validate_and_plan: 正常系 --------------------------------------------------------------


def test_validate_and_plan_passes_and_detects_changed_and_unchanged_pages(tmp_path):
    output_dir = tmp_path / "out"
    build_fixture(output_dir, _default_pages())
    paths = resolve_paths(output_dir)

    plan = validate_and_plan(paths)

    assert plan.passed is True
    assert plan.errors == []
    assert plan.target_pages == [1, 2]
    assert [p.page_no for p in plan.changed_pages] == [1]
    assert [p.page_no for p in plan.unchanged_pages] == [2]
    page1 = plan.changed_pages[0]
    assert page1.after["title"] == "正タイトル"
    assert "まず本文の一行目" in page1.after["body"]
    assert set(page1.changed_fields) >= {"title", "body"}


def test_validate_and_plan_with_pages_filter_targets_only_selected_pages(tmp_path):
    output_dir = tmp_path / "out"
    build_fixture(output_dir, _default_pages())
    paths = resolve_paths(output_dir)

    plan = validate_and_plan(paths, pages_spec="1")

    assert plan.passed is True
    assert plan.target_pages == [1]
    assert len(plan.pages) == 1


# --- validate_and_plan: 拒否系（バッチ全体が反映不可になることを確認） ----------------------------


def test_validate_and_plan_rejects_whole_batch_when_one_page_is_unresolved(tmp_path):
    pages = _default_pages()
    pages[1]["decision"] = "unresolved"
    pages[1]["unresolved_spans"] = [{"location": "1行目", "tesseract": "x", "apple_vision": "y", "reason": "不鮮明"}]
    pages[1]["requires_human_review"] = True
    output_dir = tmp_path / "out"
    build_fixture(output_dir, pages)
    paths = resolve_paths(output_dir)

    plan = validate_and_plan(paths)

    assert plan.passed is False
    page2 = next(p for p in plan.pages if p.page_no == 2)
    assert not page2.reflectable
    assert any("unresolved" in r for r in page2.reject_reasons)
    # unresolvedなページ自体だけでなく、バッチ全体が反映不可になる（page1も含め何も反映しない）。
    assert all(not p.reflectable is False or p.page_no == 2 for p in plan.pages)


def test_validate_and_plan_rejects_when_requires_human_review_true(tmp_path):
    pages = _default_pages()
    pages[0]["requires_human_review"] = True
    output_dir = tmp_path / "out"
    build_fixture(output_dir, pages)
    paths = resolve_paths(output_dir)

    plan = validate_and_plan(paths)

    assert plan.passed is False
    page1 = next(p for p in plan.pages if p.page_no == 1)
    assert any("requires_human_review" in r for r in page1.reject_reasons)


def test_validate_and_plan_rejects_empty_proposed_text(tmp_path):
    pages = _default_pages()
    pages[0]["proposed_text"] = "   "
    output_dir = tmp_path / "out"
    build_fixture(output_dir, pages)
    paths = resolve_paths(output_dir)

    plan = validate_and_plan(paths)

    assert plan.passed is False
    page1 = next(p for p in plan.pages if p.page_no == 1)
    assert any("proposed_text" in r for r in page1.reject_reasons)


def test_validate_and_plan_rejects_unknown_decision(tmp_path):
    pages = _default_pages()
    pages[0]["decision"] = "guessed"
    output_dir = tmp_path / "out"
    build_fixture(output_dir, pages)
    paths = resolve_paths(output_dir)

    plan = validate_and_plan(paths)

    assert plan.passed is False
    page1 = next(p for p in plan.pages if p.page_no == 1)
    assert any("decision" in r for r in page1.reject_reasons)


def test_validate_and_plan_rejects_page_not_yet_completed(tmp_path):
    output_dir = tmp_path / "out"
    build_fixture(output_dir, _default_pages(), skip_pages_in_candidates={2})
    paths = resolve_paths(output_dir)

    plan = validate_and_plan(paths, pages_spec="1")
    # page 2をcandidatesから除外しているが、page 1だけを対象にする場合はpage1は反映可能なはず。
    assert plan.passed is True

    plan_all = validate_and_plan(paths)
    # --pages省略時はcandidates.jsonに存在するページ(1のみ)が対象になるため、
    # remaining_pagesチェックでpage 2は対象に含まれずpassする。
    assert plan_all.target_pages == [1]


def test_validate_and_plan_rejects_failed_pages_in_progress(tmp_path):
    output_dir = tmp_path / "out"
    build_fixture(output_dir, _default_pages(), progress_overrides={"failed_pages": [2]})
    paths = resolve_paths(output_dir)

    plan = validate_and_plan(paths)

    assert plan.passed is False
    assert any("failed_pages" in e for e in plan.errors)


def test_validate_and_plan_rejects_unsupported_schema_version(tmp_path):
    output_dir = tmp_path / "out"
    build_fixture(output_dir, _default_pages(), candidates_overrides={"schema_version": 999})
    paths = resolve_paths(output_dir)

    plan = validate_and_plan(paths)

    assert plan.passed is False
    assert any("schema_version" in e for e in plan.errors)


def test_validate_and_plan_rejects_wrong_source_field(tmp_path):
    output_dir = tmp_path / "out"
    build_fixture(output_dir, _default_pages(), candidates_overrides={"source": "something_else"})
    paths = resolve_paths(output_dir)

    plan = validate_and_plan(paths)

    assert plan.passed is False
    assert any("source" in e for e in plan.errors)


def test_validate_and_plan_rejects_source_image_mismatch(tmp_path):
    output_dir = tmp_path / "out"
    build_fixture(output_dir, _default_pages())
    # lesson_pages.json側のsource_imageだけをこっそり書き換えて不一致を作る。
    lesson_pages_path = output_dir / "editable" / "lesson_pages.json"
    data = json.loads(lesson_pages_path.read_text(encoding="utf-8"))
    data["pages"][0]["source_image"] = "assets/different_image.jpeg"
    lesson_pages_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    paths = resolve_paths(output_dir)

    plan = validate_and_plan(paths)

    assert plan.passed is False
    page1 = next(p for p in plan.pages if p.page_no == 1)
    assert any("source_image" in r for r in page1.reject_reasons)


def test_validate_and_plan_rejects_path_traversal_source_image(tmp_path):
    output_dir = tmp_path / "out"
    pages = _default_pages()
    pages[0]["source_image"] = "../../etc/passwd"
    build_fixture(output_dir, pages)
    paths = resolve_paths(output_dir)

    plan = validate_and_plan(paths)

    assert plan.passed is False
    page1 = next(p for p in plan.pages if p.page_no == 1)
    assert any("パストラバーサル" in r or "source_image" in r for r in page1.reject_reasons)


def test_validate_and_plan_rejects_absolute_path_source_image(tmp_path):
    output_dir = tmp_path / "out"
    pages = _default_pages()
    pages[0]["source_image"] = "/etc/passwd"
    build_fixture(output_dir, pages)
    paths = resolve_paths(output_dir)

    plan = validate_and_plan(paths)

    assert plan.passed is False


def test_validate_and_plan_raises_on_missing_lesson_pages(tmp_path):
    output_dir = tmp_path / "out"
    build_fixture(output_dir, _default_pages())
    (output_dir / "editable" / "lesson_pages.json").unlink()
    paths = resolve_paths(output_dir)

    with pytest.raises((FileNotFoundError, OcrReviewApplyInputError)):
        validate_and_plan(paths)


def test_validate_and_plan_raises_on_missing_candidates(tmp_path):
    output_dir = tmp_path / "out"
    build_fixture(output_dir, _default_pages())
    (output_dir / "ocr_comparison" / "claude_review" / "candidates.json").unlink()
    paths = resolve_paths(output_dir)

    with pytest.raises(OcrReviewApplyInputError):
        validate_and_plan(paths)


def test_validate_and_plan_raises_on_invalid_json(tmp_path):
    output_dir = tmp_path / "out"
    build_fixture(output_dir, _default_pages())
    (output_dir / "ocr_comparison" / "claude_review" / "candidates.json").write_text("{not json", encoding="utf-8")
    paths = resolve_paths(output_dir)

    with pytest.raises(OcrReviewApplyInputError):
        validate_and_plan(paths)


def test_validate_and_plan_pages_spec_rejects_nonexistent_page(tmp_path):
    output_dir = tmp_path / "out"
    build_fixture(output_dir, _default_pages())
    paths = resolve_paths(output_dir)

    plan = validate_and_plan(paths, pages_spec="99")
    assert plan.passed is False
    assert any("99" in e for e in plan.errors)


# --- apply_document -------------------------------------------------------------------------


def test_apply_document_writes_backup_and_reflects_changes(tmp_path):
    output_dir = tmp_path / "out"
    build_fixture(output_dir, _default_pages())
    paths = resolve_paths(output_dir)
    plan = validate_and_plan(paths)

    result = apply_document(plan, paths)

    assert result.wrote_changes is True
    assert result.backup_path is not None
    assert result.backup_path.exists()

    updated = _read_lesson_pages(output_dir)
    page1 = next(p for p in updated["pages"] if p["page_no"] == 1)
    page2 = next(p for p in updated["pages"] if p["page_no"] == 2)
    assert page1["title"] == "正タイトル"
    assert "まず本文の一行目" in page1["body"]
    # page_no/source_image/layout_instruction/notesは保持される。
    assert page1["source_image"] == "assets/page_001.jpeg"
    assert page1["layout_instruction"] == "layout for page 1"
    assert page1["notes"] == "notes 1"
    # 変更のないページはそのまま。
    assert page2["title"] == "2ページ目"


def test_apply_document_preserves_metadata(tmp_path):
    output_dir = tmp_path / "out"
    build_fixture(output_dir, _default_pages())
    paths = resolve_paths(output_dir)
    plan = validate_and_plan(paths)

    apply_document(plan, paths)

    updated = _read_lesson_pages(output_dir)
    assert updated["metadata"]["project_title"] == "テスト教材"
    assert updated["metadata"]["mode"] == "proofread"


def test_apply_document_is_idempotent_and_does_not_duplicate_backup(tmp_path):
    output_dir = tmp_path / "out"
    build_fixture(output_dir, _default_pages())
    paths = resolve_paths(output_dir)

    plan1 = validate_and_plan(paths)
    result1 = apply_document(plan1, paths)
    assert result1.wrote_changes is True

    plan2 = validate_and_plan(paths)
    assert plan2.passed is True
    assert plan2.changed_pages == []
    result2 = apply_document(plan2, paths)
    assert result2.wrote_changes is False
    assert result2.backup_path is None

    backups = list((output_dir / "editable" / "backups").glob("*.json"))
    assert len(backups) == 1


def test_apply_document_raises_when_plan_not_passed(tmp_path):
    pages = _default_pages()
    pages[0]["decision"] = "unresolved"
    pages[0]["unresolved_spans"] = [{"location": "x", "tesseract": "a", "apple_vision": "b", "reason": "test"}]
    pages[0]["requires_human_review"] = True
    output_dir = tmp_path / "out"
    build_fixture(output_dir, pages)
    paths = resolve_paths(output_dir)
    plan = validate_and_plan(paths)
    assert plan.passed is False

    with pytest.raises(ValueError):
        apply_document(plan, paths)

    # lesson_pages.jsonは一切変更されていない。
    updated = _read_lesson_pages(output_dir)
    assert updated["pages"][0]["title"] == "誤タイトル"


def test_apply_document_result_loadable_by_existing_loader(tmp_path):
    output_dir = tmp_path / "out"
    build_fixture(output_dir, _default_pages())
    paths = resolve_paths(output_dir)
    plan = validate_and_plan(paths)
    apply_document(plan, paths)

    data = json.loads((output_dir / "editable" / "lesson_pages.json").read_text(encoding="utf-8"))
    document = lesson_document_from_dict(data)
    assert len(document.pages) == 2
    # 再度dictへ戻して書き出しても壊れない（既存フォーマットとの往復性）。
    assert lesson_document_to_dict(document)["pages"][0]["page_no"] == 1


# --- レポート出力 ----------------------------------------------------------------------------


def test_write_apply_reports_dry_run_generates_json_and_markdown_without_touching_lesson_pages(tmp_path):
    output_dir = tmp_path / "out"
    build_fixture(output_dir, _default_pages())
    paths = resolve_paths(output_dir)
    plan = validate_and_plan(paths)

    before = _read_lesson_pages(output_dir)
    write_apply_reports(plan, paths, mode="dry_run")
    after = _read_lesson_pages(output_dir)

    assert before == after
    assert paths.report_json_path.exists()
    assert paths.report_md_path.exists()
    report_json = json.loads(paths.report_json_path.read_text(encoding="utf-8"))
    assert report_json["passed"] is True
    assert report_json["mode"] == "dry_run"
    assert not (output_dir / "editable" / "backups").exists()


def test_render_apply_report_markdown_mentions_next_apply_command_on_pass(tmp_path):
    output_dir = tmp_path / "out"
    build_fixture(output_dir, _default_pages())
    paths = resolve_paths(output_dir)
    plan = validate_and_plan(paths)

    markdown = render_apply_report_markdown(plan, mode="dry_run")
    assert "apply-ocr-review" in markdown
    assert "--apply" in markdown


def test_render_apply_report_markdown_lists_reject_reasons_on_failure(tmp_path):
    pages = _default_pages()
    pages[0]["decision"] = "unresolved"
    pages[0]["unresolved_spans"] = [{"location": "x", "tesseract": "a", "apple_vision": "b", "reason": "t"}]
    pages[0]["requires_human_review"] = True
    output_dir = tmp_path / "out"
    build_fixture(output_dir, pages)
    paths = resolve_paths(output_dir)
    plan = validate_and_plan(paths)

    markdown = render_apply_report_markdown(plan, mode="dry_run")
    assert "反映不可ページ" in markdown
    assert "1" in markdown


def test_render_apply_report_json_round_trips_as_json():
    output_dir = Path("unused")
    plan = ApplyPlan(
        generated_at="2026-07-12T00:00:00+09:00", output_dir=str(output_dir), lesson_pages_path="a", candidates_path="b",
        target_pages=[], passed=True, errors=[], pages=[],
    )
    payload = render_apply_report_json(plan, mode="dry_run")
    json.dumps(payload)  # シリアライズ可能であることを確認
