import json

import pytest

from src import verification_runner


def _make_fake_project(tmp_path):
    """src/verification_runner.pyのrun_standard_verification()が想定するディレクトリ構成
    （pytest対象・scripts/run_sample.sh相当）を、実際のプロジェクト全体を再帰的に
    起動せずに検証するための最小のダミープロジェクトを組み立てる。"""
    project_root = tmp_path / "fake_project"
    (project_root / "scripts").mkdir(parents=True)
    (project_root / "output").mkdir()

    # run_sample.sh相当。実際の重い処理は行わず、期待される受け入れ確認ファイルを1つ作るだけ。
    run_sample = project_root / "scripts" / "run_sample.sh"
    run_sample.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "echo 'ok' > \"$(dirname \"$0\")/../output/lesson_pages.json\"\n",
        encoding="utf-8",
    )
    run_sample.chmod(0o755)

    # pytest対象。プロジェクト全体ではなく、このダミーテストファイルだけを実行する。
    (project_root / "test_dummy.py").write_text(
        "def test_ok():\n    assert True\n", encoding="utf-8"
    )
    return project_root


def test_run_standard_verification_orchestrates_pytest_then_run_sample(tmp_path, monkeypatch):
    project_root = _make_fake_project(tmp_path)
    monkeypatch.setattr(verification_runner, "_project_root", lambda: project_root)
    monkeypatch.setenv("AI_KYOUZAI_EVIDENCE_DIR", str(project_root / "logs" / "evidence"))

    # run_sample.shの受け入れ確認対象を、このダミープロジェクトに存在するファイルだけに絞る。
    monkeypatch.setattr(verification_runner, "_ACCEPTANCE_FILES", ["output/lesson_pages.json"])

    original_run_command = None
    from src.verification_evidence import EvidenceRun

    def patched_run_command(self, name, command, **kwargs):
        if name == "pytest":
            # プロジェクト全体のpytestではなく、ダミーテストファイルだけを対象にする。
            command = [command[0], "-m", "pytest", "-q", str(project_root / "test_dummy.py")] + [
                arg for arg in command if arg.startswith("--junitxml")
            ]
        return original_run_command(self, name, command, **kwargs)

    original_run_command = EvidenceRun.run_command
    monkeypatch.setattr(EvidenceRun, "run_command", patched_run_command)

    exit_code = verification_runner.run_standard_verification(purpose="orchestration test")

    assert exit_code == 0

    latest = json.loads((project_root / "logs" / "evidence" / "latest.json").read_text(encoding="utf-8"))
    manifest = json.loads(
        (project_root / "logs" / "evidence" / latest["run_id"] / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["overall_status"] == "passed"
    command_names = [c["name"] for c in manifest["commands"]]
    assert command_names == ["pytest", "run_sample"]
    assert manifest["commands"][0]["pytest_summary"]["total"] == 1
    assert manifest["commands"][1]["acceptance_checks"][0]["exists"] is True


def test_run_standard_verification_continues_after_pytest_failure(tmp_path, monkeypatch):
    """pytest側が失敗しても、run_sample.sh側は続けて実行され、全体の終了コードが
    失敗を反映することを確認する。"""
    project_root = _make_fake_project(tmp_path)
    (project_root / "test_dummy.py").write_text(
        "def test_fails():\n    assert False\n", encoding="utf-8"
    )
    monkeypatch.setattr(verification_runner, "_project_root", lambda: project_root)
    monkeypatch.setenv("AI_KYOUZAI_EVIDENCE_DIR", str(project_root / "logs" / "evidence"))
    monkeypatch.setattr(verification_runner, "_ACCEPTANCE_FILES", ["output/lesson_pages.json"])

    from src.verification_evidence import EvidenceRun

    original_run_command = EvidenceRun.run_command

    def patched_run_command(self, name, command, **kwargs):
        if name == "pytest":
            command = [command[0], "-m", "pytest", "-q", str(project_root / "test_dummy.py")] + [
                arg for arg in command if arg.startswith("--junitxml")
            ]
        return original_run_command(self, name, command, **kwargs)

    monkeypatch.setattr(EvidenceRun, "run_command", patched_run_command)

    exit_code = verification_runner.run_standard_verification(purpose="failure continuation test")

    assert exit_code != 0
    latest = json.loads((project_root / "logs" / "evidence" / "latest.json").read_text(encoding="utf-8"))
    manifest = json.loads(
        (project_root / "logs" / "evidence" / latest["run_id"] / "manifest.json").read_text(encoding="utf-8")
    )
    command_names = [c["name"] for c in manifest["commands"]]
    # pytestが失敗しても、run_sampleも実行されている（途中で止めない）。
    assert command_names == ["pytest", "run_sample"]
    assert manifest["commands"][0]["status"] == "failed"
    assert manifest["commands"][1]["status"] == "passed"
    assert manifest["overall_status"] == "failed"
