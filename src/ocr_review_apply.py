from __future__ import annotations

import copy
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

from .import_source import _derive_title_and_summary, _text_to_lines
from .lesson_pages import LessonDocument, LessonPage, _apply_derived_fields, _body_from_lines, write_lesson_pages_json
from .models import DialogueLine, Page as SourcePage
from .ocr_claude_review import _ALLOWED_DECISIONS
from .parser import load_lesson_document

# Phase 10.10（Claude Codeによる画像照合レビュー）が生成した`claude_review/candidates.json`を、
# 明示的な確認操作（--dry-run → --apply）を経てoutput/editable/lesson_pages.jsonへ安全に反映する
# モジュール。
#
# 重要な位置づけ:
# - `ocr_check.py`/`ocr_apply.py`/`ocr_approval.py`（substring単位のOCR補正候補ワークフロー。
#   docs/14_apply_ocr_corrections_workflow.md）とは完全に別のワークフローであり、候補スキーマも
#   安全条件も混在させない。Claude Codeが画像照合済みのページ全文（`proposed_text`）を対象とする。
# - `proposed_text`から`title`/`body`/`summary`を再構築するロジックは、`import_source.py`の
#   `_derive_title_and_summary()`/`_text_to_lines()`（OCR取り込み時の実際の分割ルール）と、
#   `lesson_pages.py`の`_body_from_lines()`/`_apply_derived_fields()`（image_text/canva_prompt/
#   video_sceneの再計算）をそのまま再利用する。新しい独自の分割・派生ルールは実装しない。
# - `layout_instruction`はOCR本文ではないため常に保持し、再計算しない。
# - `--allow-unresolved`のような安全条件のバイパスは提供しない。`unresolved`/`requires_human_review`
#   のページが対象範囲に含まれる場合、バッチ全体を反映不可として拒否する（詳細は
#   `validate_and_plan()`のdocstring参照）。

_SUPPORTED_CANDIDATES_SCHEMA_VERSIONS = (1,)
_EXPECTED_CANDIDATES_SOURCE = "claude_code_image_review"

_REPORT_JSON_FILENAME = "apply_report.json"
_REPORT_MD_FILENAME = "apply_report.md"


class OcrReviewApplyInputError(ValueError):
    """入力ファイルの読み込み自体が出来ない致命的な不備（レポートすら組み立てられない）。"""


# --- パス解決 -----------------------------------------------------------------------------


@dataclass
class OcrReviewApplyPaths:
    output_dir: Path
    lesson_pages_path: Path
    candidates_path: Path
    comparison_pages_dir: Path
    claude_review_pages_dir: Path
    progress_path: Path
    report_dir: Path
    report_json_path: Path
    report_md_path: Path
    backups_dir: Path


def resolve_paths(
    output_dir: str | Path,
    *,
    lesson_pages_path: str | Path | None = None,
    candidates_path: str | Path | None = None,
    report_dir: str | Path | None = None,
) -> OcrReviewApplyPaths:
    """`--output-dir`から既定パスを組み立てる（`--lesson-pages`/`--candidates`/`--report-dir`で個別上書き可）。"""
    base = Path(output_dir)
    comparison_dir = base / "ocr_comparison"
    claude_review_dir = comparison_dir / "claude_review"
    resolved_report_dir = Path(report_dir) if report_dir else claude_review_dir
    return OcrReviewApplyPaths(
        output_dir=base,
        lesson_pages_path=Path(lesson_pages_path) if lesson_pages_path else base / "editable" / "lesson_pages.json",
        candidates_path=Path(candidates_path) if candidates_path else claude_review_dir / "candidates.json",
        comparison_pages_dir=comparison_dir / "pages",
        claude_review_pages_dir=claude_review_dir / "pages",
        progress_path=claude_review_dir / "progress.json",
        report_dir=resolved_report_dir,
        report_json_path=resolved_report_dir / _REPORT_JSON_FILENAME,
        report_md_path=resolved_report_dir / _REPORT_MD_FILENAME,
        backups_dir=base / "editable" / "backups",
    )


# --- --pages パース -------------------------------------------------------------------------


def parse_page_selection(spec: str, available_pages: list[int]) -> list[int]:
    """`--pages`の"1,4,7-11"形式を解析し、ページ番号の昇順リストを返す。

    重複・逆順区間（開始>終了）・`available_pages`に存在しないページ番号はすべてエラーにする。
    """
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


# --- source_image正規化 ---------------------------------------------------------------------


def _normalize_source_image(raw: str, *, label: str) -> str:
    """相対パスとして正規化する。絶対パス・パストラバーサル・空文字は拒否する。"""
    if not raw or not raw.strip():
        raise ValueError(f"{label}のsource_imageが空です")
    posix_raw = raw.strip().replace("\\", "/")
    candidate = PurePosixPath(posix_raw)
    if candidate.is_absolute():
        raise ValueError(f"{label}のsource_imageに絶対パスは使用できません: {raw!r}")
    if any(part in ("..", "") for part in candidate.parts if part != "."):
        raise ValueError(f"{label}のsource_imageにパストラバーサルは使用できません: {raw!r}")
    return candidate.as_posix()


# --- フィールド再構築（既存ロジックの再利用のみ） -----------------------------------------------


def reconstruct_fields_from_proposed_text(proposed_text: str, page_no: int, source_image: str) -> dict[str, str]:
    """`proposed_text`（Claudeが画像照合して確定したページ全文）から、`title`/`body`/`summary`を
    再構築する。

    `import_source.py`が実際のOCR取り込み時に使っている分割ルールをそのまま再利用する
    （先頭の空でない行=title、先頭2行を結合したもの=summary、各行を空speakerの1行として
    body化。titleはbodyからは除外しない＝重複させる。これは既存proofread取り込みの実仕様）。
    """
    raw_lines = _text_to_lines(proposed_text)
    dialogue_lines = [DialogueLine(speaker=d["speaker"], text=d["text"]) for d in raw_lines]
    temp_page = SourcePage(page_no=page_no, source_image=source_image, title="", summary="", lines=dialogue_lines)
    new_body = _body_from_lines(temp_page)
    new_title, new_summary = _derive_title_and_summary(proposed_text, page_no, source_image)
    return {"title": new_title, "body": new_body, "summary": new_summary}


_OCR_DERIVED_FIELDS = ("title", "body", "summary", "image_text", "canva_prompt", "video_scene")
_PRESERVED_FIELDS = ("layout_instruction", "notes", "source_image", "source_assets", "source_page_no", "role", "page_no")


def apply_proposed_text_to_page(page: LessonPage, proposed_text: str) -> LessonPage:
    """`page`のコピーへ`proposed_text`を反映する（引数の`page`自体は変更しない）。

    title/body/summaryを再構築したうえで、image_text/canva_prompt/video_sceneを
    `lesson_pages._apply_derived_fields()`で再計算する（既存の再計算ロジックをそのまま再利用）。
    layout_instruction/notes/source_image/source_assets/source_page_no/role/page_noは変更しない。
    """
    new_page = copy.deepcopy(page)
    fields = reconstruct_fields_from_proposed_text(proposed_text, page.page_no, page.source_image)
    new_page.title = fields["title"]
    new_page.body = fields["body"]
    new_page.summary = fields["summary"]
    return _apply_derived_fields(new_page)


# --- 検証・計画 -----------------------------------------------------------------------------


@dataclass
class PageChangePlan:
    page_no: int
    source_image: str
    decision: str | None
    reflectable: bool
    reject_reasons: list[str] = field(default_factory=list)
    has_changes: bool = False
    changed_fields: list[str] = field(default_factory=list)
    before: dict[str, str] = field(default_factory=dict)
    after: dict[str, str] = field(default_factory=dict)
    corrections: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ApplyPlan:
    generated_at: str
    output_dir: str
    lesson_pages_path: str
    candidates_path: str
    target_pages: list[int]
    passed: bool
    errors: list[str]
    pages: list[PageChangePlan]
    document: LessonDocument | None = None

    @property
    def reflectable_pages(self) -> list[PageChangePlan]:
        return [p for p in self.pages if p.reflectable]

    @property
    def not_reflectable_pages(self) -> list[PageChangePlan]:
        return [p for p in self.pages if not p.reflectable]

    @property
    def changed_pages(self) -> list[PageChangePlan]:
        return [p for p in self.pages if p.reflectable and p.has_changes]

    @property
    def unchanged_pages(self) -> list[PageChangePlan]:
        return [p for p in self.pages if p.reflectable and not p.has_changes]


def _load_json(path: Path, *, label: str) -> dict[str, Any]:
    if not path.exists():
        raise OcrReviewApplyInputError(f"{label}が見つかりません: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        raise OcrReviewApplyInputError(f"{label}がUTF-8として読み込めません: {path} ({e})") from e
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise OcrReviewApplyInputError(
            f"{label}のJSONが不正です: {path} ({e.lineno}行目 {e.colno}列目: {e.msg})"
        ) from e
    if not isinstance(data, dict):
        raise OcrReviewApplyInputError(f"{label}がオブジェクト形式ではありません: {path}")
    return data


def validate_and_plan(
    paths: OcrReviewApplyPaths,
    *,
    pages_spec: str | None = None,
) -> ApplyPlan:
    """`candidates.json`を`lesson_pages.json`へ反映してよいか検証し、ページ別の反映計画を組み立てる。

    このモジュールは実データ・実書き込みを一切行わず、`--dry-run`/`--apply`共通の検証と計画
    づくりだけを担当する（`--apply`側で実際の書き込みを行うのは`apply_document()`）。

    設計方針（重要）: ページ単位の反映可否判定（`decision: unresolved`・`requires_human_review`・
    `unresolved_spans`が残っている・`proposed_text`が空・`decision`が未知の値・進捗未完了等）で
    1件でも対象ページが条件を満たさない場合、**そのページだけを除外するのではなく、対象範囲
    全体を反映不可として扱う**（`passed=False`。`--apply`は何も書き込まない）。`--allow-unresolved`
    のようなバイパスは提供しない。該当ページをPhase 10.9のレビューUI（またはcandidates.jsonの
    手動修正）で確定させ、Claude Codeによる画像照合レビューを再実行してから、本コマンドを
    再実行することを想定している。この設計判断はCodexの確認事項として完了報告に明記する。
    """
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    errors: list[str] = []

    document = load_lesson_document(paths.lesson_pages_path)
    candidates_data = _load_json(paths.candidates_path, label="candidates.json")

    schema_version = candidates_data.get("schema_version")
    if schema_version not in _SUPPORTED_CANDIDATES_SCHEMA_VERSIONS:
        errors.append(f"candidates.jsonのschema_versionが未対応です: {schema_version!r}")

    source = candidates_data.get("source")
    if source != _EXPECTED_CANDIDATES_SOURCE:
        errors.append(
            f"candidates.jsonのsourceがClaude画像照合レビュー由来ではありません: {source!r}"
            f"（期待値: {_EXPECTED_CANDIDATES_SOURCE!r}）"
        )

    raw_pages = candidates_data.get("pages")
    if not isinstance(raw_pages, list):
        errors.append("candidates.jsonのpagesがリスト形式ではありません")
        raw_pages = []

    candidate_by_page: dict[int, dict[str, Any]] = {}
    for entry in raw_pages:
        if not isinstance(entry, dict) or "page_no" not in entry:
            errors.append(f"candidates.jsonのpagesに不正な要素があります: {entry!r}")
            continue
        try:
            page_no = int(entry["page_no"])
        except (TypeError, ValueError):
            errors.append(f"candidates.jsonのpage_noが不正です: {entry.get('page_no')!r}")
            continue
        if page_no in candidate_by_page:
            errors.append(f"candidates.jsonにpage_noの重複があります: {page_no}")
            continue
        candidate_by_page[page_no] = entry

    decision_counts = candidates_data.get("decision_counts", {})
    if isinstance(decision_counts, dict):
        decision_counts_sum = sum(v for v in decision_counts.values() if isinstance(v, int))
    else:
        errors.append("candidates.jsonのdecision_countsがオブジェクト形式ではありません")
        decision_counts_sum = None

    total_pages = candidates_data.get("total_pages")
    completed_pages_count = candidates_data.get("completed_pages")
    lesson_pages_count = len(document.pages)

    progress_data: dict[str, Any] | None = None
    if paths.progress_path.exists():
        try:
            progress_data = _load_json(paths.progress_path, label="progress.json")
        except OcrReviewApplyInputError as e:
            errors.append(str(e))
    else:
        errors.append(f"progress.jsonが見つかりません: {paths.progress_path}")

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

    # --pagesを指定せず全件を対象にする場合のみ、全体の整合性（件数一致）を厳密にチェックする。
    # --pagesで意図的に一部だけを対象にする場合は、この時点での完全一致は前提にしない。
    if not explicit_pages:
        if isinstance(total_pages, int) and total_pages != len(raw_pages):
            errors.append(f"total_pages({total_pages})とpagesの件数({len(raw_pages)})が一致しません")
        if isinstance(completed_pages_count, int) and completed_pages_count != len(raw_pages):
            errors.append(
                f"completed_pages({completed_pages_count})とpagesの件数({len(raw_pages)})が一致しません"
            )
        if decision_counts_sum is not None and decision_counts_sum != len(raw_pages):
            errors.append(
                f"decision_countsの合計({decision_counts_sum})とpagesの件数({len(raw_pages)})が一致しません"
            )
        if isinstance(total_pages, int) and total_pages != lesson_pages_count:
            errors.append(
                f"candidates.jsonのtotal_pages({total_pages})とlesson_pages.jsonのページ数"
                f"({lesson_pages_count})が一致しません"
            )
        if progress_data is not None:
            if isinstance(total_pages, int) and progress_data.get("total_pages") != total_pages:
                errors.append("progress.jsonのtotal_pagesがcandidates.jsonと一致しません")

    if progress_data is not None:
        failed_pages = progress_data.get("failed_pages") or []
        if failed_pages:
            errors.append(f"progress.jsonのfailed_pagesが空ではありません: {failed_pages}")
        remaining_pages = set(progress_data.get("remaining_pages") or [])
    else:
        remaining_pages = set()

    lesson_page_by_no = {p.page_no: p for p in document.pages}
    comparison_by_page: dict[int, dict[str, Any]] = {}

    page_plans: list[PageChangePlan] = []

    for page_no in target_pages:
        candidate = candidate_by_page.get(page_no)
        if candidate is None:
            page_plans.append(PageChangePlan(
                page_no=page_no, source_image="", decision=None, reflectable=False,
                reject_reasons=["candidates.jsonにこのページの候補がありません"],
            ))
            continue

        reject_reasons: list[str] = []

        lesson_page = lesson_page_by_no.get(page_no)
        if lesson_page is None:
            reject_reasons.append("lesson_pages.jsonに対応するページが見つかりません")

        # 個別ページのcandidate JSONファイル（claude_review/pages/page_NNN.json）を読み、
        # 集約JSON（candidates.json）内の同ページ内容と一致するか検証する。
        per_page_path = paths.claude_review_pages_dir / f"page_{page_no:03d}.json"
        per_page_data: dict[str, Any] | None = None
        if not per_page_path.exists():
            reject_reasons.append(f"ページ別候補JSONが見つかりません: {per_page_path}")
        else:
            try:
                per_page_data = _load_json(per_page_path, label=f"page_{page_no:03d}.json")
            except OcrReviewApplyInputError as e:
                reject_reasons.append(str(e))
            else:
                if per_page_data.get("proposed_text") != candidate.get("proposed_text") or (
                    per_page_data.get("decision") != candidate.get("decision")
                ):
                    reject_reasons.append("ページ別候補JSONと集約candidates.jsonの内容が一致しません")

        # 比較元JSON（ocr_comparison/pages/page_NNN.json）とのpage_no・source_image整合性を検証する。
        comparison_path = paths.comparison_pages_dir / f"page_{page_no:03d}.json"
        comparison_data: dict[str, Any] | None = None
        if not comparison_path.exists():
            reject_reasons.append(f"比較元ページJSONが見つかりません: {comparison_path}")
        else:
            try:
                comparison_data = _load_json(comparison_path, label=f"比較元page_{page_no:03d}.json")
            except OcrReviewApplyInputError as e:
                reject_reasons.append(str(e))
            else:
                comparison_by_page[page_no] = comparison_data

        normalized_candidate_image: str | None = None
        try:
            normalized_candidate_image = _normalize_source_image(
                str(candidate.get("source_image", "")), label=f"Page{page_no}のcandidates.json"
            )
        except ValueError as e:
            reject_reasons.append(str(e))

        if normalized_candidate_image is not None:
            if lesson_page is not None:
                try:
                    normalized_lesson_image = _normalize_source_image(
                        lesson_page.source_image, label=f"Page{page_no}のlesson_pages.json"
                    )
                except ValueError as e:
                    reject_reasons.append(str(e))
                else:
                    if normalized_lesson_image != normalized_candidate_image:
                        reject_reasons.append(
                            "source_imageがlesson_pages.jsonとcandidates.jsonで一致しません: "
                            f"{normalized_lesson_image!r} != {normalized_candidate_image!r}"
                        )
            if comparison_data is not None:
                try:
                    normalized_comparison_image = _normalize_source_image(
                        str(comparison_data.get("source_image", "")), label=f"Page{page_no}の比較元JSON"
                    )
                except ValueError as e:
                    reject_reasons.append(str(e))
                else:
                    if normalized_comparison_image != normalized_candidate_image:
                        reject_reasons.append(
                            "source_imageがcandidates.jsonと比較元JSONで一致しません: "
                            f"{normalized_candidate_image!r} != {normalized_comparison_image!r}"
                        )
                if comparison_data.get("page_no") != page_no:
                    reject_reasons.append("比較元JSONのpage_noが一致しません")

        decision = candidate.get("decision")
        if decision not in _ALLOWED_DECISIONS:
            reject_reasons.append(f"decisionが未知の値です: {decision!r}")
        elif decision == "unresolved":
            reject_reasons.append("decisionがunresolvedです（画像から確定できていません）")

        if candidate.get("requires_human_review"):
            reject_reasons.append("requires_human_reviewがtrueです（人間の確認が必要です）")

        unresolved_spans = candidate.get("unresolved_spans") or []
        if unresolved_spans:
            reject_reasons.append(f"unresolved_spansが残っています（{len(unresolved_spans)}件）")

        proposed_text = candidate.get("proposed_text")
        if not isinstance(proposed_text, str) or not proposed_text.strip():
            reject_reasons.append("proposed_textが空です")

        if page_no in remaining_pages:
            reject_reasons.append("progress.jsonのremaining_pagesに含まれています（未完了）")

        reflectable = not reject_reasons
        plan = PageChangePlan(
            page_no=page_no,
            source_image=normalized_candidate_image or str(candidate.get("source_image", "")),
            decision=decision,
            reflectable=reflectable,
            reject_reasons=reject_reasons,
            corrections=candidate.get("corrections") or [],
        )

        if reflectable and lesson_page is not None and isinstance(proposed_text, str):
            before = {
                "title": lesson_page.title, "body": lesson_page.body, "summary": lesson_page.summary,
                "image_text": lesson_page.image_text, "canva_prompt": lesson_page.canva_prompt,
                "video_scene": lesson_page.video_scene,
            }
            new_page = apply_proposed_text_to_page(lesson_page, proposed_text)
            after = {
                "title": new_page.title, "body": new_page.body, "summary": new_page.summary,
                "image_text": new_page.image_text, "canva_prompt": new_page.canva_prompt,
                "video_scene": new_page.video_scene,
            }
            changed_fields = [f for f in _OCR_DERIVED_FIELDS if before[f] != after[f]]
            plan.before = before
            plan.after = after
            plan.changed_fields = changed_fields
            plan.has_changes = bool(changed_fields)

        page_plans.append(plan)

    passed = not errors and bool(page_plans) and all(p.reflectable for p in page_plans)

    return ApplyPlan(
        generated_at=generated_at,
        output_dir=str(paths.output_dir),
        lesson_pages_path=str(paths.lesson_pages_path),
        candidates_path=str(paths.candidates_path),
        target_pages=target_pages,
        passed=passed,
        errors=errors,
        pages=page_plans,
        document=document if passed else None,
    )


# --- 反映（--apply） -------------------------------------------------------------------------


def _atomic_write_json(path: Path, document: LessonDocument) -> None:
    """一時ファイルへ書いてから`os.replace`で置換する（途中状態のファイルを完成済みとして
    誤読させないため。`src/verification_evidence.py`の`_atomic_write_text`と同じ方式）。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + f".tmp-{os.getpid()}")
    write_lesson_pages_json(tmp_path, document)
    # 書き込んだ内容が正しくJSONとして読み戻せることを確認してから置換する。
    json.loads(tmp_path.read_text(encoding="utf-8"))
    os.replace(tmp_path, path)


def _create_backup(lesson_pages_path: Path, backups_dir: Path) -> Path:
    backups_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    backup_path = backups_dir / f"{timestamp}_lesson_pages.before_ocr_review.json"
    if backup_path.exists():
        raise ValueError(f"バックアップ先が既に存在します（上書きしません）: {backup_path}")
    backup_path.write_text(lesson_pages_path.read_text(encoding="utf-8"), encoding="utf-8")
    return backup_path


@dataclass
class ApplyResult:
    plan: ApplyPlan
    wrote_changes: bool
    backup_path: Path | None


def apply_document(plan: ApplyPlan, paths: OcrReviewApplyPaths) -> ApplyResult:
    """検証済み（`plan.passed`が`True`）の計画を、実際に`lesson_pages.json`へ書き込む。

    冪等性: 対象ページすべてが`has_changes=False`（既に反映済みと同一内容）の場合、
    バックアップも書き込みも行わない（`wrote_changes=False`で返す）。
    """
    if not plan.passed or plan.document is None:
        raise ValueError("検証に失敗した計画は反映できません（validate_and_plan()の結果を確認してください）")

    if not plan.changed_pages:
        return ApplyResult(plan=plan, wrote_changes=False, backup_path=None)

    new_document = copy.deepcopy(plan.document)
    page_by_no = {p.page_no: p for p in new_document.pages}
    for page_plan in plan.changed_pages:
        page = page_by_no[page_plan.page_no]
        page.title = page_plan.after["title"]
        page.body = page_plan.after["body"]
        page.summary = page_plan.after["summary"]
        page.image_text = page_plan.after["image_text"]
        page.canva_prompt = page_plan.after["canva_prompt"]
        page.video_scene = page_plan.after["video_scene"]

    backup_path = _create_backup(paths.lesson_pages_path, paths.backups_dir)
    try:
        _atomic_write_json(paths.lesson_pages_path, new_document)
    except Exception:
        # 書き込み失敗時、元ファイルはos.replace前なので未変更のまま。バックアップは残しておく
        # （原因調査のため）。
        raise

    return ApplyResult(plan=plan, wrote_changes=True, backup_path=backup_path)


# --- レポート -------------------------------------------------------------------------------


def _truncate(text: str, width: int = 60) -> str:
    text = text.replace("\n", "\\n")
    if len(text) <= width:
        return text
    return text[:width] + "…"


def render_apply_report_json(plan: ApplyPlan, *, mode: str, result: ApplyResult | None = None) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "mode": mode,
        "generated_at": plan.generated_at,
        "passed": plan.passed,
        "output_dir": plan.output_dir,
        "lesson_pages_path": plan.lesson_pages_path,
        "candidates_path": plan.candidates_path,
        "target_pages": plan.target_pages,
        "errors": plan.errors,
        "wrote_changes": result.wrote_changes if result else False,
        "backup_path": str(result.backup_path) if result and result.backup_path else None,
        "pages": [
            {
                "page_no": p.page_no,
                "source_image": p.source_image,
                "decision": p.decision,
                "reflectable": p.reflectable,
                "reject_reasons": p.reject_reasons,
                "has_changes": p.has_changes,
                "changed_fields": p.changed_fields,
                "before": p.before,
                "after": p.after,
                "corrections": p.corrections,
            }
            for p in plan.pages
        ],
    }


def render_apply_report_markdown(plan: ApplyPlan, *, mode: str, result: ApplyResult | None = None) -> str:
    lines: list[str] = ["# Claude OCRレビュー候補 反映レポート", ""]
    mode_label = {"dry_run": "dry-run（分析のみ。書き込みは行っていません）", "apply": "apply（実反映）"}[mode]
    lines.append(f"- モード: {mode_label}")
    lines.append(f"- 実行日時: {plan.generated_at}")
    lines.append(f"- 判定: {'passed' if plan.passed else 'failed'}")
    lines.append(f"- 入力lesson_pages: `{plan.lesson_pages_path}`")
    lines.append(f"- 入力candidates: `{plan.candidates_path}`")
    lines.append(f"- 対象ページ: {', '.join(str(p) for p in plan.target_pages) if plan.target_pages else '(なし)'}")
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
            lines.append(f"- decision: {p.decision}")
            lines.append(f"- 変更あり: {'はい' if p.has_changes else 'いいえ'}")
            if p.has_changes:
                lines.append(f"- 変更field: {', '.join(p.changed_fields)}")
                lines.append(f"- title: `{_truncate(p.before.get('title', ''))}` → `{_truncate(p.after.get('title', ''))}`")
                lines.append(f"- body（先頭のみ）: `{_truncate(p.before.get('body', ''))}` → `{_truncate(p.after.get('body', ''))}`")
                if p.corrections:
                    lines.append("- 主な修正:")
                    for c in p.corrections[:5]:
                        lines.append(
                            f"  - {c.get('location', '')}: `{c.get('tesseract', '')}` / `{c.get('apple_vision', '')}`"
                            f" → 採用: `{c.get('adopted', '')}`（{c.get('reason', '')}）"
                        )
            lines.append("")

    lines.append("## 次の操作")
    lines.append("")
    if mode == "dry_run":
        if plan.passed:
            lines.append("```bash")
            lines.append(
                f"python3 -m src.cli apply-ocr-review --output-dir {_output_dir_hint(plan)} --apply"
            )
            lines.append("```")
        else:
            lines.append(
                "反映不可ページを解消してから（Phase 10.9のレビューUIまたはcandidates.jsonの手動修正 → "
                "Claude Codeによる画像照合レビューの再実行）、再度dry-runを実行してください。"
            )
    else:
        if result and result.wrote_changes:
            lines.append("```bash")
            lines.append(
                f"python3 -m src.cli regenerate --input {plan.lesson_pages_path} --output-format all"
            )
            lines.append("```")
        else:
            lines.append("変更はありませんでした（既に反映済み、または反映可能なページがありません）。")
    lines.append("")

    return "\n".join(lines)


def _output_dir_hint(plan: ApplyPlan) -> str:
    return plan.output_dir


def write_apply_reports(plan: ApplyPlan, paths: OcrReviewApplyPaths, *, mode: str, result: ApplyResult | None = None) -> None:
    paths.report_dir.mkdir(parents=True, exist_ok=True)
    paths.report_json_path.write_text(
        json.dumps(render_apply_report_json(plan, mode=mode, result=result), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    paths.report_md_path.write_text(render_apply_report_markdown(plan, mode=mode, result=result), encoding="utf-8")
