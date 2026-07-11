import json
import subprocess
import sys
import time

import pytest

from src.execution_logger import mask_secrets as execution_logger_mask_secrets
from src.verification_evidence import (
    EvidenceRun,
    check_acceptance_files,
    collect_git_info,
    generate_run_id,
    mask_secrets,
    parse_junit_summary,
)


def _init_git_repo(path):
    subprocess.run(["git", "init", "-q"], cwd=str(path), check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(path), check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(path), check=True)
    (path / "file.txt").write_text("hello", encoding="utf-8")
    subprocess.run(["git", "add", "file.txt"], cwd=str(path), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=str(path), check=True)


def test_generate_run_id_is_unique_across_calls():
    ids = {generate_run_id() for _ in range(20)}
    assert len(ids) == 20


def test_evidence_run_creates_unique_directory_per_run(tmp_path):
    evidence_root = tmp_path / "evidence"
    run1 = EvidenceRun(purpose="p1", evidence_root=evidence_root, project_root=tmp_path)
    run1.run_command("noop", ["bash", "-c", "exit 0"])
    run1.finalize()

    time.sleep(0.01)
    run2 = EvidenceRun(purpose="p2", evidence_root=evidence_root, project_root=tmp_path)
    run2.run_command("noop", ["bash", "-c", "exit 0"])
    run2.finalize()

    assert run1.run_dir != run2.run_dir
    assert run1.run_dir.exists()
    assert run2.run_dir.exists()


def test_evidence_run_does_not_overwrite_previous_results(tmp_path):
    evidence_root = tmp_path / "evidence"
    run1 = EvidenceRun(purpose="first run", evidence_root=evidence_root, project_root=tmp_path)
    run1.run_command("noop", ["bash", "-c", "echo first"])
    run1.finalize()
    first_manifest_text = (run1.run_dir / "manifest.json").read_text(encoding="utf-8")

    run2 = EvidenceRun(purpose="second run", evidence_root=evidence_root, project_root=tmp_path)
    run2.run_command("noop", ["bash", "-c", "echo second"])
    run2.finalize()

    # 1回目のディレクトリ・内容が変更されていないことを確認する。
    assert (run1.run_dir / "manifest.json").read_text(encoding="utf-8") == first_manifest_text
    assert run1.run_dir.exists()
    assert run2.run_dir.exists()
    assert list(evidence_root.iterdir())  # 複数run_idが共存している


def test_successful_run_manifest_fields(tmp_path):
    run = EvidenceRun(purpose="success case", evidence_root=tmp_path / "evidence", project_root=tmp_path)
    run.run_command("ok1", ["bash", "-c", "echo hi"])
    run.run_command("ok2", ["bash", "-c", "exit 0"])
    manifest = run.finalize()

    assert manifest["overall_status"] == "passed"
    assert manifest["overall_exit_code"] == 0
    assert manifest["schema_version"] == 1
    assert manifest["run_id"] == run.run_id
    assert len(manifest["commands"]) == 2
    assert all(c["status"] == "passed" for c in manifest["commands"])
    assert manifest["started_at"] is not None
    assert manifest["ended_at"] is not None


def test_failed_command_still_produces_manifest_and_log(tmp_path):
    run = EvidenceRun(purpose="failure case", evidence_root=tmp_path / "evidence", project_root=tmp_path)
    record = run.run_command("will_fail", ["bash", "-c", "echo boom 1>&2; exit 7"])
    manifest = run.finalize()

    assert record.exit_code == 7
    assert record.status == "failed"
    log_path = run.run_dir / record.log_file
    assert log_path.exists()
    assert "boom" in log_path.read_text(encoding="utf-8")

    assert manifest["overall_status"] == "failed"
    assert manifest["overall_exit_code"] != 0
    assert (run.run_dir / "manifest.json").exists()
    assert (run.run_dir / "summary.md").exists()


def test_exit_codes_are_recorded_accurately(tmp_path):
    run = EvidenceRun(purpose="exit codes", evidence_root=tmp_path / "evidence", project_root=tmp_path)
    r0 = run.run_command("c0", ["bash", "-c", "exit 0"])
    r1 = run.run_command("c1", ["bash", "-c", "exit 1"])
    r42 = run.run_command("c42", ["bash", "-c", "exit 42"])
    run.finalize()

    assert r0.exit_code == 0
    assert r1.exit_code == 1
    assert r42.exit_code == 42


def test_overall_exit_code_reflects_any_failure(tmp_path):
    run = EvidenceRun(purpose="mixed", evidence_root=tmp_path / "evidence", project_root=tmp_path)
    run.run_command("ok", ["bash", "-c", "exit 0"])
    run.run_command("bad", ["bash", "-c", "exit 5"])
    manifest = run.finalize()

    assert manifest["overall_status"] == "failed"
    assert manifest["overall_exit_code"] != 0


def test_stdout_and_stderr_are_saved(tmp_path):
    run = EvidenceRun(purpose="stdio", evidence_root=tmp_path / "evidence", project_root=tmp_path)
    record = run.run_command("stdio", ["bash", "-c", "echo out-marker; echo err-marker 1>&2"])
    run.finalize()

    content = (run.run_dir / record.log_file).read_text(encoding="utf-8")
    assert "out-marker" in content
    assert "err-marker" in content
    assert "STDOUT" in content
    assert "STDERR" in content


def test_junit_xml_summary_is_parsed():
    junit_xml = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
<testsuite name="pytest" errors="1" failures="2" skipped="3" tests="10" time="1.234">
</testsuite>
</testsuites>
"""

    def _write(path):
        path.write_text(junit_xml, encoding="utf-8")
        return path

    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        path = _write(Path(tmp) / "junit.xml")
        summary = parse_junit_summary(path)
        assert summary["total"] == 10
        assert summary["failed"] == 2
        assert summary["errors"] == 1
        assert summary["skipped"] == 3
        assert summary["passed"] == 4


def test_junit_xml_missing_returns_none(tmp_path):
    assert parse_junit_summary(tmp_path / "does_not_exist.xml") is None


def test_pytest_command_saves_real_junit_xml(tmp_path):
    """実際にpytestをダミーの小さなテストファイルへ対して実行し、--junitxmlが機能することを
    確認する（プロジェクト全体のpytestを再帰的に起動するわけではない）。"""
    dummy_test_dir = tmp_path / "dummy_tests"
    dummy_test_dir.mkdir()
    (dummy_test_dir / "test_dummy.py").write_text(
        "def test_ok():\n    assert 1 == 1\n", encoding="utf-8"
    )

    run = EvidenceRun(purpose="junit smoke", evidence_root=tmp_path / "evidence", project_root=tmp_path)
    junit_path = run.run_dir / "pytest" / "junit.xml"
    junit_path.parent.mkdir(parents=True)
    run.run_command(
        "pytest",
        [sys.executable, "-m", "pytest", "-q", str(dummy_test_dir), f"--junitxml={junit_path}"],
        extra_artifacts=[junit_path],
    )
    run.finalize()

    assert junit_path.exists()
    summary = parse_junit_summary(junit_path)
    assert summary["total"] == 1
    assert summary["passed"] == 1


def test_latest_json_points_to_finalized_run(tmp_path):
    evidence_root = tmp_path / "evidence"
    run = EvidenceRun(purpose="latest test", evidence_root=evidence_root, project_root=tmp_path)
    run.run_command("noop", ["bash", "-c", "exit 0"])
    run.finalize()

    latest = json.loads((evidence_root / "latest.json").read_text(encoding="utf-8"))
    assert latest["run_id"] == run.run_id
    assert (run.run_dir / "manifest.json").exists()
    assert (run.run_dir / "summary.md").exists()


def test_git_head_and_dirty_state_are_recorded(tmp_path):
    _init_git_repo(tmp_path)
    info_clean = collect_git_info(tmp_path)
    assert info_clean["head"]
    assert info_clean["branch"]
    assert info_clean["is_dirty"] is False

    (tmp_path / "file.txt").write_text("changed", encoding="utf-8")
    info_dirty = collect_git_info(tmp_path)
    assert info_dirty["is_dirty"] is True
    assert any("file.txt" in line for line in info_dirty["status_summary"])


def test_secrets_are_masked_in_command_log(tmp_path):
    run = EvidenceRun(purpose="secret masking", evidence_root=tmp_path / "evidence", project_root=tmp_path)
    record = run.run_command(
        "leaky", ["bash", "-c", "echo 'password=supersecret123'; echo 'token: abcXYZ999' 1>&2"]
    )
    run.finalize()

    content = (run.run_dir / record.log_file).read_text(encoding="utf-8")
    assert "supersecret123" not in content
    assert "abcXYZ999" not in content
    assert "[REDACTED]" in content


def test_secrets_are_masked_in_manifest_command_args(tmp_path):
    run = EvidenceRun(purpose="secret args", evidence_root=tmp_path / "evidence", project_root=tmp_path)
    run.run_command("leaky_args", ["bash", "-c", "--api-key=sk-should-not-leak; exit 0"])
    manifest = run.finalize()

    manifest_text = json.dumps(manifest, ensure_ascii=False)
    assert "sk-should-not-leak" not in manifest_text


def test_does_not_read_or_record_dotenv_contents(tmp_path):
    (tmp_path / ".env").write_text("SECRET_KEY=do-not-leak-this-value\n", encoding="utf-8")
    run = EvidenceRun(purpose="dotenv safety", evidence_root=tmp_path / "evidence", project_root=tmp_path)
    run.run_command("noop", ["bash", "-c", "echo nothing-related"])
    manifest = run.finalize()

    manifest_text = json.dumps(manifest, ensure_ascii=False)
    assert "do-not-leak-this-value" not in manifest_text
    for log_file in (run.run_dir / "commands").glob("*.log"):
        assert "do-not-leak-this-value" not in log_file.read_text(encoding="utf-8")


def test_manifest_json_is_written_atomically_not_left_partial(tmp_path):
    """一時ファイル経由での置換により、書き込み途中の.tmpファイルが残らないことを確認する。"""
    run = EvidenceRun(purpose="atomic write", evidence_root=tmp_path / "evidence", project_root=tmp_path)
    run.run_command("noop", ["bash", "-c", "exit 0"])
    run.finalize()

    tmp_leftovers = list(run.run_dir.glob("*.tmp-*"))
    assert tmp_leftovers == []
    # 出来上がったmanifest.jsonが正しくパース可能であること（途中状態でないこと）を確認する。
    json.loads((run.run_dir / "manifest.json").read_text(encoding="utf-8"))


def test_check_acceptance_files_reports_existence_size_and_hash(tmp_path):
    existing = tmp_path / "exists.txt"
    existing.write_text("content", encoding="utf-8")
    missing = tmp_path / "missing.txt"

    results = check_acceptance_files([existing, missing])

    by_path = {r["path"]: r for r in results}
    assert by_path[str(existing)]["exists"] is True
    assert by_path[str(existing)]["size_bytes"] == len("content")
    assert by_path[str(existing)]["sha256"] is not None
    assert by_path[str(missing)]["exists"] is False
    assert by_path[str(missing)]["sha256"] is None


def test_verification_evidence_reuses_execution_logger_mask_secrets():
    """既存のsrc/execution_logger.pyの秘密情報マスク実装を再利用しており、
    重複実装になっていないことを確認する（既存のCLIログ機能との一貫性を担保）。"""
    assert mask_secrets is execution_logger_mask_secrets


def test_command_extra_fields_are_recorded_in_manifest(tmp_path):
    run = EvidenceRun(purpose="extra fields", evidence_root=tmp_path / "evidence", project_root=tmp_path)
    record = run.run_command("with_extra", ["bash", "-c", "exit 0"])
    record.extra["pytest_summary"] = {"total": 3, "passed": 3, "failed": 0, "errors": 0, "skipped": 0}
    manifest = run.finalize()

    assert manifest["commands"][0]["pytest_summary"]["total"] == 3
