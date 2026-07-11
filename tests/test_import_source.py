import json

import pytest
from PIL import Image

from src.import_source import import_images, import_source
from src.models import project_from_dict


def _make_image(path, size=(80, 120)):
    Image.new("RGB", size, color=(220, 220, 220)).save(path)


def test_import_images_assigns_page_no_in_filename_order(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    # わざと逆順・非連番のファイル名で作成し、ファイル名昇順に並び替わることを確認する。
    for name in ("page_003.png", "page_001.png", "page_002.png"):
        _make_image(source_dir / name)

    assets_dir = tmp_path / "assets"
    result = import_source(source_dir, assets_dir)

    page_nos = [page["page_no"] for page in result["pages"]]
    assert page_nos == [1, 2, 3]
    titles_or_names = [page["source_image"] for page in result["pages"]]
    assert titles_or_names == ["assets/page_001.png", "assets/page_002.png", "assets/page_003.png"]


def test_import_images_orders_numeric_suffixes_naturally(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    # iPhone写真アプリ等の連番書き出し名を想定。単純な文字列ソートだと
    # "...- 1" -> "...- 10" -> "...- 11" -> "...- 2" の順になってしまうため、
    # 数値として比較する自然順ソートで 1, 2, ..., 11 の順になることを確認する。
    numbers = (1, 2, 9, 10, 11)
    for n in numbers:
        # サイズを変えて内容を区別できるようにし、コピー順の検証に使えるようにする。
        _make_image(source_dir / f"おとすた講座１ - {n}.jpeg", size=(80 + n, 120))

    assets_dir = tmp_path / "assets"
    result = import_source(source_dir, assets_dir)

    page_nos = [page["page_no"] for page in result["pages"]]
    assert page_nos == [1, 2, 3, 4, 5]
    source_images = [page["source_image"] for page in result["pages"]]
    assert source_images == [
        "assets/page_001.jpeg",
        "assets/page_002.jpeg",
        "assets/page_003.jpeg",
        "assets/page_004.jpeg",
        "assets/page_005.jpeg",
    ]
    # 元ファイルとの対応（1, 2, 9, 10, 11の順）を、コピー元バイト列の一致で確認する。
    expected_order = [
        source_dir / "おとすた講座１ - 1.jpeg",
        source_dir / "おとすた講座１ - 2.jpeg",
        source_dir / "おとすた講座１ - 9.jpeg",
        source_dir / "おとすた講座１ - 10.jpeg",
        source_dir / "おとすた講座１ - 11.jpeg",
    ]
    for dest_name, src_path in zip(
        ("page_001.jpeg", "page_002.jpeg", "page_003.jpeg", "page_004.jpeg", "page_005.jpeg"),
        expected_order,
    ):
        assert (assets_dir / dest_name).read_bytes() == src_path.read_bytes()


def test_import_images_copies_original_files_into_assets_dir(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    _make_image(source_dir / "photo.jpg")

    assets_dir = tmp_path / "output" / "assets"
    result = import_source(source_dir, assets_dir)

    source_image = result["pages"][0]["source_image"]
    assert source_image == "assets/page_001.jpg"
    copied_path = assets_dir / "page_001.jpg"
    assert copied_path.exists()
    assert copied_path.read_bytes() == (source_dir / "photo.jpg").read_bytes()


def test_import_images_single_file_input(tmp_path):
    image_path = tmp_path / "single.png"
    _make_image(image_path)

    assets_dir = tmp_path / "assets"
    result = import_source(image_path, assets_dir)

    assert len(result["pages"]) == 1
    assert result["pages"][0]["source_image"] == "assets/page_001.png"


def test_import_images_result_is_compatible_with_lesson_pages_input(tmp_path):
    """import_sourceの戻り値が、そのままlesson-pagesの--input(pages形式)として使えることを確認する。"""
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    _make_image(source_dir / "page_001.png")
    _make_image(source_dir / "page_002.png")

    assets_dir = tmp_path / "assets"
    result = import_source(source_dir, assets_dir)

    project = project_from_dict(result)
    assert len(project.pages) == 2
    assert project.pages[0].page_no == 1
    assert project.pages[0].source_image == "assets/page_001.png"


def test_import_images_missing_directory_raises_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="取り込み元が見つかりません"):
        import_source(tmp_path / "does_not_exist", tmp_path / "assets")


def test_import_images_empty_directory_raises_clear_error(tmp_path):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    with pytest.raises(ValueError, match="画像ファイル"):
        import_source(empty_dir, tmp_path / "assets")


def test_import_source_unsupported_extension_raises_clear_error(tmp_path):
    unsupported = tmp_path / "note.txt"
    unsupported.write_text("hello", encoding="utf-8")
    with pytest.raises(ValueError, match="対応していない形式"):
        import_source(unsupported, tmp_path / "assets")


def test_import_source_legacy_ppt_raises_clear_error(tmp_path):
    legacy = tmp_path / "old.ppt"
    legacy.write_bytes(b"dummy")
    with pytest.raises(ValueError, match=r"\.ppt"):
        import_source(legacy, tmp_path / "assets")


def test_import_images_ocr_failure_falls_back_gracefully(tmp_path, monkeypatch):
    """tesseract本体が無い環境でも、OCRに失敗した扱いで空文字にフォールバックし、取り込み自体は成立する。"""
    import src.import_source as import_source_module

    monkeypatch.setattr(import_source_module, "_try_ocr", lambda image_path, ocr_status: "")

    source_dir = tmp_path / "source"
    source_dir.mkdir()
    _make_image(source_dir / "page_001.png")

    result = import_source(source_dir, tmp_path / "assets")
    page = result["pages"][0]
    assert page["lines"] == []
    assert page["source_image"] == "assets/page_001.png"
    assert "OCR" in page["canva"]["notes"]


def test_import_images_preserves_ocr_text_when_available(tmp_path, monkeypatch):
    import src.import_source as import_source_module

    monkeypatch.setattr(
        import_source_module, "_try_ocr", lambda image_path, ocr_status: "1行目のテキスト\n2行目のテキスト"
    )

    source_dir = tmp_path / "source"
    source_dir.mkdir()
    _make_image(source_dir / "page_001.png")

    result = import_source(source_dir, tmp_path / "assets")
    page = result["pages"][0]
    assert page["lines"] == [
        {"speaker": "", "text": "1行目のテキスト"},
        {"speaker": "", "text": "2行目のテキスト"},
    ]
    assert page["title"] == "1行目のテキスト"


def test_import_images_prints_precondition_warning_when_ocr_not_ready(tmp_path, monkeypatch, capsys):
    import src.import_source as import_source_module

    not_ready_status = {
        "tesseract_available": False, "tesseract_path": None, "tesseract_on_path": False,
        "languages": [], "japanese_available": False, "english_available": False,
        "brew_available": False, "brew_path": None, "brew_on_path": False,
        "path_suggestions": [], "warnings": [], "errors": ["Tesseract command was not found."],
        "ocr_ready": False,
    }
    monkeypatch.setattr(import_source_module, "get_ocr_environment_status", lambda: not_ready_status)

    source_dir = tmp_path / "source"
    source_dir.mkdir()
    _make_image(source_dir / "page_001.png")

    import_source(source_dir, tmp_path / "assets")

    captured = capsys.readouterr()
    assert "ERROR" in captured.err
    assert "Tesseract" in captured.err


def test_import_images_prints_all_pages_empty_warning(tmp_path, monkeypatch, capsys):
    import src.import_source as import_source_module

    monkeypatch.setattr(import_source_module, "_try_ocr", lambda image_path, ocr_status: "")

    source_dir = tmp_path / "source"
    source_dir.mkdir()
    _make_image(source_dir / "page_001.png")
    _make_image(source_dir / "page_002.png")

    import_source(source_dir, tmp_path / "assets")

    captured = capsys.readouterr()
    assert "check-ocr" in captured.err


def test_import_images_does_not_warn_when_ocr_succeeds_for_some_pages(tmp_path, monkeypatch, capsys):
    import src.import_source as import_source_module

    call_count = {"n": 0}

    def _fake_ocr(image_path, ocr_status):
        call_count["n"] += 1
        return "検出されたテキスト" if call_count["n"] == 1 else ""

    monkeypatch.setattr(import_source_module, "_try_ocr", _fake_ocr)

    source_dir = tmp_path / "source"
    source_dir.mkdir()
    _make_image(source_dir / "page_001.png")
    _make_image(source_dir / "page_002.png")

    import_source(source_dir, tmp_path / "assets")

    captured = capsys.readouterr()
    assert "check-ocr" not in captured.err


@pytest.mark.real_ocr
def test_try_ocr_uses_resolved_tesseract_path_and_language(tmp_path, monkeypatch):
    """_try_ocrが、環境診断で見つかったtesseractパスと言語をpytesseractに渡すことを確認する。

    内部実装はsrc/ocr_engine.py（image_to_data・複数前処理・複数PSM）に委譲しているため、
    フェイクのpytesseractモジュールもimage_to_data互換の形で応答を返す。
    """
    import src.import_source as import_source_module

    captured = {}

    class _Output:
        DICT = "dict"

    class _FakePytesseractModule:
        Output = _Output

        class pytesseract:
            tesseract_cmd = None

        @staticmethod
        def image_to_data(image, lang=None, config=None, output_type=None):
            captured["tesseract_cmd"] = _FakePytesseractModule.pytesseract.tesseract_cmd
            captured["lang"] = lang
            return {
                "text": ["OCR結果"],
                "conf": ["95"],
                "left": [0],
                "top": [0],
                "width": [50],
                "height": [20],
                "block_num": [1],
                "par_num": [1],
                "line_num": [1],
                "word_num": [1],
            }

    ocr_status = {
        "tesseract_available": True,
        "tesseract_path": "/opt/homebrew/bin/tesseract",
        "languages": ["eng", "jpn"],
    }

    import sys
    monkeypatch.setitem(sys.modules, "pytesseract", _FakePytesseractModule)

    image_path = tmp_path / "page_001.png"
    _make_image(image_path)

    text = import_source_module._try_ocr(image_path, ocr_status)

    assert "OCR結果" in text
    assert captured["tesseract_cmd"] == "/opt/homebrew/bin/tesseract"
    assert captured["lang"] == "jpn+eng"


@pytest.mark.real_ocr
def test_try_ocr_returns_empty_string_when_tesseract_unavailable(tmp_path):
    import src.import_source as import_source_module

    ocr_status = {"tesseract_available": False, "tesseract_path": None, "languages": []}
    assert import_source_module._try_ocr(tmp_path / "does_not_matter.png", ocr_status) == ""


@pytest.mark.real_ocr
def test_try_ocr_returns_empty_string_when_ocr_engine_raises(tmp_path, monkeypatch):
    """ocr_engine.run_multi_ocr()が例外を送出しても、_try_ocr()は空文字を返す
    （既存の「OCRが使えない環境でも取り込み自体は成立する」動作を維持する）。"""
    import src.import_source as import_source_module

    def _raise(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(import_source_module.ocr_engine, "run_multi_ocr", _raise)

    ocr_status = {
        "tesseract_available": True,
        "tesseract_path": "/opt/homebrew/bin/tesseract",
        "languages": ["eng", "jpn"],
    }
    image_path = tmp_path / "page_001.png"
    _make_image(image_path)

    assert import_source_module._try_ocr(image_path, ocr_status) == ""
    assert import_source_module._last_ocr_diagnostics is None


@pytest.mark.real_ocr
def test_try_ocr_diagnostics_side_channel_reflects_engine_result(tmp_path, monkeypatch):
    """_try_ocr()実行後、モジュールレベルの_last_ocr_diagnosticsから診断情報を取得できることを
    確認する（_page_from_image()がOCR品質診断をログへ渡すための副チャンネル）。"""
    import src.import_source as import_source_module
    from src.ocr_engine import OcrDiagnostics, OcrResult

    fake_result = OcrResult(
        text="テスト本文",
        diagnostics=OcrDiagnostics(preprocess="enhanced", psm=6, score=0.9, quality="ok"),
    )
    monkeypatch.setattr(
        import_source_module.ocr_engine, "run_multi_ocr", lambda *a, **k: fake_result
    )

    ocr_status = {
        "tesseract_available": True,
        "tesseract_path": "/opt/homebrew/bin/tesseract",
        "languages": ["eng", "jpn"],
    }
    image_path = tmp_path / "page_001.png"
    _make_image(image_path)

    text = import_source_module._try_ocr(image_path, ocr_status)

    assert text == "テスト本文"
    assert import_source_module._last_ocr_diagnostics is fake_result.diagnostics


def test_page_from_image_collects_diagnostics_when_sink_provided(tmp_path, monkeypatch):
    """diagnostics_sinkを渡すと、_try_ocr()実行後の診断情報がページ番号付きで記録される。
    diagnostics_sinkの指定有無にかかわらず、常に_try_ocr()（唯一の呼び出し口）を経由するため、
    tests/conftest.pyの既定モックはそのまま機能する。"""
    import src.import_source as import_source_module
    from src.ocr_engine import OcrDiagnostics

    monkeypatch.setattr(
        import_source_module, "_last_ocr_diagnostics", OcrDiagnostics(preprocess="original", psm=11, score=0.8)
    )

    image_path = tmp_path / "page_001.png"
    _make_image(image_path)
    ocr_status = {"tesseract_available": True, "tesseract_path": "/usr/bin/tesseract", "languages": ["jpn", "eng"]}

    sink: list = []
    import_source_module._page_from_image(1, image_path, tmp_path / "assets", ocr_status, diagnostics_sink=sink)

    assert len(sink) == 1
    assert sink[0]["page_no"] == 1
    assert sink[0]["preprocess"] == "original"
    assert sink[0]["psm"] == 11


def test_page_from_image_without_sink_does_not_collect_diagnostics(tmp_path):
    """diagnostics_sinkを渡さない場合（既定）は、従来どおり診断情報を収集しない。"""
    import src.import_source as import_source_module

    image_path = tmp_path / "page_001.png"
    _make_image(image_path)
    ocr_status = {"tesseract_available": True, "tesseract_path": "/usr/bin/tesseract", "languages": ["jpn", "eng"]}

    page = import_source_module._page_from_image(1, image_path, tmp_path / "assets", ocr_status)
    assert page["page_no"] == 1
