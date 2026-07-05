from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Flowable, ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer

from .lesson_pages import LessonDocument, parse_body_lines

_FONT_NAME = "HeiseiKakuGo-W5"
if _FONT_NAME not in pdfmetrics.getRegisteredFontNames():
    pdfmetrics.registerFont(UnicodeCIDFont(_FONT_NAME))


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("JPTitle", parent=base["Title"], fontName=_FONT_NAME, fontSize=20, leading=26),
        "heading1": ParagraphStyle("JPHeading1", parent=base["Heading1"], fontName=_FONT_NAME, fontSize=14, leading=20),
        "heading2": ParagraphStyle("JPHeading2", parent=base["Heading2"], fontName=_FONT_NAME, fontSize=12, leading=18),
        "body": ParagraphStyle("JPBody", parent=base["BodyText"], fontName=_FONT_NAME, fontSize=10, leading=16),
    }


def _bullet_list(items: list[str], style: ParagraphStyle) -> ListFlowable:
    return ListFlowable(
        [ListItem(Paragraph(item, style)) for item in items],
        bulletType="bullet",
    )


def render_pdf(document: LessonDocument) -> list[Flowable]:
    styles = _styles()
    story: list[Flowable] = []

    story.append(Paragraph(document.project_title, styles["title"]))
    story.append(Paragraph(f"対象読者: {document.target_reader}", styles["body"]))
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("全体方針", styles["heading1"]))
    story.append(_bullet_list(
        [
            "ページ単位で情報を整理する。",
            "話者ごとに台詞を分ける。",
            "教材として理解しやすい順序・表現に整える。",
        ],
        styles["body"],
    ))
    story.append(Spacer(1, 6 * mm))

    for page in document.pages:
        story.append(Paragraph(f"Page {page.page_no}: {page.title}", styles["heading1"]))

        story.append(Paragraph("概要", styles["heading2"]))
        story.append(Paragraph(page.summary or "未設定", styles["body"]))

        story.append(Paragraph("本文", styles["heading2"]))
        parsed = parse_body_lines(page.body)
        if parsed:
            story.append(_bullet_list(
                [f"{speaker}: {text}" if speaker else text for speaker, text in parsed],
                styles["body"],
            ))
        else:
            story.append(Paragraph("未設定", styles["body"]))

        story.append(Spacer(1, 6 * mm))

    return story


def write_pdf(path: str | Path, document: LessonDocument) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_document = SimpleDocTemplate(str(output_path), pagesize=A4)
    pdf_document.build(render_pdf(document))
