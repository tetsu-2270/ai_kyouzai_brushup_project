from __future__ import annotations

import json
from pathlib import Path

from .lesson_pages import LessonDocument, dialogue_lines_for_scenario


def build_scenario_data(document: LessonDocument) -> dict:
    scenes = []
    order = 0
    for page in document.pages:
        for speaker, text in dialogue_lines_for_scenario(page):
            order += 1
            scenes.append({
                "page_no": page.page_no,
                "order": order,
                "speaker": speaker,
                "text": text,
                "source_image": page.source_image,
            })
    return {"project_title": document.project_title, "scenes": scenes}


def render_scenario_json(document: LessonDocument) -> str:
    return json.dumps(build_scenario_data(document), ensure_ascii=False, indent=2) + "\n"


def render_scenario_markdown(document: LessonDocument) -> str:
    lines = [f"# シナリオ: {document.project_title}", ""]
    for page in document.pages:
        lines.append(f"## Page {page.page_no}: {page.title}")
        lines.append("")
        parsed = dialogue_lines_for_scenario(page)
        if parsed:
            for speaker, text in parsed:
                lines.append(f"- **{speaker}**: {text}" if speaker else f"- {text}")
        else:
            lines.append("- (台詞なし)")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_voicevox_text(document: LessonDocument) -> str:
    blocks = [
        f"[{speaker or 'ナレーション'}]\n{text}"
        for page in document.pages
        for speaker, text in dialogue_lines_for_scenario(page)
    ]
    return "\n\n".join(blocks).rstrip() + "\n"


def build_scene_data(document: LessonDocument) -> dict:
    scenes = []
    for page in document.pages:
        parsed = dialogue_lines_for_scenario(page)
        visual_prompt = "。".join(part for part in [page.layout_instruction, page.notes] if part)
        dialogue_text = " / ".join(f"{speaker}: {text}" if speaker else text for speaker, text in parsed)
        scenes.append({
            "scene_no": page.page_no,
            "page_no": page.page_no,
            "visual_prompt": visual_prompt,
            "dialogue_text": dialogue_text,
            "lines": [{"speaker": speaker, "text": text} for speaker, text in parsed],
        })
    return {"project_title": document.project_title, "scenes": scenes}


def render_scene_json(document: LessonDocument) -> str:
    return json.dumps(build_scene_data(document), ensure_ascii=False, indent=2) + "\n"


def write_scenario_outputs(output_dir: str | Path, document: LessonDocument) -> None:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    (output_path / "scenario.json").write_text(render_scenario_json(document), encoding="utf-8")
    (output_path / "scenario.md").write_text(render_scenario_markdown(document), encoding="utf-8")
    (output_path / "voicevox.txt").write_text(render_voicevox_text(document), encoding="utf-8")
    (output_path / "scene.json").write_text(render_scene_json(document), encoding="utf-8")
