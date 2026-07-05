from src.ocr_environment import (
    check_homebrew_environment,
    check_tesseract_environment,
    format_all_pages_empty_warning,
    format_environment_report,
    format_precondition_warning,
    get_ocr_environment_status,
    resolve_ocr_lang,
)


def _patch_probe(
    monkeypatch,
    *,
    tesseract_on_path=None,
    tesseract_common_path=None,
    tesseract_version=None,
    tesseract_languages=None,
    brew_on_path=None,
    brew_common_path=None,
):
    """tesseract/brewの探索結果をまとめて1回でパッチする。

    _find_on_path/_find_common_pathをテストごとに複数回パッチすると後勝ちで上書きされて
    しまうため、tesseract/brew両方の条件を1つの関数呼び出しで指定できるようにする。
    """

    def _find_on_path(cmd):
        if cmd == "tesseract":
            return tesseract_on_path
        if cmd == "brew":
            return brew_on_path
        return None

    def _find_common_path(paths):
        if any("tesseract" in p for p in paths):
            return tesseract_common_path
        if any("brew" in p for p in paths):
            return brew_common_path
        return None

    monkeypatch.setattr("src.ocr_environment._find_on_path", _find_on_path)
    monkeypatch.setattr("src.ocr_environment._find_common_path", _find_common_path)
    monkeypatch.setattr("src.ocr_environment._tesseract_version", lambda cmd: tesseract_version)
    monkeypatch.setattr("src.ocr_environment._tesseract_languages", lambda cmd: tesseract_languages or [])


# --- tesseract環境チェック ---------------------------------------------------


def test_check_tesseract_environment_when_on_path(monkeypatch):
    _patch_probe(monkeypatch, tesseract_on_path="/usr/bin/tesseract", tesseract_version="tesseract 5.3.0", tesseract_languages=["eng", "jpn"])
    status = check_tesseract_environment()
    assert status["tesseract_available"] is True
    assert status["tesseract_on_path"] is True
    assert status["tesseract_path"] == "/usr/bin/tesseract"
    assert status["japanese_available"] is True
    assert status["english_available"] is True


def test_check_tesseract_environment_when_only_at_common_path(monkeypatch):
    _patch_probe(
        monkeypatch, tesseract_on_path=None, tesseract_common_path="/opt/homebrew/bin/tesseract",
        tesseract_version="tesseract 5.3.0", tesseract_languages=["eng", "jpn"],
    )
    status = check_tesseract_environment()
    assert status["tesseract_available"] is True
    assert status["tesseract_on_path"] is False
    assert status["tesseract_path"] == "/opt/homebrew/bin/tesseract"


def test_check_tesseract_environment_when_not_found_anywhere(monkeypatch):
    _patch_probe(monkeypatch)
    status = check_tesseract_environment()
    assert status["tesseract_available"] is False
    assert status["tesseract_path"] is None
    assert status["japanese_available"] is False


def test_check_tesseract_environment_japanese_missing(monkeypatch):
    _patch_probe(monkeypatch, tesseract_on_path="/usr/bin/tesseract", tesseract_version="tesseract 5.3.0", tesseract_languages=["eng"])
    status = check_tesseract_environment()
    assert status["tesseract_available"] is True
    assert status["japanese_available"] is False


# --- Homebrew環境チェック -----------------------------------------------------


def test_check_homebrew_environment_when_on_path(monkeypatch):
    _patch_probe(monkeypatch, brew_on_path="/usr/local/bin/brew")
    status = check_homebrew_environment()
    assert status["brew_available"] is True
    assert status["brew_on_path"] is True


def test_check_homebrew_environment_when_only_at_common_path(monkeypatch):
    _patch_probe(monkeypatch, brew_on_path=None, brew_common_path="/opt/homebrew/bin/brew")
    status = check_homebrew_environment()
    assert status["brew_available"] is True
    assert status["brew_on_path"] is False
    assert status["brew_path"] == "/opt/homebrew/bin/brew"


def test_check_homebrew_environment_when_not_found(monkeypatch):
    _patch_probe(monkeypatch)
    status = check_homebrew_environment()
    assert status["brew_available"] is False


# --- 総合診断（get_ocr_environment_status） ------------------------------------


def test_get_ocr_environment_status_all_ready(monkeypatch):
    _patch_probe(
        monkeypatch, tesseract_on_path="/usr/bin/tesseract", tesseract_version="tesseract 5.3.0",
        tesseract_languages=["eng", "jpn"], brew_on_path="/usr/local/bin/brew",
    )
    status = get_ocr_environment_status()
    assert status["ocr_ready"] is True
    assert status["errors"] == []


def test_get_ocr_environment_status_tesseract_missing_entirely(monkeypatch):
    _patch_probe(monkeypatch)
    status = get_ocr_environment_status()
    assert status["ocr_ready"] is False
    assert any("not found" in e for e in status["errors"])


def test_get_ocr_environment_status_tesseract_found_but_not_on_path_suggests_shellenv(monkeypatch):
    _patch_probe(
        monkeypatch,
        tesseract_on_path=None, tesseract_common_path="/opt/homebrew/bin/tesseract",
        tesseract_version="tesseract 5.3.0", tesseract_languages=["eng", "jpn"],
        brew_on_path=None, brew_common_path="/opt/homebrew/bin/brew",
    )
    status = get_ocr_environment_status()
    assert status["ocr_ready"] is False
    assert any("not available on PATH" in e for e in status["errors"])
    assert status["path_suggestions"] == ['eval "$(/opt/homebrew/bin/brew shellenv)"']


def test_get_ocr_environment_status_japanese_missing(monkeypatch):
    _patch_probe(
        monkeypatch, tesseract_on_path="/usr/bin/tesseract", tesseract_version="tesseract 5.3.0",
        tesseract_languages=["eng"], brew_on_path="/usr/local/bin/brew",
    )
    status = get_ocr_environment_status()
    assert status["ocr_ready"] is False
    assert any("jpn" in e for e in status["errors"])


def test_get_ocr_environment_status_brew_missing_gives_warning_not_error(monkeypatch):
    _patch_probe(
        monkeypatch, tesseract_on_path="/usr/bin/tesseract", tesseract_version="tesseract 5.3.0",
        tesseract_languages=["eng", "jpn"],
    )
    status = get_ocr_environment_status()
    assert status["ocr_ready"] is True  # tesseract自体は使えるためbrewの有無はOCR可否に影響しない
    assert any("Homebrew" in w for w in status["warnings"])


# --- 言語選択 -----------------------------------------------------------------


def test_resolve_ocr_lang_prefers_jpn_plus_eng():
    assert resolve_ocr_lang(["eng", "jpn"]) == "jpn+eng"


def test_resolve_ocr_lang_jpn_only():
    assert resolve_ocr_lang(["jpn"]) == "jpn"


def test_resolve_ocr_lang_eng_only_when_jpn_missing():
    assert resolve_ocr_lang(["eng"]) == "eng"


def test_resolve_ocr_lang_fallback_when_neither_available():
    assert resolve_ocr_lang([]) == "eng"


# --- メッセージ生成 -------------------------------------------------------------


def test_format_precondition_warning_when_tesseract_missing_mentions_install_commands():
    status = {
        "tesseract_available": False, "tesseract_path": None, "tesseract_on_path": False,
        "japanese_available": False, "path_suggestions": [],
    }
    message = format_precondition_warning(status)
    assert "brew install tesseract" in message
    assert "tesseract-lang" in message


def test_format_precondition_warning_when_path_issue_mentions_shellenv():
    status = {
        "tesseract_available": True, "tesseract_path": "/opt/homebrew/bin/tesseract", "tesseract_on_path": False,
        "japanese_available": True, "path_suggestions": ['eval "$(/opt/homebrew/bin/brew shellenv)"'],
    }
    message = format_precondition_warning(status)
    assert "not available on PATH" in message
    assert 'eval "$(/opt/homebrew/bin/brew shellenv)"' in message
    assert "~/.zprofile" in message


def test_format_all_pages_empty_warning_mentions_check_ocr_command():
    message = format_all_pages_empty_warning()
    assert "check-ocr" in message


def test_format_environment_report_when_ready(monkeypatch):
    _patch_probe(
        monkeypatch, tesseract_on_path="/usr/bin/tesseract", tesseract_version="tesseract 5.3.0",
        tesseract_languages=["eng", "jpn"], brew_on_path="/usr/local/bin/brew",
    )
    status = get_ocr_environment_status()
    report = format_environment_report(status)
    assert "ready" in report.lower() or "利用可能" in report


def test_format_environment_report_when_not_ready_lists_action_steps(monkeypatch):
    _patch_probe(monkeypatch, brew_common_path="/opt/homebrew/bin/brew")
    status = get_ocr_environment_status()
    report = format_environment_report(status)
    assert "Action required" in report
    assert "brew shellenv" in report
