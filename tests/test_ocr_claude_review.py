import inspect
from pathlib import Path

from src import ocr_claude_review, ocr_comparison


def _make_summary(page_count, *, needs_review_pages=None, vision_helper_available=True, vision_unavailable_reason=""):
    pages = [
        ocr_comparison.PageComparison(
            page_no=n,
            source_image=f"assets/page_{n:03d}.jpeg",
            tesseract_text="T",
            tesseract_available=True,
            tesseract_duration_seconds=1.0,
            tesseract_score=0.7,
            tesseract_quality="ok",
            vision_text="V",
            vision_available=True,
            vision_warnings=[],
            vision_duration_seconds=0.3,
            metrics=None,
            needs_review=(n in (needs_review_pages or [])),
            mismatch_reasons=[],
        )
        for n in range(1, page_count + 1)
    ]
    return ocr_comparison.ComparisonSummary(
        generated_at="2026-01-01T00:00:00+09:00", language="ja-JP",
        vision_helper_available=vision_helper_available, vision_unavailable_reason=vision_unavailable_reason,
        total_pages=page_count, compared_pages=page_count if vision_helper_available else 0,
        needs_review_pages=needs_review_pages or [], tesseract_only_review_pages=[],
        vision_only_review_pages=needs_review_pages or [], both_engines_review_pages=[], pages=pages,
    )


# --- format_page_number_ranges -----------------------------------------------------------------


def test_format_page_number_ranges_collapses_contiguous_runs():
    assert ocr_claude_review.format_page_number_ranges([1, 2, 3, 5, 7, 8, 9]) == "1-3, 5, 7-9"


def test_format_page_number_ranges_handles_single_page():
    assert ocr_claude_review.format_page_number_ranges([4]) == "4"


def test_format_page_number_ranges_handles_empty():
    assert ocr_claude_review.format_page_number_ranges([]) == "(なし)"


def test_format_page_number_ranges_scales_to_large_page_counts_without_listing_each_page():
    text = ocr_claude_review.format_page_number_ranges(list(range(1, 138)))
    assert text == "1-137"
    assert len(text) < 20  # 137個すべてを列挙していれば数百文字になるはず


# --- render_claude_ocr_review_instructions（実データ埋め込み） -----------------------------------


def test_instructions_embed_actual_total_pages_and_page_numbers():
    summary = _make_summary(11)
    doc = ocr_claude_review.render_claude_ocr_review_instructions(summary, Path("output"))
    assert "対象ページ総数: 11" in doc
    assert "1-11" in doc


def test_instructions_embed_actual_relative_paths():
    summary = _make_summary(3)
    doc = ocr_claude_review.render_claude_ocr_review_instructions(summary, Path("output"))
    assert "output/ocr_comparison/summary.json" in doc
    assert "output/ocr_comparison/summary.md" in doc
    assert "output/ocr_comparison/pages/page_XXX.json" in doc
    assert "output/ocr_comparison/claude_review/pages/page_XXX.json" in doc
    assert "output/ocr_comparison/claude_review/candidates.json" in doc
    assert "output/ocr_comparison/claude_review/progress.json" in doc
    assert "output/ocr_comparison/claude_review/review_summary.md" in doc


def test_instructions_do_not_contain_absolute_paths(tmp_path):
    summary = _make_summary(2)
    # 絶対パスを渡した場合でも、指示書へは相対化されたパスだけが埋め込まれることを確認する。
    doc = ocr_claude_review.render_claude_ocr_review_instructions(summary, tmp_path / "output")
    assert str(tmp_path) not in doc
    assert "/private/" not in doc
    assert "/Users/" not in doc
    assert "/tmp/" not in doc


def test_instructions_do_not_duplicate_ocr_full_text():
    summary = _make_summary(1)
    summary.pages[0].tesseract_text = "これはTesseractの全文サンプルです、重複埋め込み禁止確認用"
    summary.pages[0].vision_text = "これはApple Visionの全文サンプルです、重複埋め込み禁止確認用"
    doc = ocr_claude_review.render_claude_ocr_review_instructions(summary, Path("output"))
    assert "これはTesseractの全文サンプルです" not in doc
    assert "これはApple Visionの全文サンプルです" not in doc
    assert "OCR全文はこの指示書に埋め込まれていません" in doc


def test_instructions_do_not_contain_secrets_or_api_keys():
    summary = _make_summary(2)
    doc = ocr_claude_review.render_claude_ocr_review_instructions(summary, Path("output"))
    lowered = doc.lower()
    for token in ("api_key", "apikey", "secret", "password", "bearer ", "sk-"):
        assert token not in lowered


def test_source_module_does_not_call_external_apis_or_claude():
    """Claude API呼び出しコード・外部送信コードが追加されていないことを、
    ソースコード自体から静的に確認する。"""
    source = inspect.getsource(ocr_claude_review)
    lowered = source.lower()
    for forbidden in (
        "import requests", "import httpx", "urllib.request", "anthropic",
        "api.anthropic.com", "openai", "http.client", "socket.socket",
    ):
        assert forbidden not in lowered


def test_instructions_document_candidate_json_required_schema():
    summary = _make_summary(1)
    doc = ocr_claude_review.render_claude_ocr_review_instructions(summary, Path("output"))
    for field in (
        "schema_version", "page_no", "source_image", "decision", "proposed_text",
        "corrections", "unresolved_spans", "requires_human_review", "review_notes",
        "reviewed_by", "reviewed_at",
    ):
        assert field in doc


def test_instructions_list_all_allowed_decision_values():
    summary = _make_summary(1)
    doc = ocr_claude_review.render_claude_ocr_review_instructions(summary, Path("output"))
    for decision in ("tesseract", "apple_vision", "merged", "corrected", "unresolved"):
        assert f"`{decision}`" in doc


def test_instructions_forbid_guessing_on_unresolved():
    summary = _make_summary(1)
    doc = ocr_claude_review.render_claude_ocr_review_instructions(summary, Path("output"))
    assert "推測" in doc
    assert "unresolved" in doc


def test_instructions_describe_page_by_page_save_and_resume():
    summary = _make_summary(1)
    doc = ocr_claude_review.render_claude_ocr_review_instructions(summary, Path("output"))
    assert "中断" in doc
    assert "再開" in doc
    assert "1ページごとに保存" in doc or "保存する（全ページ確認後にまとめて" in doc


def test_instructions_document_progress_candidates_and_summary_specs():
    summary = _make_summary(1)
    doc = ocr_claude_review.render_claude_ocr_review_instructions(summary, Path("output"))
    assert "progress.json" in doc
    assert "candidates.json" in doc
    assert "review_summary.md" in doc
    assert "remaining_pages" in doc
    assert "decision_counts" in doc
    assert "requires_human_review_pages" in doc


def test_instructions_do_not_assume_fixed_page_count():
    """固定ページ数（例: 実データの11ページ）に依存したロジックが無いことを、
    大きく異なるページ数（3ページ・137ページ）で同じ関数が正しく動くことで確認する。"""
    small = ocr_claude_review.render_claude_ocr_review_instructions(_make_summary(3), Path("output"))
    large = ocr_claude_review.render_claude_ocr_review_instructions(_make_summary(137), Path("output"))
    assert "対象ページ総数: 3" in small
    assert "対象ページ総数: 137" in large
    assert "ページ番号一覧: 1-3" in small
    assert "ページ番号一覧: 1-137" in large
    # 先頭ページ番号(1)の例だけを示し、ページ数がいくつであっても全件を列挙しない。
    assert "page_001.json" in small
    assert "page_001.json" in large


def test_instructions_do_not_embed_arbitrary_source_image_strings():
    """source_imageに特殊文字が含まれていても、指示書はそれをそのまま埋め込まない
    （番号ベースの一般化された例だけを使う設計）ため、構造が壊れないことを確認する。"""
    summary = _make_summary(1)
    summary.pages[0].source_image = "assets/`weird*name]_[test.jpeg"
    doc = ocr_claude_review.render_claude_ocr_review_instructions(summary, Path("output"))
    assert "`weird*name]_[test.jpeg" not in doc
    # コードブロックの```フェンスの数が偶数（開始・終了が対応している）ことを確認する。
    assert doc.count("```") % 2 == 0


# --- write_claude_review_entry_points -----------------------------------------------------------


def test_write_entry_points_creates_instructions_and_readme_when_vision_available(tmp_path):
    summary = _make_summary(2)
    output_dir = tmp_path / "output"
    paths = ocr_claude_review.write_claude_review_entry_points(output_dir, summary)
    assert paths is not None
    assert paths["claude_ocr_review_md"].exists()
    assert paths["claude_review_readme"].exists()
    assert paths["claude_review_readme"].parent.name == "claude_review"


def test_write_entry_points_creates_nothing_when_vision_unavailable(tmp_path):
    summary = _make_summary(2, vision_helper_available=False, vision_unavailable_reason="テスト環境では利用不可")
    output_dir = tmp_path / "output"
    result = ocr_claude_review.write_claude_review_entry_points(output_dir, summary)
    assert result is None
    assert not (output_dir / "ocr_comparison" / "CLAUDE_OCR_REVIEW.md").exists()
    assert not (output_dir / "ocr_comparison" / "claude_review").exists()


def test_write_entry_points_does_not_create_pages_progress_or_candidates(tmp_path):
    """build-all時点ではclaude_review/README.md以外(pages/・progress.json・candidates.json・
    review_summary.md)を生成しないことを確認する。"""
    summary = _make_summary(2)
    output_dir = tmp_path / "output"
    paths = ocr_claude_review.write_claude_review_entry_points(output_dir, summary)
    claude_review_dir = paths["claude_review_readme"].parent
    entries = {p.name for p in claude_review_dir.iterdir()}
    assert entries == {"README.md"}


def test_readme_explains_no_auto_reflection_and_git_exclusion():
    readme = ocr_claude_review.render_claude_review_readme()
    assert "自動反映" in readme
    assert "Git管理対象外" in readme
