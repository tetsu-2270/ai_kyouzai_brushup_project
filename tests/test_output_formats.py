import json

from PIL import Image

from src.cli import main


def _make_source_images(source_dir, count=2):
    source_dir.mkdir(parents=True, exist_ok=True)
    for i in range(1, count + 1):
        Image.new("RGB", (80, 120), color=(220, 220, 220)).save(source_dir / f"page_{i:03d}.png")


def _make_source_pdf(pdf_path, page_count=2):
    import fitz

    doc = fitz.open()
    for i in range(page_count):
        page = doc.new_page()
        page.insert_text((72, 72), f"page {i + 1}", fontsize=14)
    doc.save(pdf_path)
    doc.close()


def _make_source_pptx(pptx_path):
    from pptx import Presentation

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = "スライドタイトル"
    prs.save(pptx_path)


def test_build_all_always_writes_editable_lesson_pages_json(tmp_path, monkeypatch):
    """--output-formatの指定に関わらず、editable/lesson_pages.jsonは常に生成される。"""
    source_dir = tmp_path / "source"
    _make_source_images(source_dir)
    output_dir = tmp_path / "output"
    monkeypatch.setattr(
        "sys.argv",
        ["cli", "build-all", "--input", str(source_dir), "--mode", "proofread", "--output-dir", str(output_dir)],
    )
    main()

    editable_path = output_dir / "editable" / "lesson_pages.json"
    assert editable_path.exists()
    data = json.loads(editable_path.read_text(encoding="utf-8"))
    assert len(data["pages"]) == 2
    # Phase 8互換のlesson_pages.json/canva_design.mdはoutput/compat/配下に生成される
    # （editable//canva/と同名のファイルをoutput_dir直下に重複させないため）。
    assert (output_dir / "compat" / "lesson_pages.json").exists()
    assert (output_dir / "compat" / "canva_design.md").exists()


def test_build_all_does_not_duplicate_lesson_pages_json_or_canva_design_md_at_root(tmp_path, monkeypatch):
    """output/lesson_pages.jsonとoutput/canva_design.mdが直下に重複生成されないことを確認する。

    正式な編集対象はoutput/editable/lesson_pages.jsonのみ、正式なCanva指示書は
    output/canva/canva_design.mdのみであり、output_dir直下には同名ファイルを置かない。
    """
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
            "--output-format", "all",
        ],
    )
    main()

    assert not (output_dir / "lesson_pages.json").exists()
    assert not (output_dir / "canva_design.md").exists()
    assert (output_dir / "editable" / "lesson_pages.json").exists()
    assert (output_dir / "canva" / "canva_design.md").exists()
    assert (output_dir / "compat" / "lesson_pages.json").exists()
    assert (output_dir / "compat" / "canva_design.md").exists()


def test_build_all_no_compat_output_flag_skips_compat_directory(tmp_path, monkeypatch):
    """--no-compat-outputを指定すると、output/compat/配下が生成されないことを確認する。

    editable//canva/や、重複の無いbrushup.md等の生成には影響しない。
    """
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
            "--no-compat-output",
        ],
    )
    main()

    assert not (output_dir / "compat").exists()
    assert (output_dir / "editable" / "lesson_pages.json").exists()
    assert (output_dir / "brushup.md").exists()
    assert (output_dir / "brushup.docx").exists()


def test_build_all_default_output_format_resolves_to_image_for_image_input(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    _make_source_images(source_dir)
    output_dir = tmp_path / "output"
    monkeypatch.setattr(
        "sys.argv",
        ["cli", "build-all", "--input", str(source_dir), "--mode", "proofread", "--output-dir", str(output_dir)],
    )
    main()

    assert (output_dir / "rendered" / "page_001.png").exists()
    assert (output_dir / "rendered" / "page_002.png").exists()
    # 明示的にcanva/pptx/docx/mdを要求していないため、それらは生成されない。
    assert not (output_dir / "canva").exists()
    assert not (output_dir / "exports").exists()


def test_build_all_default_output_format_resolves_to_pdf_for_pdf_input(tmp_path, monkeypatch):
    pdf_path = tmp_path / "source.pdf"
    _make_source_pdf(pdf_path)
    output_dir = tmp_path / "output"
    monkeypatch.setattr(
        "sys.argv",
        ["cli", "build-all", "--input", str(pdf_path), "--mode", "proofread", "--output-dir", str(output_dir)],
    )
    main()

    assert (output_dir / "exports" / "material.pdf").exists()
    assert not (output_dir / "rendered").exists()


def test_build_all_default_output_format_resolves_to_pptx_for_pptx_input(tmp_path, monkeypatch):
    pptx_path = tmp_path / "source.pptx"
    _make_source_pptx(pptx_path)
    output_dir = tmp_path / "output"
    monkeypatch.setattr(
        "sys.argv",
        ["cli", "build-all", "--input", str(pptx_path), "--mode", "proofread", "--output-dir", str(output_dir)],
    )
    main()

    assert (output_dir / "exports" / "material.pptx").exists()


def test_build_all_output_format_image_generates_rendered_pages(tmp_path, monkeypatch):
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
            "--output-format", "image",
        ],
    )
    main()

    for i in (1, 2, 3):
        assert (output_dir / "rendered" / f"page_{i:03d}.png").exists()


def test_build_all_output_format_canva_generates_canva_option_output(tmp_path, monkeypatch):
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
            "--output-format", "canva",
        ],
    )
    main()

    canva_path = output_dir / "canva" / "canva_design.md"
    assert canva_path.exists()
    assert "元画像: assets/page_001.png" in canva_path.read_text(encoding="utf-8")
    # canva指定時でも、後方互換のためoutput_dir直下の一式は引き続き生成される
    # （Canva指示書だけが最終成果物になる設計にはしない）。
    assert (output_dir / "brushup.md").exists()
    assert (output_dir / "brushup.docx").exists()


def test_build_all_output_format_json_does_not_create_rendered_or_exports(tmp_path, monkeypatch):
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
            "--output-format", "json",
        ],
    )
    main()

    assert (output_dir / "editable" / "lesson_pages.json").exists()
    assert not (output_dir / "rendered").exists()
    assert not (output_dir / "exports").exists()
    assert not (output_dir / "canva").exists()


def test_build_all_output_format_all_generates_every_format(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    _make_source_images(source_dir, count=2)
    output_dir = tmp_path / "output"
    monkeypatch.setattr(
        "sys.argv",
        [
            "cli", "build-all",
            "--input", str(source_dir),
            "--mode", "proofread",
            "--output-dir", str(output_dir),
            "--output-format", "all",
        ],
    )
    main()

    assert (output_dir / "editable" / "lesson_pages.json").exists()
    assert (output_dir / "rendered" / "page_001.png").exists()
    assert (output_dir / "canva" / "canva_design.md").exists()
    assert (output_dir / "exports" / "material.pdf").exists()
    assert (output_dir / "exports" / "material.pptx").exists()
    assert (output_dir / "exports" / "material.docx").exists()
    assert (output_dir / "exports" / "material.md").exists()


def test_build_all_output_format_pdf_pptx_docx_md_individually(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    _make_source_images(source_dir, count=1)

    for output_format, expected_file in (
        ("pdf", "material.pdf"),
        ("pptx", "material.pptx"),
        ("docx", "material.docx"),
        ("md", "material.md"),
    ):
        output_dir = tmp_path / f"output_{output_format}"
        monkeypatch.setattr(
            "sys.argv",
            [
                "cli", "build-all",
                "--input", str(source_dir),
                "--mode", "proofread",
                "--output-dir", str(output_dir),
                "--output-format", output_format,
            ],
        )
        main()
        assert (output_dir / "exports" / expected_file).exists()


def test_regenerate_from_editable_file_produces_rendered_images(tmp_path, monkeypatch):
    """output/editable/lesson_pages.json を編集した後、再生成コマンドでrendered/を作り直せる。"""
    source_dir = tmp_path / "source"
    _make_source_images(source_dir, count=2)
    output_dir = tmp_path / "output"
    monkeypatch.setattr(
        "sys.argv",
        ["cli", "build-all", "--input", str(source_dir), "--mode", "proofread", "--output-dir", str(output_dir)],
    )
    main()

    editable_path = output_dir / "editable" / "lesson_pages.json"
    data = json.loads(editable_path.read_text(encoding="utf-8"))
    data["pages"][0]["title"] = "編集後のタイトル"
    editable_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    monkeypatch.setattr(
        "sys.argv",
        ["cli", "regenerate", "--input", str(editable_path), "--output-format", "canva"],
    )
    main()

    canva_text = (output_dir / "canva" / "canva_design.md").read_text(encoding="utf-8")
    assert "編集後のタイトル" in canva_text


def test_regenerate_with_explicit_output_dir(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    _make_source_images(source_dir, count=1)
    output_dir = tmp_path / "output"
    monkeypatch.setattr(
        "sys.argv",
        ["cli", "build-all", "--input", str(source_dir), "--mode", "proofread", "--output-dir", str(output_dir)],
    )
    main()

    editable_path = output_dir / "editable" / "lesson_pages.json"
    other_output_dir = tmp_path / "other_output"
    monkeypatch.setattr(
        "sys.argv",
        [
            "cli", "regenerate",
            "--input", str(editable_path),
            "--output-format", "image",
            "--output-dir", str(other_output_dir),
        ],
    )
    main()

    assert (other_output_dir / "rendered" / "page_001.png").exists()


def test_regenerate_works_for_generate_mode_document_without_source_image(tmp_path, monkeypatch):
    """新規構築(generateモード)相当のsource_image無しドキュメントでも、再生成が例外なく成功する。"""
    editable_path = tmp_path / "output" / "editable" / "lesson_pages.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "cli", "lesson-pages",
            "--mode", "generate",
            "--requirements", "examples/requirements_ai_instagram.json",
            "--output", str(editable_path),
        ],
    )
    main()

    monkeypatch.setattr(
        "sys.argv",
        ["cli", "regenerate", "--input", str(editable_path), "--output-format", "all"],
    )
    main()

    output_dir = editable_path.parent.parent
    assert (output_dir / "rendered").exists()
    assert len(list((output_dir / "rendered").glob("page_*.png"))) > 0
    assert (output_dir / "canva" / "canva_design.md").exists()
    canva_text = (output_dir / "canva" / "canva_design.md").read_text(encoding="utf-8")
    assert "元画像:" not in canva_text
    assert "参考画像:" not in canva_text
