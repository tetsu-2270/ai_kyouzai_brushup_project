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


# --- Phase 9.2: brushup系outputとexports系outputの役割重複整理 --------------------


def test_docs_state_exports_is_the_sole_official_completed_output_location():
    """正式な完成output(Markdown/DOCX/PDF/PPTX)はoutput/exports/のみであることが明記されていることを確認する。"""
    for path in (REPO_ROOT / "README.md", REPO_ROOT / "docs" / "04_output_spec.md", REPO_ROOT / "docs" / "08_user_acceptance_test.md"):
        text = _read(path)
        assert "output/exports/material" in text
    combined = _read(REPO_ROOT / "docs" / "04_output_spec.md") + _read(REPO_ROOT / "README.md")
    assert "正式な完成output" in combined


def test_docs_state_brushup_files_are_compat_only_and_not_referenced_for_new_use():
    """brushup.*が後方互換専用であり、新規利用では参照しないことが明記されていることを確認する。"""
    for path in (REPO_ROOT / "docs" / "04_output_spec.md", REPO_ROOT / "docs" / "08_user_acceptance_test.md"):
        text = _read(path)
        assert "compat/brushup" in text or "compat`配下" in text or "compat/`配下" in text


def test_docs_do_not_claim_brushup_is_generated_at_output_root_by_build_all():
    """build-allの出力としてbrushup.*がoutput_dir直下に生成される、という古い記述が残っていないことを確認する。"""
    text = _read(REPO_ROOT / "docs" / "08_user_acceptance_test.md")
    assert "brushup.md`・`brushup.docx`・`brushup.pdf` | 同名重複が無いため引き続き" not in text


# --- 共通設計ルールの明文化（Phase 9.2完了後） -----------------------------------


def test_claude_rules_documents_common_design_rules():
    """CLAUDE_RULES.mdにプロジェクト共通設計ルール（output構成/editable/source情報）が
    明記されていることを確認する。"""
    text = _read(REPO_ROOT / "CLAUDE_RULES.md")
    assert "プロジェクト設計ルール" in text
    assert "output/editable/lesson_pages.json" in text
    assert "source_page_no" in text
    assert "output/compat/" in text or "compat/" in text


def test_docs_04_has_canonical_standard_output_structure_section():
    """docs/04_output_spec.mdに、共通設計ルールの正となる「プロジェクト標準output構成」節が
    存在することを確認する。"""
    text = _read(REPO_ROOT / "docs" / "04_output_spec.md")
    assert "プロジェクト標準output構成" in text


def test_docs_02_and_docs_readme_point_to_common_design_rules():
    """docs/02_architecture.md・docs/README.mdから共通設計ルールへの参照があることを確認する。"""
    for path in (REPO_ROOT / "docs" / "02_architecture.md", REPO_ROOT / "docs" / "README.md"):
        text = _read(path)
        assert "プロジェクト標準output構成" in text or "プロジェクト設計ルール" in text


def test_claude_rules_provides_short_reference_wording_for_future_phases():
    """今後のPhase指示文で使える短い参照文言がCLAUDE_RULES.mdに含まれていることを確認する。"""
    text = _read(REPO_ROOT / "CLAUDE_RULES.md")
    assert "今後のPhase指示文" in text


# --- Phase 10: 画像output品質・日本語フォント・再生成編集ガイドの改善 ------------------


def test_editable_regenerate_guide_exists_and_is_indexed():
    """docs/09_editable_regenerate_guide.mdが存在し、docs/README.mdから参照されていることを確認する。"""
    guide_path = REPO_ROOT / "docs" / "09_editable_regenerate_guide.md"
    assert guide_path.exists()
    docs_readme_text = _read(REPO_ROOT / "docs" / "README.md")
    assert "09_editable_regenerate_guide.md" in docs_readme_text


def test_editable_regenerate_guide_lists_editable_and_non_editable_fields():
    text = _read(REPO_ROOT / "docs" / "09_editable_regenerate_guide.md")
    for editable_field in ("title", "summary", "body", "layout_instruction", "notes"):
        assert f"`{editable_field}`" in text
    for non_editable_field in ("source_page_no", "source_image", "source_assets"):
        assert f"`{non_editable_field}`" in text


def test_docs_explain_not_editing_completed_outputs_directly():
    """完成画像・PDFを直接編集せず、editable/lesson_pages.jsonを編集して再生成する方針が
    README/docs/09に明記されていることを確認する。"""
    for path in (REPO_ROOT / "README.md", REPO_ROOT / "docs" / "09_editable_regenerate_guide.md"):
        text = _read(path)
        assert "直接編集" in text


def test_docs_provide_font_path_usage_examples():
    """--font-pathの使用例がREADME/docs/04/08/09に含まれていることを確認する。"""
    for path in (
        REPO_ROOT / "README.md",
        REPO_ROOT / "docs" / "04_output_spec.md",
        REPO_ROOT / "docs" / "08_user_acceptance_test.md",
        REPO_ROOT / "docs" / "09_editable_regenerate_guide.md",
    ):
        text = _read(path)
        assert "--font-path" in text


def test_docs_explain_missing_japanese_font_warning():
    """日本語フォントが見つからない場合の警告についてREADME/docs/04/08/09で説明されていることを確認する。"""
    for path in (
        REPO_ROOT / "docs" / "04_output_spec.md",
        REPO_ROOT / "docs" / "08_user_acceptance_test.md",
        REPO_ROOT / "docs" / "09_editable_regenerate_guide.md",
    ):
        text = _read(path)
        assert "WARNING" in text or "文字化け" in text


def test_docs_04_documents_font_resolution_functions():
    text = _read(REPO_ROOT / "docs" / "04_output_spec.md")
    assert "resolve_font_path" in text


# --- Phase 10.1: OCR前提ソフトウェアの事前チェック・PATH診断 -------------------------


def test_docs_document_check_ocr_command_and_scripts():
    """check-ocrコマンド・診断スクリプトの使い方がREADME/docs/04/08に記載されていることを確認する。"""
    for path in (
        REPO_ROOT / "README.md",
        REPO_ROOT / "docs" / "04_output_spec.md",
        REPO_ROOT / "docs" / "08_user_acceptance_test.md",
    ):
        text = _read(path)
        assert "check-ocr" in text


def test_docs_explain_tesseract_and_japanese_language_data_requirement():
    """Tesseract本体・日本語言語データ(jpn)が必要である旨がREADME/docs/08に明記されていることを確認する。"""
    for path in (REPO_ROOT / "README.md", REPO_ROOT / "docs" / "08_user_acceptance_test.md"):
        text = _read(path)
        assert "tesseract" in text.lower()
        assert "jpn" in text or "言語データ" in text


def test_docs_explain_homebrew_path_diagnosis_for_apple_silicon_and_intel():
    """Apple Silicon/Intel Macそれぞれのbrewパスと、PATHが通っていないだけの場合のbrew shellenv案内が
    docs/04・docs/08に明記されていることを確認する。"""
    for path in (REPO_ROOT / "docs" / "04_output_spec.md", REPO_ROOT / "docs" / "08_user_acceptance_test.md"):
        text = _read(path)
        assert "brew shellenv" in text


def test_scripts_check_ocr_env_exists_and_is_documented():
    script_path = REPO_ROOT / "scripts" / "check_ocr_env.sh"
    assert script_path.exists()
    docs_04_text = _read(REPO_ROOT / "docs" / "04_output_spec.md")
    assert "check_ocr_env.sh" in docs_04_text


# --- Phase 10.1 追加修正: OCR必須モードでOCR不能時は正常終了しない -------------------


def test_docs_explain_build_all_fails_on_ocr_precondition():
    """build-allのproofread/restructureが、OCR不能時にエラー終了する仕様がREADME/docs/04/08に
    明記されていることを確認する。"""
    for path in (
        REPO_ROOT / "README.md",
        REPO_ROOT / "docs" / "04_output_spec.md",
        REPO_ROOT / "docs" / "08_user_acceptance_test.md",
    ):
        text = _read(path)
        assert "エラー終了" in text or "exit 1" in text


def test_docs_document_allow_empty_ocr_flag():
    """--allow-empty-ocrオプションがREADME/docs/01/04/08に記載されていることを確認する。"""
    for path in (
        REPO_ROOT / "README.md",
        REPO_ROOT / "docs" / "01_requirements.md",
        REPO_ROOT / "docs" / "04_output_spec.md",
        REPO_ROOT / "docs" / "08_user_acceptance_test.md",
    ):
        text = _read(path)
        assert "--allow-empty-ocr" in text


# --- Phase 10.2: 成功判定の再点検・実行ログ出力・ログ仕様の共通設計化 ------------------


def test_claude_rules_documents_logging_common_design_rule():
    """logs/の共通仕様がCLAUDE_RULES.mdに明記されていることを確認する。"""
    text = _read(REPO_ROOT / "CLAUDE_RULES.md")
    assert "logs/" in text
    assert "ログ出力の共通設計ルール" in text or "ログ出力" in text


def test_claude_rules_documents_success_judgment_policy():
    """成功判定の方針（実質失敗を正常終了扱いにしない）がCLAUDE_RULES.mdに明記されていることを確認する。"""
    text = _read(REPO_ROOT / "CLAUDE_RULES.md")
    assert "成功判定" in text


def test_docs_04_has_logs_standard_spec_section():
    text = _read(REPO_ROOT / "docs" / "04_output_spec.md")
    assert "実行ログ" in text
    assert "logs/" in text
    assert "成功判定の方針" in text


def test_docs_explain_logs_git_and_zip_management():
    """logs/ディレクトリ自体はGit対象・中身は対象外・ZIPには含める、という管理方針が
    README/docs/01/04に明記されていることを確認する。"""
    for path in (
        REPO_ROOT / "README.md",
        REPO_ROOT / "docs" / "01_requirements.md",
        REPO_ROOT / "docs" / "04_output_spec.md",
    ):
        text = _read(path)
        assert "logs/" in text


def test_logs_gitkeep_exists_and_gitignore_configured():
    """logs/.gitkeepが存在し、.gitignoreでlogs/*が除外・!logs/.gitkeepが例外設定されていることを
    確認する。"""
    gitkeep_path = REPO_ROOT / "logs" / ".gitkeep"
    assert gitkeep_path.exists()

    gitignore_text = _read(REPO_ROOT / ".gitignore")
    assert "logs/*" in gitignore_text
    assert "!logs/.gitkeep" in gitignore_text


def test_make_release_zip_does_not_exclude_logs():
    """scripts/make_release_zip.shがlogs/を除外していない（ZIP対象に含まれる）ことを確認する。"""
    script_text = _read(REPO_ROOT / "scripts" / "make_release_zip.sh")
    assert '-x "logs' not in script_text
    assert "logs/" in script_text  # 意図を明記したコメントが存在する


def test_docs_08_explains_success_failure_judgment():
    text = _read(REPO_ROOT / "docs" / "08_user_acceptance_test.md")
    assert "成功判定" in text
    assert "logs/" in text


# --- Phase 10.2追加修正: 個別CLI成果物未生成チェック・ログの機密情報マスク --------------


def test_docs_document_log_masking_policy():
    """logs/*.log の機密情報マスク仕様がCLAUDE_RULES.md/docs/04/08に明記されていることを確認する。"""
    for path in (
        REPO_ROOT / "CLAUDE_RULES.md",
        REPO_ROOT / "docs" / "04_output_spec.md",
        REPO_ROOT / "docs" / "08_user_acceptance_test.md",
    ):
        text = _read(path)
        assert "REDACTED" in text


def test_docs_04_lists_masking_target_keywords():
    text = _read(REPO_ROOT / "docs" / "04_output_spec.md")
    for keyword in ("password", "token", "api_key", "secret", "authorization"):
        assert keyword in text.lower()
