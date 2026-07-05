from src.execution_logger import ExecutionLogger, TeeStderr, mask_secrets


def test_execution_logger_creates_log_file_with_timestamped_name(tmp_path):
    logger = ExecutionLogger("build-all", ["build-all", "--input", "x"], logs_dir=tmp_path)
    logger.finalize(0)

    log_files = list(tmp_path.glob("*_build-all.log"))
    assert len(log_files) == 1


def test_execution_logger_content_includes_required_sections(tmp_path):
    logger = ExecutionLogger("build-all", ["build-all", "--mode", "proofread"], logs_dir=tmp_path)
    logger.add_section("INPUT", {"input_path": "input/source", "mode": "proofread"})
    logger.record_generated_file("output/imported_pages.json")
    logger.warn("一部ページが空でした")
    logger.error("致命的なエラー")
    logger.finalize(1, captured_stderr="stderrの内容")

    log_files = list(tmp_path.glob("*.log"))
    text = log_files[0].read_text(encoding="utf-8")

    assert "===== START =====" in text
    assert "command: build-all" in text
    assert "===== ENVIRONMENT =====" in text
    assert "python:" in text
    assert "===== INPUT =====" in text
    assert "input_path: input/source" in text
    assert "===== OUTPUT =====" in text
    assert "output/imported_pages.json" in text
    assert "===== WARNINGS =====" in text
    assert "一部ページが空でした" in text
    assert "===== ERRORS =====" in text
    assert "致命的なエラー" in text
    assert "===== STDERR =====" in text
    assert "stderrの内容" in text
    assert "===== RESULT =====" in text
    assert "exit_code: 1" in text


def test_execution_logger_sanitizes_command_name_for_filename(tmp_path):
    logger = ExecutionLogger("weird/command name!", [], logs_dir=tmp_path)
    logger.finalize(0)

    log_files = list(tmp_path.iterdir())
    assert len(log_files) == 1
    assert "/" not in log_files[0].name
    assert "!" not in log_files[0].name


def test_execution_logger_does_not_raise_when_logs_dir_creation_fails(tmp_path, capsys):
    blocked_path = tmp_path / "not_a_directory"
    blocked_path.write_text("this is a file, not a directory", encoding="utf-8")

    logger = ExecutionLogger("build-all", [], logs_dir=blocked_path / "logs")
    logger.finalize(0)

    captured = capsys.readouterr()
    assert "WARNING" in captured.err


def test_tee_stderr_writes_to_original_and_captures(capsys):
    import sys

    original = sys.stderr
    tee = TeeStderr(original)
    tee.write("hello stderr\n")

    captured = capsys.readouterr()
    assert "hello stderr" in captured.err
    assert "hello stderr" in tee.captured


# --- Phase 10.2追加修正: ログの機密情報マスク ---------------------------------------


def test_mask_secrets_cli_flag_with_space():
    assert mask_secrets("--api-key sk-xxxx") == "--api-key [REDACTED]"


def test_mask_secrets_cli_flag_with_equals():
    assert mask_secrets("--api-key=sk-xxxx") == "--api-key=[REDACTED]"


def test_mask_secrets_token_flag():
    assert mask_secrets("--token secret-value") == "--token [REDACTED]"
    assert mask_secrets("--token=secret-value") == "--token=[REDACTED]"


def test_mask_secrets_authorization_bearer_header():
    assert mask_secrets("Authorization: Bearer xxxxx") == "Authorization: Bearer [REDACTED]"


def test_mask_secrets_password_key_value():
    assert mask_secrets("password=abc123") == "password=[REDACTED]"


def test_mask_secrets_is_case_insensitive():
    assert mask_secrets("PASSWORD=abc123") == "PASSWORD=[REDACTED]"
    assert mask_secrets("--API-KEY sk-xxxx") == "--API-KEY [REDACTED]"


def test_mask_secrets_other_keywords():
    assert mask_secrets("client_secret: abcdef123456") == "client_secret: [REDACTED]"
    assert mask_secrets("refresh_token=xyz") == "refresh_token=[REDACTED]"
    assert mask_secrets("access_key=AKIA1234567890") == "access_key=[REDACTED]"


def test_mask_secrets_leaves_unrelated_text_untouched():
    text = "normal text with no secrets should stay: hello world"
    assert mask_secrets(text) == text


def test_mask_secrets_does_not_falsely_trigger_on_substring_words():
    text = "tokenizer processed the document"
    assert mask_secrets(text) == text


def test_mask_secrets_within_full_args_line():
    line = "args: build-all --input input/source --password hunter2 --output-dir output"
    masked = mask_secrets(line)
    assert "hunter2" not in masked
    assert "--password [REDACTED]" in masked
    assert "--input input/source" in masked
    assert "--output-dir output" in masked


def test_mask_secrets_handles_empty_string():
    assert mask_secrets("") == ""


def test_execution_logger_masks_sensitive_args_in_log_file(tmp_path):
    """ExecutionLoggerのargsに秘密情報らしき値が含まれていても、書き出したログでは
    マスクされていることを確認する。"""
    logger = ExecutionLogger(
        "build-all", ["build-all", "--api-key", "sk-super-secret-value"], logs_dir=tmp_path
    )
    logger.finalize(0)

    log_files = list(tmp_path.glob("*.log"))
    text = log_files[0].read_text(encoding="utf-8")
    assert "sk-super-secret-value" not in text
    assert "[REDACTED]" in text


def test_execution_logger_masks_sensitive_content_in_captured_stderr(tmp_path):
    """TeeStderr経由で蓄積したstderr内容に秘密情報が含まれていても、書き出したログでは
    マスクされていることを確認する。"""
    logger = ExecutionLogger("build-all", ["build-all"], logs_dir=tmp_path)
    logger.finalize(1, captured_stderr="Authorization: Bearer secret-token-value\npassword=hunter2")

    log_files = list(tmp_path.glob("*.log"))
    text = log_files[0].read_text(encoding="utf-8")
    assert "secret-token-value" not in text
    assert "hunter2" not in text
    assert "Authorization: Bearer [REDACTED]" in text
    assert "password=[REDACTED]" in text


def test_execution_logger_masks_sensitive_content_in_error_messages(tmp_path):
    logger = ExecutionLogger("build-all", ["build-all"], logs_dir=tmp_path)
    logger.error("接続に失敗しました: api_key=sk-abcdef1234567890")
    logger.finalize(1)

    log_files = list(tmp_path.glob("*.log"))
    text = log_files[0].read_text(encoding="utf-8")
    assert "sk-abcdef1234567890" not in text
    assert "[REDACTED]" in text
