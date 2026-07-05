"""テスト全体で共有するfixture。

このプロジェクトの開発・CI環境にはTesseract本体が入っていないことが多い。Phase 10.1で
OCR前提の事前チェック（画像input+proofread/restructureでOCRが実質使えない場合はエラー終了する）
を追加したため、OCRの有無を直接検証しないテスト（画像output・--output-format・
--no-compat-output・--font-path等）がTesseract未導入によって巻き添えでエラー終了しないよう、
既定でOCR環境が利用可能・OCRが常に何らかのテキストを返す状態にしておく。

OCR未導入・言語データ無し・全ページ空といった挙動そのものを検証するテストは、各テスト内で
`get_ocr_environment_status`/`_try_ocr`を個別にmonkeypatchして上書きする
（monkeypatchは後勝ちのため、このfixtureの既定値を問題なく上書きできる）。
"""

import pytest

_READY_OCR_STATUS = {
    "tesseract_available": True,
    "tesseract_path": "/usr/bin/tesseract",
    "tesseract_on_path": True,
    "version": "tesseract 5.0.0 (test fixture)",
    "languages": ["eng", "jpn"],
    "japanese_available": True,
    "english_available": True,
    "brew_available": True,
    "brew_path": "/usr/local/bin/brew",
    "brew_on_path": True,
    "path_suggestions": [],
    "warnings": [],
    "errors": [],
    "ocr_ready": True,
}


@pytest.fixture(autouse=True)
def default_ocr_environment_ready(request, monkeypatch):
    # src.ocr_environment.get_ocr_environment_status自体はパッチしない
    # （tests/test_ocr_environment.pyがこの関数の実装そのものを検証するため）。
    # 呼び出し元モジュール（import_source.py/cli.py）にimportされた束縛だけを差し替える。
    monkeypatch.setattr("src.import_source.get_ocr_environment_status", lambda: dict(_READY_OCR_STATUS))
    monkeypatch.setattr("src.cli.get_ocr_environment_status", lambda: dict(_READY_OCR_STATUS))

    # @pytest.mark.real_ocr を付けたテスト（_try_ocr自体を検証するテスト）には適用しない。
    if "real_ocr" not in request.keywords:
        monkeypatch.setattr(
            "src.import_source._try_ocr",
            lambda image_path, ocr_status: "テスト用ダミーOCRテキスト（自動テスト環境の既定値）",
        )


@pytest.fixture(autouse=True)
def isolate_execution_logs(tmp_path, monkeypatch):
    """CLI経由のテストが実際のプロジェクトの`logs/`を汚さないよう、実行ログの出力先を
    テストごとの一時ディレクトリへ差し替える（`src/execution_logger.py`が参照する
    `AI_KYOUZAI_LOGS_DIR`環境変数を使う）。"""
    monkeypatch.setenv("AI_KYOUZAI_LOGS_DIR", str(tmp_path / "test_logs"))
