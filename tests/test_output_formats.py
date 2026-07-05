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
    """--no-compat-outputを指定すると、output/compat/配下(lesson_pages.json/canva_design.md/
    brushup.md/brushup.docx/brushup.pdf)が一切生成されないことを確認する。

    editable//canva/の生成には影響しない。
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
    assert not (output_dir / "brushup.md").exists()
    assert not (output_dir / "brushup.docx").exists()
    assert not (output_dir / "brushup.pdf").exists()
    assert (output_dir / "editable" / "lesson_pages.json").exists()


def test_build_all_does_not_duplicate_brushup_role_at_root(tmp_path, monkeypatch):
    """brushup.*(md/docx/pdf)がoutput_dir直下に生成されず、正式outputはexports/、
    後方互換outputはcompat/に整理されていることを確認する（Phase 9.2）。
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

    # output_dir直下にはbrushup.*を置かない。
    assert not (output_dir / "brushup.md").exists()
    assert not (output_dir / "brushup.docx").exists()
    assert not (output_dir / "brushup.pdf").exists()

    # 正式な完成outputはexports/にある。
    assert (output_dir / "exports" / "material.md").exists()
    assert (output_dir / "exports" / "material.docx").exists()
    assert (output_dir / "exports" / "material.pdf").exists()

    # 後方互換outputはcompat/にまとめられる（既定で生成）。
    assert (output_dir / "compat" / "brushup.md").exists()
    assert (output_dir / "compat" / "brushup.docx").exists()
    assert (output_dir / "compat" / "brushup.pdf").exists()

    # Phase 9.1で整理済みのcompat/lesson_pages.json・canva_design.mdの扱いは変わらない。
    assert (output_dir / "compat" / "lesson_pages.json").exists()
    assert (output_dir / "compat" / "canva_design.md").exists()
    assert (output_dir / "editable" / "lesson_pages.json").exists()
    assert (output_dir / "canva" / "canva_design.md").exists()


def test_build_all_no_compat_output_skips_brushup_compat_files(tmp_path, monkeypatch):
    """--no-compat-output指定時は、compat/brushup.*が一切生成されないことを確認する。"""
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
            "--no-compat-output",
        ],
    )
    main()

    assert not (output_dir / "compat").exists()
    assert not (output_dir / "brushup.md").exists()
    assert not (output_dir / "brushup.docx").exists()
    assert not (output_dir / "brushup.pdf").exists()
    # 正式outputは--no-compat-outputの影響を受けない。
    assert (output_dir / "exports" / "material.md").exists()
    assert (output_dir / "editable" / "lesson_pages.json").exists()
    assert (output_dir / "canva" / "canva_design.md").exists()


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
    # canva指定時でも、後方互換のためcompat/配下の一式は引き続き生成される
    # （Canva指示書だけが最終成果物になる設計にはしない）。output_dir直下には生成しない。
    assert (output_dir / "compat" / "brushup.md").exists()
    assert (output_dir / "compat" / "brushup.docx").exists()
    assert not (output_dir / "brushup.md").exists()
    assert not (output_dir / "brushup.docx").exists()


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


# --- Phase 10: --font-path / フォント未検出警告 ----------------------------------


def test_build_all_accepts_font_path_option(tmp_path, monkeypatch):
    """build-all --font-path が受け付けられ、指定フォントで画像outputが生成されることを確認する。"""
    from src.image_renderer import resolve_font_path

    font_path = resolve_font_path(None)
    if font_path is None:
        return  # 実行環境に日本語フォントが無い場合はスキップ相当

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
            "--output-format", "image",
            "--font-path", font_path,
        ],
    )
    main()

    assert (output_dir / "rendered" / "page_001.png").exists()


def test_build_all_font_path_reaches_image_renderer(tmp_path, monkeypatch):
    """--font-pathで指定したパスが実際にimage_rendererへ渡ることを確認する（呼び出し引数を検証）。"""
    import src.cli as cli_module

    captured = {}
    original = cli_module.render_document_images

    def _spy(document, output_dir, rendered_dir, font_path=None):
        captured["font_path"] = font_path
        return original(document, output_dir, rendered_dir, font_path=font_path)

    monkeypatch.setattr(cli_module, "render_document_images", _spy)

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
            "--output-format", "image",
            "--font-path", "/dummy/font/path.ttc",
        ],
    )
    try:
        main()
    except SystemExit:
        pass  # 存在しないダミーパスなのでエラー終了するが、渡された引数の検証が目的
    assert captured.get("font_path") == "/dummy/font/path.ttc"


def test_build_all_invalid_font_path_raises_clear_error(tmp_path, monkeypatch, capsys):
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
            "--output-format", "image",
            "--font-path", "/no/such/font.ttc",
        ],
    )
    try:
        main()
        assert False, "SystemExitが発生するはず"
    except SystemExit as e:
        assert e.code == 1
    captured = capsys.readouterr()
    assert "見つかりません" in captured.err


def test_regenerate_accepts_font_path_option(tmp_path, monkeypatch):
    """regenerate --font-path が受け付けられ、指定フォントで画像outputが再生成されることを確認する。"""
    from src.image_renderer import resolve_font_path

    font_path = resolve_font_path(None)
    if font_path is None:
        return  # 実行環境に日本語フォントが無い場合はスキップ相当

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
        [
            "cli", "regenerate",
            "--input", str(editable_path),
            "--output-format", "image",
            "--font-path", font_path,
        ],
    )
    main()

    output_dir = editable_path.parent.parent
    assert len(list((output_dir / "rendered").glob("page_*.png"))) > 0


def test_build_all_warns_when_synthesizing_text_without_japanese_font(tmp_path, monkeypatch, capsys):
    """source_imageが無いページの画像合成が必要なのに日本語フォントが無い場合、警告が出ることを確認する。"""
    import src.image_renderer as image_renderer_module

    monkeypatch.setattr(image_renderer_module, "_JAPANESE_FONT_CANDIDATES", ())

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
        ["cli", "regenerate", "--input", str(editable_path), "--output-format", "image"],
    )
    main()

    captured = capsys.readouterr()
    assert "WARNING" in captured.err
    # 警告が出ても画像自体は生成され、処理が継続していることを確認する。
    output_dir = editable_path.parent.parent
    assert len(list((output_dir / "rendered").glob("page_*.png"))) > 0
