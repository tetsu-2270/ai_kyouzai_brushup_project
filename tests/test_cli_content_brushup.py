from __future__ import annotations

import json

import pytest

from src.cli import main
from src import content_brushup as cb
from tests.test_content_brushup_apply import _default_pages, build_fixture


def _run(monkeypatch, argv):
    monkeypatch.setattr("sys.argv", ["cli"] + argv)
    main()


# --- prepare-content-brushup --------------------------------------------------------------------


def test_prepare_content_brushup_generates_snapshot_and_instructions(tmp_path, monkeypatch, capsys):
    output_dir = tmp_path / "out"
    paths = cb.resolve_paths(output_dir)
    build_fixture(paths, _default_pages())  # プロジェクトの状態を作るためにfixtureを流用（候補は上書きされる）

    _run(monkeypatch, ["prepare-content-brushup", "--output-dir", str(output_dir)])

    captured = capsys.readouterr()
    assert "CONTENT_BRUSHUP_PREPARE: passed" in captured.out
    assert paths.snapshot_path.exists()
    assert paths.instructions_path.exists()
    assert paths.readme_path.exists()


def test_prepare_content_brushup_prints_copyable_instruction_line(tmp_path, monkeypatch, capsys):
    output_dir = tmp_path / "out"
    paths = cb.resolve_paths(output_dir)
    build_fixture(paths, _default_pages())

    _run(monkeypatch, ["prepare-content-brushup", "--output-dir", str(output_dir)])

    captured = capsys.readouterr()
    assert "を読み、記載された手順を最後まで実行してください" in captured.out
    assert str(tmp_path) not in captured.out


def test_prepare_content_brushup_rejects_stale_snapshot_without_force(tmp_path, monkeypatch, capsys):
    output_dir = tmp_path / "out"
    paths = cb.resolve_paths(output_dir)
    build_fixture(paths, _default_pages())

    # lesson_pages.jsonを書き換えてスナップショットを古くする。
    data = json.loads(paths.lesson_pages_path.read_text(encoding="utf-8"))
    data["pages"][0]["summary"] = "changed"
    paths.lesson_pages_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["cli", "prepare-content-brushup", "--output-dir", str(output_dir)])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code != 0

    captured = capsys.readouterr()
    assert "force" in captured.err.lower() or "--force" in captured.err


def test_prepare_content_brushup_force_overwrites_stale_snapshot(tmp_path, monkeypatch, capsys):
    output_dir = tmp_path / "out"
    paths = cb.resolve_paths(output_dir)
    build_fixture(paths, _default_pages())
    old_hash = json.loads(paths.snapshot_path.read_text(encoding="utf-8"))["source_sha256"]

    data = json.loads(paths.lesson_pages_path.read_text(encoding="utf-8"))
    data["pages"][0]["summary"] = "changed"
    paths.lesson_pages_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    _run(monkeypatch, ["prepare-content-brushup", "--output-dir", str(output_dir), "--force"])

    captured = capsys.readouterr()
    assert "CONTENT_BRUSHUP_PREPARE: passed" in captured.out
    new_hash = json.loads(paths.snapshot_path.read_text(encoding="utf-8"))["source_sha256"]
    assert new_hash != old_hash


def test_prepare_content_brushup_requires_output_dir(monkeypatch):
    monkeypatch.setattr("sys.argv", ["cli", "prepare-content-brushup"])
    with pytest.raises(SystemExit):
        main()


# --- apply-content-brushup ----------------------------------------------------------------------


def test_apply_content_brushup_requires_dry_run_or_apply(tmp_path, monkeypatch):
    output_dir = tmp_path / "out"
    paths = cb.resolve_paths(output_dir)
    build_fixture(paths, _default_pages())
    monkeypatch.setattr("sys.argv", ["cli", "apply-content-brushup", "--output-dir", str(output_dir)])
    with pytest.raises(SystemExit):
        main()


def test_apply_content_brushup_rejects_both_dry_run_and_apply(tmp_path, monkeypatch):
    output_dir = tmp_path / "out"
    paths = cb.resolve_paths(output_dir)
    build_fixture(paths, _default_pages())
    monkeypatch.setattr(
        "sys.argv", ["cli", "apply-content-brushup", "--output-dir", str(output_dir), "--dry-run", "--apply"]
    )
    with pytest.raises(SystemExit):
        main()


def test_apply_content_brushup_dry_run_passes_and_prints_banner(tmp_path, monkeypatch, capsys):
    output_dir = tmp_path / "out"
    paths = cb.resolve_paths(output_dir)
    build_fixture(paths, _default_pages())

    _run(monkeypatch, ["apply-content-brushup", "--output-dir", str(output_dir), "--dry-run"])

    captured = capsys.readouterr()
    assert "CONTENT_BRUSHUP_APPLY_DRY_RUN: passed" in captured.out
    assert "変更予定ページ: 1" in captured.out
    assert "反映不可ページ: なし" in captured.out
    lesson_pages = json.loads(paths.lesson_pages_path.read_text(encoding="utf-8"))
    assert lesson_pages["pages"][0]["body"] == ": 完璧を求めない"
    assert not paths.backups_dir.exists()


def test_apply_content_brushup_apply_writes_backup_and_suggests_prepare_image_brushup(tmp_path, monkeypatch, capsys):
    output_dir = tmp_path / "out"
    paths = cb.resolve_paths(output_dir)
    build_fixture(paths, _default_pages())

    _run(monkeypatch, ["apply-content-brushup", "--output-dir", str(output_dir), "--apply"])

    captured = capsys.readouterr()
    assert "CONTENT_BRUSHUP_APPLY: passed" in captured.out
    assert "prepare-image-brushup" in captured.out
    lesson_pages = json.loads(paths.lesson_pages_path.read_text(encoding="utf-8"))
    assert "完璧を目指さず" in lesson_pages["pages"][0]["body"]
    backups = list(paths.backups_dir.glob("*.json"))
    assert len(backups) == 1


def test_apply_content_brushup_apply_is_idempotent_on_second_run(tmp_path, monkeypatch, capsys):
    output_dir = tmp_path / "out"
    paths = cb.resolve_paths(output_dir)
    build_fixture(paths, _default_pages())

    _run(monkeypatch, ["apply-content-brushup", "--output-dir", str(output_dir), "--apply"])
    capsys.readouterr()
    _run(monkeypatch, ["apply-content-brushup", "--output-dir", str(output_dir), "--apply"])

    captured = capsys.readouterr()
    assert "CONTENT_BRUSHUP_APPLY: passed" in captured.out
    assert "反映ページ: なし" in captured.out
    backups = list(paths.backups_dir.glob("*.json"))
    assert len(backups) == 1


def test_apply_content_brushup_rejects_high_risk_with_nonzero_exit_and_no_changes(tmp_path, monkeypatch, capsys):
    output_dir = tmp_path / "out"
    paths = cb.resolve_paths(output_dir)
    pages = _default_pages()
    pages[1]["risk_level"] = "high"
    pages[1]["requires_human_review"] = True
    build_fixture(paths, pages)
    before = paths.lesson_pages_path.read_text(encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["cli", "apply-content-brushup", "--output-dir", str(output_dir), "--apply"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code != 0

    captured = capsys.readouterr()
    assert "CONTENT_BRUSHUP_APPLY: failed" in captured.out
    after = paths.lesson_pages_path.read_text(encoding="utf-8")
    assert before == after
    assert not paths.backups_dir.exists()


def test_apply_content_brushup_pages_flag_limits_target(tmp_path, monkeypatch, capsys):
    output_dir = tmp_path / "out"
    paths = cb.resolve_paths(output_dir)
    build_fixture(paths, _default_pages())

    _run(monkeypatch, ["apply-content-brushup", "--output-dir", str(output_dir), "--pages", "1", "--dry-run"])

    captured = capsys.readouterr()
    assert "変更予定ページ: 1" in captured.out
    report = json.loads((paths.content_dir / "apply_report.json").read_text(encoding="utf-8"))
    assert report["target_pages"] == [1]
