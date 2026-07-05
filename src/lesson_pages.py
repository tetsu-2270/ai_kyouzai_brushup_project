from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import CanvaInfo, DialogueLine, Page, Project, Requirements, VALID_MODES

_LINE_SEPARATOR = ": "

_STRING_FIELDS = (
    "title",
    "body",
    "summary",
    "image_text",
    "layout_instruction",
    "canva_prompt",
    "video_scene",
    "source_image",
    "notes",
    "role",
)

_METADATA_STRING_FIELDS = (
    "project_title",
    "mode",
    "source_policy",
    "target_audience",
    "tone",
    "generated_at",
    "requirements_source",
)


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


@dataclass
class LessonMetadata:
    project_title: str = "教材ブラッシュアップ設計書"
    mode: str = "proofread"
    source_policy: str = ""
    target_audience: str = "教材制作者"
    tone: str = ""
    generated_at: str = ""
    requirements_source: str = ""


@dataclass
class LessonPage:
    page_no: int
    title: str
    body: str
    summary: str
    image_text: str
    layout_instruction: str
    canva_prompt: str
    video_scene: str
    source_image: str
    notes: str
    source_page_no: list[int] = field(default_factory=list)
    role: str = ""
    source_assets: list[str] = field(default_factory=list)


@dataclass
class LessonDocument:
    metadata: LessonMetadata
    pages: list[LessonPage]

    @property
    def project_title(self) -> str:
        return self.metadata.project_title

    @property
    def target_reader(self) -> str:
        return self.metadata.target_audience


def parse_body_lines(body: str) -> list[tuple[str, str]]:
    """bodyを「話者: 台詞」形式の行として分解する。話者が無い行は空文字として扱う。"""
    parsed: list[tuple[str, str]] = []
    for raw_line in body.splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        speaker, sep, text = raw_line.partition(_LINE_SEPARATOR)
        if sep:
            parsed.append((speaker.strip(), text.strip()))
        else:
            parsed.append(("", raw_line))
    return parsed


def _body_from_lines(page: Page) -> str:
    return "\n".join(f"{line.speaker}{_LINE_SEPARATOR}{line.text}" for line in page.lines)


_HEADING_MARKUP_PATTERN = re.compile(r"^#{1,6}(?=\s|$)\s*")


def _clean_derived_text(text: str) -> str:
    """image_text/canva_prompt/video_scene生成時に、Markdown見出し記法(#/##/###等)を取り除く。

    restructureのmergeはbody中に「## タイトル」という見出し行を挿入するが、これはbrushup.md/
    DOCX/PDFの本文構造化のためのものであり、bodyからは削除しない（parse_body_linesは変更しない）。
    一方でimage_text/canva_prompt/video_sceneはCanva・動画向けの自然文として使うため、
    この3つを組み立てる際にのみ見出し記法を取り除く。
    """
    return _HEADING_MARKUP_PATTERN.sub("", text).strip()


def _clean_parsed_lines(parsed: list[tuple[str, str]]) -> list[tuple[str, str]]:
    cleaned = [(speaker, _clean_derived_text(text)) for speaker, text in parsed]
    return [(speaker, text) for speaker, text in cleaned if text]


def clean_dialogue_lines(body: str) -> list[tuple[str, str]]:
    """bodyから、Markdown見出し記法を除去した「話者・台詞」のペア一覧を取得する。

    _derive_video_sceneが内部で使うクリーニングと同じロジックを、scenario出力等の
    構造化データ生成でも再利用できるように公開する。
    """
    return _clean_parsed_lines(parse_body_lines(body))


_VIDEO_SCENE_DIALOGUE_PREFIX = "台詞: "


def dialogue_lines_from_video_scene(video_scene: str) -> list[tuple[str, str]]:
    """video_sceneの「台詞: ...」行を、bodyと同じ「speaker: text」区切りで分解し直す。

    video_sceneは通常_derive_video_sceneがbodyから機械的に再計算するため内容は一致するが、
    LessonPageを直接組み立てるなどbodyと独立してvideo_sceneが設定されるケースでも、
    video_sceneの内容をそのまま尊重できるようにする。
    """
    for line in video_scene.splitlines():
        if not line.startswith(_VIDEO_SCENE_DIALOGUE_PREFIX):
            continue
        dialogue_text = line[len(_VIDEO_SCENE_DIALOGUE_PREFIX):]
        lines: list[tuple[str, str]] = []
        for token in dialogue_text.split(" / "):
            speaker, sep, text = token.partition(_LINE_SEPARATOR)
            if sep:
                lines.append((speaker.strip(), text.strip()))
            else:
                lines.append(("", token.strip()))
        return lines
    return []


def dialogue_lines_for_scenario(page: LessonPage) -> list[tuple[str, str]]:
    """scenario出力向けに、話者・台詞のペア一覧を取得する。

    LessonPage.video_sceneが存在する場合はそれを動画・読み上げ用テキストの主情報として使い、
    空の場合のみbodyからクリーン済みテキストを生成してフォールバックする。
    """
    if page.video_scene:
        return dialogue_lines_from_video_scene(page.video_scene)
    return clean_dialogue_lines(page.body)


def _derive_image_text(title: str, body: str, summary: str) -> str:
    cleaned = _clean_parsed_lines(parse_body_lines(body))
    if cleaned:
        return " / ".join(text for _, text in cleaned)
    return summary or title


def _derive_canva_prompt(title: str, summary: str, body: str, layout_instruction: str) -> str:
    cleaned = _clean_parsed_lines(parse_body_lines(body))
    prompt_lines = [
        "縦長SNS教材デザイン。以下の内容を、スマホで読みやすい教材ページとして作成してください。",
        f"タイトル: {title}",
        f"概要: {summary}",
    ]
    if cleaned:
        joined = " / ".join(f"{speaker}{_LINE_SEPARATOR}{text}" if speaker else text for speaker, text in cleaned)
        prompt_lines.append(f"テキスト: {joined}")
    prompt_lines.append(f"レイアウト: {layout_instruction}")
    prompt_lines.append("文字は大きく、余白を広めに、重要語句を強調してください。")
    return "\n".join(prompt_lines)


def _derive_video_scene(body: str, layout_instruction: str, notes: str) -> str:
    cleaned = _clean_parsed_lines(parse_body_lines(body))
    dialogue_text = " / ".join(f"{speaker}{_LINE_SEPARATOR}{text}" if speaker else text for speaker, text in cleaned)
    visual_prompt = "。".join(part for part in [layout_instruction, notes] if part)

    scene_lines = []
    if visual_prompt:
        scene_lines.append(f"ビジュアル: {visual_prompt}")
    if dialogue_text:
        scene_lines.append(f"台詞: {dialogue_text}")
    return "\n".join(scene_lines)


def _apply_derived_fields(page: LessonPage) -> LessonPage:
    """image_text/canva_prompt/video_sceneを、常にtitle/body/summary/layout_instruction/notesから再計算する。

    これにより、bodyや他の元データを編集した場合でも、これら3項目が
    自動的に最新の内容へ同期される（原稿と画像設計の乖離を防ぐ）。
    """
    page.image_text = _derive_image_text(page.title, page.body, page.summary)
    page.canva_prompt = _derive_canva_prompt(page.title, page.summary, page.body, page.layout_instruction)
    page.video_scene = _derive_video_scene(page.body, page.layout_instruction, page.notes)
    return page


def lesson_page_from_page(page: Page) -> LessonPage:
    lesson_page = LessonPage(
        page_no=page.page_no,
        title=page.title,
        body=_body_from_lines(page),
        summary=page.summary,
        image_text="",
        layout_instruction=page.canva.main_visual,
        canva_prompt="",
        video_scene="",
        source_image=page.source_image,
        notes=page.canva.notes,
        source_page_no=[page.page_no],
        source_assets=list(page.source_assets),
    )
    return _apply_derived_fields(lesson_page)


def build_lesson_document(
    project: Project, *, mode: str = "proofread", source_policy: str = "preserve_original"
) -> LessonDocument:
    metadata = LessonMetadata(
        project_title=project.project_title,
        mode=mode,
        source_policy=source_policy,
        target_audience=project.target_reader,
        tone="",
        generated_at=_now_iso(),
    )
    return LessonDocument(
        metadata=metadata,
        pages=[lesson_page_from_page(page) for page in project.pages],
    )


def lesson_document_to_dict(document: LessonDocument) -> dict[str, Any]:
    metadata = document.metadata
    metadata_dict = {
        "project_title": metadata.project_title,
        "mode": metadata.mode,
        "source_policy": metadata.source_policy,
        "target_audience": metadata.target_audience,
        "tone": metadata.tone,
        "generated_at": metadata.generated_at,
    }
    if metadata.requirements_source:
        metadata_dict["requirements_source"] = metadata.requirements_source
    return {
        "metadata": metadata_dict,
        "pages": [
            {
                "page_no": page.page_no,
                "source_page_no": page.source_page_no,
                "role": page.role,
                "title": page.title,
                "body": page.body,
                "summary": page.summary,
                "image_text": page.image_text,
                "layout_instruction": page.layout_instruction,
                "canva_prompt": page.canva_prompt,
                "video_scene": page.video_scene,
                "source_image": page.source_image,
                "source_assets": page.source_assets,
                "notes": page.notes,
            }
            for page in document.pages
        ],
    }


def lesson_page_from_dict(data: dict[str, Any]) -> LessonPage:
    if not isinstance(data, dict):
        raise ValueError(f"lesson_pagesのページデータがオブジェクト形式ではありません: {data!r}")
    if "page_no" not in data:
        raise ValueError(f"lesson_pagesのページに page_no が指定されていません: {data!r}")
    try:
        page_no = int(data["page_no"])
    except (TypeError, ValueError) as e:
        raise ValueError(f"page_no は整数で指定してください: {data['page_no']!r}") from e

    string_values: dict[str, str] = {}
    for field_name in _STRING_FIELDS:
        value = data.get(field_name, "")
        if not isinstance(value, str):
            raise ValueError(
                f"lesson_pagesのpage_no={page_no} の {field_name} は文字列で指定してください: {value!r}"
            )
        string_values[field_name] = value

    raw_source_page_no = data.get("source_page_no", [])
    if isinstance(raw_source_page_no, int):
        raw_source_page_no = [raw_source_page_no]
    if not isinstance(raw_source_page_no, list):
        raise ValueError(
            f"lesson_pagesのpage_no={page_no} の source_page_no はリスト形式で指定してください: {raw_source_page_no!r}"
        )
    source_page_no: list[int] = []
    for i, no in enumerate(raw_source_page_no):
        try:
            source_page_no.append(int(no))
        except (TypeError, ValueError) as e:
            raise ValueError(
                f"lesson_pagesのpage_no={page_no} の source_page_no[{i}] は整数で指定してください: {no!r}"
            ) from e

    raw_source_assets = data.get("source_assets", [])
    if not isinstance(raw_source_assets, list):
        raise ValueError(
            f"lesson_pagesのpage_no={page_no} の source_assets はリスト形式で指定してください: {raw_source_assets!r}"
        )
    for i, asset in enumerate(raw_source_assets):
        if not isinstance(asset, str):
            raise ValueError(
                f"lesson_pagesのpage_no={page_no} の source_assets[{i}] は文字列で指定してください: {asset!r}"
            )

    lesson_page = LessonPage(
        page_no=page_no,
        title=string_values["title"],
        body=string_values["body"],
        summary=string_values["summary"],
        image_text=string_values["image_text"],
        layout_instruction=string_values["layout_instruction"],
        canva_prompt=string_values["canva_prompt"],
        video_scene=string_values["video_scene"],
        source_image=string_values["source_image"],
        notes=string_values["notes"],
        source_page_no=source_page_no,
        role=string_values["role"],
        source_assets=list(raw_source_assets),
    )
    return _apply_derived_fields(lesson_page)


def _metadata_from_dict(data: dict[str, Any]) -> LessonMetadata:
    raw_metadata = data.get("metadata")
    source: dict[str, Any] = raw_metadata if isinstance(raw_metadata, dict) else {}

    defaults = LessonMetadata()
    fallback = {
        "project_title": data.get("project_title", defaults.project_title),
        "target_audience": data.get("target_reader", defaults.target_audience),
    }

    values: dict[str, str] = {}
    for field_name in _METADATA_STRING_FIELDS:
        value = source.get(field_name, fallback.get(field_name, getattr(defaults, field_name)))
        if not isinstance(value, str):
            raise ValueError(f"lesson_pagesのmetadata.{field_name}は文字列で指定してください: {value!r}")
        values[field_name] = value

    if values["mode"] not in VALID_MODES:
        raise ValueError(f"lesson_pagesのmetadata.modeが不正です: {values['mode']!r}")

    return LessonMetadata(**values)


def lesson_document_from_dict(data: dict[str, Any]) -> LessonDocument:
    if not isinstance(data, dict):
        raise ValueError(f"lesson_pagesの入力データがオブジェクト形式ではありません: {data!r}")

    raw_pages = data.get("pages", [])
    if not isinstance(raw_pages, list):
        raise ValueError(f"lesson_pagesのpagesはリスト形式で指定してください: {raw_pages!r}")

    pages = [lesson_page_from_dict(page) for page in raw_pages]

    page_nos = [page.page_no for page in pages]
    duplicates = sorted({no for no in page_nos if page_nos.count(no) > 1})
    if duplicates:
        raise ValueError(f"lesson_pagesのpage_noが重複しています: {duplicates}")

    pages.sort(key=lambda page: page.page_no)
    return LessonDocument(metadata=_metadata_from_dict(data), pages=pages)


def write_lesson_pages_json(path: str | Path, document: LessonDocument) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(lesson_document_to_dict(document), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def project_from_lesson_document(document: LessonDocument) -> Project:
    """LessonDocumentをProjectへ変換する（canva-sync/wp-publishなど、Projectを前提とする機能向け）。

    lesson_pages形式には improvement_points に相当する項目が無いため空リストになる。
    """
    pages = []
    for lesson_page in document.pages:
        lines = [
            DialogueLine(speaker=speaker, text=text)
            for speaker, text in parse_body_lines(lesson_page.body)
        ]
        pages.append(Page(
            page_no=lesson_page.page_no,
            source_image=lesson_page.source_image,
            title=lesson_page.title,
            summary=lesson_page.summary,
            lines=lines,
            improvement_points=[],
            canva=CanvaInfo(layout_type="", main_visual=lesson_page.layout_instruction, notes=lesson_page.notes),
            source_assets=list(lesson_page.source_assets),
        ))
    return Project(
        project_title=document.project_title,
        target_reader=document.target_reader,
        pages=pages,
    )


def is_lesson_pages_format(data: Any) -> bool:
    """入力JSONがlesson_pages形式（body等を持つ）か、従来のpages形式（lines等を持つ）かを判定する。"""
    if not isinstance(data, dict):
        return False
    raw_pages = data.get("pages", [])
    if not isinstance(raw_pages, list):
        return False
    return any(isinstance(page, dict) and "body" in page for page in raw_pages)


def _finalize_metadata(
    document: LessonDocument, *, mode: str, source_policy: str, requirements: Requirements | None
) -> LessonDocument:
    """proofread/restructureで読み込んだLessonDocumentに、モード・要件を反映したmetadataを付け直す。"""
    metadata = document.metadata
    target_audience = requirements.target_audience if requirements and requirements.target_audience else metadata.target_audience
    tone = requirements.tone if requirements and requirements.tone else metadata.tone
    new_metadata = LessonMetadata(
        project_title=metadata.project_title,
        mode=mode,
        source_policy=source_policy,
        target_audience=target_audience,
        tone=tone,
        generated_at=_now_iso(),
        requirements_source=requirements.theme if requirements else "",
    )
    return LessonDocument(metadata=new_metadata, pages=document.pages)


def _new_lesson_page(
    page_no: int,
    title: str,
    body: str,
    summary: str,
    notes: str = "",
    source_page_no: list[int] | None = None,
    role: str = "",
    layout_instruction: str = "",
    source_image: str = "",
    source_assets: list[str] | None = None,
) -> LessonPage:
    lesson_page = LessonPage(
        page_no=page_no,
        title=title,
        body=body,
        summary=summary,
        image_text="",
        layout_instruction=layout_instruction,
        canva_prompt="",
        video_scene="",
        source_image=source_image,
        notes=notes,
        source_page_no=source_page_no if source_page_no is not None else [],
        role=role,
        source_assets=source_assets if source_assets is not None else [],
    )
    return _apply_derived_fields(lesson_page)


def build_lesson_pages_from_requirements(requirements: Requirements) -> LessonDocument:
    """requirementsのみからlesson_pages.jsonのたたき台を組み立てる（generateモード）。

    外部LLM APIを使わないルールベースの骨子生成であり、本文は人が仕上げる前提のたたき台。
    元ファイルが存在しないため、全ページの source_page_no は空配列にする。
    """
    topics = requirements.must_include or ["教材の要点"]

    pages: list[LessonPage] = []
    page_no = 1

    intro_notes = ""
    if requirements.must_not_include:
        intro_notes = "次の表現は避けてください: " + "、".join(requirements.must_not_include)
    pages.append(_new_lesson_page(
        page_no=page_no,
        title=f"はじめに：{requirements.theme or '教材の紹介'}",
        body=(
            f"この教材は、{requirements.target_audience or '読者'}向けに、"
            f"{requirements.reader_problem or '読者の悩み'}を解決するために作られています。\n"
            f"ゴールは「{requirements.goal or '未設定'}」です。"
        ),
        summary=requirements.reader_problem or "導入",
        notes=intro_notes,
        role="intro",
    ))
    page_no += 1

    for topic in topics:
        pages.append(_new_lesson_page(
            page_no=page_no,
            title=topic,
            body=(
                f"{topic}について、{requirements.target_audience or '読者'}向けに、"
                f"{requirements.tone or 'わかりやすい'}トーンで説明します。"
            ),
            summary=topic,
            role="explanation",
        ))
        page_no += 1

    pages.append(_new_lesson_page(
        page_no=page_no,
        title="まとめ",
        body=requirements.promised_value or "この教材で伝えたい価値をまとめます。",
        summary="まとめ",
        role="summary",
    ))

    metadata = LessonMetadata(
        project_title=requirements.theme or "教材ブラッシュアップ設計書",
        mode="generate",
        source_policy="requirements_based",
        target_audience=requirements.target_audience or "教材制作者",
        tone=requirements.tone,
        generated_at=_now_iso(),
        requirements_source=requirements.theme,
    )
    return LessonDocument(metadata=metadata, pages=pages)


# --- restructure: 中間表現・再構成プラン ------------------------------------

_MERGE_ORPHAN_THRESHOLD_CHARS = 30
_SPLIT_THRESHOLD_CHARS = 200


@dataclass
class SourcePageSummary:
    """restructureの材料として、元ページから抽出した中間表現。"""
    source_page_no: int
    title: str
    summary: str
    key_points: list[str]
    raw_text: str
    layout_instruction: str
    source_image: str
    source_assets: list[str]


def _extract_source_summaries(document: LessonDocument) -> list[SourcePageSummary]:
    summaries: list[SourcePageSummary] = []
    for page in document.pages:
        parsed = parse_body_lines(page.body)
        key_points = [text for _, text in parsed if text]
        if not key_points and page.body:
            key_points = [page.body]
        summary = page.summary or (key_points[0] if key_points else page.title)
        summaries.append(SourcePageSummary(
            source_page_no=page.page_no,
            title=page.title,
            summary=summary,
            key_points=key_points,
            raw_text=page.body,
            layout_instruction=page.layout_instruction,
            source_image=page.source_image,
            source_assets=list(page.source_assets),
        ))
    return summaries


def _cluster_source_pages(source_pages: list[SourcePageSummary]) -> list[list[SourcePageSummary]]:
    """連続する短い（=説明が薄い）ページを次のページへ統合し、クラスタ単位にまとめる。"""
    clusters: list[list[SourcePageSummary]] = []
    i = 0
    while i < len(source_pages):
        current = source_pages[i]
        is_orphan = len(current.raw_text) < _MERGE_ORPHAN_THRESHOLD_CHARS
        has_next = i + 1 < len(source_pages)
        if is_orphan and has_next:
            clusters.append([current, source_pages[i + 1]])
            i += 2
        else:
            clusters.append([current])
            i += 1
    return clusters


def _split_half(raw_text: str) -> tuple[str, str]:
    """本文を句点(。)の区切りに近い位置で前半・後半に分割する。"""
    midpoint = len(raw_text) // 2
    split_at = raw_text.rfind("。", 0, midpoint + 1)
    if split_at == -1:
        split_at = midpoint
    else:
        split_at += 1
    first_half = raw_text[:split_at].strip()
    second_half = raw_text[split_at:].strip()
    if not first_half or not second_half:
        return raw_text, ""
    return first_half, second_half


def build_restructure_plan(document: LessonDocument, requirements: Requirements | None = None) -> dict[str, Any]:
    """元ページの統合・分割・導入/実践/まとめ追加を行う再構成プランを組み立てる。

    プランは構造（どのページから何を作るか）のみを持ち、本文の組み立ては
    apply_restructure_plan() が行う。
    """
    source_pages = _extract_source_summaries(document)
    target_audience = (requirements.target_audience if requirements else "") or document.target_reader
    clusters = _cluster_source_pages(source_pages)

    all_source_nos = [sp.source_page_no for sp in source_pages]
    strategy = (
        f"元教材『{document.project_title}』の主旨を維持しつつ、{target_audience}向けに"
        "導入・実践・まとめを追加し、内容の薄いページは統合、長すぎるページは分割して再構成する。"
    )

    plan_pages: list[dict[str, Any]] = []
    new_page_no = 1

    plan_pages.append({
        "new_page_no": new_page_no,
        "role": "intro",
        "title": "この教材でできるようになること",
        "source_page_no": [source_pages[0].source_page_no] if source_pages else [],
        "operation": "add_intro_from_source",
    })
    new_page_no += 1

    for cluster in clusters:
        if len(cluster) > 1:
            plan_pages.append({
                "new_page_no": new_page_no,
                "role": "explanation",
                "title": " / ".join(p.title for p in cluster if p.title),
                "source_page_no": [p.source_page_no for p in cluster],
                "operation": "merge",
            })
            new_page_no += 1
            continue

        page = cluster[0]
        if len(page.raw_text) > _SPLIT_THRESHOLD_CHARS:
            first_half, second_half = _split_half(page.raw_text)
            if second_half:
                plan_pages.append({
                    "new_page_no": new_page_no,
                    "role": "explanation",
                    "title": f"{page.title}（前半）",
                    "source_page_no": [page.source_page_no],
                    "operation": "split_first_half",
                })
                new_page_no += 1
                plan_pages.append({
                    "new_page_no": new_page_no,
                    "role": "explanation",
                    "title": f"{page.title}（後半）",
                    "source_page_no": [page.source_page_no],
                    "operation": "split_second_half",
                })
                new_page_no += 1
                continue

        plan_pages.append({
            "new_page_no": new_page_no,
            "role": "explanation",
            "title": page.title,
            "source_page_no": [page.source_page_no],
            "operation": "carry_over",
        })
        new_page_no += 1

    plan_pages.append({
        "new_page_no": new_page_no,
        "role": "practice",
        "title": "実際にやってみましょう",
        "source_page_no": all_source_nos,
        "operation": "add_practice",
    })
    new_page_no += 1

    plan_pages.append({
        "new_page_no": new_page_no,
        "role": "summary",
        "title": "まとめ",
        "source_page_no": all_source_nos,
        "operation": "add_summary",
    })

    return {
        "mode": "restructure",
        "strategy": strategy,
        "pages": plan_pages,
    }


def _build_intro_body(sources: list[SourcePageSummary], target_audience: str, requirements: Requirements | None) -> str:
    goal = (requirements.goal if requirements else "") or (sources[0].summary if sources else "この教材の要点を理解すること")
    lines = [f"この教材では、{target_audience or '読者'}が「{goal}」を目指します。"]
    if sources:
        lines.append(f"元となる教材の内容（{sources[0].title}）をもとに、分かりやすく再構成しています。")
    return "\n".join(lines)


def _build_practice_body(sources: list[SourcePageSummary], requirements: Requirements | None) -> str:
    """practiceページの本文を組み立てる。

    各項目はMarkdown箇条書き記号("- ")を付けない自然文の行にする。箇条書きとしての表示は
    brushup.md/DOCX/PDF側の描画（parse_body_linesの結果に対する箇条書きレンダリング）が
    担うため、body自体に記号を埋め込むと表示側の箇条書きと二重になってしまう。
    """
    key_points = [point for sp in sources for point in sp.key_points][:5]
    lines = ["ここまでの内容を踏まえて、実際に手を動かしてみましょう。"]
    if key_points:
        lines.append("次のポイントを意識して取り組んでください。")
        lines.extend(key_points)
    else:
        lines.append("学んだ内容を自分の言葉でまとめてみましょう。")
    return "\n".join(lines)


def _build_summary_body(sources: list[SourcePageSummary], requirements: Requirements | None) -> str:
    """まとめページの本文を組み立てる（箇条書き記号を付けない方針は_build_practice_bodyと同じ）。"""
    lines = ["今回学んだこと:"]
    lines.extend(sp.title for sp in sources if sp.title)
    lines.append("次にやること: 今回の内容を実際に使ってみましょう。")
    if requirements and requirements.must_not_include:
        lines.append("注意点: " + "、".join(requirements.must_not_include))
    return "\n".join(lines)


# operationごとに、参照するsource_page_noが実データに存在することを必須とする操作。
# add_intro_from_source/add_practice/add_summaryは教材全体を俯瞰する集約ページであり、
# 元ページが0件の教材（空のdocument）でもbuild_restructure_plan自身が意図的に
# source_page_no=[]を生成しうるため、空を許容する。
_OPERATIONS_REQUIRING_SOURCES = {"merge", "split_first_half", "split_second_half", "carry_over"}

_ROLE_LAYOUT_INSTRUCTIONS = {
    "intro": "導入ページとして、教材全体の目的と読み終えた後にできるようになることが一目で伝わるレイアウトにする。",
    "practice": "実践ページとして、手順やワークを上から順に追えるレイアウトにする。",
    "summary": "まとめページとして、学んだ内容と次の行動を簡潔に振り返れるレイアウトにする。",
}


def _generic_layout_instruction(role: str) -> str:
    """intro/practice/summaryのような集約ページ向けに、roleに応じた汎用レイアウト指示を返す。"""
    return _ROLE_LAYOUT_INSTRUCTIONS.get(role, "")


def _merge_layout_instruction(sources: list[SourcePageSummary]) -> str:
    """統合元ページのlayout_instructionを結合する（空のものは除く）。"""
    return " / ".join(s.layout_instruction for s in sources if s.layout_instruction)


def _first_source_image(sources: list[SourcePageSummary]) -> str:
    """統合元のうち、最初に存在するsource_imageを採用する。"""
    for source in sources:
        if source.source_image:
            return source.source_image
    return ""


def _merge_source_assets(sources: list[SourcePageSummary]) -> list[str]:
    """統合元ページのsource_assetsを、重複を除いて結合する。"""
    merged: list[str] = []
    for source in sources:
        for asset in source.source_assets:
            if asset not in merged:
                merged.append(asset)
    return merged


def _merge_body(sources: list[SourcePageSummary]) -> str:
    """統合元ページの本文を、各ページのtitleを見出しとして挿入しながら結合する。"""
    blocks = []
    for source in sources:
        if source.title:
            blocks.append(f"## {source.title}\n{source.raw_text}")
        else:
            blocks.append(source.raw_text)
    return "\n\n".join(blocks)


def apply_restructure_plan(
    document: LessonDocument, plan: dict[str, Any], requirements: Requirements | None = None
) -> LessonDocument:
    """restructureプランから最終的なLessonDocumentを組み立てる。"""
    source_by_no = {sp.source_page_no: sp for sp in _extract_source_summaries(document)}
    target_audience = (requirements.target_audience if requirements else "") or document.target_reader

    pages: list[LessonPage] = []
    for plan_page in plan["pages"]:
        source_page_no = list(plan_page["source_page_no"])
        sources = [source_by_no[no] for no in source_page_no if no in source_by_no]
        operation = plan_page["operation"]

        if operation in _OPERATIONS_REQUIRING_SOURCES and not sources:
            raise ValueError(
                f"restructure_planが不正です: operation={operation!r} の "
                f"source_page_no={source_page_no!r} に対応する元ページが見つかりません。"
            )

        layout_instruction = ""
        source_image = ""
        source_assets: list[str] = []

        if operation == "add_intro_from_source":
            body = _build_intro_body(sources, target_audience, requirements)
            summary = sources[0].summary if sources else "導入"
            layout_instruction = _generic_layout_instruction("intro")
        elif operation == "merge":
            body = _merge_body(sources)
            summary = "、".join(s.summary for s in sources if s.summary)
            layout_instruction = _merge_layout_instruction(sources)
            source_image = _first_source_image(sources)
            source_assets = _merge_source_assets(sources)
        elif operation == "split_first_half":
            body, _ = _split_half(sources[0].raw_text)
            summary = sources[0].summary
            layout_instruction = sources[0].layout_instruction
            source_image = sources[0].source_image
            source_assets = list(sources[0].source_assets)
        elif operation == "split_second_half":
            _, body = _split_half(sources[0].raw_text)
            summary = sources[0].summary
            layout_instruction = sources[0].layout_instruction
            source_image = sources[0].source_image
            source_assets = list(sources[0].source_assets)
        elif operation == "carry_over":
            body = sources[0].raw_text
            summary = sources[0].summary
            layout_instruction = sources[0].layout_instruction
            source_image = sources[0].source_image
            source_assets = list(sources[0].source_assets)
        elif operation == "add_practice":
            body = _build_practice_body(sources, requirements)
            summary = "実践"
            layout_instruction = _generic_layout_instruction("practice")
        elif operation == "add_summary":
            body = _build_summary_body(sources, requirements)
            summary = "まとめ"
            layout_instruction = _generic_layout_instruction("summary")
        else:
            raise ValueError(f"restructure_planに未知のoperationが指定されました: {operation!r}")

        pages.append(_new_lesson_page(
            page_no=plan_page["new_page_no"],
            title=plan_page["title"],
            body=body,
            summary=summary,
            source_page_no=source_page_no,
            role=plan_page["role"],
            layout_instruction=layout_instruction,
            source_image=source_image,
            source_assets=source_assets,
        ))

    metadata = LessonMetadata(
        project_title=document.project_title,
        mode="restructure",
        source_policy="preserve_intent",
        target_audience=target_audience,
        tone=(requirements.tone if requirements else "") or document.metadata.tone,
        generated_at=_now_iso(),
        requirements_source=requirements.theme if requirements else "",
    )
    return LessonDocument(metadata=metadata, pages=pages)


def build_lesson_pages_from_source_restructure(
    document: LessonDocument, requirements: Requirements | None = None
) -> tuple[LessonDocument, dict[str, Any]]:
    """元ページを素材として、統合・分割・導入/実践/まとめ追加を行い再構成する（restructureモード）。"""
    plan = build_restructure_plan(document, requirements)
    return apply_restructure_plan(document, plan, requirements), plan


def render_review_report(document: LessonDocument) -> str:
    """制作者確認用に、各ページがどの元ページ由来かをまとめたレポートを生成する。

    source_page_no/roleは内部管理情報であり、配布用PDF/DOCXには表示しない。
    このレポートは制作者向けの確認用途に限定して使う。
    """
    lines = [f"# レビュー用レポート: {document.project_title}", ""]
    lines.append(f"モード: {document.metadata.mode}")
    lines.append("")
    for page in document.pages:
        role = page.role or "(未設定)"
        source = ", ".join(str(no) for no in page.source_page_no) or "(なし)"
        lines.append(f"## Page {page.page_no}: {page.title}")
        lines.append(f"- role: {role}")
        lines.append(f"- source_page_no: {source}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_lesson_pages(
    mode: str,
    source_path: str | Path | None,
    requirements_path: str | Path | None,
) -> tuple[LessonDocument, dict[str, Any] | None]:
    """モードに応じてlesson_pages.jsonを構築する（lesson-pagesコマンドの本体）。

    戻り値は (LessonDocument, restructure_plan)。restructure_planはrestructureモード
    以外ではNone。
    """
    if mode not in VALID_MODES:
        raise ValueError(f"未知のmodeが指定されました: {mode}")

    # 循環importを避けるため、parserモジュールは呼び出し時に遅延importする。
    from .parser import load_lesson_document, load_requirements

    requirements = load_requirements(requirements_path) if requirements_path else None

    if mode == "generate":
        if requirements is None:
            raise ValueError("generateモードでは--requirementsが必須です")
        return build_lesson_pages_from_requirements(requirements), None

    if not source_path:
        raise ValueError(f"{mode}モードでは--inputが必須です")

    document = load_lesson_document(source_path)

    if mode == "restructure":
        result_document, plan = build_lesson_pages_from_source_restructure(document, requirements)
        return result_document, plan

    return _finalize_metadata(document, mode=mode, source_policy="preserve_original", requirements=requirements), None
