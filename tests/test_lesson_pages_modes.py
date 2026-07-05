import json

import pytest

from src.lesson_pages import (
    apply_restructure_plan,
    build_lesson_pages,
    build_restructure_plan,
    render_review_report,
)
from src.parser import load_lesson_document

_SOURCE_PAGES = {
    "project_title": "テスト教材",
    "target_reader": "テスター",
    "pages": [
        {"page_no": 1, "source_image": "a.png", "title": "P1", "summary": "概要1", "lines": []},
        {"page_no": 2, "source_image": "b.png", "title": "P2", "summary": "概要2", "lines": []},
    ],
}

# page1は短文(orphan)なのでpage2へ統合され、page3は単独クラスタとして残る想定のフィクスチャ
_RESTRUCTURE_SOURCE_PAGES = {
    "project_title": "AI活用入門",
    "target_reader": "初心者",
    "pages": [
        {
            "page_no": 1,
            "source_image": "a.png",
            "title": "AIとは",
            "summary": "",
            "lines": [{"speaker": "講師", "text": "AIとは"}],
            "canva": {"main_visual": "中央にAIのイラスト"},
        },
        {
            "page_no": 2,
            "source_image": "b.png",
            "title": "ChatGPTとは",
            "summary": "",
            "lines": [{"speaker": "講師", "text": "ChatGPTは、AIを使った対話サービスです。使い方を覚えると投稿文作りが楽になります。"}],
            "canva": {"main_visual": "左にChatGPTのロゴ"},
        },
        {
            "page_no": 3,
            "source_image": "c.png",
            "title": "実践編",
            "summary": "",
            "lines": [{"speaker": "講師", "text": "実際に投稿文を作ってみましょう。まずはテーマを決めます。"}],
            "canva": {"main_visual": "下部に手順アイコン"},
        },
    ],
}

_LONG_PAGE_SOURCE = {
    "project_title": "長文教材",
    "target_reader": "読者",
    "pages": [
        {
            "page_no": 1,
            "source_image": "a.png",
            "title": "長い説明",
            "summary": "",
            "lines": [{"speaker": "講師", "text": "これはとても長い説明文です。" * 20}],
            "canva": {"main_visual": "全面にテキストを配置"},
        },
    ],
}

_REQUIREMENTS = {
    "theme": "テストテーマ",
    "target_audience": "テスト対象読者",
    "goal": "テストゴール",
    "reader_problem": "テストの悩み",
    "promised_value": "テストの価値",
    "tone": "テストトーン",
    "must_include": ["要素A", "要素B"],
    "must_not_include": ["避けたい表現"],
}


def _write_json(path, data, filename="input.json") -> str:
    file_path = path / filename
    file_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return str(file_path)


# --- proofread ---------------------------------------------------------------


def test_proofread_builds_lesson_pages_from_existing_input(tmp_path):
    source_path = _write_json(tmp_path, _SOURCE_PAGES)

    document, plan = build_lesson_pages("proofread", source_path, None)

    assert [p.page_no for p in document.pages] == [1, 2]
    assert plan is None


def test_proofread_page_count_matches_input(tmp_path):
    source_path = _write_json(tmp_path, _SOURCE_PAGES)

    document, _ = build_lesson_pages("proofread", source_path, None)

    assert len(document.pages) == len(_SOURCE_PAGES["pages"])


def test_proofread_preserves_page_order_and_dialogue_text_verbatim(tmp_path):
    """proofreadでは「元資料の趣旨が神」であり、ページ順・重要な発言内容を勝手に落とさない。"""
    source = {
        "project_title": "テスト教材",
        "target_reader": "テスター",
        "pages": [
            {
                "page_no": 1,
                "source_image": "a.png",
                "title": "第1回",
                "summary": "概要1",
                "lines": [{"speaker": "講師", "text": "重要な結論その1です。"}],
            },
            {
                "page_no": 2,
                "source_image": "b.png",
                "title": "第2回",
                "summary": "概要2",
                "lines": [{"speaker": "講師", "text": "重要な結論その2です。"}],
            },
        ],
    }
    source_path = _write_json(tmp_path, source)

    document, _ = build_lesson_pages("proofread", source_path, None)

    assert [p.page_no for p in document.pages] == [1, 2]
    assert [p.title for p in document.pages] == ["第1回", "第2回"]
    assert "重要な結論その1です。" in document.pages[0].body
    assert "重要な結論その2です。" in document.pages[1].body


def test_proofread_metadata_mode_is_proofread(tmp_path):
    source_path = _write_json(tmp_path, _SOURCE_PAGES)

    document, _ = build_lesson_pages("proofread", source_path, None)

    assert document.metadata.mode == "proofread"


def test_proofread_source_page_no_is_single_element_array(tmp_path):
    source_path = _write_json(tmp_path, _SOURCE_PAGES)

    document, _ = build_lesson_pages("proofread", source_path, None)

    assert document.pages[0].source_page_no == [1]
    assert document.pages[1].source_page_no == [2]


# --- restructure ---------------------------------------------------------------


def test_restructure_metadata_mode_is_restructure(tmp_path):
    source_path = _write_json(tmp_path, _SOURCE_PAGES)

    document, _ = build_lesson_pages("restructure", source_path, None)

    assert document.metadata.mode == "restructure"


def test_restructure_adds_intro_and_summary_pages(tmp_path):
    source_path = _write_json(tmp_path, _RESTRUCTURE_SOURCE_PAGES)

    document, _ = build_lesson_pages("restructure", source_path, None)

    assert document.pages[0].role == "intro"
    assert document.pages[-1].role == "summary"


def test_restructure_adds_practice_page(tmp_path):
    source_path = _write_json(tmp_path, _RESTRUCTURE_SOURCE_PAGES)

    document, _ = build_lesson_pages("restructure", source_path, None)

    assert any(page.role == "practice" for page in document.pages)


def test_practice_and_summary_body_do_not_contain_bullet_markup(tmp_path):
    """practice/summaryのbodyにMarkdown箇条書き記号("- ")が直接埋め込まれていないこと。

    埋め込まれていると、brushup.md/DOCX/PDF側の箇条書きレンダリングと二重になる
    （例:「• - サンプル記事 001」）。
    """
    source_path = _write_json(tmp_path, _RESTRUCTURE_SOURCE_PAGES)

    document, _ = build_lesson_pages("restructure", source_path, None)

    practice_page = next(p for p in document.pages if p.role == "practice")
    summary_page = next(p for p in document.pages if p.role == "summary")

    for page in (practice_page, summary_page):
        for line in page.body.splitlines():
            assert not line.startswith("- "), f"body行が'- 'で始まっています: {line!r}"


def test_restructure_page_count_is_not_fixed_to_source_count(tmp_path):
    source_path = _write_json(tmp_path, _RESTRUCTURE_SOURCE_PAGES)

    document, _ = build_lesson_pages("restructure", source_path, None)

    assert len(document.pages) != len(_RESTRUCTURE_SOURCE_PAGES["pages"])


def test_restructure_merges_short_orphan_page_with_next(tmp_path):
    source_path = _write_json(tmp_path, _RESTRUCTURE_SOURCE_PAGES)

    document, plan = build_lesson_pages("restructure", source_path, None)

    merge_pages = [p for p in plan["pages"] if p["operation"] == "merge"]
    assert len(merge_pages) == 1
    assert merge_pages[0]["source_page_no"] == [1, 2]

    merged_document_page = next(p for p in document.pages if p.source_page_no == [1, 2])
    assert merged_document_page.role == "explanation"


def test_restructure_keeps_unmerged_page_as_carry_over(tmp_path):
    source_path = _write_json(tmp_path, _RESTRUCTURE_SOURCE_PAGES)

    document, plan = build_lesson_pages("restructure", source_path, None)

    carry_over_pages = [p for p in plan["pages"] if p["operation"] == "carry_over"]
    assert len(carry_over_pages) == 1
    assert carry_over_pages[0]["source_page_no"] == [3]


def test_restructure_splits_long_single_page(tmp_path):
    source_path = _write_json(tmp_path, _LONG_PAGE_SOURCE)

    document, plan = build_lesson_pages("restructure", source_path, None)

    split_ops = [p["operation"] for p in plan["pages"] if p["operation"].startswith("split_")]
    assert split_ops == ["split_first_half", "split_second_half"]

    split_document_pages = [p for p in document.pages if p.role == "explanation"]
    assert len(split_document_pages) == 2
    assert all(p.source_page_no == [1] for p in split_document_pages)
    assert split_document_pages[0].body != split_document_pages[1].body


def test_restructure_merge_page_combines_layout_instruction_and_uses_first_source_image(tmp_path):
    source_path = _write_json(tmp_path, _RESTRUCTURE_SOURCE_PAGES)

    document, _ = build_lesson_pages("restructure", source_path, None)

    merged_page = next(p for p in document.pages if p.source_page_no == [1, 2])
    assert merged_page.layout_instruction == "中央にAIのイラスト / 左にChatGPTのロゴ"
    assert merged_page.source_image == "a.png"


def test_restructure_merge_body_includes_source_titles_as_headings(tmp_path):
    source_path = _write_json(tmp_path, _RESTRUCTURE_SOURCE_PAGES)

    document, _ = build_lesson_pages("restructure", source_path, None)

    merged_page = next(p for p in document.pages if p.source_page_no == [1, 2])
    assert "## AIとは" in merged_page.body
    assert "## ChatGPTとは" in merged_page.body


def test_restructure_merge_derived_fields_do_not_contain_heading_markup(tmp_path):
    """bodyの見出し記法(##)はimage_text/canva_prompt/video_sceneには混入しないが、
    自然文としてタイトルの内容自体は残る。"""
    source_path = _write_json(tmp_path, _RESTRUCTURE_SOURCE_PAGES)

    document, _ = build_lesson_pages("restructure", source_path, None)

    merged_page = next(p for p in document.pages if p.source_page_no == [1, 2])
    assert "#" not in merged_page.image_text
    assert "#" not in merged_page.canva_prompt
    assert "#" not in merged_page.video_scene

    assert "AIとは" in merged_page.image_text
    assert "ChatGPTとは" in merged_page.canva_prompt


def test_derived_fields_preserve_leading_hashtag_text(tmp_path):
    """"##"見出し記法は除去するが、"#タグ"のようなハッシュタグ形式の文字列は誤って除去しない。"""
    source = {
        "project_title": "SNS教材",
        "target_reader": "読者",
        "pages": [
            {
                "page_no": 1,
                "source_image": "a.png",
                "title": "投稿例",
                "summary": "",
                "lines": [{"speaker": "投稿文", "text": "#AI初心者 におすすめの使い方です"}],
            },
        ],
    }
    source_path = _write_json(tmp_path, source)

    document, _ = build_lesson_pages("proofread", source_path, None)

    assert "#AI初心者" in document.pages[0].image_text


def test_restructure_carry_over_page_keeps_layout_instruction_and_source_image(tmp_path):
    source_path = _write_json(tmp_path, _RESTRUCTURE_SOURCE_PAGES)

    document, _ = build_lesson_pages("restructure", source_path, None)

    carry_over_page = next(p for p in document.pages if p.source_page_no == [3])
    assert carry_over_page.layout_instruction == "下部に手順アイコン"
    assert carry_over_page.source_image == "c.png"


def test_restructure_split_pages_inherit_layout_instruction_and_source_image(tmp_path):
    source_path = _write_json(tmp_path, _LONG_PAGE_SOURCE)

    document, _ = build_lesson_pages("restructure", source_path, None)

    split_pages = [p for p in document.pages if p.role == "explanation"]
    assert len(split_pages) == 2
    for page in split_pages:
        assert page.layout_instruction == "全面にテキストを配置"
        assert page.source_image == "a.png"


def test_proofread_carries_source_assets_through(tmp_path):
    source = {
        "project_title": "画像取り込み教材",
        "target_reader": "読者",
        "pages": [
            {
                "page_no": 1,
                "source_image": "assets/slide_001_1.png",
                "source_assets": ["assets/slide_001_2.png", "assets/slide_001_3.png"],
                "title": "スライド1",
                "summary": "",
                "lines": [],
            },
        ],
    }
    source_path = _write_json(tmp_path, source)

    document, _ = build_lesson_pages("proofread", source_path, None)

    assert document.pages[0].source_assets == ["assets/slide_001_2.png", "assets/slide_001_3.png"]


def test_restructure_merge_page_unions_source_assets_without_duplicates(tmp_path):
    source = {
        "project_title": "画像取り込み教材",
        "target_reader": "読者",
        "pages": [
            {
                "page_no": 1,
                "source_image": "a.png",
                "source_assets": ["shared.png", "a_extra.png"],
                "title": "AIとは",
                "summary": "",
                "lines": [{"speaker": "講師", "text": "AIとは"}],
            },
            {
                "page_no": 2,
                "source_image": "b.png",
                "source_assets": ["shared.png", "b_extra.png"],
                "title": "ChatGPTとは",
                "summary": "",
                "lines": [{"speaker": "講師", "text": "ChatGPTは、AIを使った対話サービスです。使い方を覚えると投稿文作りが楽になります。"}],
            },
        ],
    }
    source_path = _write_json(tmp_path, source)

    document, _ = build_lesson_pages("restructure", source_path, None)

    merged_page = next(p for p in document.pages if p.source_page_no == [1, 2])
    assert merged_page.source_assets == ["shared.png", "a_extra.png", "b_extra.png"]


def test_restructure_intro_practice_summary_have_role_based_layout_instruction(tmp_path):
    source_path = _write_json(tmp_path, _RESTRUCTURE_SOURCE_PAGES)

    document, _ = build_lesson_pages("restructure", source_path, None)

    intro_page = next(p for p in document.pages if p.role == "intro")
    practice_page = next(p for p in document.pages if p.role == "practice")
    summary_page = next(p for p in document.pages if p.role == "summary")

    assert intro_page.layout_instruction and "導入" in intro_page.layout_instruction
    assert practice_page.layout_instruction and "実践" in practice_page.layout_instruction
    assert summary_page.layout_instruction and "まとめ" in summary_page.layout_instruction

    # 元ページのlayout_instructionをそのまま流用したものではないことを確認する
    assert intro_page.layout_instruction not in {"中央にAIのイラスト", "左にChatGPTのロゴ", "下部に手順アイコン"}


def test_apply_restructure_plan_raises_value_error_for_missing_source_on_merge(tmp_path):
    source_path = _write_json(tmp_path, _RESTRUCTURE_SOURCE_PAGES)
    document = load_lesson_document(source_path)
    bad_plan = {
        "mode": "restructure",
        "strategy": "test",
        "pages": [
            {"new_page_no": 1, "role": "explanation", "title": "X", "source_page_no": [999, 998], "operation": "merge"},
        ],
    }

    with pytest.raises(ValueError, match="restructure_planが不正です"):
        apply_restructure_plan(document, bad_plan, None)


def test_apply_restructure_plan_raises_value_error_for_missing_source_on_split(tmp_path):
    source_path = _write_json(tmp_path, _RESTRUCTURE_SOURCE_PAGES)
    document = load_lesson_document(source_path)
    bad_plan = {
        "mode": "restructure",
        "strategy": "test",
        "pages": [
            {"new_page_no": 1, "role": "explanation", "title": "X", "source_page_no": [999], "operation": "split_first_half"},
        ],
    }

    with pytest.raises(ValueError, match="restructure_planが不正です"):
        apply_restructure_plan(document, bad_plan, None)


def test_apply_restructure_plan_raises_value_error_for_missing_source_on_carry_over(tmp_path):
    source_path = _write_json(tmp_path, _RESTRUCTURE_SOURCE_PAGES)
    document = load_lesson_document(source_path)
    bad_plan = {
        "mode": "restructure",
        "strategy": "test",
        "pages": [
            {"new_page_no": 1, "role": "explanation", "title": "X", "source_page_no": [999], "operation": "carry_over"},
        ],
    }

    with pytest.raises(ValueError, match="restructure_planが不正です"):
        apply_restructure_plan(document, bad_plan, None)


def test_apply_restructure_plan_tolerates_empty_sources_for_aggregate_roles(tmp_path):
    """intro/practice/summaryは教材全体の集約ページのため、空document(元ページ0件)でも例外にしない。"""
    source_path = _write_json(tmp_path, {"project_title": "空教材", "target_reader": "読者", "pages": []})
    document = load_lesson_document(source_path)
    plan = build_restructure_plan(document, requirements=None)

    result = apply_restructure_plan(document, plan, requirements=None)

    assert result.metadata.mode == "restructure"
    assert any(p.role == "intro" for p in result.pages)


def test_restructure_applies_requirements_target_audience_and_tone(tmp_path):
    source_path = _write_json(tmp_path, _SOURCE_PAGES)
    requirements_path = tmp_path / "requirements.json"
    requirements_path.write_text(json.dumps(_REQUIREMENTS, ensure_ascii=False), encoding="utf-8")

    document, _ = build_lesson_pages("restructure", source_path, str(requirements_path))

    assert document.metadata.target_audience == "テスト対象読者"
    assert document.metadata.tone == "テストトーン"


def test_restructure_plan_has_expected_structure(tmp_path):
    source_path = _write_json(tmp_path, _RESTRUCTURE_SOURCE_PAGES)

    _, plan = build_lesson_pages("restructure", source_path, None)

    assert plan["mode"] == "restructure"
    assert isinstance(plan["strategy"], str) and plan["strategy"]
    for plan_page in plan["pages"]:
        assert {"new_page_no", "role", "title", "source_page_no", "operation"} <= plan_page.keys()


def test_build_restructure_plan_and_apply_restructure_plan_are_independently_usable(tmp_path):
    source_path = _write_json(tmp_path, _RESTRUCTURE_SOURCE_PAGES)
    document = load_lesson_document(source_path)

    plan = build_restructure_plan(document, requirements=None)
    result = apply_restructure_plan(document, plan, requirements=None)

    assert result.metadata.mode == "restructure"
    assert len(result.pages) == len(plan["pages"])


# --- generate ---------------------------------------------------------------


def test_generate_builds_lesson_pages_from_requirements_only(tmp_path):
    requirements_path = tmp_path / "requirements.json"
    requirements_path.write_text(json.dumps(_REQUIREMENTS, ensure_ascii=False), encoding="utf-8")

    document, plan = build_lesson_pages("generate", None, str(requirements_path))

    assert len(document.pages) > 0
    titles = [p.title for p in document.pages]
    assert "要素A" in titles
    assert "要素B" in titles
    assert plan is None


def test_generate_metadata_mode_is_generate(tmp_path):
    requirements_path = tmp_path / "requirements.json"
    requirements_path.write_text(json.dumps(_REQUIREMENTS, ensure_ascii=False), encoding="utf-8")

    document, _ = build_lesson_pages("generate", None, str(requirements_path))

    assert document.metadata.mode == "generate"


def test_generate_source_page_no_is_empty_for_all_pages(tmp_path):
    requirements_path = tmp_path / "requirements.json"
    requirements_path.write_text(json.dumps(_REQUIREMENTS, ensure_ascii=False), encoding="utf-8")

    document, _ = build_lesson_pages("generate", None, str(requirements_path))

    assert all(page.source_page_no == [] for page in document.pages)


# --- errors ---------------------------------------------------------------


def test_generate_without_requirements_raises_error():
    with pytest.raises(ValueError, match="requirements"):
        build_lesson_pages("generate", None, None)


def test_proofread_without_input_raises_error():
    with pytest.raises(ValueError, match="input"):
        build_lesson_pages("proofread", None, None)


def test_restructure_without_input_raises_error():
    with pytest.raises(ValueError, match="input"):
        build_lesson_pages("restructure", None, None)


def test_unknown_mode_raises_error(tmp_path):
    source_path = _write_json(tmp_path, _SOURCE_PAGES)

    with pytest.raises(ValueError, match="未知のmode"):
        build_lesson_pages("unknown-mode", source_path, None)


# --- review report ---------------------------------------------------------------


def test_render_review_report_lists_role_and_source_page_no(tmp_path):
    source_path = _write_json(tmp_path, _RESTRUCTURE_SOURCE_PAGES)
    document, _ = build_lesson_pages("restructure", source_path, None)

    report = render_review_report(document)

    assert "role: intro" in report
    assert "source_page_no: 1, 2" in report or "source_page_no: 1" in report
