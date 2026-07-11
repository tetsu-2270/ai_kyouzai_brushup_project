from src import ocr_compare


_ALLOWED = {"url", "sns", "ai"}


# --- 正規化 -------------------------------------------------------------------------------


def test_normalize_collapses_whitespace_and_trims_lines():
    text = "  タイトル  \n\n\n本文　　です\n"
    normalized = ocr_compare.normalize_for_comparison(text)
    assert normalized == "タイトル\n\n本文 です"


def test_normalize_does_not_touch_kanji_punctuation_choonpu_or_digits():
    text = "一貫したキャラ設定！「引用」70〜80%"
    assert ocr_compare.normalize_for_comparison(text) == text


def test_normalize_strips_leading_and_trailing_blank_lines():
    text = "\n\n本文\n\n"
    assert ocr_compare.normalize_for_comparison(text) == "本文"


# --- 類似度 -------------------------------------------------------------------------------


def test_text_similarity_is_1_for_identical_text():
    assert ocr_compare.text_similarity("同じ本文です", "同じ本文です") == 1.0


def test_text_similarity_is_low_for_unrelated_text():
    assert ocr_compare.text_similarity("これは本文です", "まったく異なる内容の別ページ") < 0.5


def test_title_similarity_uses_only_first_line():
    a = "【共通タイトル】\n本文A"
    b = "【共通タイトル】\n本文Bはまったく違う"
    assert ocr_compare.title_similarity(a, b) == 1.0


def test_title_similarity_detects_mismatched_title():
    a = "【一貫したキャラ設定】\n本文"
    b = "アウトプットタイム\n本文"
    assert ocr_compare.title_similarity(a, b) < 0.3


# --- 行数・文字数差 --------------------------------------------------------------------------


def test_line_count_diff_counts_extra_lines():
    a = "行1\n行2"
    b = "行1\n行2\n行3\n行4"
    assert ocr_compare.line_count_diff(a, b) == 2


def test_effective_char_count_diff_ignores_whitespace_differences():
    a = "本文です"
    b = "本文　です"
    assert ocr_compare.effective_char_count_diff(a, b) == 0


# --- 一方にしか無い行 -------------------------------------------------------------------------


def test_lines_only_in_one_side_detects_missing_line():
    a = "タイトル\n本文1\n※無断転載禁止"
    b = "タイトル\n本文1"
    diff = ocr_compare.lines_only_in_one_side(a, b)
    assert diff.only_in_a == ["※無断転載禁止"]
    assert diff.only_in_b == []


def test_lines_only_in_one_side_tolerates_minor_misreads():
    a = "タイトル\n一貫したキャラ設定"
    b = "タイトル\n一買したキャラ設定"
    diff = ocr_compare.lines_only_in_one_side(a, b)
    assert diff.only_in_a == []
    assert diff.only_in_b == []


# --- 読み順の差 ----------------------------------------------------------------------------


def test_reading_order_difference_ratio_is_zero_for_same_order():
    a = "行A\n行B\n行C"
    b = "行A\n行B\n行C"
    assert ocr_compare.reading_order_difference_ratio(a, b) == 0.0


def test_reading_order_difference_ratio_detects_swapped_lines():
    a = "行A\n行B\n行C\n行D"
    b = "行C\n行D\n行A\n行B"
    assert ocr_compare.reading_order_difference_ratio(a, b) > 0.3


# --- 記号・ノイズトークン差 -------------------------------------------------------------------


def test_noise_token_diff_counts_symbol_noise():
    a = "本文です :"
    b = "本文です"
    diff = ocr_compare.noise_token_diff(a, b, _ALLOWED)
    assert diff.tesseract_noise_count == 1
    assert diff.vision_noise_count == 0
    assert diff.diff == 1


def test_noise_token_diff_ignores_allowed_words():
    a = "詳細はURLを参照"
    b = "詳細はURLを参照"
    diff = ocr_compare.noise_token_diff(a, b, _ALLOWED)
    assert diff.diff == 0


# --- 重要語句差 ----------------------------------------------------------------------------


def test_important_diff_snippets_reports_japanese_substitutions():
    a = "苦労したことを書く"
    b = "店労したことを書く"
    snippets = ocr_compare.important_diff_snippets(a, b)
    assert "苦" in snippets
    assert "店" in snippets


def test_important_diff_snippets_ignores_short_or_latin_only_diffs():
    a = "OK"
    b = "NG"
    snippets = ocr_compare.important_diff_snippets(a, b)
    assert snippets == []


# --- needs_review判定 -----------------------------------------------------------------------


def test_evaluate_needs_review_false_for_identical_text():
    metrics = ocr_compare.compute_comparison_metrics("同じ本文です", "同じ本文です", _ALLOWED)
    needs_review, reasons = ocr_compare.evaluate_needs_review(metrics)
    assert needs_review is False
    assert reasons == []


def test_evaluate_needs_review_true_when_title_mismatches():
    tesseract_text = "【一貫したキャラ設定】\n本文です"
    vision_text = "アウトプットタイム\n本文です"
    metrics = ocr_compare.compute_comparison_metrics(tesseract_text, vision_text, _ALLOWED)
    needs_review, reasons = ocr_compare.evaluate_needs_review(metrics)
    assert needs_review is True
    assert any("タイトル" in r for r in reasons)


def test_evaluate_needs_review_true_when_line_missing_on_one_side():
    tesseract_text = "タイトル\n苦労したこと"
    vision_text = "タイトル\n苦労したこと\n※無断転載禁止"
    metrics = ocr_compare.compute_comparison_metrics(tesseract_text, vision_text, _ALLOWED)
    needs_review, reasons = ocr_compare.evaluate_needs_review(metrics)
    assert needs_review is True


def test_evaluate_needs_review_true_when_reading_order_differs_substantially():
    tesseract_text = "タイトル\n左1\n左2\n右1\n右2"
    vision_text = "タイトル\n右1\n右2\n左1\n左2"
    metrics = ocr_compare.compute_comparison_metrics(tesseract_text, vision_text, _ALLOWED)
    needs_review, reasons = ocr_compare.evaluate_needs_review(metrics)
    assert needs_review is True
    assert any("読み順" in r for r in reasons)


def test_evaluate_needs_review_tolerates_minor_whitespace_only_difference():
    tesseract_text = "タイトル\n本文です　ね"
    vision_text = "タイトル\n本文です ね"
    metrics = ocr_compare.compute_comparison_metrics(tesseract_text, vision_text, _ALLOWED)
    needs_review, reasons = ocr_compare.evaluate_needs_review(metrics)
    assert needs_review is False
    assert reasons == []
