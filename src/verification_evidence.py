from __future__ import annotations

import json
import os
import platform
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from .execution_logger import mask_secrets

# logs/evidence/<run_id>/ 配下に、pytest・run_sample.sh等の検証結果を永続保存するための
# エビデンス記録ライブラリ。Codexが実行結果をローカルファイルから直接検証できるようにし、
# 確認のためだけの再実行を避けることが目的（詳細はREADME/docs/04_output_spec.md参照）。
#
# 過去の実行結果は上書きしない（run_idごとに新しいディレクトリを作る）。成功時だけでなく、
# 失敗・中断時にも可能な限りmanifest.json/summary.mdを書き出す。

_SCHEMA_VERSION = 1

_EVIDENCE_DIR_ENV_VAR = "AI_KYOUZAI_EVIDENCE_DIR"


def _default_evidence_root() -> Path:
    override = os.environ.get(_EVIDENCE_DIR_ENV_VAR)
    if override:
        return Path(override)
    return Path("logs") / "evidence"


def generate_run_id(now: datetime | None = None) -> str:
    """時刻+衝突防止用のランダムサフィックスからrun_idを作る（例: 20260711_153012_4821）。"""
    now = now or datetime.now().astimezone()
    suffix = f"{uuid.uuid4().int % 10000:04d}"
    return f"{now.strftime('%Y%m%d_%H%M%S')}_{suffix}"


def _atomic_write_text(path: Path, content: str) -> None:
    """書き込み途中のファイルを完成済みとして誤読させないよう、一時ファイルへ書いてから置換する。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + f".tmp-{os.getpid()}")
    tmp_path.write_text(content, encoding="utf-8")
    os.replace(tmp_path, path)


def _mask_any(value: Any) -> Any:
    """文字列・リスト・辞書を再帰的に辿り、文字列値だけにmask_secrets()を適用する。"""
    if isinstance(value, str):
        return mask_secrets(value)
    if isinstance(value, list):
        return [_mask_any(v) for v in value]
    if isinstance(value, dict):
        return {k: _mask_any(v) for k, v in value.items()}
    return value


def _run_git(args: list[str], cwd: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def collect_git_info(project_root: Path, status_limit: int = 200) -> dict[str, Any]:
    """Gitのブランチ・HEAD・作業ツリーがdirtyかどうかを記録する。

    ファイル内容・秘密情報は記録しない。`git status --porcelain`のパス一覧のみを、
    上限件数まで記録する（大量差分でmanifestが肥大化しないようにする）。
    """
    branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], project_root)
    head = _run_git(["rev-parse", "HEAD"], project_root)
    status_raw = _run_git(["status", "--porcelain"], project_root)
    status_lines = status_raw.splitlines() if status_raw else []
    return {
        "branch": branch,
        "head": head,
        "is_dirty": bool(status_lines),
        "status_summary": status_lines[:status_limit],
        "status_truncated": len(status_lines) > status_limit,
    }


def collect_environment_info() -> dict[str, Any]:
    return {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
    }


class CommandRecord:
    """1コマンド分の実行結果（開始/終了時刻・終了コード・ログファイル・付随成果物）。"""

    def __init__(self, index: int, name: str, command: list[str]):
        self.index = index
        self.name = name
        self.command = command
        self.started_at: datetime | None = None
        self.ended_at: datetime | None = None
        self.exit_code: int | None = None
        self.status = "not_run"
        self.log_file: str | None = None
        self.artifacts: list[str] = []
        self.extra: dict[str, Any] = {}

    def to_dict(self) -> dict[str, Any]:
        duration = None
        if self.started_at and self.ended_at:
            duration = round((self.ended_at - self.started_at).total_seconds(), 3)
        data: dict[str, Any] = {
            "index": self.index,
            "name": self.name,
            "command": _mask_any(self.command),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration_seconds": duration,
            "exit_code": self.exit_code,
            "status": self.status,
            "log_file": self.log_file,
            "artifacts": self.artifacts,
        }
        data.update(_mask_any(self.extra))
        return data


class EvidenceRun:
    """1回の検証実行（run_id単位）のエビデンスを記録するコンテキスト。

    `logs/evidence/<run_id>/`配下にコマンドログ・manifest.json・summary.mdを書き出す。
    過去のrun_idディレクトリは削除・上書きしない。失敗・例外・中断時にもfinalize()で
    可能な限りmanifest.json/summary.mdを確定させる想定（呼び出し側はtry/finallyで使う）。
    """

    def __init__(self, purpose: str, evidence_root: Path | str | None = None, project_root: Path | str | None = None):
        self.purpose = purpose
        self.run_id = generate_run_id()
        self.evidence_root = Path(evidence_root) if evidence_root is not None else _default_evidence_root()
        self.project_root = Path(project_root) if project_root is not None else Path.cwd()
        self.run_dir = self.evidence_root / self.run_id
        self.commands_dir = self.run_dir / "commands"
        self.started_at = datetime.now().astimezone()
        self.ended_at: datetime | None = None
        self.overall_status = "not_run"
        self.overall_exit_code: int | None = None
        self._commands: list[CommandRecord] = []
        self._finalized = False

        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.commands_dir.mkdir(parents=True, exist_ok=True)

    def run_command(
        self,
        name: str,
        command: list[str],
        *,
        cwd: Path | str | None = None,
        env: dict[str, str] | None = None,
        timeout: int | None = None,
        extra_artifacts: list[Path | str] | None = None,
    ) -> CommandRecord:
        """コマンドを実行し、標準出力・標準エラー・終了コードをエビデンスへ保存する。

        コマンドの実行自体が失敗（非ゼロ終了・例外）してもここでは例外を送出しない
        （エビデンスへ記録したうえで呼び出し元に結果を返す。中断時のみKeyboardInterruptを
        再送出する）。
        """
        index = len(self._commands) + 1
        record = CommandRecord(index, name, command)
        record.started_at = datetime.now().astimezone()

        log_relpath = f"commands/{index:03d}_{_safe_name(name)}.log"
        log_path = self.run_dir / log_relpath
        record.log_file = log_relpath

        run_env = dict(os.environ)
        if env:
            run_env.update(env)

        interrupted = False
        try:
            result = subprocess.run(
                command,
                cwd=str(cwd) if cwd is not None else str(self.project_root),
                env=run_env,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            record.exit_code = result.returncode
            stdout, stderr = result.stdout, result.stderr
            record.status = "passed" if result.returncode == 0 else "failed"
        except subprocess.TimeoutExpired as e:
            record.exit_code = None
            stdout = e.stdout or ""
            stderr = (e.stderr or "") + f"\n[timeout after {timeout}s]"
            record.status = "timeout"
        except KeyboardInterrupt:
            record.exit_code = None
            stdout, stderr = "", "[interrupted by user]"
            record.status = "interrupted"
            interrupted = True
        except OSError as e:
            record.exit_code = None
            stdout, stderr = "", f"[failed to launch command: {e}]"
            record.status = "error"
        finally:
            record.ended_at = datetime.now().astimezone()

        log_content = (
            f"command: {' '.join(mask_secrets(part) for part in command)}\n"
            f"cwd: {cwd if cwd is not None else self.project_root}\n"
            f"started_at: {record.started_at.isoformat()}\n"
            f"ended_at: {record.ended_at.isoformat()}\n"
            f"exit_code: {record.exit_code}\n"
            f"status: {record.status}\n"
            "\n===== STDOUT =====\n"
            f"{mask_secrets(stdout)}\n"
            "\n===== STDERR =====\n"
            f"{mask_secrets(stderr)}\n"
        )
        _atomic_write_text(log_path, log_content)

        if extra_artifacts:
            for artifact in extra_artifacts:
                artifact_path = Path(artifact)
                if artifact_path.exists():
                    try:
                        record.artifacts.append(str(artifact_path.relative_to(self.run_dir)))
                    except ValueError:
                        record.artifacts.append(str(artifact_path))

        self._commands.append(record)

        if interrupted:
            self.finalize(overall_status="interrupted")
            raise KeyboardInterrupt

        return record

    def _write_manifest(self) -> dict[str, Any]:
        duration = None
        if self.ended_at:
            duration = round((self.ended_at - self.started_at).total_seconds(), 3)
        git_info = collect_git_info(self.project_root)
        env_info = collect_environment_info()
        manifest = {
            "schema_version": _SCHEMA_VERSION,
            "run_id": self.run_id,
            "purpose": self.purpose,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration_seconds": duration,
            "overall_status": self.overall_status,
            "overall_exit_code": self.overall_exit_code,
            "project_root": str(self.project_root),
            "python_version": env_info["python_version"],
            "platform": env_info["platform"],
            "git": git_info,
            "commands": [c.to_dict() for c in self._commands],
            "external": [],
        }
        manifest = _mask_any(manifest)
        _atomic_write_text(self.run_dir / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        return manifest

    def _write_summary(self, manifest: dict[str, Any]) -> None:
        lines: list[str] = []
        lines.append(f"# 検証エビデンス: {self.run_id}")
        lines.append("")
        lines.append(f"- 目的: {manifest['purpose']}")
        lines.append(f"- 総合結果: **{manifest['overall_status']}**（終了コード: {manifest['overall_exit_code']}）")
        lines.append(f"- 開始: {manifest['started_at']}")
        lines.append(f"- 終了: {manifest['ended_at']}")
        lines.append(f"- 所要時間: {manifest['duration_seconds']}秒")
        git_info = manifest["git"]
        lines.append(
            f"- Git: branch={git_info.get('branch')} head={git_info.get('head')} "
            f"dirty={git_info.get('is_dirty')}"
        )
        lines.append("")
        lines.append("## 実行したコマンド")
        lines.append("")
        for cmd in manifest["commands"]:
            lines.append(f"### {cmd['index']}. {cmd['name']} — {cmd['status']}")
            lines.append(f"- コマンド: `{' '.join(cmd['command'])}`")
            lines.append(f"- 終了コード: {cmd['exit_code']}")
            lines.append(f"- 所要時間: {cmd['duration_seconds']}秒")
            lines.append(f"- ログ: `{cmd['log_file']}`")
            if cmd.get("artifacts"):
                lines.append(f"- 成果物: {', '.join(cmd['artifacts'])}")
            pytest_summary = cmd.get("pytest_summary")
            if pytest_summary:
                lines.append(
                    "- pytest結果: "
                    f"{pytest_summary.get('passed', 0)} passed / "
                    f"{pytest_summary.get('failed', 0)} failed / "
                    f"{pytest_summary.get('skipped', 0)} skipped / "
                    f"{pytest_summary.get('errors', 0)} errors "
                    f"(total {pytest_summary.get('total', 0)})"
                )
            acceptance = cmd.get("acceptance_checks")
            if acceptance:
                ok_count = sum(1 for a in acceptance if a.get("exists") and a.get("size_bytes", 0) > 0)
                lines.append(f"- 受け入れ確認: {ok_count}/{len(acceptance)}件のファイルが存在・非空")
            lines.append("")

        failed_commands = [c for c in manifest["commands"] if c["status"] not in ("passed",)]
        if failed_commands:
            lines.append("## 失敗・未完了コマンドの先頭エラー")
            lines.append("")
            for cmd in failed_commands:
                log_path = self.run_dir / cmd["log_file"] if cmd.get("log_file") else None
                snippet = ""
                if log_path and log_path.exists():
                    text = log_path.read_text(encoding="utf-8")
                    snippet = "\n".join(text.splitlines()[-20:])
                lines.append(f"### {cmd['name']}")
                lines.append("```text")
                lines.append(snippet or "(ログなし)")
                lines.append("```")
                lines.append("")

        not_run = [c for c in manifest["commands"] if c["status"] == "not_run"]
        if not_run:
            lines.append("## 未実行項目")
            lines.append("")
            for cmd in not_run:
                lines.append(f"- {cmd['name']}")
            lines.append("")

        _atomic_write_text(self.run_dir / "summary.md", "\n".join(lines) + "\n")

    def _write_latest_pointer(self, manifest: dict[str, Any]) -> None:
        latest = {
            "run_id": self.run_id,
            "run_dir": str(self.run_dir),
            "overall_status": manifest["overall_status"],
            "overall_exit_code": manifest["overall_exit_code"],
            "updated_at": datetime.now().astimezone().isoformat(),
        }
        _atomic_write_text(
            self.evidence_root / "latest.json", json.dumps(latest, ensure_ascii=False, indent=2) + "\n"
        )

    def finalize(self, overall_status: str | None = None, overall_exit_code: int | None = None) -> dict[str, Any]:
        """manifest.json/summary.mdを確定させ、latest.jsonを完成済みのrun_idへ更新する。

        例外・中断時にも呼べるよう、複数回呼ばれても安全（2回目以降は最新の状態で上書き）。
        `overall_status`未指定の場合は、記録済みコマンドの状態から自動判定する
        （すべてpassedならpassed、1つでもinterruptedならinterrupted、それ以外で失敗があればfailed）。
        """
        self.ended_at = datetime.now().astimezone()

        if overall_status is None:
            statuses = {c.status for c in self._commands}
            if not statuses or statuses == {"passed"}:
                overall_status = "passed"
            elif "interrupted" in statuses:
                overall_status = "interrupted"
            else:
                overall_status = "failed"
        self.overall_status = overall_status

        if overall_exit_code is None:
            overall_exit_code = 0 if overall_status == "passed" else 1
        self.overall_exit_code = overall_exit_code

        manifest = self._write_manifest()
        self._write_summary(manifest)
        # latest.jsonは、manifest/summaryの書き出しが完了した後にのみ更新する
        # （「完成した最新実行を指す」という要件を満たすため）。
        self._write_latest_pointer(manifest)
        self._finalized = True
        return manifest


_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def _safe_name(name: str) -> str:
    return _SAFE_NAME_RE.sub("_", name) or "unknown"


def parse_junit_summary(junit_xml_path: Path) -> dict[str, Any] | None:
    """pytestが`--junitxml`で出力したXMLから件数サマリーを取り出す。壊れている場合はNone。"""
    if not junit_xml_path.exists():
        return None
    try:
        import xml.etree.ElementTree as ET

        tree = ET.parse(junit_xml_path)
        root = tree.getroot()
        # pytestは<testsuites><testsuite .../></testsuites>を出力する。
        suite = root if root.tag == "testsuite" else root.find("testsuite")
        if suite is None:
            return None
        total = int(suite.attrib.get("tests", 0))
        failures = int(suite.attrib.get("failures", 0))
        errors = int(suite.attrib.get("errors", 0))
        skipped = int(suite.attrib.get("skipped", 0))
        passed = total - failures - errors - skipped
        return {
            "total": total,
            "passed": passed,
            "failed": failures,
            "errors": errors,
            "skipped": skipped,
            "time_seconds": float(suite.attrib.get("time", 0.0)),
        }
    except Exception:
        return None


def check_acceptance_files(paths: list[Path | str], run_dir: Path | None = None) -> list[dict[str, Any]]:
    """`run_sample.sh`等の受け入れ確認で、生成が期待される主要ファイルの存在・サイズを記録する。

    ファイル本文（実教材・OCR本文）はエビデンスへコピーしない。存在確認・サイズ・
    必要に応じたSHA-256のみを記録する。
    """
    import hashlib

    results: list[dict[str, Any]] = []
    for raw_path in paths:
        path = Path(raw_path)
        exists = path.exists()
        size = path.stat().st_size if exists else 0
        sha256 = None
        if exists and path.is_file() and size <= 50 * 1024 * 1024:
            digest = hashlib.sha256()
            with path.open("rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    digest.update(chunk)
            sha256 = digest.hexdigest()
        results.append({"path": str(path), "exists": exists, "size_bytes": size, "sha256": sha256})
    return results
