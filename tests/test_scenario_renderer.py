import json

from src.lesson_pages import (
    LessonPage,
    build_lesson_document,
    build_lesson_pages,
    dialogue_lines_for_scenario,
)
from src.models import project_from_dict
from src.scenario_renderer import (
    render_scenario_json,
    render_scenario_markdown,
    render_scene_json,
    render_voicevox_text,
    write_scenario_outputs,
)

_MERGE_SOURCE_PAGES = {
    "project_title": "SNS教材",
    "target_reader": "初心者",
    "pages": [
        {"page_no": 1, "source_image": "a.png", "title": "AIとは", "summary": "", "lines": [{"speaker": "講師", "text": "AIとは"}]},
        {
            "page_no": 2,
            "source_image": "b.png",
            "title": "ChatGPTとは",
            "summary": "",
            "lines": [{"speaker": "講師", "text": "ChatGPTは、AIを使った対話サービスです。使い方を覚えると投稿文作りが楽になります。"}],
        },
    ],
}


def _restructured_document(tmp_path):
    source_path = tmp_path / "source.json"
    source_path.write_text(json.dumps(_MERGE_SOURCE_PAGES, ensure_ascii=False), encoding="utf-8")
    document, _ = build_lesson_pages("restructure", str(source_path), None)
    return document


def _document():
    project = project_from_dict({
        "project_title": "テスト教材",
        "target_reader": "テスター",
        "pages": [
            {
                "page_no": 1,
                "source_image": "a.png",
                "title": "P1",
                "summary": "概要",
                "lines": [
                    {"speaker": "状況説明者", "text": "むかしむかし"},
                    {"speaker": "まじょこ", "text": "こんにちは"},
                ],
                "canva": {"main_visual": "中央に人物", "notes": "余白を広めに"},
            },
            {"page_no": 2, "source_image": "b.png", "title": "P2", "summary": "概要2"},
        ],
    })
    return build_lesson_document(project)


def test_render_scenario_json_lists_lines_in_order():
    data = json.loads(render_scenario_json(_document()))
    assert data["project_title"] == "テスト教材"
    assert [s["text"] for s in data["scenes"]] == ["むかしむかし", "こんにちは"]
    assert data["scenes"][0]["order"] == 1
    assert data["scenes"][0]["page_no"] == 1


def test_render_scenario_markdown_contains_speakers_and_lines():
    md = render_scenario_markdown(_document())
    assert "# シナリオ: テスト教材" in md
    assert "**状況説明者**: むかしむかし" in md
    assert "(台詞なし)" in md


def test_render_voicevox_text_formats_speaker_blocks():
    text = render_voicevox_text(_document())
    assert "[状況説明者]\nむかしむかし" in text
    assert "[まじょこ]\nこんにちは" in text


def test_render_scene_json_combines_canva_and_dialogue():
    data = json.loads(render_scene_json(_document()))
    scene1 = data["scenes"][0]
    assert scene1["visual_prompt"] == "中央に人物。余白を広めに"
    assert scene1["dialogue_text"] == "状況説明者: むかしむかし / まじょこ: こんにちは"
    assert scene1["lines"] == [
        {"speaker": "状況説明者", "text": "むかしむかし"},
        {"speaker": "まじょこ", "text": "こんにちは"},
    ]


# --- Markdown見出し記法(##)の非混入 ---------------------------------------------


def test_scenario_json_scenes_do_not_contain_heading_markup(tmp_path):
    document = _restructured_document(tmp_path)
    data = json.loads(render_scenario_json(document))
    assert all("#" not in scene["text"] for scene in data["scenes"])


def test_scenario_markdown_does_not_contain_merged_source_titles_as_headings(tmp_path):
    document = _restructured_document(tmp_path)
    md = render_scenario_markdown(document)
    assert "## AIとは" not in md
    assert "## ChatGPTとは" not in md


def test_voicevox_text_does_not_contain_heading_markup(tmp_path):
    document = _restructured_document(tmp_path)
    text = render_voicevox_text(document)
    assert "#" not in text


def test_scene_json_does_not_contain_heading_markup(tmp_path):
    document = _restructured_document(tmp_path)
    data = json.loads(render_scene_json(document))
    for scene in data["scenes"]:
        assert "#" not in scene["dialogue_text"]
        assert all("#" not in line["text"] for line in scene["lines"])


# --- Markdown箇条書き記号("- ")の非混入 -----------------------------------------


def test_scenario_markdown_does_not_double_up_bullet_markers(tmp_path):
    document = _restructured_document(tmp_path)
    md = render_scenario_markdown(document)
    assert "- - " not in md


def test_scenario_json_scenes_do_not_start_with_bullet_marker(tmp_path):
    document = _restructured_document(tmp_path)
    data = json.loads(render_scenario_json(document))
    assert not any(scene["text"].startswith("- ") for scene in data["scenes"])


def test_voicevox_text_does_not_contain_bullet_markup(tmp_path):
    document = _restructured_document(tmp_path)
    text = render_voicevox_text(document)
    assert "- " not in text


# --- video_sceneの優先利用・フォールバック ---------------------------------------


def _bare_page(body: str, video_scene: str) -> LessonPage:
    return LessonPage(
        page_no=1,
        title="P1",
        body=body,
        summary="",
        image_text="",
        layout_instruction="",
        canva_prompt="",
        video_scene=video_scene,
        source_image="",
        notes="",
    )


def test_dialogue_lines_for_scenario_prefers_video_scene_when_present():
    page = _bare_page(
        body="## 見出し\n講師: 本文由来のテキスト",
        video_scene="台詞: 講師: video_scene由来のテキスト",
    )

    assert dialogue_lines_for_scenario(page) == [("講師", "video_scene由来のテキスト")]


def test_dialogue_lines_for_scenario_falls_back_to_cleaned_body_when_video_scene_empty():
    page = _bare_page(
        body="## 見出し\n講師: 本文由来のテキスト",
        video_scene="",
    )

    lines = dialogue_lines_for_scenario(page)

    assert ("", "見出し") in lines
    assert ("講師", "本文由来のテキスト") in lines
    assert not any("#" in text for _, text in lines)


def test_write_scenario_outputs_creates_four_files(tmp_path):
    output_dir = tmp_path / "scenario_out"
    write_scenario_outputs(output_dir, _document())

    assert (output_dir / "scenario.json").exists()
    assert (output_dir / "scenario.md").exists()
    assert (output_dir / "voicevox.txt").exists()
    assert (output_dir / "scene.json").exists()
