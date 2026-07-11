import subprocess

import pytest

from src import apple_vision_ocr


def _make_fake_helper(tmp_path, name="apple-vision-ocr"):
    helper_dir = tmp_path / "tools" / "apple_vision_ocr" / ".build" / "release"
    helper_dir.mkdir(parents=True)
    helper_path = helper_dir / name
    helper_path.write_text("#!/bin/sh\necho fake\n", encoding="utf-8")
    helper_path.chmod(0o755)
    return helper_path


# --- macOS判定・ヘルパー検出 -------------------------------------------------------------------


def test_find_apple_vision_helper_path_returns_none_when_missing(tmp_path):
    assert apple_vision_ocr.find_apple_vision_helper_path(tmp_path) is None


def test_find_apple_vision_helper_path_finds_release_build(tmp_path):
    helper_path = _make_fake_helper(tmp_path)
    found = apple_vision_ocr.find_apple_vision_helper_path(tmp_path)
    assert found == helper_path


def test_check_apple_vision_availability_false_on_non_macos(tmp_path, monkeypatch):
    monkeypatch.setattr(apple_vision_ocr, "is_macos", lambda: False)
    _make_fake_helper(tmp_path)
    availability = apple_vision_ocr.check_apple_vision_availability(tmp_path)
    assert availability.available is False
    assert "macOS" in availability.reason


def test_check_apple_vision_availability_false_when_helper_not_built(tmp_path, monkeypatch):
    monkeypatch.setattr(apple_vision_ocr, "is_macos", lambda: True)
    availability = apple_vision_ocr.check_apple_vision_availability(tmp_path)
    assert availability.available is False
    assert "ビルド" in availability.reason


def test_check_apple_vision_availability_true_when_macos_and_built(tmp_path, monkeypatch):
    monkeypatch.setattr(apple_vision_ocr, "is_macos", lambda: True)
    helper_path = _make_fake_helper(tmp_path)
    availability = apple_vision_ocr.check_apple_vision_availability(tmp_path)
    assert availability.available is True
    assert availability.helper_path == str(helper_path)


# --- run_apple_vision_ocr（安全なフォールバック。例外を投げない） --------------------------------


def test_run_apple_vision_ocr_falls_back_when_not_macos(monkeypatch):
    monkeypatch.setattr(apple_vision_ocr, "is_macos", lambda: False)

    def _should_not_be_called(*args, **kwargs):
        raise AssertionError("macOS以外ではsubprocessを呼び出してはいけない")

    monkeypatch.setattr(apple_vision_ocr.subprocess, "run", _should_not_be_called)

    result = apple_vision_ocr.run_apple_vision_ocr("dummy.png")
    assert result.available is False
    assert result.error == "not_macos"
    assert result.text == ""


def test_run_apple_vision_ocr_falls_back_when_helper_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(apple_vision_ocr, "is_macos", lambda: True)
    result = apple_vision_ocr.run_apple_vision_ocr(
        "dummy.png", helper_path=tmp_path / "does-not-exist"
    )
    assert result.available is False
    assert result.error == "helper_not_found"


def test_run_apple_vision_ocr_falls_back_on_timeout(tmp_path, monkeypatch):
    monkeypatch.setattr(apple_vision_ocr, "is_macos", lambda: True)
    helper_path = _make_fake_helper(tmp_path)

    def _raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="apple-vision-ocr", timeout=1.0)

    monkeypatch.setattr(apple_vision_ocr.subprocess, "run", _raise_timeout)

    result = apple_vision_ocr.run_apple_vision_ocr("dummy.png", helper_path=helper_path, timeout=1.0)
    assert result.available is False
    assert result.error == "timeout"


def test_run_apple_vision_ocr_falls_back_on_exec_error(tmp_path, monkeypatch):
    monkeypatch.setattr(apple_vision_ocr, "is_macos", lambda: True)
    helper_path = _make_fake_helper(tmp_path)

    def _raise_oserror(*args, **kwargs):
        raise OSError("permission denied")

    monkeypatch.setattr(apple_vision_ocr.subprocess, "run", _raise_oserror)

    result = apple_vision_ocr.run_apple_vision_ocr("dummy.png", helper_path=helper_path)
    assert result.available is False
    assert result.error == "exec_failed"


def test_run_apple_vision_ocr_falls_back_on_invalid_json(tmp_path, monkeypatch):
    monkeypatch.setattr(apple_vision_ocr, "is_macos", lambda: True)
    helper_path = _make_fake_helper(tmp_path)

    def _fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="not json", stderr="")

    monkeypatch.setattr(apple_vision_ocr.subprocess, "run", _fake_run)

    result = apple_vision_ocr.run_apple_vision_ocr("dummy.png", helper_path=helper_path)
    assert result.available is False
    assert result.error == "invalid_json_output"


def test_run_apple_vision_ocr_falls_back_on_empty_output(tmp_path, monkeypatch):
    monkeypatch.setattr(apple_vision_ocr, "is_macos", lambda: True)
    helper_path = _make_fake_helper(tmp_path)

    def _fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args, returncode=64, stdout="", stderr="usage error")

    monkeypatch.setattr(apple_vision_ocr.subprocess, "run", _fake_run)

    result = apple_vision_ocr.run_apple_vision_ocr("dummy.png", helper_path=helper_path)
    assert result.available is False
    assert result.error == "empty_output"
    assert "usage error" in result.warnings[0]


def test_run_apple_vision_ocr_parses_valid_json_successfully(tmp_path, monkeypatch):
    monkeypatch.setattr(apple_vision_ocr, "is_macos", lambda: True)
    helper_path = _make_fake_helper(tmp_path)

    payload = {
        "engine": "apple_vision",
        "available": True,
        "language": "ja-JP",
        "duration_seconds": 0.42,
        "observations": [
            {
                "text": "【タイトル】",
                "confidence": 0.95,
                "bounding_box": {"x": 0.1, "y": 0.8, "width": 0.5, "height": 0.05},
                "candidates": [{"text": "【タイトル】", "confidence": 0.95}],
            }
        ],
        "text": "【タイトル】\n本文",
        "warnings": [],
    }
    import json as json_module

    def _fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args, returncode=0, stdout=json_module.dumps(payload), stderr=""
        )

    monkeypatch.setattr(apple_vision_ocr.subprocess, "run", _fake_run)

    result = apple_vision_ocr.run_apple_vision_ocr("dummy.png", helper_path=helper_path)
    assert result.available is True
    assert result.text == "【タイトル】\n本文"
    assert result.duration_seconds == 0.42
    assert len(result.observations) == 1
    assert result.observations[0].text == "【タイトル】"
    assert result.observations[0].candidates[0].confidence == 0.95


def test_run_apple_vision_ocr_uses_argv_list_not_shell_string(tmp_path, monkeypatch):
    """画像パスをシェル文字列へ埋め込まず、引数配列として渡していることを確認する
    （コマンドインジェクション対策）。"""
    monkeypatch.setattr(apple_vision_ocr, "is_macos", lambda: True)
    helper_path = _make_fake_helper(tmp_path)

    captured = {}

    def _fake_run(argv, **kwargs):
        captured["argv"] = argv
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            args=argv, returncode=0,
            stdout='{"available": true, "language": "ja-JP", "duration_seconds": 0, "observations": [], "text": "", "warnings": []}',
            stderr="",
        )

    monkeypatch.setattr(apple_vision_ocr.subprocess, "run", _fake_run)

    dangerous_path = "dummy; rm -rf /tmp/should-not-run.png"
    apple_vision_ocr.run_apple_vision_ocr(dangerous_path, helper_path=helper_path)

    assert isinstance(captured["argv"], list)
    assert dangerous_path in captured["argv"]
    assert captured["kwargs"].get("shell") is False
