from dataclasses import dataclass, field
from typing import Any


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


@dataclass
class Project:
    project_title: str
    target_reader: str
    pages: list[Page]


def page_from_dict(data: dict[str, Any]) -> Page:
    lines = [DialogueLine(**line) for line in data.get("lines", [])]
    canva = CanvaInfo(**data.get("canva", {}))
    return Page(
        page_no=int(data["page_no"]),
        source_image=data.get("source_image", ""),
        title=data.get("title", ""),
        summary=data.get("summary", ""),
        lines=lines,
        improvement_points=data.get("improvement_points", []),
        canva=canva,
    )


def project_from_dict(data: dict[str, Any]) -> Project:
    pages = [page_from_dict(page) for page in data.get("pages", [])]
    pages.sort(key=lambda page: page.page_no)
    return Project(
        project_title=data.get("project_title", "教材ブラッシュアップ設計書"),
        target_reader=data.get("target_reader", "教材制作者"),
        pages=pages,
    )
