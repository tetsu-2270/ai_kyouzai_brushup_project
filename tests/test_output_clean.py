import pytest

from src.output_clean import (
    KNOWN_OUTPUT_DIRS,
    KNOWN_OUTPUT_FILES,
    UnsafeOutputDirError,
    clean_known_outputs,
    validate_clean_output_dir,
)


def _make_project_root(tmp_path):
    project_root = tmp_path / "proj"
    (project_root / "input").mkdir(parents=True)
    (project_root / "input" / "photo.jpg").write_bytes(b"dummy")
    (project_root / "src").mkdir()
    (project_root / "tests").mkdir()
    (project_root / "docs").mkdir()
    (project_root / ".git").mkdir()
    return project_root


def test_validate_rejects_empty_string(tmp_path):
    project_root = _make_project_root(tmp_path)
    with pytest.raises(UnsafeOutputDirError):
        validate_clean_output_dir("", project_root=project_root)


def test_validate_rejects_filesystem_root(tmp_path):
    project_root = _make_project_root(tmp_path)
    with pytest.raises(UnsafeOutputDirError):
        validate_clean_output_dir("/", project_root=project_root)


def test_validate_rejects_home_directory(tmp_path, monkeypatch):
    project_root = _make_project_root(tmp_path)
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr("pathlib.Path.home", lambda: fake_home)
    with pytest.raises(UnsafeOutputDirError):
        validate_clean_output_dir(str(fake_home), project_root=project_root)


def test_validate_rejects_project_root_itself(tmp_path):
    project_root = _make_project_root(tmp_path)
    with pytest.raises(UnsafeOutputDirError):
        validate_clean_output_dir(str(project_root), project_root=project_root)


def test_validate_rejects_path_outside_project_and_outside_tmp(tmp_path, monkeypatch):
    """pytest自体が一時ディレクトリ配下で動くため、「/tmp配下でもない」状況を再現するには
    tempfile.gettempdir()が指す実際の許可ルートを、テスト対象パスを含まない別の場所に
    差し替える必要がある（`_allowed_tmp_roots()`が実プロセスのtempfile.gettempdir()を
    見に行くため）。"""
    project_root = _make_project_root(tmp_path)
    outside_dir = tmp_path / "elsewhere" / "output"
    monkeypatch.setattr(
        "src.output_clean.tempfile.gettempdir", lambda: str(tmp_path / "not_the_allowed_tempdir")
    )
    with pytest.raises(UnsafeOutputDirError):
        validate_clean_output_dir(str(outside_dir), project_root=project_root)


def test_validate_accepts_subdir_of_project_root(tmp_path):
    project_root = _make_project_root(tmp_path)
    output_dir = project_root / "output"
    resolved = validate_clean_output_dir(str(output_dir), project_root=project_root)
    assert resolved == output_dir.resolve()


def test_validate_accepts_real_tmp_subdir(tmp_path):
    """project_rootとは無関係でも、実際の/tmp配下であれば許可される。"""
    import shutil
    import tempfile

    project_root = _make_project_root(tmp_path)
    real_tmp_dir = tempfile.mkdtemp(dir="/tmp")
    try:
        output_dir = f"{real_tmp_dir}/output"
        resolved = validate_clean_output_dir(output_dir, project_root=project_root)
        assert str(resolved).startswith("/private/tmp") or str(resolved).startswith("/tmp")
    finally:
        shutil.rmtree(real_tmp_dir, ignore_errors=True)


@pytest.mark.parametrize("protected_name", ["input", ".git", "src", "tests", "docs"])
def test_validate_rejects_protected_directories(tmp_path, protected_name):
    project_root = _make_project_root(tmp_path)
    protected_dir = project_root / protected_name
    with pytest.raises(UnsafeOutputDirError):
        validate_clean_output_dir(str(protected_dir), project_root=project_root)


def _populate_known_outputs(output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in KNOWN_OUTPUT_DIRS:
        d = output_dir / name
        d.mkdir()
        (d / "dummy.txt").write_text("x", encoding="utf-8")
    for name in KNOWN_OUTPUT_FILES:
        (output_dir / name).write_text("x", encoding="utf-8")


def test_clean_known_outputs_removes_only_known_dirs_and_files(tmp_path):
    project_root = _make_project_root(tmp_path)
    output_dir = project_root / "output"
    _populate_known_outputs(output_dir)

    # output-dir配下の未知の手動ファイル・ディレクトリ。削除されないことを確認する。
    (output_dir / "my_notes.txt").write_text("メモ", encoding="utf-8")
    custom_dir = output_dir / "custom_dir"
    custom_dir.mkdir()
    (custom_dir / "keep.txt").write_text("keep", encoding="utf-8")

    result = clean_known_outputs(output_dir, project_root=project_root)

    for name in KNOWN_OUTPUT_DIRS:
        assert not (output_dir / name).exists()
    for name in KNOWN_OUTPUT_FILES:
        assert not (output_dir / name).exists()

    assert (output_dir / "my_notes.txt").exists()
    assert (custom_dir / "keep.txt").exists()

    assert len(result["removed"]) == len(KNOWN_OUTPUT_DIRS) + len(KNOWN_OUTPUT_FILES)


def test_clean_known_outputs_removes_legacy_phase8_root_level_files(tmp_path):
    """Phase 8時点のbuild-allがoutput_dir直下に直接生成していた旧仕様の完成output
    （lesson_pages.json/canva_design.md/brushup.md/brushup.docx/brushup.pdf）が、
    output/compat/配下の現行版と紛らわしいまま残らないよう、--clean-outputの削除対象に
    含まれることを確認する。"""
    project_root = _make_project_root(tmp_path)
    output_dir = project_root / "output"
    output_dir.mkdir(parents=True)
    legacy_names = ["lesson_pages.json", "canva_design.md", "brushup.md", "brushup.docx", "brushup.pdf"]
    for name in legacy_names:
        (output_dir / name).write_text("legacy", encoding="utf-8")

    result = clean_known_outputs(output_dir, project_root=project_root)

    for name in legacy_names:
        assert not (output_dir / name).exists()
    assert len(result["removed"]) == len(legacy_names)


def test_clean_known_outputs_does_not_remove_ambiguous_or_out_of_scope_files(tmp_path):
    """手動ファイルと区別できないファイル・OCR承認/反映ワークフローの生成物・現行の
    optional機能（restructure_plan.json等）は、--clean-outputの削除対象に含めない
    仕様を固定する。"""
    project_root = _make_project_root(tmp_path)
    output_dir = project_root / "output"
    output_dir.mkdir(parents=True)
    out_of_scope_names = [
        # コード上のどのコマンドの固定既定パスにも一致しない（手動生成・カスタム出力先の可能性があり
        # 人間の手動ファイルと区別できないため対象外）。
        "lesson_pages_restructured.json",
        "llm_handoff_proofread.md",
        "llm_handoff_restructure.md",
        "ocr_check_report.after_apply.md",
        "ocr_correction_candidates.after_apply.json",
        # lesson-pages --plan-outputはユーザーが任意のファイル名を指定できるオプション機能であり、
        # build-all自体は生成しないため対象外。
        "restructure_plan.json",
        # approve-ocr-candidates/apply-ocr-correctionsの生成物。OCR候補レビュー・反映ワークフローは
        # 今回のクリーンアップ対象スコープ外（build-all/import-source/review-report/ocr-check/
        # llm-handoffの既知生成物のみが対象）。
        "ocr_apply_report.md",
        "ocr_approval_report.md",
        "ocr_correction_candidates.approved.json",
    ]
    for name in out_of_scope_names:
        (output_dir / name).write_text("x", encoding="utf-8")

    clean_known_outputs(output_dir, project_root=project_root)

    for name in out_of_scope_names:
        assert (output_dir / name).exists()


def test_clean_known_outputs_simulates_page_count_shrink(tmp_path):
    """前回52ページ相当のrendered/page_014.png等がある状態で再生成すると、
    古いページ画像がクリーンアップ後は残らないことを確認する（本タスクの動機となったシナリオ）。
    """
    project_root = _make_project_root(tmp_path)
    output_dir = project_root / "output"
    rendered_dir = output_dir / "rendered"
    rendered_dir.mkdir(parents=True)
    for i in range(1, 53):
        (rendered_dir / f"page_{i:03d}.png").write_bytes(b"old-image")

    clean_known_outputs(output_dir, project_root=project_root)

    assert not rendered_dir.exists()

    # クリーン後、新しい13ページ分だけを再生成したことを模擬する。
    rendered_dir.mkdir(parents=True)
    for i in range(1, 14):
        (rendered_dir / f"page_{i:03d}.png").write_bytes(b"new-image")

    remaining = sorted(p.name for p in rendered_dir.iterdir())
    assert remaining == [f"page_{i:03d}.png" for i in range(1, 14)]
    assert not (rendered_dir / "page_014.png").exists()


def test_clean_known_outputs_skips_missing_targets_without_error(tmp_path):
    project_root = _make_project_root(tmp_path)
    output_dir = project_root / "output"
    output_dir.mkdir()

    result = clean_known_outputs(output_dir, project_root=project_root)

    assert result["removed"] == []
    assert len(result["skipped"]) == len(KNOWN_OUTPUT_DIRS) + len(KNOWN_OUTPUT_FILES)


def test_clean_known_outputs_does_not_touch_input_directory(tmp_path):
    project_root = _make_project_root(tmp_path)
    output_dir = project_root / "output"
    _populate_known_outputs(output_dir)

    clean_known_outputs(output_dir, project_root=project_root)

    assert (project_root / "input" / "photo.jpg").exists()
    assert (project_root / "src").exists()
    assert (project_root / "tests").exists()
    assert (project_root / "docs").exists()
    assert (project_root / ".git").exists()


def test_clean_known_outputs_raises_and_deletes_nothing_for_unsafe_output_dir(tmp_path):
    project_root = _make_project_root(tmp_path)
    # output-dirをプロジェクトルートそのものにする（安全条件違反）。
    with pytest.raises(UnsafeOutputDirError):
        clean_known_outputs(str(project_root), project_root=project_root)

    # 何も削除されていないことを確認する。
    assert (project_root / "input" / "photo.jpg").exists()
    assert (project_root / "src").exists()
