from __future__ import annotations

import copy
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .content_brushup import (
    ContentBrushupPaths,
    _EDITABLE_FIELDS,
    format_page_number_ranges,
    render_review_html,
    render_review_summary_markdown,
    validate_candidate_page,
    validate_candidates_aggregate,
)
from .lesson_pages import LessonDocument, LessonPage, _apply_derived_fields, write_lesson_pages_json
from .parser import load_lesson_document

# Phase 10.13: `content_brushup/candidates.json`（AIエージェントが作成した教材本文ブラッシュアップ
# 候補）を、確認操作（--dry-run→--apply）を経て`output/editable/lesson_pages.json`へ安全に反映する
# モジュール。設計方針はPhase 10.11の`ocr_review_apply.py`と同じ（検証と実書き込みを分離する
# `validate_and_plan()`/`apply_document()`の2関数構成、対象範囲内で1ページでも条件を満たさない
# 場合は全体を反映不可として扱う「全体停止方式」、バックアップ＋原子的書き込み、冪等性）。
#
# 重要な違い: Phase 10.11はOCR確定文字列という「事実の確定」を反映したが、本Phaseは
# 「文章表現の改善」を反映する。そのため`risk_level: high`・`requires_human_review: true`の
# ページは、`--allow-high-risk`のようなバイパスを用意せず常に反映不可として扱う
# （人間がPhase 10.9相当のレビューUI・候補JSONの手動修正で解消してから再実行する）。


class ContentBrushupInputError(ValueError):
    """入力ファイルの読み込み自体が出来ない致命的な不備（レポートすら組み立てられない）。"""


def _load_json(path: Path, *, label: str) -> dict[str, Any]:
    if not path.exists():
        raise ContentBrushupInputError(f"{label}が見つかりません: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        raise ContentBrushupInputError(f"{label}がUTF-8として読み込めません: {path} ({e})") from e
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ContentBrushupInputError(f"{label}のJSONが不正です: {path} ({e.lineno}行目 {e.colno}列目: {e.msg})") from e
    if not isinstance(data, dict):
        raise ContentBrushupInputError(f"{label}がオブジェクト形式ではありません: {path}")
    return data


def parse_page_selection(spec: str, available_pages: list[int]) -> list[int]:
    """`--pages`の"1,4,7-11"形式を解析する（`ocr_review_apply.parse_page_selection`と同仕様）。"""
    if not spec or not spec.strip():
        raise ValueError("--pagesが空です")

    available = set(available_pages)
    selected: list[int] = []
    seen: set[int] = set()

    for raw_token in spec.split(","):
        token = raw_token.strip()
        if not token:
            continue
        if "-" in token:
            start_str, _, end_str = token.partition("-")
            try:
                start, end = int(start_str.strip()), int(end_str.strip())
            except ValueError as e:
                raise ValueError(f"--pagesの区間指定が不正です: {token!r}") from e
            if start > end:
                raise ValueError(f"--pagesの区間指定が逆順です（開始 > 終了）: {token!r}")
            page_range = range(start, end + 1)
        else:
            try:
                page_range = [int(token)]
            except ValueError as e:
                raise ValueError(f"--pagesのページ番号が不正です: {token!r}") from e

        for page_no in page_range:
            if page_no in seen:
                raise ValueError(f"--pagesにページ番号の重複があります: {page_no}")
            if page_no not in available:
                raise ValueError(f"--pagesに存在しないページ番号が指定されました: {page_no}")
            seen.add(page_no)
            selected.append(page_no)

    if not selected:
        raise ValueError("--pagesが空です")
    return sorted(selected)


@dataclass
class PageContentPlan:
    page_no: int
    reflectable: bool
    reject_reasons: list[str] = field(default_factory=list)
    risk_level: str | None = None
    has_changes: bool = False
    changed_fields: list[str] = field(default_factory=list)
    before: dict[str, str] = field(default_factory=dict)
    after: dict[str, str] = field(default_factory=dict)
    changes: list[dict[str, Any]] = field(default_factory=list)
    preserved_facts: list[str] = field(default_factory=list)


@dataclass
class ContentApplyPlan:
    generated_at: str
    output_dir: str
    lesson_pages_path: str
    candidates_path: str
    snapshot_sha256: str
    target_pages: list[int]
    passed: bool
    errors: list[str]
    pages: list[PageContentPlan]
    document: LessonDocument | None = None
    snapshot: dict[str, Any] | None = None
    candidates_data: dict[str, Any] | None = None
    candidate_pages: dict[int, dict[str, Any]] = field(default_factory=dict)

    @property
    def reflectable_pages(self) -> list[PageContentPlan]:
        return [p for p in self.pages if p.reflectable]

    @property
    def not_reflectable_pages(self) -> list[PageContentPlan]:
        return [p for p in self.pages if not p.reflectable]

    @property
    def changed_pages(self) -> list[PageContentPlan]:
        return [p for p in self.pages if p.reflectable and p.has_changes]

    @property
    def unchanged_pages(self) -> list[PageContentPlan]:
        return [p for p in self.pages if p.reflectable and not p.has_changes]


def validate_and_plan(paths: ContentBrushupPaths, *, pages_spec: str | None = None) -> ContentApplyPlan:
    """`candidates.json`を`lesson_pages.json`へ反映してよいか検証し、ページ別の反映計画を組み立てる。

    設計方針: 対象範囲内で1ページでも反映不可条件（`risk_level: high`・
    `requires_human_review: true`・スキーマ不正・スナップショット不一致等）を満たす場合、
    そのページだけを除外するのではなく対象範囲全体を反映不可として扱う（`passed=False`）。
    `--allow-high-risk`のようなバイパスは提供しない。
    """
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    errors: list[str] = []

    document = load_lesson_document(paths.lesson_pages_path)
    snapshot = _load_json(paths.snapshot_path, label="VERIFIED_OCR_SNAPSHOT.json")
    candidates_data = _load_json(paths.candidates_path, label="candidates.json")

    # 現在のlesson_pages.json全体のハッシュをスナップショットと比較する方式は採らない。
    # --apply成功後はlesson_pages.json自体が意図的に変化するため、全体一致チェックだと
    # 2回目以降のdry-run/applyが常に失敗してしまう（冪等性が壊れる）。代わりに、対象ページ
    # ごとに「現在値が原文と一致する（未反映）」か「現在値が改善案と一致する（反映済み＝
    # 冪等）」かをこの後のループで個別に確認し、どちらでもない場合だけ競合として拒否する。
    snapshot_sha256 = snapshot.get("source_sha256", "")

    errors.extend(validate_candidates_aggregate(
        candidates_data, expected_page_numbers=[p.page_no for p in document.pages], expected_snapshot_sha256=snapshot_sha256,
    ))

    progress_data: dict[str, Any] | None = None
    if paths.progress_path.exists():
        try:
            progress_data = _load_json(paths.progress_path, label="progress.json")
        except ContentBrushupInputError as e:
            errors.append(str(e))
    else:
        errors.append(f"progress.jsonが見つかりません: {paths.progress_path}")

    raw_pages = candidates_data.get("pages", []) if isinstance(candidates_data.get("pages"), list) else []
    candidate_by_page: dict[int, dict[str, Any]] = {}
    for entry in raw_pages:
        if isinstance(entry, dict) and isinstance(entry.get("page_no"), int):
            candidate_by_page[entry["page_no"]] = entry

    snapshot_by_page: dict[int, dict[str, Any]] = {p["page_no"]: p for p in snapshot.get("pages", []) if isinstance(p, dict)}
    available_pages = sorted(candidate_by_page.keys())

    explicit_pages = pages_spec is not None
    if explicit_pages:
        try:
            target_pages = parse_page_selection(pages_spec, available_pages)
        except ValueError as e:
            errors.append(str(e))
            target_pages = []
    else:
        target_pages = available_pages

    if progress_data is not None:
        failed_pages = progress_data.get("failed_pages") or []
        if failed_pages:
            errors.append(f"progress.jsonのfailed_pagesが空ではありません: {failed_pages}")
        remaining_pages = set(progress_data.get("remaining_pages") or [])
    else:
        remaining_pages = set()

    lesson_page_by_no = {p.page_no: p for p in document.pages}
    page_plans: list[PageContentPlan] = []

    for page_no in target_pages:
        candidate = candidate_by_page.get(page_no)
        snapshot_page = snapshot_by_page.get(page_no)
        if candidate is None:
            page_plans.append(PageContentPlan(page_no=page_no, reflectable=False, reject_reasons=["candidates.jsonにこのページの候補がありません"]))
            continue
        if snapshot_page is None:
            page_plans.append(PageContentPlan(page_no=page_no, reflectable=False, reject_reasons=["スナップショットにこのページがありません"]))
            continue

        reject_reasons = validate_candidate_page(candidate, expected_page_no=page_no, snapshot_page=snapshot_page)

        lesson_page = lesson_page_by_no.get(page_no)
        if lesson_page is None:
            reject_reasons.append("lesson_pages.jsonに対応するページが見つかりません")
        elif lesson_page.source_image != snapshot_page.get("source_image"):
            reject_reasons.append("source_imageがlesson_pages.jsonとスナップショットで一致しません")
        elif not reject_reasons:
            # 現在のlesson_pages.jsonの値が「原文（未反映）」か「改善案（反映済み＝冪等）」の
            # どちらかと一致していればOKとする。どちらとも一致しない場合は、他の変更と競合
            # している可能性があるため反映を拒否する（全体sha256の単純比較だと--apply成功後に
            # 恒久的に不一致となり冪等にならないため、フィールド単位でこの判定を行う）。
            proposed = candidate.get("proposed", {})
            for field_name in _EDITABLE_FIELDS:
                current_value = getattr(lesson_page, field_name)
                if current_value == snapshot_page.get(field_name):
                    continue
                if current_value == proposed.get(field_name):
                    continue
                reject_reasons.append(
                    f"lesson_pages.jsonの{field_name}が原文・改善案のいずれとも一致しません"
                    "（他の変更と競合している可能性があります）"
                )

        risk_level = candidate.get("risk_level")
        if risk_level == "high":
            reject_reasons.append("risk_levelがhighです（人間の確認・修正が必要です）")
        if candidate.get("requires_human_review"):
            reject_reasons.append("requires_human_reviewがtrueです（人間の確認が必要です）")
        if page_no in remaining_pages:
            reject_reasons.append("progress.jsonのremaining_pagesに含まれています（未完了）")

        reflectable = not reject_reasons
        plan = PageContentPlan(
            page_no=page_no, reflectable=reflectable, reject_reasons=reject_reasons, risk_level=risk_level,
            changes=candidate.get("changes", []) if isinstance(candidate.get("changes"), list) else [],
            preserved_facts=candidate.get("preserved_facts", []) if isinstance(candidate.get("preserved_facts"), list) else [],
        )

        if reflectable and lesson_page is not None:
            proposed = candidate["proposed"]
            before = {f: getattr(lesson_page, f) for f in ("title", "body", "summary", "image_text", "canva_prompt", "video_scene")}
            new_page = copy.deepcopy(lesson_page)
            new_page.title = proposed["title"]
            new_page.body = proposed["body"]
            new_page.summary = proposed["summary"]
            new_page = _apply_derived_fields(new_page)
            after = {f: getattr(new_page, f) for f in ("title", "body", "summary", "image_text", "canva_prompt", "video_scene")}
            changed_fields = [f for f in before if before[f] != after[f]]
            plan.before = before
            plan.after = after
            plan.changed_fields = changed_fields
            plan.has_changes = bool(changed_fields)

        page_plans.append(plan)

    passed = not errors and bool(page_plans) and all(p.reflectable for p in page_plans)

    return ContentApplyPlan(
        generated_at=generated_at, output_dir=str(paths.output_dir), lesson_pages_path=str(paths.lesson_pages_path),
        candidates_path=str(paths.candidates_path), snapshot_sha256=snapshot_sha256, target_pages=target_pages,
        passed=passed, errors=errors, pages=page_plans,
        document=document if passed else None, snapshot=snapshot, candidates_data=candidates_data,
        candidate_pages=candidate_by_page,
    )


# --- 反映（--apply） -------------------------------------------------------------------------


def _atomic_write_json(path: Path, document: LessonDocument) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + f".tmp-{os.getpid()}")
    write_lesson_pages_json(tmp_path, document)
    json.loads(tmp_path.read_text(encoding="utf-8"))
    os.replace(tmp_path, path)


def _create_backup(lesson_pages_path: Path, backups_dir: Path) -> Path:
    backups_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    backup_path = backups_dir / f"{timestamp}_lesson_pages.before_content_brushup.json"
    if backup_path.exists():
        raise ValueError(f"バックアップ先が既に存在します（上書きしません）: {backup_path}")
    backup_path.write_text(lesson_pages_path.read_text(encoding="utf-8"), encoding="utf-8")
    return backup_path


@dataclass
class ContentApplyResult:
    plan: ContentApplyPlan
    wrote_changes: bool
    backup_path: Path | None


def apply_document(plan: ContentApplyPlan, paths: ContentBrushupPaths) -> ContentApplyResult:
    """検証済み（`plan.passed`が`True`）の計画を、実際に`lesson_pages.json`へ書き込む。"""
    if not plan.passed or plan.document is None:
        raise ValueError("検証に失敗した計画は反映できません（validate_and_plan()の結果を確認してください）")

    if not plan.changed_pages:
        return ContentApplyResult(plan=plan, wrote_changes=False, backup_path=None)

    new_document = copy.deepcopy(plan.document)
    page_by_no = {p.page_no: p for p in new_document.pages}
    for page_plan in plan.changed_pages:
        page = page_by_no[page_plan.page_no]
        for field_name in ("title", "body", "summary", "image_text", "canva_prompt", "video_scene"):
            setattr(page, field_name, page_plan.after[field_name])

    backup_path = _create_backup(paths.lesson_pages_path, paths.backups_dir)
    _atomic_write_json(paths.lesson_pages_path, new_document)

    return ContentApplyResult(plan=plan, wrote_changes=True, backup_path=backup_path)


# --- レポート -------------------------------------------------------------------------------


def _truncate(text: str, width: int = 60) -> str:
    text = text.replace("\n", "\\n")
    if len(text) <= width:
        return text
    return text[:width] + "…"


def render_apply_report_json(plan: ContentApplyPlan, *, mode: str, result: ContentApplyResult | None = None) -> dict[str, Any]:
    return {
        "schema_version": 1, "mode": mode, "generated_at": plan.generated_at, "passed": plan.passed,
        "output_dir": plan.output_dir, "lesson_pages_path": plan.lesson_pages_path, "candidates_path": plan.candidates_path,
        "target_pages": plan.target_pages, "errors": plan.errors,
        "wrote_changes": result.wrote_changes if result else False,
        "backup_path": str(result.backup_path) if result and result.backup_path else None,
        "pages": [
            {
                "page_no": p.page_no, "reflectable": p.reflectable, "reject_reasons": p.reject_reasons,
                "risk_level": p.risk_level, "has_changes": p.has_changes, "changed_fields": p.changed_fields,
                "before": p.before, "after": p.after, "changes": p.changes, "preserved_facts": p.preserved_facts,
            }
            for p in plan.pages
        ],
    }


def render_apply_report_markdown(plan: ContentApplyPlan, *, mode: str, result: ContentApplyResult | None = None) -> str:
    lines: list[str] = ["# 教材本文ブラッシュアップ 反映レポート", ""]
    mode_label = {"dry_run": "dry-run（分析のみ。書き込みは行っていません）", "apply": "apply（実反映）"}[mode]
    lines.append(f"- モード: {mode_label}")
    lines.append(f"- 実行日時: {plan.generated_at}")
    lines.append(f"- 判定: {'passed' if plan.passed else 'failed'}")
    lines.append(f"- 入力lesson_pages: `{plan.lesson_pages_path}`")
    lines.append(f"- 入力candidates: `{plan.candidates_path}`")
    lines.append(f"- 対象ページ: {format_page_number_ranges(plan.target_pages) if plan.target_pages else '(なし)'}")
    if result:
        lines.append(f"- 書き込みを行ったか: {'はい' if result.wrote_changes else 'いいえ（変更なし、または未passed）'}")
        lines.append(f"- バックアップ: `{result.backup_path}`" if result.backup_path else "- バックアップ: (作成していません)")
    lines.append("")

    if plan.errors:
        lines.append("## 全体エラー")
        lines.append("")
        for e in plan.errors:
            lines.append(f"- {e}")
        lines.append("")

    lines.append("## サマリー")
    lines.append("")
    lines.append(f"- 対象ページ数: {len(plan.pages)}")
    lines.append(f"- 反映可能ページ数: {len(plan.reflectable_pages)}")
    lines.append(f"- 反映不可ページ数: {len(plan.not_reflectable_pages)}")
    if plan.passed:
        lines.append(f"- 変更ありページ数: {len(plan.changed_pages)}")
        lines.append(f"- 変更なしページ数: {len(plan.unchanged_pages)}")
    lines.append("")

    if plan.not_reflectable_pages:
        lines.append("## 反映不可ページ")
        lines.append("")
        lines.append("| Page | 理由 |")
        lines.append("|---|---|")
        for p in plan.not_reflectable_pages:
            lines.append(f"| {p.page_no} | {'; '.join(p.reject_reasons)} |")
        lines.append("")

    if plan.passed:
        lines.append("## ページ別変更内容")
        lines.append("")
        for p in plan.pages:
            lines.append(f"### Page {p.page_no}")
            lines.append("")
            lines.append(f"- risk_level: {p.risk_level}")
            lines.append(f"- 変更あり: {'はい' if p.has_changes else 'いいえ'}")
            if p.has_changes:
                lines.append(f"- 変更field: {', '.join(p.changed_fields)}")
                lines.append(f"- title: `{_truncate(p.before.get('title', ''))}` → `{_truncate(p.after.get('title', ''))}`")
                if p.changes:
                    lines.append("- 主な変更:")
                    for c in p.changes[:5]:
                        lines.append(f"  - [{c.get('change_type','')}] 「{c.get('before','')}」→「{c.get('after','')}」（{c.get('reason','')}）")
                if p.preserved_facts:
                    lines.append(f"- 保持した重要情報: {', '.join(p.preserved_facts)}")
            lines.append("")

    lines.append("## 次の操作")
    lines.append("")
    if mode == "dry_run":
        if plan.passed:
            lines.append("```bash")
            lines.append(f"python3 -m src.cli apply-content-brushup --output-dir {plan.output_dir} --apply")
            lines.append("```")
        else:
            lines.append(
                "反映不可ページを解消してから（候補JSONの手動修正・AIエージェントによる再作成）、"
                "再度dry-runを実行してください。"
            )
    else:
        if result and result.wrote_changes:
            lines.append("本文が更新されました。既存の`brushup_design`は古い本文を前提としている可能性があります。")
            lines.append("")
            lines.append("```bash")
            lines.append(f"python3 -m src.cli prepare-image-brushup --output-dir {plan.output_dir}")
            lines.append("```")
        else:
            lines.append("変更はありませんでした（既に反映済み、または反映可能なページがありません）。")
    lines.append("")

    return "\n".join(lines)


def write_apply_reports(plan: ContentApplyPlan, paths: ContentBrushupPaths, *, mode: str, result: ContentApplyResult | None = None) -> None:
    paths.content_dir.mkdir(parents=True, exist_ok=True)
    report_json_path = paths.content_dir / "apply_report.json"
    report_md_path = paths.content_dir / "apply_report.md"
    report_json_path.write_text(
        json.dumps(render_apply_report_json(plan, mode=mode, result=result), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    report_md_path.write_text(render_apply_report_markdown(plan, mode=mode, result=result), encoding="utf-8")

    # review.html/review_summary.mdは、検証済み(document/snapshot/candidates_dataが揃っている)
    # 場合にのみ再生成する（passedしていなくても、原文・候補データ自体は読めていれば人間確認用に
    # 生成する。document読み込み自体に失敗した場合は例外が既にvalidate_and_plan()側で送出される）。
    if plan.snapshot is not None and plan.candidates_data is not None:
        document = load_lesson_document(paths.lesson_pages_path)
        html_text = render_review_html(document, plan.snapshot, plan.candidate_pages, paths.output_dir)
        paths.review_html_path.write_text(html_text, encoding="utf-8")
        next_command = f"python3 -m src.cli apply-content-brushup --output-dir {plan.output_dir} --apply"
        summary_md = render_review_summary_markdown(document, plan.candidates_data, next_command=next_command)
        paths.review_summary_path.write_text(summary_md, encoding="utf-8")
