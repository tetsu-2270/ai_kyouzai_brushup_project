from __future__ import annotations

import json
from pathlib import Path

from .lesson_pages import (
    LessonDocument,
    build_lesson_document,
    is_lesson_pages_format,
    lesson_document_from_dict,
    project_from_lesson_document,
)
from .models import Project, Requirements, project_from_dict, requirements_from_dict


def _read_json(path: str | Path) -> dict:
    input_path = Path(path)
    if not input_path.exists():
        raise FileNotFoundError(f"入力ファイルが見つかりません: {input_path}")

    try:
        text = input_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        raise ValueError(
            f"入力ファイルがUTF-8として読み込めません: {input_path} ({e})"
        ) from e

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"入力ファイルのJSONが不正です: {input_path} "
            f"({e.lineno}行目 {e.colno}列目: {e.msg})"
        ) from e


def load_project(path: str | Path) -> Project:
    """入力JSONを読み込みProjectを返す。

    canva-sync/wp-publish向け。従来のpages形式（linesを持つ）ならそのまま読み込み、
    lesson_pages形式（bodyを持つ）ならProjectへ変換して読み込む
    （lesson_pages形式にはimprovement_pointsに相当する項目が無いため空リストになる）。
    """
    data = _read_json(path)
    if is_lesson_pages_format(data):
        document = lesson_document_from_dict(data)
        return project_from_lesson_document(document)
    return project_from_dict(data)


def load_lesson_document(path: str | Path) -> LessonDocument:
    """入力JSONを読み込みLessonDocumentを返す。

    lesson_pages形式（bodyを持つ）ならそのまま読み込み、
    従来のpages形式（linesを持つ）ならProjectを経由してLessonDocumentへ変換する。
    """
    data = _read_json(path)
    if is_lesson_pages_format(data):
        return lesson_document_from_dict(data)

    project = project_from_dict(data)
    return build_lesson_document(project)


def load_requirements(path: str | Path) -> Requirements:
    """要件定義JSON（requirements.json）を読み込みRequirementsを返す。"""
    data = _read_json(path)
    return requirements_from_dict(data)
