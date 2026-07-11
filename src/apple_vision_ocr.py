from __future__ import annotations

import json
import platform
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# macOS標準のVisionフレームワーク（VNRecognizeTextRequest）を使う、第二のOCRエンジン向けアダプター。
#
# 実際のOCR処理はSwift製のローカルヘルパー（tools/apple_vision_ocr/、`scripts/build_apple_vision_ocr.sh`
# でビルドする`apple-vision-ocr`実行ファイル）が行い、このモジュールはそれを安全に呼び出すだけの薄い層。
# 画像・OCR結果はいずれもローカルのVisionフレームワーク内で処理され、外部へ送信されない。
#
# Tesseractは既存の唯一のOCRエンジンとして維持し（`src/ocr_engine.py`）、このモジュールは
# 比較用の独立した第二の結果を得るためだけに使う（`src/ocr_compare.py`/`src/ocr_comparison.py`参照）。
# Apple Visionが使えない環境（macOS以外、ヘルパー未ビルド等）では、常に`available=False`の
# 結果を返して安全にフォールバックする（例外を投げない）。

_DEFAULT_TIMEOUT_SECONDS = 30.0
_HELPER_RELATIVE_RELEASE = Path("tools/apple_vision_ocr/.build/release/apple-vision-ocr")
_HELPER_RELATIVE_DEBUG = Path("tools/apple_vision_ocr/.build/debug/apple-vision-ocr")


@dataclass
class BoundingBox:
    x: float
    y: float
    width: float
    height: float


@dataclass
class ObservationCandidate:
    text: str
    confidence: float


@dataclass
class AppleVisionObservation:
    text: str
    confidence: float
    bounding_box: BoundingBox
    candidates: list[ObservationCandidate] = field(default_factory=list)


@dataclass
class AppleVisionResult:
    """`apple-vision-ocr`ヘルパーの実行結果（またはフォールバック時の代替結果）。

    `available=False`の場合、`text`は空文字・`observations`は空リストになる。呼び出し側は
    `available`だけを見て、Apple Vision結果を使うか、Tesseractのみで処理を続けるかを判断できる。
    """

    engine: str = "apple_vision"
    available: bool = False
    language: str = ""
    duration_seconds: float = 0.0
    observations: list[AppleVisionObservation] = field(default_factory=list)
    text: str = ""
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class AppleVisionAvailability:
    """ヘルパーを実際に実行せずに判定できる、環境面の利用可否（ビルド済みか等）。"""

    available: bool
    reason: str
    helper_path: str | None = None


def is_macos() -> bool:
    return platform.system() == "Darwin"


def find_apple_vision_helper_path(project_root: Path | None = None) -> Path | None:
    """ビルド済みのApple Visionヘルパー実行ファイルを探す。無ければ`None`を返す。

    `scripts/build_apple_vision_ocr.sh`が生成するreleaseビルドを優先し、無ければ
    開発中に`swift build`だけ実行した場合のdebugビルドも見る。
    """
    root = project_root or Path(__file__).resolve().parent.parent
    for relative in (_HELPER_RELATIVE_RELEASE, _HELPER_RELATIVE_DEBUG):
        candidate = root / relative
        if candidate.is_file() and _is_executable(candidate):
            return candidate
    return None


def _is_executable(path: Path) -> bool:
    import os

    return os.access(path, os.X_OK)


def check_apple_vision_availability(project_root: Path | None = None) -> AppleVisionAvailability:
    """実際にヘルパーを起動せずに判定できる範囲で、Apple Visionが使えそうかを判定する。

    macOS以外では常に利用不可。macOSでもヘルパーが未ビルドなら利用不可（エラーではなく、
    `scripts/build_apple_vision_ocr.sh`でのビルドを促す案内として扱う）。
    """
    if not is_macos():
        return AppleVisionAvailability(available=False, reason="Apple VisionはmacOS専用です（現在のOS: 非macOS）。")
    helper_path = find_apple_vision_helper_path(project_root)
    if helper_path is None:
        return AppleVisionAvailability(
            available=False,
            reason="Apple Vision OCRヘルパーが未ビルドです。`bash scripts/build_apple_vision_ocr.sh`でビルドしてください。",
        )
    return AppleVisionAvailability(available=True, reason="利用可能", helper_path=str(helper_path))


def _build_argv(helper_path: Path, image_path: str | Path, *, language: str, recognition_level: str,
                 language_correction: bool, custom_words: list[str] | None) -> list[str]:
    """ヘルパーに渡す引数配列を組み立てる。シェル文字列へ画像パスを埋め込まず、常に配列として渡す
    （`shell=True`は使用しない。コマンドインジェクションを構造的に防ぐ）。
    """
    argv = [str(helper_path), "--input", str(image_path), "--language", language,
            "--recognition-level", recognition_level]
    if language_correction:
        argv.append("--language-correction")
    if custom_words:
        argv.extend(["--custom-words", ",".join(custom_words)])
    return argv


def _parse_observation(raw: dict[str, Any]) -> AppleVisionObservation:
    bbox_raw = raw.get("bounding_box") or {}
    bounding_box = BoundingBox(
        x=float(bbox_raw.get("x", 0.0)),
        y=float(bbox_raw.get("y", 0.0)),
        width=float(bbox_raw.get("width", 0.0)),
        height=float(bbox_raw.get("height", 0.0)),
    )
    candidates = [
        ObservationCandidate(text=str(c.get("text", "")), confidence=float(c.get("confidence", 0.0)))
        for c in raw.get("candidates", []) or []
    ]
    return AppleVisionObservation(
        text=str(raw.get("text", "")),
        confidence=float(raw.get("confidence", 0.0)),
        bounding_box=bounding_box,
        candidates=candidates,
    )


def _parse_helper_stdout(stdout: str, *, language: str) -> AppleVisionResult:
    """ヘルパーの標準出力（JSON文字列）を`AppleVisionResult`へ変換する。

    想定外の形式（キー欠落・型不一致等）でも例外を外へ伝播させず、`available=False`の
    結果として扱う（ヘルパーのバージョン差異等に対して壊れにくくするため）。
    """
    try:
        data = json.loads(stdout)
        observations = [_parse_observation(o) for o in data.get("observations", []) or []]
        return AppleVisionResult(
            engine=str(data.get("engine", "apple_vision")),
            available=bool(data.get("available", False)),
            language=str(data.get("language", language)),
            duration_seconds=float(data.get("duration_seconds", 0.0)),
            observations=observations,
            text=str(data.get("text", "")),
            warnings=[str(w) for w in data.get("warnings", []) or []],
        )
    except (json.JSONDecodeError, TypeError, ValueError, AttributeError) as e:
        return AppleVisionResult(
            available=False,
            language=language,
            warnings=[f"ヘルパーの出力をJSONとして解釈できませんでした: {e}"],
            error="invalid_json_output",
        )


def run_apple_vision_ocr(
    image_path: str | Path,
    *,
    language: str = "ja-JP",
    recognition_level: str = "accurate",
    language_correction: bool = True,
    custom_words: list[str] | None = None,
    timeout: float = _DEFAULT_TIMEOUT_SECONDS,
    helper_path: str | Path | None = None,
    project_root: Path | None = None,
) -> AppleVisionResult:
    """画像1枚に対してApple Vision OCRを実行する。

    例外を投げない（呼び出し側が`try/except`無しで安全に使える）。macOS以外・ヘルパー未ビルド・
    タイムアウト・不正なJSON出力・ヘルパーの異常終了等、あらゆる失敗ケースで
    `available=False`の`AppleVisionResult`を返す（Tesseractへの安全なフォールバックを前提にした設計）。
    """
    resolved_helper: Path | None
    if helper_path is not None:
        resolved_helper = Path(helper_path)
    else:
        resolved_helper = find_apple_vision_helper_path(project_root)

    if not is_macos():
        return AppleVisionResult(
            available=False, language=language, warnings=["Apple VisionはmacOS専用です。"], error="not_macos"
        )
    if resolved_helper is None or not resolved_helper.is_file():
        return AppleVisionResult(
            available=False,
            language=language,
            warnings=["Apple Vision OCRヘルパーが見つかりません（未ビルドの可能性があります）。"],
            error="helper_not_found",
        )

    argv = _build_argv(
        resolved_helper, image_path, language=language, recognition_level=recognition_level,
        language_correction=language_correction, custom_words=custom_words,
    )

    try:
        completed = subprocess.run(
            argv, capture_output=True, text=True, timeout=timeout, shell=False
        )
    except subprocess.TimeoutExpired:
        return AppleVisionResult(
            available=False, language=language,
            warnings=[f"Apple Vision OCRヘルパーがタイムアウトしました（{timeout}秒）。"], error="timeout",
        )
    except OSError as e:
        return AppleVisionResult(
            available=False, language=language,
            warnings=[f"Apple Vision OCRヘルパーの実行に失敗しました: {e}"], error="exec_failed",
        )

    stdout = completed.stdout.strip()
    if not stdout:
        stderr_snippet = completed.stderr.strip()[:500]
        return AppleVisionResult(
            available=False,
            language=language,
            warnings=[f"Apple Vision OCRヘルパーから出力がありませんでした（終了コード{completed.returncode}）: {stderr_snippet}"],
            error="empty_output",
        )

    result = _parse_helper_stdout(stdout, language=language)
    return result
