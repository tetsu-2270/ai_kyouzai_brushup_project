from src.lesson_pages import LessonDocument, LessonMetadata, LessonPage
from src.ocr_check import (
    analyze_page_ocr_quality,
    build_ocr_correction_candidates,
    candidate_priority_score,
    deduplicate_ocr_candidates,
    detect_common_ocr_misreads,
    detect_garbled_latin_sequences,
    detect_incomplete_sentences,
    detect_inferred_ocr_corrections,
    detect_source_check_required_phrases,
    detect_suspicious_tokens,
    detect_title_anomalies,
    detect_unusual_symbols,
    render_ocr_check_report_markdown,
)
from src.ocr_patterns import default_ocr_patterns, merge_ocr_patterns


def _document(pages: list[LessonPage], mode: str = "proofread") -> LessonDocument:
    return LessonDocument(metadata=LessonMetadata(mode=mode), pages=pages)


def _page(page_no: int = 1, **kwargs) -> LessonPage:
    defaults = dict(
        page_no=page_no, title="", body="", summary="", image_text="",
        layout_instruction="", canva_prompt="", video_scene="", source_image="", notes="",
    )
    defaults.update(kwargs)
    return LessonPage(**defaults)


# --- 検出器の単体テスト ----------------------------------------------------------------


def test_detect_common_ocr_misreads_finds_known_dictionary_entries():
    candidates = detect_common_ocr_misreads("一買性を大事にする。アウトブットが重要。")
    detected = {c["original"] for c in candidates}
    assert "一買" in detected
    assert "アウトブット" in detected
    misread = next(c for c in candidates if c["original"] == "一買")
    assert misread["suggested"] == "一貫"
    assert misread["severity"] == "high"


def test_detect_garbled_latin_sequences_flags_noise():
    candidates = detect_garbled_latin_sequences("RSS ERRh se rel Cee oe がありました")
    assert len(candidates) >= 1
    assert candidates[0]["detection_type"] == "garbled_latin"


def test_detect_garbled_latin_sequences_does_not_flag_allowed_terms():
    text = "OK、AIとLLM、OCRの技術を使い、InstagramにPDFやDOCXをアップロードします。URLはSNSで共有します。"
    candidates = detect_garbled_latin_sequences(text)
    assert candidates == []


def test_detect_unusual_symbols_flags_broken_numbering():
    candidates = detect_unusual_symbols("(⑤番目の項目について説明します")
    assert any(c["detection_type"] == "unusual_symbol" for c in candidates)


def test_detect_incomplete_sentences_flags_dangling_ending():
    candidates = detect_incomplete_sentences("※もし何も思い浮かばなかったら")
    assert len(candidates) == 1
    assert candidates[0]["detection_type"] == "incomplete_sentence"


def test_detect_incomplete_sentences_does_not_flag_completed_sentence():
    candidates = detect_incomplete_sentences("これは完結した文章です。")
    assert candidates == []


def test_detect_suspicious_tokens_flags_number_japanese_spacing():
    candidates = detect_suspicious_tokens("全部で 11問あります")
    assert any(c["detection_type"] == "spacing" for c in candidates)


# --- analyze/build のテスト -------------------------------------------------------------


def test_build_ocr_correction_candidates_includes_required_fields():
    document = _document([_page(page_no=3, title="一買性のある教材", source_page_no=[5], source_image="p5.png")])
    data = build_ocr_correction_candidates(document, source_file="test.json")
    assert data["candidates"], "候補が生成されていること"
    candidate = data["candidates"][0]
    for key in ("candidate_id", "page_no", "page_index", "field", "original", "suggested", "severity", "reason", "status"):
        assert key in candidate
    assert candidate["page_no"] == 3
    assert candidate["status"] == "proposed"
    assert candidate["field"] == "title"


def test_build_ocr_correction_candidates_severity_counts():
    document = _document([_page(title="一買性のある教材")])
    data = build_ocr_correction_candidates(document)
    assert data["summary"]["total_candidates"] >= 1
    assert data["summary"]["high"] >= 1


def test_build_ocr_correction_candidates_does_not_crash_on_missing_fields():
    document = _document([_page(page_no=1)])  # 全フィールド空
    data = build_ocr_correction_candidates(document)
    assert data["summary"]["total_candidates"] == 0
    assert data["candidates"] == []


def test_build_ocr_correction_candidates_avoids_false_positives_for_allowed_terms():
    document = _document([_page(body="OK、AI、LLM、OCR、Instagram、PDF、DOCXを使います。")])
    data = build_ocr_correction_candidates(document)
    assert data["summary"]["total_candidates"] == 0


# --- Markdownレポートのテスト ------------------------------------------------------------


def test_render_ocr_check_report_includes_overall_summary():
    document = _document([_page(title="一買性のある教材")])
    data = build_ocr_correction_candidates(document)
    text = render_ocr_check_report_markdown(document, data)
    assert "全体サマリー" in text
    assert "ページ数: 1" in text


def test_render_ocr_check_report_includes_detection_summary():
    document = _document([_page(title="一買性のある教材")])
    data = build_ocr_correction_candidates(document)
    text = render_ocr_check_report_markdown(document, data)
    assert "システム検出結果サマリー" in text
    assert "よくあるOCR誤認識候補" in text


def test_render_ocr_check_report_includes_per_page_detail():
    document = _document([
        _page(page_no=1, title="ページ1"),
        _page(page_no=2, title="ページ2"),
    ])
    data = build_ocr_correction_candidates(document)
    text = render_ocr_check_report_markdown(document, data)
    assert "### Page 1: ページ1" in text
    assert "### Page 2: ページ2" in text


def test_render_ocr_check_report_includes_correction_candidates_table():
    document = _document([_page(title="一買性のある教材")])
    data = build_ocr_correction_candidates(document)
    text = render_ocr_check_report_markdown(document, data)
    assert "## 9. 修正候補" in text
    assert "一買" in text
    assert "一貫" in text


def test_render_ocr_check_report_includes_severity_labels():
    document = _document([_page(title="一買性のある教材")])
    data = build_ocr_correction_candidates(document)
    text = render_ocr_check_report_markdown(document, data)
    assert "重要度：高" in text


def test_render_ocr_check_report_does_not_crash_on_missing_fields():
    document = _document([_page(page_no=1)])
    data = build_ocr_correction_candidates(document)
    text = render_ocr_check_report_markdown(document, data)
    assert "### Page 1" in text
    assert "候補はありません" in text or "該当なし" in text


def test_render_ocr_check_report_mentions_candidates_json_path():
    document = _document([_page(title="P1")])
    data = build_ocr_correction_candidates(document)
    text = render_ocr_check_report_markdown(document, data, candidates_output="output/custom_candidates.json")
    assert "output/custom_candidates.json" in text


# --- 過検出抑制・実データ向け精度改善 ------------------------------------------------------


def test_layout_instruction_assets_and_page_are_not_flagged():
    """layout_instruction内のassets/pageがgarbled_latin候補として検出されないことを確認する
    （実データで全27ページが要確認扱いになっていた主要因）。"""
    page = _page(layout_instruction="assets: page_001.png / page: 1")
    candidates = analyze_page_ocr_quality(page)
    assert candidates == []


def test_layout_instruction_only_candidates_do_not_count_as_image_check_pages():
    """layout_instruction由来の候補だけでは元画像確認が必要なページ数に数えないことを確認する。"""
    document = _document([
        _page(page_no=1, layout_instruction="assets: page_001.png / page: 1"),
    ])
    data = build_ocr_correction_candidates(document)
    text = render_ocr_check_report_markdown(document, data)
    assert "元画像確認が必要そうなページ数: 0" in text


def test_body_garbled_latin_is_still_detected():
    """body内の意味不明な英字列（RSS/ERRh se rel Cee oe等）は引き続き検出されることを確認する。"""
    candidates = detect_garbled_latin_sequences("RSS ERRh se rel Cee oeが混入している")
    assert len(candidates) >= 1


def test_title_short_english_word_is_flagged():
    """titleがRSSのような短い英字のみの場合、title崩れ候補として検出されることを確認する。"""
    page = _page(title="RSS")
    candidates = analyze_page_ocr_quality(page)
    assert any(c["field"] == "title" for c in candidates)


def test_title_with_stray_symbols_is_flagged():
    """titleに「|」「°」「@」等の不自然な記号が混入している場合に検出されることを確認する。"""
    candidates = detect_title_anomalies("@ ジ 記| ジャンル設定 °")
    assert len(candidates) == 1
    assert candidates[0]["detection_type"] == "unusual_symbol"


def test_title_with_broken_brackets_is_flagged():
    """titleの括弧が半角始まり・全角終わりのように崩れている場合に検出されることを確認する
    （辞書一致「実貴」でも検出されるため、いずれかで検出されればよい）。"""
    title = "[キャラ設定実貴タイム】"
    unusual = detect_unusual_symbols(title)
    dictionary = detect_common_ocr_misreads(title)
    assert unusual or dictionary


def test_incomplete_sentence_at_end_of_body_is_flagged():
    candidates = detect_incomplete_sentences("※もし何も思い浮かばなかったら")
    assert len(candidates) == 1


def test_incomplete_sentence_with_natural_continuation_is_not_flagged():
    """次の行に文章が自然に続いている場合は未完文候補にしないことを確認する。"""
    text = "ご希望がなければ指名させていただきますので\nミュートを解除してお話しください"
    candidates = detect_incomplete_sentences(text)
    assert candidates == []


def test_simple_number_word_spacing_is_low_severity():
    """「1 つ」は辞書一致で低重要度として検出されることを確認する（内容破壊ではないため）。"""
    dict_candidates = detect_common_ocr_misreads("1 つ")
    assert len(dict_candidates) == 1
    assert dict_candidates[0]["severity"] == "low"


def test_garbled_number_kana_mix_is_elevated_severity():
    """「時 9ま1よう」のような数字とかなの不自然な混在は中または高重要度になることを確認する。"""
    candidates = detect_suspicious_tokens("時 9ま1よう")
    elevated = [c for c in candidates if c["severity"] in ("medium", "high")]
    assert elevated


def test_date_like_pattern_requires_image_check():
    """「7 / 1 現在」のような日付風の表記は、誤修正を避けるため元画像確認候補になることを確認する。"""
    candidates = detect_suspicious_tokens("7 / 1 現在")
    date_like = [c for c in candidates if c["requires_image_check"]]
    assert date_like


def test_json_candidates_exclude_layout_instruction_internal_words():
    """補正候補JSONにも、layout_instruction由来の内部語句候補が含まれないことを確認する。"""
    document = _document([
        _page(page_no=1, layout_instruction="assets: page_001.png / page: 1", title="正常なタイトル"),
    ])
    data = build_ocr_correction_candidates(document)
    assert data["candidates"] == []


def test_markdown_report_excludes_layout_instruction_internal_words():
    """Markdownレポートにも、layout_instruction由来の内部語句候補が含まれないことを確認する。"""
    document = _document([
        _page(page_no=1, layout_instruction="assets: page_001.png / page: 1", title="正常なタイトル"),
    ])
    data = build_ocr_correction_candidates(document)
    text = render_ocr_check_report_markdown(document, data)
    assert "検出された候補はありませんでした" in text


# --- 削除候補・推定修正候補・元画像確認必須候補の分類 -------------------------------------


def test_common_misreads_are_high_confidence_correction():
    """明確な誤字はhigh confidence correction（status: proposed, action: replace）として出る。"""
    candidates = detect_common_ocr_misreads("共通説識を持つ")
    assert candidates[0]["action"] == "replace"
    assert candidates[0]["status"] == "proposed"
    assert candidates[0]["confidence"] == "high"


def test_zenbu_11_mon_with_extra_space_is_candidated():
    candidates = detect_common_ocr_misreads("全1 1 問あります")
    assert any(c["original"] == "全1 1 問" and c["suggested"] == "全11問" for c in candidates)


def test_arikuzusu_is_candidated():
    candidates = detect_common_ocr_misreads("有崩すことができる")
    assert any(c["original"] == "有崩す" and c["suggested"] == "崩す" for c in candidates)


def test_sonna_keiken_is_candidated():
    candidates = detect_common_ocr_misreads("生んな経験をした")
    assert any(c["original"] == "生んな経験" and c["suggested"] == "そんな経験" for c in candidates)


def test_doiu_is_candidated():
    candidates = detect_common_ocr_misreads("どいうことか分からない")
    assert any(c["original"] == "どいう" and c["suggested"] == "という" for c in candidates)


def test_mudan_tensai_kinshi_is_candidated_as_inferred():
    """「六坂載祭上 → ※無断転載禁止」は推定修正候補（needs_source_check）として出る。"""
    candidates = detect_inferred_ocr_corrections("六坂載祭上と書いてある")
    assert len(candidates) == 1
    assert candidates[0]["suggested"] == "※無断転載禁止"
    assert candidates[0]["status"] == "needs_source_check"
    assert candidates[0]["detection_type"] == "inferred_ocr_correction"


def test_short_english_noise_is_deletion_candidate():
    """ae/BQ/Ps/RSSのような短い英字ノイズは削除候補（action: delete）として出る。"""
    for noise in ("ae", "BQ", "Ps", "RSS"):
        candidates = detect_garbled_latin_sequences(f"本文中に{noise}が混入")
        assert candidates, f"failed for: {noise}"
        assert candidates[0]["action"] == "delete"
        assert candidates[0]["status"] == "needs_human_review"


def test_allowed_terms_are_not_deletion_candidates():
    """Instagram/SNS/AI/URL/ID/OK/NG/PDF/JSON/CSV/API/LLMは削除候補にしないことを確認する。"""
    allowed_terms = ("Instagram", "SNS", "AI", "URL", "ID", "OK", "NG", "PDF", "JSON", "CSV", "API", "LLM")
    for term in allowed_terms:
        candidates = detect_garbled_latin_sequences(f"これは{term}を使った説明です")
        assert candidates == [], f"failed for: {term}"


def test_source_check_required_phrases_are_flagged():
    """マチオロウーざん/ERRh se rel Cee oe/SAAT こコ全わったはsource check requiredとして出る。"""
    for phrase in ("マチオロウーざん", "ERRh se rel Cee oe", "SAAT こコ全わった"):
        candidates = detect_source_check_required_phrases(f"本文に{phrase}が含まれる")
        assert len(candidates) == 1, f"failed for: {phrase}"
        assert candidates[0]["status"] == "needs_source_check"
        assert candidates[0]["action"] == "source_check"
        assert candidates[0]["detection_type"] == "source_check_required"


def test_candidates_json_includes_action_confidence_human_note():
    document = _document([_page(body="共通説識を持つ")])
    data = build_ocr_correction_candidates(document)
    candidate = data["candidates"][0]
    assert "action" in candidate
    assert "confidence" in candidate
    assert "human_note" in candidate
    assert candidate["action"] == "replace"


def test_report_includes_classification_breakdown():
    document = _document([
        _page(page_no=1, body="共通説識を持つ。RSSが混入。六坂載祭上と書いてある。ERRh se rel Cee oe。"),
    ])
    data = build_ocr_correction_candidates(document)
    text = render_ocr_check_report_markdown(document, data)
    assert "high confidence correction" in text
    assert "deletion candidate" in text
    assert "inferred correction candidate" in text
    assert "source check required" in text


# --- OCRパターン外部辞書（config/ocr_patterns.json）との連携 -------------------------------


def test_external_pattern_addition_is_candidated_in_candidates_json():
    """外部辞書で追加した候補がocr_correction_candidates.jsonに出ることを確認する。"""
    custom_patterns = merge_ocr_patterns(
        default_ocr_patterns(), {"high_confidence_replacements": {"外部辞書誤字": "外部辞書正字"}}
    )
    document = _document([_page(body="外部辞書誤字が含まれる本文です")])
    data = build_ocr_correction_candidates(document, patterns=custom_patterns)
    assert any(c["original"] == "外部辞書誤字" and c["suggested"] == "外部辞書正字" for c in data["candidates"])


def test_allowed_words_from_external_patterns_suppress_deletion_candidates():
    """外部辞書のallowed_wordsが、短い英字ノイズの削除候補化を抑制することを確認する。"""
    custom_patterns = merge_ocr_patterns(default_ocr_patterns(), {"allowed_words": ["ZzNoise"]})
    candidates = detect_garbled_latin_sequences("これはZzNoiseという製品名です", custom_patterns)
    assert candidates == []


def test_report_includes_pattern_load_info():
    """ocr_check_report.mdに辞書読み込み情報が出ることを確認する。"""
    document = _document([_page(body="通常の本文です")])
    data = build_ocr_correction_candidates(document)
    text = render_ocr_check_report_markdown(document, data)
    assert "使用したOCRパターン辞書" in text
    assert "読み込み結果" in text
    assert "default_only" in text


def test_candidates_json_includes_patterns_summary():
    document = _document([_page(body="通常の本文です")])
    data = build_ocr_correction_candidates(document)
    assert "patterns" in data
    assert data["patterns"]["load_status"] == "default_only"
    assert data["patterns"]["high_confidence_replacements"] > 0


# --- OCR候補の重複抑制（deduplicate_ocr_candidates） ---------------------------------------


def _raw_candidate(**kwargs):
    defaults = dict(
        candidate_id="ocr-0001", page_no=1, page_index=0, field="body",
        original="x", suggested=None, action="source_check", severity="medium",
        reason="test", detection_type="spacing", source_page_no=[1], source_image="",
        confidence="medium", requires_image_check=True, status="proposed", human_note="",
    )
    defaults.update(kwargs)
    return defaults


def test_exact_duplicate_candidates_are_reduced_to_one():
    candidates = [
        _raw_candidate(original="RSS", detection_type="garbled_latin"),
        _raw_candidate(original="RSS", detection_type="garbled_latin"),
    ]
    deduped, summary = deduplicate_ocr_candidates(candidates)
    assert len(deduped) == 1
    assert summary == {"before": 2, "after": 1, "suppressed": 1}


def test_page7_style_dedupe_keeps_only_inferred_correction():
    """「時 9ま1よう → 決めましょう」と「9ま1よう」がある場合、前者が残ることを確認する。"""
    candidates = [
        _raw_candidate(
            original="時 9ま1よう", suggested="決めましょう", action="replace",
            detection_type="inferred_ocr_correction", status="needs_source_check", confidence="low",
        ),
        _raw_candidate(original="9ま1よう", detection_type="spacing", action="source_check"),
        _raw_candidate(original="を\n: 時 9ま1よう", detection_type="spacing", action="source_check"),
    ]
    deduped, summary = deduplicate_ocr_candidates(candidates)
    assert len(deduped) == 1
    assert deduped[0]["original"] == "時 9ま1よう"
    assert summary["suppressed"] == 2


def test_page20_style_dedupe_keeps_only_source_check_required():
    """「SAAT こコ全わった」と「SAAT」がある場合、前者が残ることを確認する。"""
    candidates = [
        _raw_candidate(
            original="SAAT こコ全わった", detection_type="source_check_required",
            action="source_check", status="needs_source_check",
        ),
        _raw_candidate(original="SAAT", detection_type="garbled_latin", action="delete", status="needs_human_review"),
    ]
    deduped, summary = deduplicate_ocr_candidates(candidates)
    assert len(deduped) == 1
    assert deduped[0]["original"] == "SAAT こコ全わった"


def test_page24_style_both_high_confidence_and_unusual_symbol_are_kept():
    """「実貴 → 実践」と「[キャラ設定実貴タイム】」は両方残ることを確認する
    （単純な包含関係だけで消しすぎない）。"""
    candidates = [
        _raw_candidate(
            original="実貴", suggested="実践", action="replace",
            detection_type="common_ocr_misread", status="proposed", confidence="high", field="title",
        ),
        _raw_candidate(
            original="[キャラ設定実貴タイム】", detection_type="unusual_symbol",
            action="source_check", status="proposed", field="title",
        ),
    ]
    deduped, summary = deduplicate_ocr_candidates(candidates)
    assert len(deduped) == 2
    assert summary["suppressed"] == 0


def test_dedupe_does_not_suppress_across_different_fields():
    candidates = [
        _raw_candidate(original="ae", field="title", detection_type="garbled_latin", action="delete"),
        _raw_candidate(original="ae", field="body", detection_type="garbled_latin", action="delete"),
    ]
    deduped, summary = deduplicate_ocr_candidates(candidates)
    assert len(deduped) == 2
    assert summary["suppressed"] == 0


def test_dedupe_does_not_suppress_across_different_pages():
    candidates = [
        _raw_candidate(original="ae", page_no=1, detection_type="garbled_latin", action="delete"),
        _raw_candidate(original="ae", page_no=2, detection_type="garbled_latin", action="delete"),
    ]
    deduped, summary = deduplicate_ocr_candidates(candidates)
    assert len(deduped) == 2
    assert summary["suppressed"] == 0


def test_high_confidence_replacement_not_suppressed_by_longer_low_confidence_candidate():
    """高確信度の短い置換候補は、より長い低信頼候補があっても消されないことを確認する。"""
    candidates = [
        _raw_candidate(
            original="1 つ", suggested="1つ", action="replace",
            detection_type="common_ocr_misread", status="proposed", confidence="high",
        ),
        _raw_candidate(
            original="全部で1 つあります", detection_type="spacing", action="source_check",
            status="proposed", confidence="low", severity="low",
        ),
    ]
    deduped, summary = deduplicate_ocr_candidates(candidates)
    originals = {c["original"] for c in deduped}
    assert "1 つ" in originals
    assert summary["suppressed"] == 1


def test_dedupe_summary_reported_in_candidates_json():
    document = _document([
        _page(page_no=1, body="時 9ま1よう な表現があります"),
    ])
    data = build_ocr_correction_candidates(document)
    assert "dedupe" in data
    assert set(data["dedupe"].keys()) == {"before", "after", "suppressed"}
    assert data["summary"]["candidates_before_dedupe"] == data["dedupe"]["before"]
    assert data["summary"]["suppressed_duplicate_candidates"] == data["dedupe"]["suppressed"]


def test_report_includes_dedupe_counts():
    document = _document([_page(page_no=1, body="時 9ま1よう な表現があります")])
    data = build_ocr_correction_candidates(document)
    text = render_ocr_check_report_markdown(document, data)
    assert "重複抑制前の候補数" in text
    assert "重複抑制された候補数" in text


def test_candidate_priority_score_orders_replace_above_delete():
    replace_candidate = _raw_candidate(action="replace", status="proposed", confidence="high", severity="high")
    delete_candidate = _raw_candidate(action="delete", status="needs_human_review", confidence="medium", severity="medium")
    assert candidate_priority_score(replace_candidate) > candidate_priority_score(delete_candidate)
