import json

from PIL import Image

from src.cli import main


def _make_source_images(source_dir, count=3):
    source_dir.mkdir(parents=True, exist_ok=True)
    for i in range(1, count + 1):
        Image.new("RGB", (80, 120), color=(220, 220, 220)).save(source_dir / f"page_{i:03d}.png")


def test_cli_import_source_generates_imported_pages_json(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    _make_source_images(source_dir, count=2)

    output_path = tmp_path / "imported_pages.json"
    monkeypatch.setattr(
        "sys.argv",
        ["cli", "import-source", "--input", str(source_dir), "--output", str(output_path)],
    )
    main()

    assert output_path.exists()
    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert len(data["pages"]) == 2
    assert data["pages"][0]["source_image"] == "assets/page_001.png"

    assets_dir = output_path.parent / "assets"
    assert (assets_dir / "page_001.png").exists()
    assert (assets_dir / "page_002.png").exists()


def test_cli_import_source_then_lesson_pages_proofread(tmp_path, monkeypatch):
    """import-sourceの出力を、そのままlesson-pagesの--inputに渡せることを確認する。"""
    source_dir = tmp_path / "source"
    _make_source_images(source_dir, count=2)

    imported_path = tmp_path / "imported_pages.json"
    monkeypatch.setattr(
        "sys.argv",
        ["cli", "import-source", "--input", str(source_dir), "--output", str(imported_path)],
    )
    main()

    lesson_pages_path = tmp_path / "lesson_pages.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "cli", "lesson-pages",
            "--mode", "proofread",
            "--input", str(imported_path),
            "--output", str(lesson_pages_path),
        ],
    )
    main()

    data = json.loads(lesson_pages_path.read_text(encoding="utf-8"))
    assert data["metadata"]["mode"] == "proofread"
    assert [page["page_no"] for page in data["pages"]] == [1, 2]
    assert data["pages"][0]["source_image"] == "assets/page_001.png"


def test_cli_build_all_proofread_generates_full_output_set(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    _make_source_images(source_dir, count=3)

    output_dir = tmp_path / "output"
    monkeypatch.setattr(
        "sys.argv",
        [
            "cli", "build-all",
            "--input", str(source_dir),
            "--mode", "proofread",
            "--output-dir", str(output_dir),
        ],
    )
    main()

    assert (output_dir / "imported_pages.json").exists()
    assert (output_dir / "lesson_pages.json").exists()
    assert (output_dir / "assets" / "page_001.png").exists()
    assert (output_dir / "assets" / "page_002.png").exists()
    assert (output_dir / "assets" / "page_003.png").exists()
    assert (output_dir / "brushup.md").exists()
    assert (output_dir / "canva_design.md").exists()
    assert (output_dir / "brushup.docx").exists()
    assert (output_dir / "brushup.pdf").exists()
    assert (output_dir / "review_report.md").exists()
    for name in ("scenario.json", "scenario.md", "voicevox.txt", "scene.json"):
        assert (output_dir / "scenario" / name).exists()


def test_cli_build_all_proofread_preserves_page_order_and_count(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    _make_source_images(source_dir, count=3)

    output_dir = tmp_path / "output"
    monkeypatch.setattr(
        "sys.argv",
        [
            "cli", "build-all",
            "--input", str(source_dir),
            "--mode", "proofread",
            "--output-dir", str(output_dir),
        ],
    )
    main()

    data = json.loads((output_dir / "lesson_pages.json").read_text(encoding="utf-8"))
    assert [page["page_no"] for page in data["pages"]] == [1, 2, 3]
    assert [page["source_page_no"] for page in data["pages"]] == [[1], [2], [3]]


def test_cli_build_all_restructure_keeps_source_page_no(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    _make_source_images(source_dir, count=3)

    output_dir = tmp_path / "output"
    monkeypatch.setattr(
        "sys.argv",
        [
            "cli", "build-all",
            "--input", str(source_dir),
            "--mode", "restructure",
            "--output-dir", str(output_dir),
        ],
    )
    main()

    data = json.loads((output_dir / "lesson_pages.json").read_text(encoding="utf-8"))
    assert data["metadata"]["mode"] == "restructure"
    assert all("source_page_no" in page for page in data["pages"])
    all_source_nos = sorted({no for page in data["pages"] for no in page["source_page_no"]})
    assert all_source_nos == [1, 2, 3]


def test_cli_build_all_canva_design_shows_source_image(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    _make_source_images(source_dir, count=1)

    output_dir = tmp_path / "output"
    monkeypatch.setattr(
        "sys.argv",
        [
            "cli", "build-all",
            "--input", str(source_dir),
            "--mode", "proofread",
            "--output-dir", str(output_dir),
        ],
    )
    main()

    canva_text = (output_dir / "canva_design.md").read_text(encoding="utf-8")
    assert "元画像: assets/page_001.png" in canva_text


def test_cli_build_all_restructure_with_requirements(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    _make_source_images(source_dir, count=2)

    output_dir = tmp_path / "output"
    monkeypatch.setattr(
        "sys.argv",
        [
            "cli", "build-all",
            "--input", str(source_dir),
            "--mode", "restructure",
            "--requirements", "examples/requirements_ai_instagram.json",
            "--output-dir", str(output_dir),
        ],
    )
    main()

    data = json.loads((output_dir / "lesson_pages.json").read_text(encoding="utf-8"))
    assert data["metadata"]["mode"] == "restructure"
    assert (output_dir / "brushup.md").exists()


def test_build_all_and_individual_commands_coexist_in_same_session(tmp_path, monkeypatch):
    """build-all導線（元資料あり）と個別CLI導線（examples/sample_pages.json直接指定）が
    同一プロセス内で互いに干渉せず両立することを確認する。"""
    # 1. build-all導線: 元資料(画像)からの一括生成
    source_dir = tmp_path / "source"
    _make_source_images(source_dir, count=2)
    build_all_output = tmp_path / "build_all_output"
    monkeypatch.setattr(
        "sys.argv",
        [
            "cli", "build-all",
            "--input", str(source_dir),
            "--mode", "proofread",
            "--output-dir", str(build_all_output),
        ],
    )
    main()
    assert (build_all_output / "lesson_pages.json").exists()
    assert (build_all_output / "assets" / "page_001.png").exists()

    # 2. 個別CLI導線: examples/sample_pages.json（pages形式・開発者向けサンプル）を直接指定
    individual_lesson_pages = tmp_path / "individual_lesson_pages.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "cli", "lesson-pages",
            "--mode", "proofread",
            "--input", "examples/sample_pages.json",
            "--output", str(individual_lesson_pages),
        ],
    )
    main()
    individual_canva = tmp_path / "individual_canva_design.md"
    monkeypatch.setattr(
        "sys.argv",
        ["cli", "canva", "--input", str(individual_lesson_pages), "--output", str(individual_canva)],
    )
    main()

    # 個別CLI導線側の結果が、build-all導線側の出力の影響を受けていないことを確認する。
    individual_data = json.loads(individual_lesson_pages.read_text(encoding="utf-8"))
    assert individual_data["pages"][0]["source_image"] == "page_01.png"
    assert "元画像: page_01.png" in individual_canva.read_text(encoding="utf-8")

    # build-all導線側の出力も、後続の個別CLI実行によって書き換わっていないことを確認する。
    build_all_data = json.loads((build_all_output / "lesson_pages.json").read_text(encoding="utf-8"))
    assert build_all_data["pages"][0]["source_image"] == "assets/page_001.png"
