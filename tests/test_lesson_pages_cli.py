import json

from src.cli import main


def test_cli_lesson_pages_proofread_mode(tmp_path, monkeypatch):
    output_path = tmp_path / "lesson_pages.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "cli", "lesson-pages",
            "--mode", "proofread",
            "--input", "examples/sample_pages.json",
            "--output", str(output_path),
        ],
    )
    main()

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["metadata"]["mode"] == "proofread"


def test_cli_lesson_pages_restructure_mode(tmp_path, monkeypatch):
    output_path = tmp_path / "lesson_pages.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "cli", "lesson-pages",
            "--mode", "restructure",
            "--input", "examples/sample_pages.json",
            "--requirements", "examples/requirements_ai_instagram.json",
            "--output", str(output_path),
        ],
    )
    main()

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["metadata"]["mode"] == "restructure"
    assert all("source_page_no" in page for page in data["pages"])
    assert data["pages"][0]["role"] == "intro"
    assert data["pages"][-1]["role"] == "summary"


def test_cli_lesson_pages_restructure_writes_plan_output(tmp_path, monkeypatch):
    output_path = tmp_path / "lesson_pages.json"
    plan_output_path = tmp_path / "restructure_plan.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "cli", "lesson-pages",
            "--mode", "restructure",
            "--input", "examples/sample_pages.json",
            "--output", str(output_path),
            "--plan-output", str(plan_output_path),
        ],
    )
    main()

    plan = json.loads(plan_output_path.read_text(encoding="utf-8"))
    assert plan["mode"] == "restructure"
    assert len(plan["pages"]) > 0


def test_cli_lesson_pages_plan_output_ignored_for_proofread(tmp_path, monkeypatch):
    output_path = tmp_path / "lesson_pages.json"
    plan_output_path = tmp_path / "restructure_plan.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "cli", "lesson-pages",
            "--mode", "proofread",
            "--input", "examples/sample_pages.json",
            "--output", str(output_path),
            "--plan-output", str(plan_output_path),
        ],
    )
    main()

    assert output_path.exists()
    assert not plan_output_path.exists()


def test_cli_review_report_lists_role_and_source_page_no(tmp_path, monkeypatch):
    lesson_pages_path = tmp_path / "lesson_pages.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "cli", "lesson-pages",
            "--mode", "restructure",
            "--input", "examples/sample_pages.json",
            "--output", str(lesson_pages_path),
        ],
    )
    main()

    report_path = tmp_path / "review_report.md"
    monkeypatch.setattr(
        "sys.argv",
        ["cli", "review-report", "--input", str(lesson_pages_path), "--output", str(report_path)],
    )
    main()

    report_text = report_path.read_text(encoding="utf-8")
    assert "role:" in report_text
    assert "source_page_no:" in report_text


def test_cli_lesson_pages_generate_mode(tmp_path, monkeypatch):
    output_path = tmp_path / "lesson_pages.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "cli", "lesson-pages",
            "--mode", "generate",
            "--requirements", "examples/requirements_ai_instagram.json",
            "--output", str(output_path),
        ],
    )
    main()

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["metadata"]["mode"] == "generate"
    assert len(data["pages"]) > 0


def test_cli_generate_mode_full_pipeline_succeeds_without_source_material(tmp_path, monkeypatch):
    """新規構築(generateモード)は元資料が無い前提のフロー。Phase 8のimport-source/source_image/
    source_assets追加後も、元資料無し・source_image/source_assets空のまま全出力が生成できることを確認する。"""
    lesson_pages_path = tmp_path / "lesson_pages.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "cli", "lesson-pages",
            "--mode", "generate",
            "--requirements", "examples/requirements_ai_instagram.json",
            "--output", str(lesson_pages_path),
        ],
    )
    main()

    data = json.loads(lesson_pages_path.read_text(encoding="utf-8"))
    assert all(page["source_image"] == "" for page in data["pages"])
    assert all(page["source_page_no"] == [] for page in data["pages"])

    brushup_path = tmp_path / "brushup.md"
    canva_path = tmp_path / "canva_design.md"
    docx_path = tmp_path / "brushup.docx"
    pdf_path = tmp_path / "brushup.pdf"
    scenario_dir = tmp_path / "scenario"
    review_path = tmp_path / "review_report.md"

    for argv in (
        ["cli", "generate", "--input", str(lesson_pages_path), "--output", str(brushup_path)],
        ["cli", "canva", "--input", str(lesson_pages_path), "--output", str(canva_path)],
        ["cli", "docx", "--input", str(lesson_pages_path), "--output", str(docx_path)],
        ["cli", "pdf", "--input", str(lesson_pages_path), "--output", str(pdf_path)],
        ["cli", "scenario", "--input", str(lesson_pages_path), "--output-dir", str(scenario_dir)],
        ["cli", "review-report", "--input", str(lesson_pages_path), "--output", str(review_path)],
    ):
        monkeypatch.setattr("sys.argv", argv)
        main()

    assert brushup_path.exists()
    assert docx_path.exists()
    assert pdf_path.exists()
    assert review_path.exists()
    for name in ("scenario.json", "scenario.md", "voicevox.txt", "scene.json"):
        assert (scenario_dir / name).exists()

    # 元画像が無いため、canva_design.mdに「元画像:」/「参考画像:」行が出ないことを確認する。
    canva_text = canva_path.read_text(encoding="utf-8")
    assert "元画像:" not in canva_text
    assert "参考画像:" not in canva_text


def test_cli_lesson_pages_then_derived_outputs_from_restructured_document(tmp_path, monkeypatch):
    lesson_pages_path = tmp_path / "lesson_pages.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "cli", "lesson-pages",
            "--mode", "restructure",
            "--input", "examples/sample_pages.json",
            "--requirements", "examples/requirements_ai_instagram.json",
            "--output", str(lesson_pages_path),
        ],
    )
    main()

    brushup_path = tmp_path / "brushup.md"
    monkeypatch.setattr(
        "sys.argv",
        ["cli", "generate", "--input", str(lesson_pages_path), "--output", str(brushup_path)],
    )
    main()

    assert brushup_path.exists()


def test_cli_restructure_then_all_derived_outputs_succeed(tmp_path, monkeypatch):
    """restructureモードの出力からDOCX/PDF/brushup.md/canva_design.md/scenarioの生成が
    引き続き成功することを確認する（scenario出力・practice/summary本文の修正後の回帰確認）。"""
    lesson_pages_path = tmp_path / "lesson_pages.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "cli", "lesson-pages",
            "--mode", "restructure",
            "--input", "examples/sample_pages.json",
            "--output", str(lesson_pages_path),
        ],
    )
    main()

    brushup_path = tmp_path / "brushup.md"
    canva_path = tmp_path / "canva_design.md"
    docx_path = tmp_path / "brushup.docx"
    pdf_path = tmp_path / "brushup.pdf"
    scenario_dir = tmp_path / "scenario"

    for argv in (
        ["cli", "generate", "--input", str(lesson_pages_path), "--output", str(brushup_path)],
        ["cli", "canva", "--input", str(lesson_pages_path), "--output", str(canva_path)],
        ["cli", "docx", "--input", str(lesson_pages_path), "--output", str(docx_path)],
        ["cli", "pdf", "--input", str(lesson_pages_path), "--output", str(pdf_path)],
        ["cli", "scenario", "--input", str(lesson_pages_path), "--output-dir", str(scenario_dir)],
    ):
        monkeypatch.setattr("sys.argv", argv)
        main()

    assert brushup_path.exists()
    assert canva_path.exists()
    assert docx_path.exists()
    assert pdf_path.exists()
    for name in ("scenario.json", "scenario.md", "voicevox.txt", "scene.json"):
        assert (scenario_dir / name).exists()
