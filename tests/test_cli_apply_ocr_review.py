from __future__ import annotations

import json

import pytest

from src.cli import main
from tests.test_ocr_review_apply import _default_pages, build_fixture


def _run(monkeypatch, argv):
    monkeypatch.setattr("sys.argv", ["cli"] + argv)
    main()


def test_apply_ocr_review_requires_dry_run_or_apply(tmp_path, monkeypatch):
    output_dir = tmp_path / "out"
    build_fixture(output_dir, _default_pages())
    monkeypatch.setattr("sys.argv", ["cli", "apply-ocr-review", "--output-dir", str(output_dir)])
    with pytest.raises(SystemExit):
        main()


def test_apply_ocr_review_rejects_both_dry_run_and_apply(tmp_path, monkeypatch):
    output_dir = tmp_path / "out"
    build_fixture(output_dir, _default_pages())
    monkeypatch.setattr(
        "sys.argv", ["cli", "apply-ocr-review", "--output-dir", str(output_dir), "--dry-run", "--apply"]
    )
    with pytest.raises(SystemExit):
        main()


def test_apply_ocr_review_dry_run_passes_and_prints_banner(tmp_path, monkeypatch, capsys):
    output_dir = tmp_path / "out"
    build_fixture(output_dir, _default_pages())

    _run(monkeypatch, ["apply-ocr-review", "--output-dir", str(output_dir), "--dry-run"])

    captured = capsys.readouterr()
    assert "OCR_REVIEW_APPLY_DRY_RUN: passed" in captured.out
    assert "変更予定ページ: 1" in captured.out
    assert "反映不可ページ: なし" in captured.out
    assert "--apply" in captured.out
    # dry-runではlesson_pages.jsonは変更されない。
    lesson_pages = json.loads((output_dir / "editable" / "lesson_pages.json").read_text(encoding="utf-8"))
    assert lesson_pages["pages"][0]["title"] == "誤タイトル"
    assert not (output_dir / "editable" / "backups").exists()


def test_apply_ocr_review_dry_run_default_output_dir_paths_resolve(tmp_path, monkeypatch):
    output_dir = tmp_path / "out"
    build_fixture(output_dir, _default_pages())

    _run(monkeypatch, ["apply-ocr-review", "--output-dir", str(output_dir), "--dry-run"])

    assert (output_dir / "ocr_comparison" / "claude_review" / "apply_report.json").exists()
    assert (output_dir / "ocr_comparison" / "claude_review" / "apply_report.md").exists()


def test_apply_ocr_review_apply_writes_backup_and_prints_regenerate_command(tmp_path, monkeypatch, capsys):
    output_dir = tmp_path / "out"
    build_fixture(output_dir, _default_pages())

    _run(monkeypatch, ["apply-ocr-review", "--output-dir", str(output_dir), "--apply"])

    captured = capsys.readouterr()
    assert "OCR_REVIEW_APPLY: passed" in captured.out
    assert "regenerate" in captured.out
    lesson_pages = json.loads((output_dir / "editable" / "lesson_pages.json").read_text(encoding="utf-8"))
    assert lesson_pages["pages"][0]["title"] == "正タイトル"
    backups = list((output_dir / "editable" / "backups").glob("*.json"))
    assert len(backups) == 1


def test_apply_ocr_review_apply_is_idempotent_on_second_run(tmp_path, monkeypatch, capsys):
    output_dir = tmp_path / "out"
    build_fixture(output_dir, _default_pages())

    _run(monkeypatch, ["apply-ocr-review", "--output-dir", str(output_dir), "--apply"])
    capsys.readouterr()
    _run(monkeypatch, ["apply-ocr-review", "--output-dir", str(output_dir), "--apply"])

    captured = capsys.readouterr()
    assert "OCR_REVIEW_APPLY: passed" in captured.out
    assert "反映ページ: なし" in captured.out
    backups = list((output_dir / "editable" / "backups").glob("*.json"))
    assert len(backups) == 1


def test_apply_ocr_review_rejects_unresolved_page_with_nonzero_exit_and_no_changes(tmp_path, monkeypatch, capsys):
    pages = _default_pages()
    pages[1]["decision"] = "unresolved"
    pages[1]["unresolved_spans"] = [{"location": "1行目", "tesseract": "x", "apple_vision": "y", "reason": "不鮮明"}]
    pages[1]["requires_human_review"] = True
    output_dir = tmp_path / "out"
    build_fixture(output_dir, pages)
    before = (output_dir / "editable" / "lesson_pages.json").read_text(encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["cli", "apply-ocr-review", "--output-dir", str(output_dir), "--apply"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code != 0

    captured = capsys.readouterr()
    assert "OCR_REVIEW_APPLY: failed" in captured.out
    assert "2" in captured.out

    after = (output_dir / "editable" / "lesson_pages.json").read_text(encoding="utf-8")
    assert before == after
    assert not (output_dir / "editable" / "backups").exists()


def test_apply_ocr_review_pages_flag_limits_target(tmp_path, monkeypatch, capsys):
    output_dir = tmp_path / "out"
    build_fixture(output_dir, _default_pages())

    _run(monkeypatch, ["apply-ocr-review", "--output-dir", str(output_dir), "--pages", "1", "--dry-run"])

    captured = capsys.readouterr()
    assert "変更予定ページ: 1" in captured.out
    report = json.loads((output_dir / "ocr_comparison" / "claude_review" / "apply_report.json").read_text(encoding="utf-8"))
    assert report["target_pages"] == [1]


def test_apply_ocr_review_lesson_pages_and_candidates_overrides(tmp_path, monkeypatch):
    output_dir = tmp_path / "out"
    build_fixture(output_dir, _default_pages())
    custom_lesson_pages = tmp_path / "custom_lesson_pages.json"
    custom_lesson_pages.write_text(
        (output_dir / "editable" / "lesson_pages.json").read_text(encoding="utf-8"), encoding="utf-8"
    )

    _run(
        monkeypatch,
        [
            "apply-ocr-review", "--output-dir", str(output_dir),
            "--lesson-pages", str(custom_lesson_pages), "--dry-run",
        ],
    )

    # --output-dir配下の既定lesson_pages.jsonではなく、--lesson-pagesで指定した方が使われる。
    report = json.loads((output_dir / "ocr_comparison" / "claude_review" / "apply_report.json").read_text(encoding="utf-8"))
    assert report["lesson_pages_path"] == str(custom_lesson_pages)
