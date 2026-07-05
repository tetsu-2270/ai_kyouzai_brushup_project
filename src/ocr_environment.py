from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

# macOSでHomebrew経由インストール時によくある場所。PATHに通っていない場合の切り分けに使う。
_COMMON_TESSERACT_PATHS = ("/opt/homebrew/bin/tesseract", "/usr/local/bin/tesseract")
_COMMON_BREW_PATHS = ("/opt/homebrew/bin/brew", "/usr/local/bin/brew")

_TESSERACT_NOT_FOUND_MESSAGE = (
    "ERROR: OCR requires Tesseract, but the 'tesseract' command was not found.\n"
    "This command needs OCR because the input contains images and text extraction is required.\n"
    "Install Tesseract and Japanese language data, then run again.\n"
    "\n"
    "macOS with Homebrew:\n"
    "  brew install tesseract\n"
    "  brew install tesseract-lang\n"
    "\n"
    "If Homebrew is not installed:\n"
    "  Install Homebrew first, or install Tesseract manually.\n"
    "\n"
    "警告: OCRにはTesseractが必要ですが、'tesseract'コマンドが見つかりませんでした。\n"
    "Tesseractと日本語言語データをインストールしてから再実行してください。"
)

_JAPANESE_LANG_MISSING_MESSAGE = (
    "ERROR: Japanese OCR language data 'jpn' was not found.\n"
    "Run:\n"
    "  tesseract --list-langs\n"
    "\n"
    "macOS with Homebrew:\n"
    "  brew install tesseract-lang\n"
    "\n"
    "警告: 日本語OCR言語データ('jpn')が見つかりませんでした。`brew install tesseract-lang`等でインストールしてください。"
)

_ALL_PAGES_OCR_EMPTY_WARNING = (
    "WARNING: OCR produced no text for any page. Proofreading/restructuring has nothing to work with.\n"
    "This can happen if Tesseract/Japanese language data is missing, or if the source images genuinely "
    "contain no readable text.\n"
    "Run `python3 -m src.cli check-ocr` to diagnose the OCR environment.\n"
    "\n"
    "警告: すべてのページでOCR結果が空でした。校正・再構成の対象となるテキストがありません。\n"
    "Tesseract/日本語言語データが無いか、元画像に読み取れるテキストが本当に無い可能性があります。\n"
    "`python3 -m src.cli check-ocr` でOCR環境を診断してください。"
)

# OCR必須モード(build-allのproofread/restructure)で画像inputを処理する際、OCRが実質的に
# 使えない状態のまま「空データで成功」させない。--allow-empty-ocrで明示的に許可した場合のみ、
# 以下のチェックをスキップして従来通り処理を継続する。
OCR_REQUIRED_MODES = frozenset({"proofread", "restructure"})


def format_ocr_required_tesseract_missing_error(mode: str, status: dict[str, Any]) -> str:
    """OCR必須モードでTesseract自体が使えない場合の、非ゼロ終了用エラーメッセージを組み立てる。"""
    lines = [
        f"ERROR: mode={mode} requires OCR text, but Tesseract is not available.",
        "Install Tesseract and Japanese language data, then run again.",
        "",
    ]
    if status["path_suggestions"]:
        lines.append("If Homebrew is installed but not on PATH:")
        for suggestion in status["path_suggestions"]:
            lines.append(f"  {suggestion}")
        lines.append("")
    lines.append("Then:")
    lines.append("  brew install tesseract")
    lines.append("  brew install tesseract-lang")
    lines.append("")
    lines.append("If you want to proceed anyway with empty OCR text (e.g. for testing), pass --allow-empty-ocr.")
    lines.append("")
    lines.append(f"警告: mode={mode}はOCRテキストが必要ですが、Tesseractが利用できません。")
    lines.append("Tesseractと日本語言語データをインストールしてから再実行してください。")
    lines.append("空のOCRテキストのまま続行したい場合（テスト目的等）は--allow-empty-ocrを指定してください。")
    return "\n".join(lines)


def format_ocr_required_japanese_missing_error(mode: str) -> str:
    """OCR必須モードで日本語言語データが無い場合の、非ゼロ終了用エラーメッセージを組み立てる。"""
    return (
        f"ERROR: mode={mode} requires Japanese OCR, but Tesseract language data 'jpn' was not found.\n"
        "Run:\n"
        "  tesseract --list-langs\n"
        "\n"
        "macOS with Homebrew:\n"
        "  brew install tesseract-lang\n"
        "\n"
        "If you want to proceed anyway with empty OCR text (e.g. for testing), pass --allow-empty-ocr.\n"
        "\n"
        f"警告: mode={mode}は日本語OCRが必要ですが、言語データ'jpn'が見つかりませんでした。\n"
        "`brew install tesseract-lang`等でインストールしてください。"
    )


def format_ocr_required_all_pages_empty_error(mode: str) -> str:
    """OCR必須モードで全ページのOCR結果が空だった場合の、非ゼロ終了用エラーメッセージを組み立てる。"""
    return (
        f"ERROR: OCR produced no text for any imported page. mode={mode} cannot continue without extracted text.\n"
        "Run `python3 -m src.cli check-ocr` to diagnose the OCR environment.\n"
        "If you want to proceed anyway with empty OCR text (e.g. for testing), pass --allow-empty-ocr.\n"
        "\n"
        f"警告: OCRで抽出できたテキストがありません。mode={mode}は抽出テキストが無いと処理を続けられません。\n"
        "`python3 -m src.cli check-ocr` でOCR環境を診断してください。"
    )


def format_partial_pages_empty_warning(empty_count: int, total_count: int) -> str:
    """一部のページのみOCR結果が空だった場合の警告（処理は継続してよい）。"""
    return (
        f"WARNING: OCR produced no text for {empty_count} of {total_count} pages.\n"
        f"警告: {total_count}ページ中{empty_count}ページでOCR結果が空でした。"
    )


def _find_on_path(command: str) -> str | None:
    return shutil.which(command)


def _find_common_path(candidates: tuple[str, ...]) -> str | None:
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return None


def _run_command(cmd: list[str]) -> str | None:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10, check=False)
        return (result.stdout or "") + (result.stderr or "")
    except (OSError, subprocess.TimeoutExpired):
        return None


def _tesseract_version(tesseract_cmd: str) -> str | None:
    output = _run_command([tesseract_cmd, "--version"])
    if not output:
        return None
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return lines[0] if lines else None


def _tesseract_languages(tesseract_cmd: str) -> list[str]:
    output = _run_command([tesseract_cmd, "--list-langs"])
    if not output:
        return []
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    # 先頭行は "List of available languages ..." のような見出し行のため除く。
    return [line for line in lines if line and not line.lower().startswith("list of")]


def check_tesseract_environment() -> dict[str, Any]:
    """tesseractコマンドの有無・所在・バージョン・利用可能言語を確認する。

    PATH上に見つからない場合でも、Homebrewでの典型的なインストール先を確認し、
    「PATHに無いだけ」か「そもそも存在しない」かを切り分ける。
    """
    on_path = _find_on_path("tesseract")
    common_path = _find_common_path(_COMMON_TESSERACT_PATHS)
    tesseract_cmd = on_path or common_path
    available = tesseract_cmd is not None

    version = _tesseract_version(tesseract_cmd) if available else None
    languages = _tesseract_languages(tesseract_cmd) if available else []

    return {
        "tesseract_available": available,
        "tesseract_path": tesseract_cmd,
        "tesseract_on_path": on_path is not None,
        "version": version,
        "languages": languages,
        "japanese_available": "jpn" in languages,
        "english_available": "eng" in languages,
    }


def check_homebrew_environment() -> dict[str, Any]:
    """brewコマンドの有無・所在を確認する（PATHに無いだけか、そもそも存在しないかを切り分ける）。"""
    on_path = _find_on_path("brew")
    common_path = _find_common_path(_COMMON_BREW_PATHS)
    brew_cmd = on_path or common_path
    available = brew_cmd is not None

    return {
        "brew_available": available,
        "brew_path": brew_cmd,
        "brew_on_path": on_path is not None,
    }


def _build_path_suggestions(tesseract_status: dict[str, Any], brew_status: dict[str, Any]) -> list[str]:
    suggestions: list[str] = []
    if brew_status["brew_available"] and not brew_status["brew_on_path"]:
        suggestions.append(f'eval "$({brew_status["brew_path"]} shellenv)"')
    elif tesseract_status["tesseract_available"] and not tesseract_status["tesseract_on_path"]:
        tesseract_bin_dir = str(Path(tesseract_status["tesseract_path"]).parent)
        suggestions.append(f'export PATH="{tesseract_bin_dir}:$PATH"')
    return suggestions


def get_ocr_environment_status() -> dict[str, Any]:
    """OCR実行に必要な環境（tesseract/日本語言語データ/Homebrew）をまとめて診断する。

    戻り値はCLI(check-ocr)・エラーメッセージ生成・テストのいずれからも扱いやすいよう、
    フラットな辞書構造にする。
    """
    tesseract_status = check_tesseract_environment()
    brew_status = check_homebrew_environment()

    warnings: list[str] = []
    errors: list[str] = []

    if not tesseract_status["tesseract_available"]:
        errors.append(
            "Tesseract command was not found (checked PATH and common install locations "
            f"{', '.join(_COMMON_TESSERACT_PATHS)})."
        )
    elif not tesseract_status["tesseract_on_path"]:
        errors.append(
            f'Tesseract was found at {tesseract_status["tesseract_path"]}, but it is not available on PATH.'
        )

    if tesseract_status["tesseract_available"] and not tesseract_status["japanese_available"]:
        errors.append("Japanese OCR language data 'jpn' was not found.")

    if not brew_status["brew_available"]:
        warnings.append(
            "Homebrew was not found on PATH or common install locations. "
            "Please install Homebrew first, or install Tesseract manually."
        )
    elif not brew_status["brew_on_path"]:
        warnings.append(f'Homebrew was found at {brew_status["brew_path"]}, but it is not available on PATH.')

    status = {
        **tesseract_status,
        **brew_status,
        "path_suggestions": _build_path_suggestions(tesseract_status, brew_status),
        "warnings": warnings,
        "errors": errors,
    }
    status["ocr_ready"] = (
        tesseract_status["tesseract_available"]
        and tesseract_status["tesseract_on_path"]
        and tesseract_status["japanese_available"]
    )
    return status


def resolve_ocr_lang(languages: list[str]) -> str:
    """tesseractの利用可能言語一覧から、OCRに使う--langの値を決める。

    日本語(jpn)・英数字混在を想定し、両方あれば"jpn+eng"、片方のみならそれのみを使う。
    どちらも無い場合はpytesseractの既定言語"eng"にフォールバックする（実際の日本語抽出はできない）。
    """
    has_jpn = "jpn" in languages
    has_eng = "eng" in languages
    if has_jpn and has_eng:
        return "jpn+eng"
    if has_jpn:
        return "jpn"
    if has_eng:
        return "eng"
    return "eng"


def format_precondition_warning(status: dict[str, Any]) -> str:
    """画像inputのOCR前に、環境が整っていない場合の警告メッセージを組み立てる。"""
    if not status["tesseract_available"]:
        return _TESSERACT_NOT_FOUND_MESSAGE

    lines: list[str] = []
    if not status["tesseract_on_path"]:
        lines.append(
            f'ERROR: Tesseract was found at {status["tesseract_path"]}, but it is not available on PATH.'
        )
        if status["path_suggestions"]:
            lines.append("Run:")
            for suggestion in status["path_suggestions"]:
                lines.append(f"  {suggestion}")
                lines.append("To make it permanent:")
                lines.append(f'  echo \'{suggestion}\' >> ~/.zprofile')
        lines.append("")

    if not status["japanese_available"]:
        lines.append(_JAPANESE_LANG_MISSING_MESSAGE)

    return "\n".join(lines).strip()


def format_all_pages_empty_warning() -> str:
    return _ALL_PAGES_OCR_EMPTY_WARNING


def format_environment_report(status: dict[str, Any]) -> str:
    """`check-ocr`コマンド向けの人間可読な診断レポートを組み立てる。"""
    lines = ["OCR environment check", "OCR環境診断"]
    lines.append("")

    lines.append(f"- tesseract on PATH: {'found' if status['tesseract_on_path'] else 'not found'}")
    if status["tesseract_available"]:
        common_note = "" if status["tesseract_on_path"] else f" ({status['tesseract_path']} found)"
        lines.append(f"- tesseract common path: available{common_note}")
        lines.append(f"- tesseract version: {status['version'] or 'unknown'}")
        lines.append(f"- tesseract languages: {', '.join(status['languages']) or '(none)'}")
    else:
        lines.append(f"- tesseract common path: not found (checked {', '.join(_COMMON_TESSERACT_PATHS)})")
    lines.append(f"- Japanese language data (jpn): {'available' if status['japanese_available'] else 'unavailable'}")

    lines.append("")
    lines.append(f"- Homebrew on PATH: {'found' if status['brew_on_path'] else 'not found'}")
    if status["brew_available"] and not status["brew_on_path"]:
        lines.append(f"- Homebrew common path: {status['brew_path']} found")
    elif not status["brew_available"]:
        lines.append(f"- Homebrew common path: not found (checked {', '.join(_COMMON_BREW_PATHS)})")

    lines.append("")
    if status["ocr_ready"]:
        lines.append("OCR is ready to use. / OCRは利用可能です。")
    else:
        lines.append("Action required / 対応が必要です:")
        step = 1
        if status["path_suggestions"]:
            lines.append(f"{step}. Enable the missing command in the current shell:")
            for suggestion in status["path_suggestions"]:
                lines.append(f"   {suggestion}")
            step += 1
        if not status["tesseract_available"]:
            lines.append(f"{step}. Install Tesseract (macOS/Homebrew: brew install tesseract)")
            step += 1
        if status["tesseract_available"] and not status["japanese_available"]:
            lines.append(f"{step}. Install Japanese language data (macOS/Homebrew: brew install tesseract-lang)")
            step += 1
        lines.append(f"{step}. Confirm:")
        lines.append("   which tesseract")
        lines.append("   tesseract --list-langs")

    return "\n".join(lines)
