from __future__ import annotations

import os
import platform
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")

# 既定のログ出力先は実行時のカレントディレクトリ直下のlogs/（プロジェクト直下を想定）。
# 自動テストが実際のプロジェクトのlogs/を汚さないよう、環境変数で上書きできるようにする
# （tests/conftest.pyがテストごとに一時ディレクトリへ差し替える）。
_LOGS_DIR_ENV_VAR = "AI_KYOUZAI_LOGS_DIR"

_REDACTED = "[REDACTED]"

# logs/*.log は配布用ZIPの対象になるため、機密情報らしき値をログへ残さない
# （CLAUDE_RULES.md「ログ出力の共通設計ルール」・docs/04_output_spec.md「実行ログ(logs/)の
# 標準仕様」参照）。大文字小文字は区別しない。
_SENSITIVE_KEYWORDS = (
    "password", "passwd", "secret", "token", "api_key", "apikey", "api-key",
    "access_key", "access-key", "access_token", "access-token",
    "authorization", "client_secret", "refresh_token", "private_key",
)
_SENSITIVE_KEY_GROUP = "|".join(re.escape(k) for k in _SENSITIVE_KEYWORDS)

# "Authorization: Bearer xxxxx" のようなHTTPヘッダ形式（Bearerトークン自体もマスクする）。
_BEARER_PATTERN = re.compile(r"\bBearer\s+\S+", re.IGNORECASE)

# "--api-key sk-xxxx" / "--api-key=sk-xxxx" のようなCLIオプション形式。
_CLI_FLAG_PATTERN = re.compile(
    rf"(--[\w-]*(?:{_SENSITIVE_KEY_GROUP})[\w-]*)(=|\s+)(\S+)", re.IGNORECASE
)

# "password=abc123" / "token: abc123" のようなkey=value / key: value形式（CLIオプション以外）。
# 値が"Bearer"で始まる場合は_BEARER_PATTERNが別途処理する（例: "Authorization: Bearer xxx"で
# "Bearer"自体を値として誤って二重マスクしないようにする）。
_KEY_VALUE_PATTERN = re.compile(
    rf"\b(\w*(?:{_SENSITIVE_KEY_GROUP})\w*)(\s*[:=]\s*)(?!Bearer\b)(\S+)", re.IGNORECASE
)


def mask_secrets(text: str) -> str:
    """ログに書き出す前に、機密情報らしき値を`[REDACTED]`に置換する。

    対象: password/passwd/secret/token/api_key/apikey/access_key/access_token/
    authorization/bearer/client_secret/refresh_token/private_key（大文字小文字を区別しない）。
    ログファイル本体（logs/*.log）は配布用ZIPに含まれるため、CLI引数・stderr出力・
    エラーメッセージ等に秘密情報が混ざっていても、書き出す前にここで必ずマスクする。
    """
    if not text:
        return text
    masked = _BEARER_PATTERN.sub(f"Bearer {_REDACTED}", text)
    masked = _CLI_FLAG_PATTERN.sub(lambda m: f"{m.group(1)}{m.group(2)}{_REDACTED}", masked)
    masked = _KEY_VALUE_PATTERN.sub(lambda m: f"{m.group(1)}{m.group(2)}{_REDACTED}", masked)
    return masked


def _default_logs_dir() -> str:
    return os.environ.get(_LOGS_DIR_ENV_VAR, "logs")


def _safe_command_name(command: str) -> str:
    return _SAFE_NAME_RE.sub("_", command) or "unknown"


class TeeStderr:
    """標準エラー出力を元のストリームへ書きつつ、後でログに残すためにバッファへも蓄積する。

    既存の`print(..., file=sys.stderr)`呼び出し箇所を個別に変更せずに、CLI全体の
    標準エラー出力をログへ残すための仕組み（ユーザーに見えるCLI出力は変更しない）。
    """

    def __init__(self, original: Any):
        self._original = original
        self.captured = ""

    def write(self, text: str) -> int:
        self._original.write(text)
        self.captured += text
        return len(text)

    def flush(self) -> None:
        self._original.flush()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._original, name)


class ExecutionLogger:
    """CLI実行ごとの実行ログを`logs/YYYYMMDD_HHMMSS_<command>.log`に書き出す。

    ログディレクトリ作成・書き込みに失敗しても本処理は止めない（stderrに警告するのみ）。
    詳細な仕様はCLAUDE_RULES.md「ログ出力の共通設計ルール」・docs/04_output_spec.md
    「プロジェクト標準output構成」の`logs/`節を参照。
    """

    def __init__(self, command: str, argv: list[str], logs_dir: str | Path | None = None):
        self.command = command
        self.argv = argv
        self.started_at = datetime.now().astimezone()
        self.warnings: list[str] = []
        self.errors: list[str] = []
        self.generated_files: list[str] = []
        self._sections: dict[str, dict[str, Any]] = {}
        self._log_path: Path | None = None
        self._enabled = True

        logs_dir = Path(logs_dir) if logs_dir is not None else Path(_default_logs_dir())
        try:
            logs_dir.mkdir(parents=True, exist_ok=True)
            timestamp = self.started_at.strftime("%Y%m%d_%H%M%S")
            self._log_path = logs_dir / f"{timestamp}_{_safe_command_name(command)}.log"
        except OSError as e:
            self._enabled = False
            print(f"WARNING: ログディレクトリを作成できませんでした（処理は続行します）: {e}", file=sys.stderr)

    @property
    def log_path(self) -> Path | None:
        return self._log_path

    def add_section(self, name: str, fields: dict[str, Any]) -> None:
        """任意の見出し（例: "INPUT"/"OUTPUT"/"OCR"）とキー・値の組を記録する。"""
        self._sections[name] = fields

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def error(self, message: str) -> None:
        self.errors.append(message)

    def record_generated_file(self, path: str | Path) -> None:
        self.generated_files.append(str(path))

    def _format_value(self, value: Any) -> list[str]:
        if isinstance(value, (list, tuple)):
            if not value:
                return ["(none)"]
            return [f"- {item}" for item in value]
        return [str(value)]

    def finalize(self, exit_code: int, captured_stderr: str = "") -> None:
        """ログ本文を組み立ててファイルに書き出す。呼び出しは1回のみを想定（例外時もfinallyで呼ぶ）。"""
        if not self._enabled or self._log_path is None:
            return

        ended_at = datetime.now().astimezone()
        lines: list[str] = []

        lines.append("===== START =====")
        lines.append(f"timestamp: {self.started_at.isoformat()}")
        lines.append(f"command: {self.command}")
        lines.append(f"args: {' '.join(self.argv)}")
        lines.append("")

        lines.append("===== ENVIRONMENT =====")
        lines.append(f"python: {platform.python_version()}")
        lines.append(f"cwd: {Path.cwd()}")
        lines.append("")

        for name, fields in self._sections.items():
            lines.append(f"===== {name.upper()} =====")
            for key, value in fields.items():
                formatted = self._format_value(value)
                if len(formatted) == 1 and not isinstance(value, (list, tuple)):
                    lines.append(f"{key}: {formatted[0]}")
                else:
                    lines.append(f"{key}:")
                    lines.extend(formatted)
            lines.append("")

        lines.append("===== OUTPUT =====")
        lines.append("generated_files:")
        lines.extend(self._format_value(self.generated_files))
        lines.append("")

        lines.append("===== WARNINGS =====")
        lines.extend(self._format_value(self.warnings))
        lines.append("")

        lines.append("===== ERRORS =====")
        lines.extend(self._format_value(self.errors))
        lines.append("")

        if captured_stderr.strip():
            lines.append("===== STDERR =====")
            lines.append(captured_stderr.rstrip("\n"))
            lines.append("")

        lines.append("===== RESULT =====")
        lines.append(f"exit_code: {exit_code}")
        lines.append(f"ended_at: {ended_at.isoformat()}")

        content = mask_secrets("\n".join(lines) + "\n")
        try:
            self._log_path.write_text(content, encoding="utf-8")
        except OSError as e:
            print(f"WARNING: ログファイルを書き込めませんでした（処理は続行します）: {e}", file=sys.stderr)
