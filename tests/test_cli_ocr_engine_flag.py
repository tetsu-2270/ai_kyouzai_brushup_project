import json

from PIL import Image

from src import apple_vision_ocr, ocr_comparison
from src.cli import main


def _make_source_images(source_dir, count=2):
    source_dir.mkdir(parents=True, exist_ok=True)
    for i in range(1, count + 1):
        Image.new("RGB", (80, 120), color=(220, 220, 220)).save(source_dir / f"page_{i:03d}.png")


def _availability_unavailable(*args, **kwargs):
    return apple_vision_ocr.AppleVisionAvailability(available=False, reason="テスト環境では利用不可")


def _availability_available(*args, **kwargs):
    return apple_vision_ocr.AppleVisionAvailability(available=True, reason="利用可能", helper_path="/fake/path")


def _fake_vision_matching_tesseract(*args, **kwargs):
    # conftest.pyのdefault_ocr_environment_readyフィクスチャが_try_ocrを固定文字列で
    # モックしているため、Apple Vision側も同じテキストを返せば一致し、needs_reviewにならない。
    return apple_vision_ocr.AppleVisionResult(
        available=True, language="ja-JP", text="テスト用ダミーOCRテキスト（自動テスト環境の既定値）"
    )


def test_build_all_default_ocr_engine_does_not_create_comparison_dir(tmp_path, monkeypatch):
    """--ocr-engineを指定しない（既定tesseract）場合、比較処理は一切実行されず、
    output/ocr_comparison/は生成されない（既存動作を完全に維持する）。"""
    source_dir = tmp_path / "source"
    _make_source_images(source_dir)
    output_dir = tmp_path / "output"

    called = {"n": 0}

    def _should_not_be_called(*args, **kwargs):
        called["n"] += 1
        raise AssertionError("--ocr-engine tesseract（既定）ではApple Visionを呼び出してはいけない")

    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "check_apple_vision_availability", _should_not_be_called)

    monkeypatch.setattr(
        "sys.argv",
        ["cli", "build-all", "--input", str(source_dir), "--mode", "proofread", "--output-dir", str(output_dir)],
    )
    main()

    assert called["n"] == 0
    assert not (output_dir / "ocr_comparison").exists()
    assert (output_dir / "editable" / "lesson_pages.json").exists()


def test_build_all_ocr_engine_tesseract_vision_creates_comparison_outputs(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    _make_source_images(source_dir)
    output_dir = tmp_path / "output"

    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "check_apple_vision_availability", _availability_available)
    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "run_apple_vision_ocr", _fake_vision_matching_tesseract)

    monkeypatch.setattr(
        "sys.argv",
        [
            "cli", "build-all", "--input", str(source_dir), "--mode", "proofread",
            "--output-dir", str(output_dir), "--ocr-engine", "tesseract+vision",
        ],
    )
    main()

    comparison_dir = output_dir / "ocr_comparison"
    assert (comparison_dir / "summary.json").exists()
    assert (comparison_dir / "summary.md").exists()
    assert (comparison_dir / "review.html").exists()

    summary_data = json.loads((comparison_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary_data["total_pages"] == 2
    assert summary_data["vision_helper_available"] is True

    # 通常のlesson_pages.json生成導線は変化しない。
    assert (output_dir / "editable" / "lesson_pages.json").exists()


def test_build_all_ocr_engine_tesseract_vision_does_not_change_editable_lesson_pages(tmp_path, monkeypatch):
    """Apple Vision結果はoutput/editable/lesson_pages.jsonへ自動反映されない。
    tesseract単体実行時とtesseract+vision実行時で、editable/lesson_pages.jsonの内容
    （テキスト由来の部分）が変わらないことを確認する。"""
    source_dir = tmp_path / "source"
    _make_source_images(source_dir)

    def _fake_vision_different_text(*args, **kwargs):
        return apple_vision_ocr.AppleVisionResult(
            available=True, language="ja-JP", text="Apple Visionだけが返す、まったく異なるテキスト"
        )

    output_dir_a = tmp_path / "output_tesseract_only"
    monkeypatch.setattr(
        "sys.argv",
        ["cli", "build-all", "--input", str(source_dir), "--mode", "proofread", "--output-dir", str(output_dir_a)],
    )
    main()

    output_dir_b = tmp_path / "output_tesseract_vision"
    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "check_apple_vision_availability", _availability_available)
    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "run_apple_vision_ocr", _fake_vision_different_text)
    monkeypatch.setattr(
        "sys.argv",
        [
            "cli", "build-all", "--input", str(source_dir), "--mode", "proofread",
            "--output-dir", str(output_dir_b), "--ocr-engine", "tesseract+vision",
        ],
    )
    main()

    lesson_a = json.loads((output_dir_a / "editable" / "lesson_pages.json").read_text(encoding="utf-8"))
    lesson_b = json.loads((output_dir_b / "editable" / "lesson_pages.json").read_text(encoding="utf-8"))
    bodies_a = [p["body"] for p in lesson_a["pages"]]
    bodies_b = [p["body"] for p in lesson_b["pages"]]
    assert bodies_a == bodies_b
    assert "Apple Visionだけが返す" not in json.dumps(lesson_b, ensure_ascii=False)


def test_build_all_ocr_engine_tesseract_vision_falls_back_when_vision_unavailable(tmp_path, monkeypatch):
    """Apple Visionが使えない環境でも--ocr-engine tesseract+visionはエラーにならず、
    比較結果（vision_helper_available: false）を記録したうえで正常終了する。"""
    source_dir = tmp_path / "source"
    _make_source_images(source_dir)
    output_dir = tmp_path / "output"

    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "check_apple_vision_availability", _availability_unavailable)

    monkeypatch.setattr(
        "sys.argv",
        [
            "cli", "build-all", "--input", str(source_dir), "--mode", "proofread",
            "--output-dir", str(output_dir), "--ocr-engine", "tesseract+vision",
        ],
    )
    main()

    summary_data = json.loads((output_dir / "ocr_comparison" / "summary.json").read_text(encoding="utf-8"))
    assert summary_data["vision_helper_available"] is False
    assert summary_data["needs_review_pages"] == []
    assert (output_dir / "editable" / "lesson_pages.json").exists()


# --- Phase 10.10: Claude Codeレビュー指示書の自動生成 --------------------------------------------


def test_build_all_ocr_engine_tesseract_vision_generates_claude_review_instructions(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    _make_source_images(source_dir)
    output_dir = tmp_path / "output"

    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "check_apple_vision_availability", _availability_available)
    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "run_apple_vision_ocr", _fake_vision_matching_tesseract)

    monkeypatch.setattr(
        "sys.argv",
        [
            "cli", "build-all", "--input", str(source_dir), "--mode", "proofread",
            "--output-dir", str(output_dir), "--ocr-engine", "tesseract+vision",
        ],
    )
    main()

    comparison_dir = output_dir / "ocr_comparison"
    assert (comparison_dir / "CLAUDE_OCR_REVIEW.md").exists()
    assert (comparison_dir / "claude_review" / "README.md").exists()
    # build-all時点ではREADME以外(pages/・progress.json・candidates.json等)は生成されない。
    claude_review_entries = {p.name for p in (comparison_dir / "claude_review").iterdir()}
    assert claude_review_entries == {"README.md"}
    # 既存の比較出力一覧(summary.json/summary.md/review.html)は引き続き生成される。
    assert (comparison_dir / "summary.json").exists()
    assert (comparison_dir / "summary.md").exists()
    assert (comparison_dir / "review.html").exists()


def test_build_all_default_ocr_engine_does_not_generate_claude_review_instructions(tmp_path, monkeypatch):
    """--ocr-engineを指定しない（既定tesseract）場合、Claude Codeレビュー指示書は生成されない。"""
    source_dir = tmp_path / "source"
    _make_source_images(source_dir)
    output_dir = tmp_path / "output"

    monkeypatch.setattr(
        "sys.argv",
        ["cli", "build-all", "--input", str(source_dir), "--mode", "proofread", "--output-dir", str(output_dir)],
    )
    main()

    assert not (output_dir / "ocr_comparison").exists()


def test_build_all_ocr_engine_tesseract_vision_prints_fixed_copyable_instruction(tmp_path, monkeypatch, capsys):
    source_dir = tmp_path / "source"
    _make_source_images(source_dir)
    output_dir = tmp_path / "output"

    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "check_apple_vision_availability", _availability_available)
    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "run_apple_vision_ocr", _fake_vision_matching_tesseract)

    monkeypatch.setattr(
        "sys.argv",
        [
            "cli", "build-all", "--input", str(source_dir), "--mode", "proofread",
            "--output-dir", str(output_dir), "--ocr-engine", "tesseract+vision",
        ],
    )
    main()

    captured = capsys.readouterr()
    assert "CLAUDE_OCR_REVIEW" in captured.out
    # --output-dirへ絶対パス(tmp_path配下)を渡した場合でも、標準出力へ絶対パスは表示されない
    # （安全側のフォールバックでディレクトリ名のみを使う）。
    assert str(tmp_path) not in captured.out
    assert "ocr_comparison/CLAUDE_OCR_REVIEW.md" in captured.out
    assert "を読み、記載された手順を最後まで実行してください。" in captured.out


def test_build_all_ocr_engine_tesseract_vision_does_not_claim_review_when_vision_unavailable(
    tmp_path, monkeypatch, capsys
):
    source_dir = tmp_path / "source"
    _make_source_images(source_dir)
    output_dir = tmp_path / "output"

    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "check_apple_vision_availability", _availability_unavailable)

    monkeypatch.setattr(
        "sys.argv",
        [
            "cli", "build-all", "--input", str(source_dir), "--mode", "proofread",
            "--output-dir", str(output_dir), "--ocr-engine", "tesseract+vision",
        ],
    )
    main()

    captured = capsys.readouterr()
    assert "生成されませんでした" in captured.out
    assert "理由" in captured.out
    assert "再実行方法" in captured.out
    # 「Claude Codeへ次の1文を渡してください」という誤った次ステップ案内を表示しない。
    assert "次の1文を渡してください" not in captured.out
    assert not (output_dir / "ocr_comparison" / "CLAUDE_OCR_REVIEW.md").exists()


def test_build_all_ocr_engine_tesseract_vision_keeps_phase10_9_review_ui_intact(tmp_path, monkeypatch):
    """Phase 10.9で追加した確定テキスト編集UI（review.html）が、Phase 10.10の追加によって
    壊れていないことを確認する。"""
    source_dir = tmp_path / "source"
    _make_source_images(source_dir)
    output_dir = tmp_path / "output"

    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "check_apple_vision_availability", _availability_available)
    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "run_apple_vision_ocr", _fake_vision_matching_tesseract)

    monkeypatch.setattr(
        "sys.argv",
        [
            "cli", "build-all", "--input", str(source_dir), "--mode", "proofread",
            "--output-dir", str(output_dir), "--ocr-engine", "tesseract+vision",
        ],
    )
    main()

    review_html = (output_dir / "ocr_comparison" / "review.html").read_text(encoding="utf-8")
    assert "diff-legend" in review_html
    assert "compare-grid" in review_html
    assert 'id="ocr-review-export-btn"' in review_html
    assert 'id="ocr-review-reset-btn"' in review_html
    assert "<textarea" in review_html


def test_build_all_ocr_engine_tesseract_vision_claude_review_files_do_not_affect_editable(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    _make_source_images(source_dir)
    output_dir = tmp_path / "output"

    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "check_apple_vision_availability", _availability_available)
    monkeypatch.setattr(ocr_comparison.apple_vision_ocr, "run_apple_vision_ocr", _fake_vision_matching_tesseract)

    monkeypatch.setattr(
        "sys.argv",
        [
            "cli", "build-all", "--input", str(source_dir), "--mode", "proofread",
            "--output-dir", str(output_dir), "--ocr-engine", "tesseract+vision",
        ],
    )
    main()

    lesson = json.loads((output_dir / "editable" / "lesson_pages.json").read_text(encoding="utf-8"))
    assert "CLAUDE_OCR_REVIEW" not in json.dumps(lesson, ensure_ascii=False)
