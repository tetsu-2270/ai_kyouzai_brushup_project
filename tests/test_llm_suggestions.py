from src.lesson_pages import LessonDocument, LessonMetadata, LessonPage
from src.llm_suggestions import (
    build_llm_suggestion_candidates,
    extract_overall_review,
    extract_page_suggestion_blocks,
    parse_llm_suggestions,
    parse_page_suggestion_block,
    render_llm_suggestion_report_markdown,
)


def _page(page_no=1, **kwargs):
    defaults = dict(
        page_no=page_no, title="", body="", summary="", image_text="",
        layout_instruction="", canva_prompt="", video_scene="", source_image="", notes="",
    )
    defaults.update(kwargs)
    return LessonPage(**defaults)


def _document(pages):
    return LessonDocument(metadata=LessonMetadata(mode="proofread", project_title="テスト教材"), pages=pages)


_STANDARD_RESPONSE = """
# 教材全体の構成チェック

## 全体評価

良い構成です。

## 大きく直す必要がある点

なし

## 直しすぎない方がよい点

雰囲気を保つ

# ページ別改善案

## Page 1: サンプルタイトル

- 現状の問題点：タイトルが分かりにくい
- 改善方針：具体的にする
- title 改善案：新しいタイトル
- summary 改善案：変更なし
- body 改善案：新しい本文です。
- 注意点：元資料を確認してください

# editable/lesson_pages.json 編集時の注意

- 直接置き換えてよい箇所：title/body
- 人間が判断すべき箇所：トーン
- 元資料確認が必要な箇所：会話部分
"""


# --- Page番号抽出の表記揺れ ---------------------------------------------------------------


def test_extract_page_number_from_standard_heading():
    blocks = extract_page_suggestion_blocks("## Page 1: タイトル\n\n本文")
    assert blocks[0]["page_no"] == 1


def test_extract_page_number_variants():
    variants = [
        "## Page 1: タイトル",
        "## Page 1",
        "### Page 1: タイトル",
        "Page 1: タイトル",
        "## ページ1",
        "## Page1",
        "## Page 01",
    ]
    for variant in variants:
        markdown = f"{variant}\n\n- title改善案：x\n"
        blocks = extract_page_suggestion_blocks(markdown)
        assert len(blocks) == 1, f"failed for: {variant}"
        assert blocks[0]["page_no"] == 1, f"wrong page_no for: {variant}"


# --- 改善案の候補化 --------------------------------------------------------------------


def test_title_suggestion_is_candidate():
    document = _document([_page(page_no=1, title="旧タイトル")])
    parsed = parse_llm_suggestions(_STANDARD_RESPONSE)
    data = build_llm_suggestion_candidates(document, parsed)
    title_candidates = [c for c in data["candidates"] if c["field"] == "title"]
    assert len(title_candidates) == 1
    assert title_candidates[0]["suggested"] == "新しいタイトル"


def test_summary_suggestion_is_candidate():
    document = _document([_page(page_no=1, summary="旧概要")])
    parsed = parse_llm_suggestions("""
## Page 1: T

- summary 改善案：新しい概要です
""")
    data = build_llm_suggestion_candidates(document, parsed)
    summary_candidates = [c for c in data["candidates"] if c["field"] == "summary"]
    assert len(summary_candidates) == 1
    assert summary_candidates[0]["suggested"] == "新しい概要です"


def test_body_suggestion_is_candidate():
    document = _document([_page(page_no=1, body="旧本文")])
    parsed = parse_llm_suggestions(_STANDARD_RESPONSE)
    data = build_llm_suggestion_candidates(document, parsed)
    body_candidates = [c for c in data["candidates"] if c["field"] == "body"]
    assert len(body_candidates) == 1
    assert body_candidates[0]["suggested"] == "新しい本文です。"


def test_no_change_phrases_are_not_candidated():
    document = _document([_page(page_no=1, summary="旧概要")])
    parsed = parse_llm_suggestions(_STANDARD_RESPONSE)
    data = build_llm_suggestion_candidates(document, parsed)
    summary_candidates = [c for c in data["candidates"] if c["field"] == "summary"]
    assert summary_candidates == []


def test_candidate_ids_are_stable_and_ordered():
    document = _document([_page(page_no=1, title="T", body="B")])
    markdown = """
## Page 1: T

- title 改善案：新title
- body 改善案：新body
"""
    parsed = parse_llm_suggestions(markdown)
    data = build_llm_suggestion_candidates(document, parsed)
    ids = [c["candidate_id"] for c in data["candidates"]]
    assert ids == ["llm-0001", "llm-0002"]
    fields = [c["field"] for c in data["candidates"]]
    assert fields == ["title", "body"]


def test_candidate_includes_required_fields():
    document = _document([_page(page_no=1, title="旧タイトル")])
    parsed = parse_llm_suggestions(_STANDARD_RESPONSE)
    data = build_llm_suggestion_candidates(document, parsed)
    candidate = data["candidates"][0]
    for key in ("candidate_id", "page_no", "page_index", "field", "original", "suggested", "status"):
        assert key in candidate
    assert candidate["status"] == "proposed"


def test_source_page_no_and_source_image_included():
    document = _document([_page(page_no=1, title="旧タイトル", source_page_no=[3], source_image="page_003.png")])
    parsed = parse_llm_suggestions(_STANDARD_RESPONSE)
    data = build_llm_suggestion_candidates(document, parsed)
    candidate = data["candidates"][0]
    assert candidate["source_page_no"] == [3]
    assert candidate["source_image"] == "page_003.png"


# --- parse_warnings ---------------------------------------------------------------------


def test_parse_warnings_are_emitted_for_missing_suggestions():
    parsed = parse_llm_suggestions("## Page 1: T\n\n- 現状の問題点：特になし\n")
    assert any(w["warning_type"] == "no_suggestions_found" for w in parsed["warnings"])


def test_nonexistent_page_number_is_warning():
    document = _document([_page(page_no=1, title="旧タイトル")])
    parsed = parse_llm_suggestions("## Page 99: T\n\n- title 改善案：x\n")
    data = build_llm_suggestion_candidates(document, parsed)
    assert any(w["warning_type"] == "page_not_found_in_lesson_pages" for w in data["parse_warnings"])
    assert data["candidates"] == []


# --- 全体評価の抽出 -----------------------------------------------------------------------


def test_extract_overall_review_sections():
    review = extract_overall_review(_STANDARD_RESPONSE)
    assert review["overall_evaluation"] == "良い構成です。"
    assert review["major_points"] == "なし"
    assert review["keep_as_is_points"] == "雰囲気を保つ"


# --- 生成物 -------------------------------------------------------------------------------


def test_build_llm_suggestion_candidates_json_structure():
    document = _document([_page(page_no=1, title="旧タイトル")])
    parsed = parse_llm_suggestions(_STANDARD_RESPONSE)
    data = build_llm_suggestion_candidates(document, parsed, source_lesson_pages="in.json", source_suggestions="resp.md")
    assert data["source_lesson_pages"] == "in.json"
    assert data["source_suggestions"] == "resp.md"
    assert "summary" in data
    assert "overall_review" in data
    assert "candidates" in data
    assert "parse_warnings" in data


def test_render_report_includes_expected_sections():
    document = _document([_page(page_no=1, title="旧タイトル")])
    parsed = parse_llm_suggestions(_STANDARD_RESPONSE)
    data = build_llm_suggestion_candidates(document, parsed)
    text = render_llm_suggestion_report_markdown(
        document, data,
        lesson_pages_path="in.json", suggestions_path="resp.md",
        candidates_output="cand.json", report_path="report.md",
    )
    assert "全体サマリー" in text
    assert "教材全体へのLLM評価" in text
    assert "ページ別改善候補一覧" in text
    assert "field別候補一覧" in text
    assert "parse_warnings" in text


def test_does_not_crash_on_incomplete_llm_response():
    """欠損項目があるLLM回答でも例外を起こさず処理できることを確認する。"""
    document = _document([_page(page_no=1, title="旧タイトル")])
    incomplete_markdown = "# 教材全体の構成チェック\n\n適当な文章のみで、期待した見出しがありません。"
    parsed = parse_llm_suggestions(incomplete_markdown)
    data = build_llm_suggestion_candidates(document, parsed)
    assert data["candidates"] == []
    text = render_llm_suggestion_report_markdown(
        document, data,
        lesson_pages_path="in.json", suggestions_path="resp.md",
        candidates_output="cand.json", report_path="report.md",
    )
    assert "改善候補は見つかりませんでした" in text


def test_parse_page_suggestion_block_handles_multiline_body():
    block = (
        "- 現状の問題点：説明不足\n"
        "- 改善方針：詳しく書く\n"
        "- body 改善案：これは1行目です。\n"
        "これは2行目です。\n"
        "- 注意点：確認してください"
    )
    parsed = parse_page_suggestion_block(block)
    assert parsed["body_suggestion"] == "これは1行目です。\nこれは2行目です。"
    assert parsed["caution"] == "確認してください"
