from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_WINDOWS_ABS_PATH_PATTERN = re.compile(r"^[a-zA-Z]:[\\/]")

VALID_MODES: tuple[str, ...] = ("proofread", "restructure", "generate")

_REQUIREMENTS_STRING_FIELDS = (
    "theme",
    "target_audience",
    "goal",
    "reader_problem",
    "promised_value",
    "tone",
    "output_style",
)
_REQUIREMENTS_LIST_FIELDS = ("must_include", "must_not_include")


@dataclass
class Requirements:
    theme: str = ""
    target_audience: str = ""
    goal: str = ""
    reader_problem: str = ""
    promised_value: str = ""
    tone: str = ""
    output_style: str = ""
    page_count: int | None = None
    must_include: list[str] = field(default_factory=list)
    must_not_include: list[str] = field(default_factory=list)


@dataclass
class DialogueLine:
    speaker: str
    text: str


@dataclass
class CanvaInfo:
    layout_type: str = ""
    main_visual: str = ""
    notes: str = ""


@dataclass
class Page:
    page_no: int
    source_image: str
    title: str
    summary: str
    lines: list[DialogueLine] = field(default_factory=list)
    improvement_points: list[str] = field(default_factory=list)
    canva: CanvaInfo = field(default_factory=CanvaInfo)
    source_assets: list[str] = field(default_factory=list)


@dataclass
class Project:
    project_title: str
    target_reader: str
    pages: list[Page]


def _validate_source_image(page_no: int, source_image: Any) -> str:
    if not isinstance(source_image, str):
        raise ValueError(f"page_no={page_no} の source_image は文字列で指定してください: {source_image!r}")
    if not source_image:
        return source_image

    normalized = source_image.replace("\\", "/")
    if (
        normalized.startswith("/")
        or _WINDOWS_ABS_PATH_PATTERN.match(source_image)
        or ".." in normalized.split("/")
    ):
        raise ValueError(
            f"page_no={page_no} の source_image に絶対パスや親ディレクトリ参照(..)は指定できません: {source_image!r}"
        )
    return source_image


def page_from_dict(data: dict[str, Any]) -> Page:
    if not isinstance(data, dict):
        raise ValueError(f"ページデータがオブジェクト形式ではありません: {data!r}")
    if "page_no" not in data:
        raise ValueError(f"ページに page_no が指定されていません: {data!r}")
    try:
        page_no = int(data["page_no"])
    except (TypeError, ValueError) as e:
        raise ValueError(f"page_no は整数で指定してください: {data['page_no']!r}") from e

    raw_lines = data.get("lines", [])
    if not isinstance(raw_lines, list):
        raise ValueError(f"page_no={page_no} の lines はリスト形式で指定してください: {raw_lines!r}")

    lines: list[DialogueLine] = []
    for i, line in enumerate(raw_lines):
        if not isinstance(line, dict):
            raise ValueError(f"page_no={page_no} の lines[{i}] がオブジェクト形式ではありません: {line!r}")
        try:
            dialogue = DialogueLine(**line)
        except TypeError as e:
            raise ValueError(
                f"page_no={page_no} の lines[{i}] は speaker と text のみ指定できます: {line!r}"
            ) from e
        if not isinstance(dialogue.speaker, str):
            raise ValueError(
                f"page_no={page_no} の lines[{i}].speaker は文字列で指定してください: {dialogue.speaker!r}"
            )
        if not isinstance(dialogue.text, str):
            raise ValueError(
                f"page_no={page_no} の lines[{i}].text は文字列で指定してください: {dialogue.text!r}"
            )
        lines.append(dialogue)

    improvement_points = data.get("improvement_points", [])
    if not isinstance(improvement_points, list):
        raise ValueError(
            f"page_no={page_no} の improvement_points はリスト形式で指定してください: {improvement_points!r}"
        )
    for i, point in enumerate(improvement_points):
        if not isinstance(point, str):
            raise ValueError(
                f"page_no={page_no} の improvement_points[{i}] は文字列で指定してください: {point!r}"
            )

    canva_data = data.get("canva", {})
    if not isinstance(canva_data, dict):
        raise ValueError(f"page_no={page_no} の canva がオブジェクト形式ではありません: {canva_data!r}")
    try:
        canva = CanvaInfo(**canva_data)
    except TypeError as e:
        raise ValueError(
            f"page_no={page_no} の canva は layout_type/main_visual/notes のみ指定できます: {canva_data!r}"
        ) from e

    source_image = _validate_source_image(page_no, data.get("source_image", ""))

    raw_source_assets = data.get("source_assets", [])
    if not isinstance(raw_source_assets, list):
        raise ValueError(
            f"page_no={page_no} の source_assets はリスト形式で指定してください: {raw_source_assets!r}"
        )
    source_assets: list[str] = []
    for i, asset in enumerate(raw_source_assets):
        if not isinstance(asset, str):
            raise ValueError(
                f"page_no={page_no} の source_assets[{i}] は文字列で指定してください: {asset!r}"
            )
        source_assets.append(_validate_source_image(page_no, asset))

    return Page(
        page_no=page_no,
        source_image=source_image,
        title=data.get("title", ""),
        summary=data.get("summary", ""),
        lines=lines,
        improvement_points=improvement_points,
        canva=canva,
        source_assets=source_assets,
    )


def requirements_from_dict(data: dict[str, Any]) -> Requirements:
    if not isinstance(data, dict):
        raise ValueError(f"requirementsがオブジェクト形式ではありません: {data!r}")

    string_values: dict[str, str] = {}
    for field_name in _REQUIREMENTS_STRING_FIELDS:
        value = data.get(field_name, "")
        if not isinstance(value, str):
            raise ValueError(f"requirementsの{field_name}は文字列で指定してください: {value!r}")
        string_values[field_name] = value

    list_values: dict[str, list[str]] = {}
    for field_name in _REQUIREMENTS_LIST_FIELDS:
        raw_value = data.get(field_name, [])
        if not isinstance(raw_value, list):
            raise ValueError(f"requirementsの{field_name}はリスト形式で指定してください: {raw_value!r}")
        for i, item in enumerate(raw_value):
            if not isinstance(item, str):
                raise ValueError(f"requirementsの{field_name}[{i}]は文字列で指定してください: {item!r}")
        list_values[field_name] = raw_value

    page_count = data.get("page_count")
    if page_count is not None and not isinstance(page_count, int):
        raise ValueError(f"requirementsのpage_countは整数で指定してください: {page_count!r}")

    return Requirements(
        theme=string_values["theme"],
        target_audience=string_values["target_audience"],
        goal=string_values["goal"],
        reader_problem=string_values["reader_problem"],
        promised_value=string_values["promised_value"],
        tone=string_values["tone"],
        output_style=string_values["output_style"],
        page_count=page_count,
        must_include=list_values["must_include"],
        must_not_include=list_values["must_not_include"],
    )


def project_from_dict(data: dict[str, Any]) -> Project:
    if not isinstance(data, dict):
        raise ValueError(f"入力データがオブジェクト形式ではありません: {data!r}")

    raw_pages = data.get("pages", [])
    if not isinstance(raw_pages, list):
        raise ValueError(f"pages はリスト形式で指定してください: {raw_pages!r}")

    pages = [page_from_dict(page) for page in raw_pages]

    page_nos = [page.page_no for page in pages]
    duplicates = sorted({no for no in page_nos if page_nos.count(no) > 1})
    if duplicates:
        raise ValueError(f"page_no が重複しています: {duplicates}")

    pages.sort(key=lambda page: page.page_no)
    return Project(
        project_title=data.get("project_title", "教材ブラッシュアップ設計書"),
        target_reader=data.get("target_reader", "教材制作者"),
        pages=pages,
    )
