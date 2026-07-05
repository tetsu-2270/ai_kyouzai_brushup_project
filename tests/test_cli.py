import json

import pytest

from src.cli import main


def _clear_optional_integration_env(monkeypatch):
    for key in ("CANVA_API_KEY", "WP_URL", "WP_USERNAME", "WP_APP_PASSWORD"):
        monkeypatch.delenv(key, raising=False)


def test_main_generate_writes_output(tmp_path, monkeypatch):
    output_path = tmp_path / "brushup.md"
    monkeypatch.setattr(
        "sys.argv",
        ["cli", "generate", "--input", "examples/sample_pages.json", "--output", str(output_path)],
    )
    main()
    assert "教材ブラッシュアップ設計書" in output_path.read_text(encoding="utf-8")


def test_core_commands_work_without_canva_or_wordpress_credentials(tmp_path, monkeypatch):
    """Canva/WordPressの環境変数が未設定でも、本体機能(必須機能)は正常に動作することを確認する。"""
    _clear_optional_integration_env(monkeypatch)

    brushup_path = tmp_path / "brushup.md"
    canva_design_path = tmp_path / "canva_design.md"
    docx_path = tmp_path / "brushup.docx"
    pdf_path = tmp_path / "brushup.pdf"
    scenario_dir = tmp_path / "scenario_out"

    for argv in (
        ["cli", "generate", "--input", "examples/sample_pages.json", "--output", str(brushup_path)],
        ["cli", "canva", "--input", "examples/sample_pages.json", "--output", str(canva_design_path)],
        ["cli", "docx", "--input", "examples/sample_pages.json", "--output", str(docx_path)],
        ["cli", "pdf", "--input", "examples/sample_pages.json", "--output", str(pdf_path)],
        ["cli", "scenario", "--input", "examples/sample_pages.json", "--output-dir", str(scenario_dir)],
    ):
        monkeypatch.setattr("sys.argv", argv)
        main()

    assert brushup_path.exists()
    assert canva_design_path.exists()
    assert docx_path.exists()
    assert pdf_path.exists()
    for name in ("scenario.json", "scenario.md", "voicevox.txt", "scene.json"):
        assert (scenario_dir / name).exists()


def test_main_canva_writes_output_to_nested_dir(tmp_path, monkeypatch):
    output_path = tmp_path / "nested" / "canva_design.md"
    monkeypatch.setattr(
        "sys.argv",
        ["cli", "canva", "--input", "examples/sample_pages.json", "--output", str(output_path)],
    )
    main()
    assert "Canva AI投入用プロンプト" in output_path.read_text(encoding="utf-8")


def test_main_scenario_writes_four_files(tmp_path, monkeypatch):
    output_dir = tmp_path / "scenario_out"
    monkeypatch.setattr(
        "sys.argv",
        ["cli", "scenario", "--input", "examples/sample_pages.json", "--output-dir", str(output_dir)],
    )
    main()
    for name in ("scenario.json", "scenario.md", "voicevox.txt", "scene.json"):
        assert (output_dir / name).exists()


def test_main_canva_sync_writes_mock_report_without_api_key(tmp_path, monkeypatch):
    monkeypatch.delenv("CANVA_API_KEY", raising=False)
    output_path = tmp_path / "canva_report.json"
    monkeypatch.setattr(
        "sys.argv",
        ["cli", "canva-sync", "--input", "examples/sample_pages.json", "--output", str(output_path)],
    )
    main()
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["mock"] is True
    assert len(report["designs"]) == 2


def test_main_wp_publish_writes_mock_report_without_credentials(tmp_path, monkeypatch):
    for key in ("WP_URL", "WP_USERNAME", "WP_APP_PASSWORD"):
        monkeypatch.delenv(key, raising=False)
    output_path = tmp_path / "wp_report.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "cli", "wp-publish",
            "--input", "examples/sample_pages.json",
            "--output", str(output_path),
            "--categories", "お知らせ",
            "--tags", "まじょこ",
        ],
    )
    main()
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["mock"] is True
    assert report["post_id"] is not None


def test_main_wp_publish_invalid_status_reports_error_without_traceback(tmp_path, monkeypatch, capsys):
    for key in ("WP_URL", "WP_USERNAME", "WP_APP_PASSWORD"):
        monkeypatch.delenv(key, raising=False)
    output_path = tmp_path / "wp_report.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "cli", "wp-publish",
            "--input", "examples/sample_pages.json",
            "--output", str(output_path),
            "--status", "deleted",
        ],
    )
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1
    assert "エラー: statusは" in capsys.readouterr().err
    assert not output_path.exists()


def test_main_canva_sync_accepts_lesson_pages_json_input(tmp_path, monkeypatch):
    monkeypatch.delenv("CANVA_API_KEY", raising=False)
    lesson_pages_path = tmp_path / "lesson_pages.json"
    report_path = tmp_path / "canva_report.json"

    monkeypatch.setattr(
        "sys.argv",
        ["cli", "lesson-pages", "--input", "examples/sample_pages.json", "--output", str(lesson_pages_path)],
    )
    main()

    monkeypatch.setattr(
        "sys.argv",
        ["cli", "canva-sync", "--input", str(lesson_pages_path), "--output", str(report_path)],
    )
    main()

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["mock"] is True
    assert len(report["designs"]) == 2


def test_main_wp_publish_accepts_lesson_pages_json_input(tmp_path, monkeypatch):
    for key in ("WP_URL", "WP_USERNAME", "WP_APP_PASSWORD"):
        monkeypatch.delenv(key, raising=False)
    lesson_pages_path = tmp_path / "lesson_pages.json"
    report_path = tmp_path / "wp_report.json"

    monkeypatch.setattr(
        "sys.argv",
        ["cli", "lesson-pages", "--input", "examples/sample_pages.json", "--output", str(lesson_pages_path)],
    )
    main()

    monkeypatch.setattr(
        "sys.argv",
        ["cli", "wp-publish", "--input", str(lesson_pages_path), "--output", str(report_path)],
    )
    main()

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["mock"] is True
    assert report["post_id"] is not None


def test_main_reports_missing_file_without_traceback(tmp_path, monkeypatch, capsys):
    output_path = tmp_path / "brushup.md"
    monkeypatch.setattr(
        "sys.argv",
        ["cli", "generate", "--input", "no_such.json", "--output", str(output_path)],
    )
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1
    assert "エラー: 入力ファイルが見つかりません" in capsys.readouterr().err
    assert not output_path.exists()
