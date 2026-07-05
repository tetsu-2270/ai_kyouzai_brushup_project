"""README/docsの主導線が、元資料自動取り込み(build-all)に一本化されていることを確認する。

Phase 8の設計見直しにより「作成者にJSON/Markdown/TXTを手作業で作らせる」運用は不採用となった。
このテストは、その方針がREADME/docsの作成者向け主導線に反映され続けていることを保証する。
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

_PRIMARY_DOCS = [
    REPO_ROOT / "README.md",
    REPO_ROOT / "docs" / "08_user_acceptance_test.md",
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_build_all_is_mentioned_in_primary_docs():
    for path in _PRIMARY_DOCS:
        assert "build-all" in _read(path), f"{path} にbuild-allの案内が見つかりません"


def test_real_material_template_json_no_longer_exists():
    assert not (REPO_ROOT / "examples" / "real_material_template.json").exists()


def test_readme_does_not_instruct_users_to_hand_author_real_material_template():
    text = _read(REPO_ROOT / "README.md")
    assert "real_material_template" not in text


def test_user_acceptance_test_doc_does_not_instruct_hand_authoring_json():
    text = _read(REPO_ROOT / "docs" / "08_user_acceptance_test.md")
    assert "real_material_template" not in text
    # 作成者向けの主導線としてJSONを手作業で「コピーして書き換える」ような案内が残っていないこと。
    assert "コピーして書き換える" not in text


def test_readme_quick_start_uses_input_source_directory():
    text = _read(REPO_ROOT / "README.md")
    assert "input/source" in text


def test_docs_04_documents_import_source_and_source_assets():
    text = _read(REPO_ROOT / "docs" / "04_output_spec.md")
    assert "import-source" in text
    assert "source_assets" in text


def test_docs_03_notes_that_pages_format_is_not_hand_authored_by_users():
    text = _read(REPO_ROOT / "docs" / "03_data_format.md")
    assert "手作業で作る必要はありません" in text


def test_gitignore_excludes_input_and_output_directories():
    gitignore_text = _read(REPO_ROOT / ".gitignore")
    assert "input/" in gitignore_text
    assert "output/" in gitignore_text


def test_release_zip_script_excludes_input_and_output():
    script_text = _read(REPO_ROOT / "scripts" / "make_release_zip.sh")
    assert "input" in script_text
    assert "output" in script_text


def test_no_markdown_doc_in_repo_references_deleted_template():
    """docs/05はPhase 8設計見直しの経緯を記録するために意図的にreal_material_templateへ言及する
    （取り消し線付き・履歴として）。それ以外のMarkdownに参照が残っていないことを確認する。"""
    allowed_historical_record = REPO_ROOT / "docs" / "05_implementation_tasks.md"
    for md_path in REPO_ROOT.rglob("*.md"):
        if ".git" in md_path.parts:
            continue
        if md_path == allowed_historical_record:
            continue
        assert "real_material_template" not in _read(md_path), (
            f"{md_path} に削除済みテンプレートへの参照が残っています"
        )


def test_readme_distinguishes_build_all_from_generate_mode_new_construction():
    """元資料が無い新規構築(generateモード)がbuild-all前提に埋没していないことを確認する。"""
    text = _read(REPO_ROOT / "README.md")
    assert "新規構築" in text
    assert "generate" in text


def test_user_acceptance_test_doc_notes_generate_mode_is_out_of_scope():
    text = _read(REPO_ROOT / "docs" / "08_user_acceptance_test.md")
    assert "generate" in text


# --- Phase 9: output形式選択・editable中間ファイル・画像output・再生成導線 -----------


def test_canva_design_is_not_described_as_the_primary_output():
    """Canva指示書が「主output」であるかのような記述が残っていないことを確認する。

    Phase 9でCanva指示書は数ある完成output形式の一つ(オプション出力)へ位置づけを変更した。
    """
    for path in (REPO_ROOT / "README.md", REPO_ROOT / "docs" / "04_output_spec.md", REPO_ROOT / "docs" / "08_user_acceptance_test.md"):
        text = _read(path)
        assert "主outputではない" in text or "オプション出力" in text, (
            f"{path} にCanva指示書がオプション出力である旨の記述が見つかりません"
        )


def test_editable_lesson_pages_json_is_documented_as_the_edit_target():
    """output/editable/lesson_pages.jsonが再生成用の編集対象として説明されていることを確認する。"""
    for path in (REPO_ROOT / "README.md", REPO_ROOT / "docs" / "04_output_spec.md", REPO_ROOT / "docs" / "08_user_acceptance_test.md"):
        text = _read(path)
        assert "editable/lesson_pages.json" in text
    readme_text = _read(REPO_ROOT / "README.md")
    assert "編集して再生成" in readme_text or "編集する対象" in readme_text or "編集対象" in readme_text


def test_image_output_is_documented_as_an_official_output_format():
    """画像outputが正式なoutput形式として説明されていることを確認する。"""
    for path in (REPO_ROOT / "README.md", REPO_ROOT / "docs" / "04_output_spec.md"):
        text = _read(path)
        assert "output/rendered" in text or "rendered/page" in text


def test_docs_04_documents_output_format_choices():
    text = _read(REPO_ROOT / "docs" / "04_output_spec.md")
    for choice in ("same", "image", "pdf", "pptx", "docx", "md", "canva", "json", "all"):
        assert choice in text, f"docs/04_output_spec.md に--output-formatの選択肢 '{choice}' の記載が見つかりません"


def test_docs_04_documents_regenerate_command():
    text = _read(REPO_ROOT / "docs" / "04_output_spec.md")
    assert "regenerate" in text


# --- Phase 9.1: 同名ファイルの重複解消と後方互換outputの整理 ----------------------


def test_docs_explain_compat_output_directory():
    """正式output(editable//canva/)と後方互換output(compat/)の違いがREADME/docsで説明されていることを確認する。"""
    for path in (REPO_ROOT / "README.md", REPO_ROOT / "docs" / "04_output_spec.md", REPO_ROOT / "docs" / "08_user_acceptance_test.md"):
        text = _read(path)
        assert "output/compat" in text, f"{path} にoutput/compat/の説明が見つかりません"


def test_docs_state_editable_is_the_sole_official_edit_target():
    """output/editable/lesson_pages.jsonのみが正式な編集対象であることが明記されていることを確認する。"""
    for path in (REPO_ROOT / "README.md", REPO_ROOT / "docs" / "04_output_spec.md"):
        text = _read(path)
        assert "編集対象は`output/editable/lesson_pages.json`のみ" in text or "正式な編集対象" in text


def test_docs_state_canva_directory_is_the_sole_official_canva_output():
    """output/canva/canva_design.mdのみが正式なCanva指示書であることが明記されていることを確認する。"""
    for path in (REPO_ROOT / "README.md", REPO_ROOT / "docs" / "04_output_spec.md"):
        text = _read(path)
        assert "正式なCanva指示書は`output/canva/canva_design.md`のみ" in text or "正式なCanva指示書" in text
