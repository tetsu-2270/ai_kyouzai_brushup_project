import pytest

from src import ocr_engine
from src.ocr_engine import (
    OcrCandidate,
    OcrWord,
    apply_high_confidence_fixes,
    combine_region_candidates,
    combine_region_words,
    complete_title_in_text,
    dictionary_hit_count,
    effective_char_count,
    find_more_complete_title,
    fix_wave_dash_misread,
    garbled_latin_token_count,
    generate_preprocess_variants,
    has_unclosed_bracket,
    is_incomplete_title_line,
    is_low_quality_title_line,
    is_noise_latin_token,
    is_noise_symbol_token,
    japanese_char_ratio,
    low_confidence_word_ratio,
    mean_confidence,
    median_confidence,
    postprocess_candidate,
    run_multi_ocr,
    score_candidate,
    select_best_candidate,
    split_region_variants,
    title_is_uncertain,
    title_line_min_confidence,
    title_similarity,
    words_to_text,
)


def _word(text, conf=90, left=0, top=0, width=10, height=10, block=1, par=1, line=1, wnum=1):
    return OcrWord(
        text=text, conf=conf, left=left, top=top, width=width, height=height,
        block_num=block, par_num=par, line_num=line, word_num=wnum,
    )


_ALLOWED = {"url", "sns", "instagram", "chatgpt", "youtube"}
_HIGH_CONF_DICT = {"一買": ("一貫", "high"), "アウトブット": ("アウトプット", "high")}


# --- 画像前処理 -------------------------------------------------------------------


def test_generate_preprocess_variants_does_not_modify_original_image():
    from PIL import Image

    original = Image.new("RGB", (100, 60), color=(200, 100, 50))
    original_bytes_before = original.tobytes()

    variants = generate_preprocess_variants(original)

    assert original.tobytes() == original_bytes_before
    assert set(variants.keys()) >= {"original", "enhanced", "binarized"}
    # 前処理結果は元画像とは別のオブジェクトである。
    assert variants["enhanced"] is not original
    assert variants["binarized"] is not original


def test_split_region_variants_produces_generic_fractional_regions():
    from PIL import Image

    image = Image.new("RGB", (400, 200), color=(255, 255, 255))
    regions = split_region_variants(image)

    assert regions["top_band"].size[0] == 400
    assert regions["top_band"].size[1] < regions["body_band"].size[1]
    assert regions["left_half"].size == (200, 200)
    assert regions["right_half"].size == (200, 200)


# --- 読み順の再構成（words_to_text） ------------------------------------------------


def test_words_to_text_does_not_insert_space_between_japanese_characters():
    words = [
        _word("【", left=0), _word("一", left=10), _word("貫", left=20),
        _word("し", left=30), _word("た", left=40),
    ]
    text = words_to_text(words)
    assert text == "【一貫した"


def test_words_to_text_inserts_space_around_latin_tokens():
    words = [_word("hello", left=0), _word("world", left=60)]
    text = words_to_text(words)
    assert text == "hello world"


def test_words_to_text_orders_multiple_lines_and_columns_by_block_par_line():
    # 左カラム（block=1）と右カラム（block=2）を模したワード集合。
    left_words = [_word("左カラム本文", block=1, par=1, line=1, left=0)]
    right_words = [_word("右カラム本文", block=2, par=1, line=1, left=0)]
    text = words_to_text(left_words + right_words)
    lines = text.split("\n")
    assert lines == ["左カラム本文", "右カラム本文"]


def test_combine_region_candidates_preserves_specified_order_for_column_split():
    """左右カラム分割後、単純にy座標で結合すると段組みが混ざるため、領域ごとに指定した
    順序（左→右）で結合されることを確認する。"""
    left_candidate = OcrCandidate(
        words=[_word("左カラム1行目", block=1, line=1, left=0), _word("左カラム2行目", block=1, line=2, left=0)],
        preprocess="enhanced", psm=6, region="left_half",
    )
    right_candidate = OcrCandidate(
        words=[_word("右カラム1行目", block=1, line=1, left=0)],
        preprocess="enhanced", psm=6, region="right_half",
    )
    combined = combine_region_candidates([("left", left_candidate), ("right", right_candidate)])
    assert combined.text == "左カラム1行目\n左カラム2行目\n右カラム1行目"


def test_combine_region_candidates_returns_ocr_candidate_usable_for_scoring():
    # 結合結果は文字列ではなくOcrCandidateであり、score_candidate()やpostprocess_candidate()に
    # そのまま渡して通常候補と比較できる構造を維持していること。
    top_candidate = OcrCandidate(
        words=[_word("タイトル", block=1, line=1, left=0, conf=90)],
        preprocess="enhanced", psm=6, region="top_band",
    )
    body_candidate = OcrCandidate(
        words=[_word("本文", block=1, line=1, left=0, conf=90)],
        preprocess="enhanced", psm=6, region="body_band",
    )
    combined = combine_region_candidates(
        [("top_band", top_candidate), ("body_band", body_candidate)], region_label="top_body_split"
    )
    assert isinstance(combined, OcrCandidate)
    assert combined.region == "top_body_split"
    assert combined.preprocess == "enhanced"
    assert combined.psm == 6
    score = score_candidate(combined, _ALLOWED, _HIGH_CONF_DICT)
    assert score >= 0.0


def test_combine_region_candidates_avoids_cross_region_line_collision():
    # 各領域は個別にOCRされるため、block_num/par_num/line_numはどちらも1から始まりうる。
    # 単純結合するとwords_to_text()が異なる領域の行を同一行として混ぜてしまう危険がある。
    top_words = [_word("上段行A", block=1, par=1, line=1, left=0)]
    body_words = [_word("下段行A", block=1, par=1, line=1, left=0)]
    top_candidate = OcrCandidate(words=top_words, preprocess="enhanced", psm=6, region="top_band")
    body_candidate = OcrCandidate(words=body_words, preprocess="enhanced", psm=6, region="body_band")
    combined = combine_region_candidates(
        [("top_band", top_candidate), ("body_band", body_candidate)], region_label="top_body_split"
    )
    lines = combined.text.split("\n")
    # 同一(block,par,line)キーに衝突して1行に混ざっていないこと。
    assert lines == ["上段行A", "下段行A"]


def test_combine_region_candidates_preserves_within_region_line_order():
    top_words = [
        _word("上段1行目", block=1, par=1, line=1, left=0),
        _word("上段2行目", block=1, par=1, line=2, left=0),
    ]
    body_words = [_word("下段1行目", block=1, par=1, line=1, left=0)]
    top_candidate = OcrCandidate(words=top_words, preprocess="enhanced", psm=6, region="top_band")
    body_candidate = OcrCandidate(words=body_words, preprocess="enhanced", psm=6, region="body_band")
    combined = combine_region_candidates(
        [("top_band", top_candidate), ("body_band", body_candidate)], region_label="top_body_split"
    )
    assert combined.text.split("\n") == ["上段1行目", "上段2行目", "下段1行目"]


# --- 品質スコアの構成要素 ------------------------------------------------------------


def test_mean_and_median_confidence():
    words = [_word("a", conf=80), _word("b", conf=90), _word("c", conf=100)]
    assert mean_confidence(words) == 90.0
    assert median_confidence(words) == 90.0


def test_japanese_char_ratio_all_japanese():
    assert japanese_char_ratio("一貫したキャラ設定") == 1.0


def test_japanese_char_ratio_mixed():
    ratio = japanese_char_ratio("あane")
    assert 0.0 < ratio < 1.0


def test_low_confidence_word_ratio():
    words = [_word("a", conf=10), _word("b", conf=90), _word("c", conf=20), _word("d", conf=95)]
    assert low_confidence_word_ratio(words, threshold=45) == 0.5


def test_is_noise_latin_token_rejects_short_unlisted_latin_word():
    assert is_noise_latin_token("ane", _ALLOWED) is True
    assert is_noise_latin_token("PPP", _ALLOWED) is True


def test_is_noise_latin_token_keeps_allowed_words():
    assert is_noise_latin_token("SNS", _ALLOWED) is False
    assert is_noise_latin_token("url", _ALLOWED) is False


def test_is_noise_latin_token_keeps_longer_latin_words():
    """5文字以上の英字は一般的な英単語の可能性が上がるため、過剰検出しない。"""
    assert is_noise_latin_token("hello", _ALLOWED) is False


def test_is_noise_latin_token_ignores_non_latin_tokens():
    assert is_noise_latin_token("こんにちは", _ALLOWED) is False
    assert is_noise_latin_token("70%", _ALLOWED) is False


def test_garbled_latin_token_count():
    text = "本文中に ane と SCRA と PPP というノイズがある"
    assert garbled_latin_token_count(text, _ALLOWED) == 3


def test_dictionary_hit_count():
    text = "一買したキャラ設定。アウトブットタイム。"
    assert dictionary_hit_count(text, _HIGH_CONF_DICT) == 2


def test_effective_char_count_ignores_whitespace():
    assert effective_char_count("あ い\nう") == 3


# --- 候補選択（ノイズの多い結果を選ばない） -------------------------------------------


def test_score_candidate_prefers_clean_japanese_over_noisy_latin():
    clean_words = [
        _word(c, conf=92, left=i * 10, block=1, line=1) for i, c in enumerate("一貫したキャラ設定も大切です")
    ]
    noisy_words = [
        _word(t, conf=35, left=i * 30, block=1, line=1)
        for i, t in enumerate(["ane", "SCRA", "PPP", "ms", "som"])
    ]
    clean = OcrCandidate(words=clean_words, preprocess="original", psm=6)
    noisy = OcrCandidate(words=noisy_words, preprocess="original", psm=11)

    clean_score = score_candidate(clean, _ALLOWED, _HIGH_CONF_DICT)
    noisy_score = score_candidate(noisy, _ALLOWED, _HIGH_CONF_DICT)
    assert clean_score > noisy_score


def test_select_best_candidate_does_not_prefer_longer_noisy_text_over_shorter_clean_text():
    """単純に文字数が多い候補を選ぶとノイズの多い結果が勝ってしまう問題への回帰テスト。"""
    short_clean = OcrCandidate(
        words=[_word(c, conf=95, left=i * 10) for i, c in enumerate("アウトプットタイム")],
        preprocess="original", psm=6,
    )
    long_noisy = OcrCandidate(
        words=[_word(t, conf=25, left=i * 40) for i, t in enumerate(["ane", "SCRA", "som", "nae", "ms", "PPP", "ap", "U"])],
        preprocess="original", psm=11,
    )
    best, _score = select_best_candidate([long_noisy, short_clean], _ALLOWED, _HIGH_CONF_DICT)
    assert best is short_clean


def test_score_candidate_is_deterministic():
    words = [_word(c, conf=88, left=i * 10) for i, c in enumerate("一貫したキャラ設定")]
    candidate = OcrCandidate(words=words, preprocess="enhanced", psm=6)
    scores = {score_candidate(candidate, _ALLOWED, _HIGH_CONF_DICT) for _ in range(5)}
    assert len(scores) == 1


def test_score_candidate_empty_words_scores_zero():
    empty = OcrCandidate(words=[], preprocess="original", psm=6)
    assert score_candidate(empty, _ALLOWED, _HIGH_CONF_DICT) == 0.0


# --- 低品質タイトル判定 --------------------------------------------------------------


def test_is_low_quality_title_line_rejects_single_character():
    assert is_low_quality_title_line("だ", _ALLOWED) is True
    assert is_low_quality_title_line("人", _ALLOWED) is True


def test_is_low_quality_title_line_rejects_symbol_only():
    assert is_low_quality_title_line("・・・", _ALLOWED) is True
    assert is_low_quality_title_line("===", _ALLOWED) is True


def test_is_low_quality_title_line_rejects_unnatural_short_latin():
    assert is_low_quality_title_line("YOU", _ALLOWED) is True
    assert is_low_quality_title_line("ane", _ALLOWED) is True


def test_is_low_quality_title_line_accepts_normal_japanese_title():
    assert is_low_quality_title_line("【一貫したキャラ設定】", _ALLOWED) is False
    assert is_low_quality_title_line("アウトプットタイム", _ALLOWED) is False


def test_is_low_quality_title_line_keeps_allowed_short_latin():
    assert is_low_quality_title_line("SNS", _ALLOWED) is False


# --- 後処理（ノイズ除去・辞書補正を一律削除しない） -------------------------------------


def test_apply_high_confidence_fixes_replaces_known_misreadings():
    text = "一買したキャラ設定。アウトブットタイム。"
    fixed = apply_high_confidence_fixes(text, _HIGH_CONF_DICT)
    assert fixed == "一貫したキャラ設定。アウトプットタイム。"


def test_fix_wave_dash_misread_handles_number_range():
    assert fix_wave_dash_misread("70て80%") == "70〜80%"
    assert fix_wave_dash_misread("運用当初からずっと茅ヶ崎と隣市の方が70て80%") == (
        "運用当初からずっと茅ヶ崎と隣市の方が70〜80%"
    )


def test_fix_wave_dash_misread_does_not_touch_unrelated_text():
    assert fix_wave_dash_misread("今日はてんきがいい") == "今日はてんきがいい"


def test_postprocess_candidate_removes_leading_and_trailing_noise_lines_but_keeps_body():
    words = (
        [_word("だ", conf=20, left=0, block=1, line=1)]
        + [_word(c, conf=92, left=10 + i * 10, block=1, line=2) for i, c in enumerate("一買したキャラ設定")]
        + [_word("人", conf=15, left=0, block=1, line=3)]
    )
    candidate = OcrCandidate(words=words, preprocess="enhanced", psm=11)
    text = postprocess_candidate(candidate, _ALLOWED, _HIGH_CONF_DICT)
    assert "だ" not in text.splitlines()
    assert "人" not in text.splitlines()
    assert "一貫したキャラ設定" in text


def test_postprocess_candidate_keeps_legitimate_english_and_urls():
    words = [
        _word("詳細は", conf=90, left=0, block=1, line=1),
        _word("https://example.com/sns", conf=85, left=60, block=1, line=1),
        _word("を参照", conf=90, left=250, block=1, line=1),
    ]
    candidate = OcrCandidate(words=words, preprocess="original", psm=6)
    text = postprocess_candidate(candidate, _ALLOWED, _HIGH_CONF_DICT)
    assert "https://example.com/sns" in text


# --- タイトル末尾欠落の検出・安全な補完 --------------------------------------------------


def test_has_unclosed_bracket_detects_missing_closing_bracket():
    assert has_unclosed_bracket("【一貫したキャラ") is True


def test_has_unclosed_bracket_accepts_balanced_brackets():
    assert has_unclosed_bracket("【一貫したキャラ設定】") is False


def test_has_unclosed_bracket_accepts_text_without_brackets():
    assert has_unclosed_bracket("アウトプットタイム") is False


def test_is_incomplete_title_line_detects_unclosed_bracket():
    assert is_incomplete_title_line("【一貫したキャラ") is True


def test_is_incomplete_title_line_accepts_complete_title():
    assert is_incomplete_title_line("【一貫したキャラ設定】") is False


def test_is_incomplete_title_line_accepts_empty_line():
    assert is_incomplete_title_line("") is False


def test_title_similarity_is_high_for_single_character_misread():
    assert title_similarity("【一買したキャラ設定】", "【一貫したキャラ設定】") >= 0.6


def test_title_similarity_is_low_for_unrelated_text():
    assert title_similarity("【一貫したキャラ設定】", "本日はご参加ありがとうございます") < 0.4


def test_find_more_complete_title_selects_longer_prefix_matching_candidate():
    # 「【新しい発表資料の作り方】」が欠落した「【新しい発表資料の作り」を、同じ画像の
    # 別候補（同一プレフィックス・完全な閉じ括弧）で安全に補完できること。特定教材の
    # タイトル文字列をハードコードせず、汎用的な括弧・類似度ルールだけで判定される。
    current_title = "【新しい発表資料の作り"
    candidates = [("【新しい発表資料の作り方】", 0.70), ("本文の一部です", 0.65)]
    result = find_more_complete_title(current_title, candidates, _ALLOWED, current_score=0.60)
    assert result == "【新しい発表資料の作り方】"


def test_find_more_complete_title_rejects_dissimilar_body_line():
    current_title = "【新しい発表資料の作り"
    candidates = [("まったく関係のない本文行です", 0.90)]
    result = find_more_complete_title(current_title, candidates, _ALLOWED, current_score=0.60)
    assert result is None


def test_find_more_complete_title_rejects_noisier_longer_candidate():
    current_title = "【新しい発表資料の作り方】"
    candidates = [("【新しい発表資料の作り方】xyz qq", 0.90)]
    result = find_more_complete_title(current_title, candidates, _ALLOWED, current_score=0.60)
    assert result is None


def test_find_more_complete_title_rejects_shorter_candidate():
    current_title = "【新しい発表資料の作り方】"
    candidates = [("【新しい発表資料の作", 0.90)]
    result = find_more_complete_title(current_title, candidates, _ALLOWED, current_score=0.60)
    assert result is None


def test_find_more_complete_title_accepts_same_length_fix_only_when_current_uncertain():
    # 文字数が同じ（欠落ではなく1文字誤読）の補完は、現在のタイトルが低信頼度（uncertain）と
    # 判定されている場合に限り採用する。信頼できる場合まで安易に別候補へ差し替えない。
    current_title = "【一皿したキャラ設定】"
    candidates = [("【一貫したキャラ設定】", 0.72)]

    rejected = find_more_complete_title(
        current_title, candidates, _ALLOWED, current_score=0.70, current_uncertain=False
    )
    assert rejected is None

    accepted = find_more_complete_title(
        current_title, candidates, _ALLOWED, current_score=0.70, current_uncertain=True
    )
    assert accepted == "【一貫したキャラ設定】"


def test_complete_title_in_text_replaces_only_first_line():
    text = "【新しい発表資料の作り\n本文1行目\n本文2行目"
    sibling_titles = [("【新しい発表資料の作り方】", 0.70)]
    result = complete_title_in_text(text, sibling_titles, _ALLOWED, current_score=0.60)
    lines = result.split("\n")
    assert lines[0] == "【新しい発表資料の作り方】"
    assert lines[1:] == ["本文1行目", "本文2行目"]


def test_complete_title_in_text_keeps_normal_title_untouched():
    # 「アウトプットタイム」のような、もともと欠落のない通常タイトルは、たとえ似た
    # より長い候補（本文の一部の誤結合等）があっても書き換えられない
    # （Page5相当の教材で不要な置換が起きないことの確認）。現在のタイトルが構造的に
    # 途中欠落でも低信頼度でもない限り、find_more_complete_title自体が候補を採用しない。
    text = "アウトプットタイム\n本文です"
    sibling_titles = [("アウトプットタイムのお知らせ", 0.90)]
    result = complete_title_in_text(text, sibling_titles, _ALLOWED, current_score=0.80)
    assert result.split("\n")[0] == "アウトプットタイム"


def test_find_more_complete_title_does_nothing_when_current_title_is_already_fine():
    # 現在のタイトルが閉じ括弧も揃っており、低信頼度でもない（current_uncertain=False）場合、
    # より長く類似した候補があっても採用しない。
    current_title = "アウトプットタイム"
    candidates = [("アウトプットタイムのお知らせ", 0.90)]
    result = find_more_complete_title(
        current_title, candidates, _ALLOWED, current_score=0.80, current_uncertain=False
    )
    assert result is None


def test_title_line_min_confidence_uses_only_first_line():
    words = [
        _word("正", conf=90, block=1, line=1, left=0),
        _word("常", conf=2, block=1, line=1, left=10),
        _word("本文行", conf=95, block=1, line=2, left=0),
    ]
    candidate = OcrCandidate(words=words, preprocess="enhanced", psm=6)
    assert title_line_min_confidence(candidate) == 2.0


def test_title_is_uncertain_true_when_min_confidence_below_threshold():
    words = [_word("疑", conf=2, block=1, line=1, left=0)]
    candidate = OcrCandidate(words=words, preprocess="enhanced", psm=6)
    assert title_is_uncertain(candidate) is True


def test_title_is_uncertain_false_for_high_confidence_title():
    words = [_word("良", conf=95, block=1, line=1, left=0)]
    candidate = OcrCandidate(words=words, preprocess="enhanced", psm=6)
    assert title_is_uncertain(candidate) is False


def test_is_noise_symbol_token_detects_short_symbol_token():
    assert is_noise_symbol_token(":") is True
    assert is_noise_symbol_token("=") is True


def test_is_noise_symbol_token_ignores_normal_word():
    assert is_noise_symbol_token("設定") is False


# --- 領域結合時のブロック番号衝突回避 --------------------------------------------------


def test_combine_region_words_offsets_block_numbers_to_avoid_collision():
    top_words = [_word("上", block=1, par=1, line=1, left=0)]
    body_words = [_word("下", block=1, par=1, line=1, left=0)]
    combined = combine_region_words([top_words, body_words])
    block_nums = {w.block_num for w in combined}
    assert len(block_nums) == 2
    # 元のリストは変更されない。
    assert top_words[0].block_num == 1
    assert body_words[0].block_num == 1


def test_combine_region_words_preserves_region_order():
    top_words = [_word("上", block=5, par=1, line=1, left=0)]
    body_words = [_word("下", block=1, par=1, line=1, left=0)]
    combined = combine_region_words([top_words, body_words])
    text = words_to_text(combined)
    assert text.split("\n") == ["上", "下"]


# --- 低品質時だけ再試行する（run_multi_ocr、pytesseractをモック） -----------------------


def _make_real_test_image():
    """generate_preprocess_variants()等の実際のPillow処理をそのまま通す、実物の小さな
    テスト画像。pytesseract（tesseract呼び出し）だけをモックし、画像処理自体は本物を使う
    ことで、前処理パイプラインの結合部分もあわせて検証する。"""
    from PIL import Image

    return Image.new("RGB", (600, 400), color=(230, 230, 230))


@pytest.fixture
def fake_ocr_status():
    return {"tesseract_available": True, "tesseract_path": "/usr/bin/tesseract", "languages": ["eng", "jpn"]}


def _good_words():
    return [_word(c, conf=95, left=i * 10, block=1, line=1) for i, c in enumerate("アウトプットタイムです")]


def _bad_words():
    return [_word(t, conf=20, left=i * 30, block=1, line=1) for i, t in enumerate(["ane", "SCRA", "ms", "PPP"])]


def test_run_multi_ocr_does_not_retry_when_quality_is_good(monkeypatch, fake_ocr_status):
    call_count = {"n": 0}

    def fake_run_image_to_data(image, lang, psm, tesseract_cmd):
        call_count["n"] += 1
        return _good_words()

    monkeypatch.setattr(ocr_engine, "_run_image_to_data", fake_run_image_to_data)
    import PIL.Image as real_pil_image
    monkeypatch.setattr(real_pil_image, "open", lambda p: _make_real_test_image())

    patterns = {
        "high_confidence_replacements": {}, "delete_candidates": [], "inferred_candidates": {},
        "source_check_required": [], "allowed_words": list(_ALLOWED),
    }
    result = run_multi_ocr(
        "dummy.png", fake_ocr_status, "jpn+eng", "/usr/bin/tesseract", patterns=patterns
    )

    # 前処理2種 x PSM2種 = 4回だけ呼ばれ、再試行（追加の二値化・領域分割）は発生しない。
    assert call_count["n"] == 4
    assert result.diagnostics.retried is False
    assert result.diagnostics.quality == "ok"


def test_run_multi_ocr_retries_only_when_quality_is_low(monkeypatch, fake_ocr_status):
    call_count = {"n": 0}

    def fake_run_image_to_data(image, lang, psm, tesseract_cmd):
        call_count["n"] += 1
        return _bad_words()

    monkeypatch.setattr(ocr_engine, "_run_image_to_data", fake_run_image_to_data)
    import PIL.Image as real_pil_image
    monkeypatch.setattr(real_pil_image, "open", lambda p: _make_real_test_image())

    patterns = {
        "high_confidence_replacements": {}, "delete_candidates": [], "inferred_candidates": {},
        "source_check_required": [], "allowed_words": list(_ALLOWED),
    }
    result = run_multi_ocr(
        "dummy.png", fake_ocr_status, "jpn+eng", "/usr/bin/tesseract", patterns=patterns
    )

    # 4回のベースライン + 二値化1回 + タイトル/本文分割2回 + 左右分割2回 = 9回。
    assert call_count["n"] == 9
    assert result.diagnostics.retried is True
    assert result.diagnostics.quality == "needs_review"


def test_run_multi_ocr_records_selected_psm_and_preprocess_in_diagnostics(monkeypatch, fake_ocr_status):
    def fake_run_image_to_data(image, lang, psm, tesseract_cmd):
        return _good_words()

    monkeypatch.setattr(ocr_engine, "_run_image_to_data", fake_run_image_to_data)
    import PIL.Image as real_pil_image
    monkeypatch.setattr(real_pil_image, "open", lambda p: _make_real_test_image())

    patterns = {
        "high_confidence_replacements": {}, "delete_candidates": [], "inferred_candidates": {},
        "source_check_required": [], "allowed_words": list(_ALLOWED),
    }
    result = run_multi_ocr("dummy.png", fake_ocr_status, "jpn+eng", "/usr/bin/tesseract", patterns=patterns)

    assert result.diagnostics.psm in (6, 11)
    assert result.diagnostics.preprocess in ("original", "enhanced")
    assert result.diagnostics.candidates_tried == 4
    assert result.diagnostics.duration_seconds >= 0


# --- タイトル異常だけを狙った条件付き再試行（run_multi_ocr、汎用データでハードコード無しを確認） ----


def _bracket_incomplete_baseline_words():
    # 「【新企画】」の閉じ括弧が欠落した状態を模す。特定教材の文言ではなく汎用的な例。
    title_chars = "【新企画"
    return [_word(c, conf=93, left=i * 10, block=1, line=1) for i, c in enumerate(title_chars)] + [
        _word(c, conf=90, left=i * 10, block=1, line=2) for i, c in enumerate("本日の内容について説明します")
    ]


def _bracket_complete_top_band_words():
    title_chars = "【新企画】"
    return [_word(c, conf=93, left=i * 10, block=1, line=1) for i, c in enumerate(title_chars)]


def _mediocre_region_words():
    return [_word(t, conf=25, left=i * 30, block=1, line=1) for i, t in enumerate(["xx", "yy", "zz"])]


def test_run_multi_ocr_retries_and_completes_truncated_bracket_title(monkeypatch, fake_ocr_status):
    def fake_run_image_to_data(image, lang, psm, tesseract_cmd):
        size = image.size
        if size == (1200, 272):
            return _bracket_complete_top_band_words()
        if size in {(1200, 624), (600, 800)}:
            return _mediocre_region_words()
        return _bracket_incomplete_baseline_words()

    monkeypatch.setattr(ocr_engine, "_run_image_to_data", fake_run_image_to_data)
    import PIL.Image as real_pil_image
    monkeypatch.setattr(real_pil_image, "open", lambda p: _make_real_test_image())

    patterns = {
        "high_confidence_replacements": {}, "delete_candidates": [], "inferred_candidates": {},
        "source_check_required": [], "allowed_words": list(_ALLOWED),
    }
    result = run_multi_ocr("dummy.png", fake_ocr_status, "jpn+eng", "/usr/bin/tesseract", patterns=patterns)

    # スコアが十分でも、タイトル行の括弧欠落だけを理由に再試行が発生すること。
    assert result.diagnostics.retried is True
    title_line = result.text.split("\n", 1)[0]
    assert title_line == "【新企画】"
    assert result.diagnostics.quality == "ok"


def _uncertain_title_baseline_words():
    return [
        _word("実", conf=95, left=0, block=1, line=1),
        _word("紙", conf=2, left=10, block=1, line=1),
        _word("果", conf=95, left=20, block=1, line=1),
    ] + [_word(c, conf=92, left=i * 10, block=1, line=2) for i, c in enumerate("本文はここに続きます")]


def _uncertain_title_top_band_words():
    return [
        _word("実", conf=95, left=0, block=1, line=1),
        _word("験", conf=95, left=10, block=1, line=1),
        _word("果", conf=95, left=20, block=1, line=1),
    ]


def test_run_multi_ocr_retries_when_title_has_low_confidence_token_despite_balanced_brackets(
    monkeypatch, fake_ocr_status
):
    # 括弧は閉じているが、タイトル行に極端に低信頼度の文字が残っている場合も、
    # 領域分割の再試行を経て、より信頼できる同一画像内の候補へ安全に差し替えられること。
    def fake_run_image_to_data(image, lang, psm, tesseract_cmd):
        size = image.size
        if size == (1200, 272):
            return _uncertain_title_top_band_words()
        if size in {(1200, 624), (600, 800)}:
            return _mediocre_region_words()
        return _uncertain_title_baseline_words()

    monkeypatch.setattr(ocr_engine, "_run_image_to_data", fake_run_image_to_data)
    import PIL.Image as real_pil_image
    monkeypatch.setattr(real_pil_image, "open", lambda p: _make_real_test_image())

    patterns = {
        "high_confidence_replacements": {}, "delete_candidates": [], "inferred_candidates": {},
        "source_check_required": [], "allowed_words": list(_ALLOWED),
    }
    result = run_multi_ocr("dummy.png", fake_ocr_status, "jpn+eng", "/usr/bin/tesseract", patterns=patterns)

    assert result.diagnostics.retried is True
    title_line = result.text.split("\n", 1)[0]
    assert title_line == "実験果"
    assert result.diagnostics.quality == "ok"


def test_run_multi_ocr_does_not_retry_for_normal_title_with_only_minor_body_noise(monkeypatch, fake_ocr_status):
    # タイトルが正常であれば、本文側にわずかなノイズが残っている程度では再試行しない
    # （すべてのページを常に再試行する設計になっていないことの確認）。
    def fake_run_image_to_data(image, lang, psm, tesseract_cmd):
        return [_word(c, conf=93, left=i * 10, block=1, line=1) for i, c in enumerate("アウトプットタイム")] + [
            _word(c, conf=90, left=i * 10, block=1, line=2) for i, c in enumerate("今日の内容はこちらです")
        ]

    monkeypatch.setattr(ocr_engine, "_run_image_to_data", fake_run_image_to_data)
    import PIL.Image as real_pil_image
    monkeypatch.setattr(real_pil_image, "open", lambda p: _make_real_test_image())

    patterns = {
        "high_confidence_replacements": {}, "delete_candidates": [], "inferred_candidates": {},
        "source_check_required": [], "allowed_words": list(_ALLOWED),
    }
    result = run_multi_ocr("dummy.png", fake_ocr_status, "jpn+eng", "/usr/bin/tesseract", patterns=patterns)

    assert result.diagnostics.retried is False
    assert result.text.split("\n", 1)[0] == "アウトプットタイム"
