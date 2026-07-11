from __future__ import annotations

import datetime
import html
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from . import apple_vision_ocr, ocr_compare
from .ocr_patterns import get_allowed_words, load_ocr_patterns

# TesseractとApple Vision、2つの独立したOCRエンジンの結果をページごとに比較し、
# 不一致の大きいページを`needs_review`へ回すためのオーケストレーション・保存・レビュー用HTML生成。
#
# 重要: このモジュールはApple Vision結果を`output/editable/lesson_pages.json`へ一切書き込まない。
# 保存するのはGit管理対象外の`output/ocr_comparison/`配下のみであり、正式な編集対象は
# 引き続き`output/editable/lesson_pages.json`（Tesseract結果ベース）である。


@dataclass
class PageComparison:
    page_no: int
    source_image: str
    tesseract_text: str
    tesseract_available: bool
    tesseract_duration_seconds: float
    tesseract_score: float | None
    tesseract_quality: str | None
    vision_text: str
    vision_available: bool
    vision_warnings: list[str]
    vision_duration_seconds: float
    metrics: dict[str, Any] | None
    needs_review: bool
    mismatch_reasons: list[str]


@dataclass
class ComparisonSummary:
    generated_at: str
    language: str
    vision_helper_available: bool
    vision_unavailable_reason: str
    total_pages: int
    compared_pages: int
    needs_review_pages: list[int]
    tesseract_only_review_pages: list[int]
    vision_only_review_pages: list[int]
    both_engines_review_pages: list[int]
    pages: list[PageComparison] = field(default_factory=list)


def _now_iso() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def _resolve_source_image_path(source_image: str, assets_dir: Path) -> Path | None:
    """`source_image`（例: "assets/page_001.jpeg"）から、実ファイルの絶対パスを解決する。
    既存の`output/assets/`をそのまま参照し、画像を重複コピーしない。
    """
    if not source_image:
        return None
    candidate = assets_dir / Path(source_image).name
    return candidate if candidate.is_file() else None


def run_ocr_comparison_for_pages(
    imported_pages: list[dict[str, Any]],
    assets_dir: Path,
    *,
    language: str = "ja-JP",
    patterns: dict[str, Any] | None = None,
    helper_path: str | Path | None = None,
    project_root: Path | None = None,
    tesseract_diagnostics: list[dict[str, Any]] | None = None,
) -> ComparisonSummary:
    """取り込み済みページ（`import_source()`の戻り値の`pages`）に対し、既存のTesseract結果
    （各ページの`lines`）とApple Visionの結果を比較する。

    Tesseract自体は再実行しない（`imported_pages`に既にある結果を使う）。Apple Visionが
    利用できない場合（macOS以外・ヘルパー未ビルド等）は、エンジン不一致を理由に全ページを
    `needs_review`にはしない（比較自体を行わず、既存のTesseract品質判定に委ねる）。
    """
    if patterns is None:
        patterns, _meta = load_ocr_patterns()
    allowed_words = get_allowed_words(patterns)

    availability = apple_vision_ocr.check_apple_vision_availability(project_root)

    diagnostics_by_page = {d.get("page_no"): d for d in (tesseract_diagnostics or [])}

    pages: list[PageComparison] = []
    needs_review_pages: list[int] = []
    tesseract_only_review: list[int] = []
    vision_only_review: list[int] = []
    both_engines_review: list[int] = []

    for page in imported_pages:
        page_no = page.get("page_no")
        source_image = page.get("source_image", "") or ""
        tesseract_lines = page.get("lines", []) or []
        tesseract_text = "\n".join(str(line.get("text", "")) for line in tesseract_lines)
        tesseract_available = bool(tesseract_text.strip())

        diag = diagnostics_by_page.get(page_no, {})
        tesseract_score = diag.get("score")
        tesseract_quality = diag.get("quality")
        tesseract_own_needs_review = tesseract_quality == "needs_review"

        vision_result = apple_vision_ocr.AppleVisionResult()
        if availability.available:
            image_path = _resolve_source_image_path(source_image, assets_dir)
            if image_path is not None:
                vision_result = apple_vision_ocr.run_apple_vision_ocr(
                    image_path, language=language, helper_path=helper_path, project_root=project_root
                )

        metrics_dict: dict[str, Any] | None = None
        needs_review = False
        reasons: list[str] = []
        comparison_flagged = False
        if vision_result.available and tesseract_available:
            metrics = ocr_compare.compute_comparison_metrics(tesseract_text, vision_result.text, allowed_words)
            comparison_flagged, reasons = ocr_compare.evaluate_needs_review(metrics)
            metrics_dict = asdict(metrics)
        # Apple Visionが使えなかった場合はエンジン不一致による判定を行わない
        # （既存のTesseract品質判定[quality]だけをneeds_reviewの根拠にする）。

        needs_review = comparison_flagged or tesseract_own_needs_review
        if needs_review:
            needs_review_pages.append(page_no)
        if tesseract_own_needs_review and not comparison_flagged:
            tesseract_only_review.append(page_no)
        elif comparison_flagged and not tesseract_own_needs_review:
            vision_only_review.append(page_no)
        elif comparison_flagged and tesseract_own_needs_review:
            both_engines_review.append(page_no)

        pages.append(
            PageComparison(
                page_no=page_no,
                source_image=source_image,
                tesseract_text=tesseract_text,
                tesseract_available=tesseract_available,
                tesseract_duration_seconds=float(diag.get("duration_seconds", 0.0) or 0.0),
                tesseract_score=tesseract_score,
                tesseract_quality=tesseract_quality,
                vision_text=vision_result.text,
                vision_available=vision_result.available,
                vision_warnings=vision_result.warnings,
                vision_duration_seconds=vision_result.duration_seconds,
                metrics=metrics_dict,
                needs_review=needs_review,
                mismatch_reasons=reasons,
            )
        )

    return ComparisonSummary(
        generated_at=_now_iso(),
        language=language,
        vision_helper_available=availability.available,
        vision_unavailable_reason=availability.reason,
        total_pages=len(pages),
        compared_pages=sum(1 for p in pages if p.metrics is not None),
        needs_review_pages=needs_review_pages,
        tesseract_only_review_pages=tesseract_only_review,
        vision_only_review_pages=vision_only_review,
        both_engines_review_pages=both_engines_review,
        pages=pages,
    )


# --- 保存（output/ocr_comparison/） -----------------------------------------------------------


def render_comparison_summary_markdown(summary: ComparisonSummary) -> str:
    lines = [
        "# OCRエンジン比較サマリー（Tesseract vs Apple Vision）",
        "",
        f"- 生成日時: {summary.generated_at}",
        f"- 言語: {summary.language}",
        f"- Apple Vision利用可否: {'利用可能' if summary.vision_helper_available else '利用不可'}"
        + (f"（{summary.vision_unavailable_reason}）" if not summary.vision_helper_available else ""),
        f"- 対象ページ数: {summary.total_pages}",
        f"- 比較実施ページ数（両エンジンとも結果あり）: {summary.compared_pages}",
        f"- 要確認ページ数（needs_review）: {len(summary.needs_review_pages)}"
        + (f"（{', '.join(str(n) for n in summary.needs_review_pages)}）" if summary.needs_review_pages else ""),
        f"- Tesseractのみ要確認: {summary.tesseract_only_review_pages}",
        f"- Apple Visionとの不一致のみで要確認: {summary.vision_only_review_pages}",
        f"- 両方の理由で要確認: {summary.both_engines_review_pages}",
        "",
        "**このJSONは`output/editable/lesson_pages.json`へ自動反映されません。** "
        "正式な編集対象は引き続き`output/editable/lesson_pages.json`です。",
        "",
        "## ページ別",
        "",
        "| Page | Tesseract | Vision | 類似度 | needs_review | 不一致理由 |",
        "|---|---|---|---:|---|---|",
    ]
    for page in summary.pages:
        similarity = f"{page.metrics['text_similarity']:.2f}" if page.metrics else "-"
        reasons = "; ".join(page.mismatch_reasons) if page.mismatch_reasons else "-"
        lines.append(
            f"| {page.page_no} | {'OK' if page.tesseract_available else '空'} | "
            f"{'OK' if page.vision_available else '利用不可'} | {similarity} | "
            f"{'要確認' if page.needs_review else '-'} | {reasons} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_comparison_outputs(output_dir: Path, summary: ComparisonSummary) -> dict[str, Path]:
    """`output/ocr_comparison/`配下へ`summary.json`/`summary.md`/`pages/page_NNN.json`/
    `review.html`を書き出す。戻り値は生成した主要ファイルのパス一覧（実行ログ記録用）。
    """
    comparison_dir = output_dir / "ocr_comparison"
    pages_dir = comparison_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    summary_json_path = comparison_dir / "summary.json"
    summary_json_path.write_text(
        json.dumps(asdict(summary), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    summary_md_path = comparison_dir / "summary.md"
    summary_md_path.write_text(render_comparison_summary_markdown(summary), encoding="utf-8")

    for page in summary.pages:
        page_path = pages_dir / f"page_{page.page_no:03d}.json"
        page_path.write_text(json.dumps(asdict(page), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    review_html_path = comparison_dir / "review.html"
    review_html_path.write_text(render_comparison_review_html(summary), encoding="utf-8")

    return {
        "summary_json": summary_json_path,
        "summary_md": summary_md_path,
        "review_html": review_html_path,
        "pages_dir": pages_dir,
    }


# --- 全ページ目視確認Artifact（review.html） ---------------------------------------------------


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _render_page_section(page: PageComparison) -> str:
    badge = '<span class="badge badge-review">要確認</span>' if page.needs_review else '<span class="badge badge-ok">OK</span>'
    image_name = Path(page.source_image).name if page.source_image else ""
    image_tag = (
        f'<img src="../assets/{_esc(image_name)}" alt="page {page.page_no} source" loading="lazy">'
        if image_name
        else "<p>(元画像なし)</p>"
    )

    reasons_html = (
        "<ul>" + "".join(f"<li>{_esc(r)}</li>" for r in page.mismatch_reasons) + "</ul>"
        if page.mismatch_reasons
        else "<p>(不一致理由なし)</p>"
    )

    metrics = page.metrics or {}
    similarity = f"{metrics.get('text_similarity', 0):.2f}" if metrics else "-"
    title_similarity = f"{metrics.get('title_similarity', 0):.2f}" if metrics else "-"
    line_diff = metrics.get("line_count_diff", "-") if metrics else "-"

    vision_warnings_html = (
        "<ul>" + "".join(f"<li>{_esc(w)}</li>" for w in page.vision_warnings) + "</ul>"
        if page.vision_warnings
        else ""
    )

    return f"""
<section class="page-card" id="page-{page.page_no}">
  <div class="page-head">
    <h2>Page {page.page_no}</h2>
    {badge}
  </div>
  <div class="page-grid">
    <div class="col image-col">
      {image_tag}
      <dl class="stat-list">
        <dt>Tesseractスコア</dt><dd>{_esc(page.tesseract_score if page.tesseract_score is not None else "-")}</dd>
        <dt>Tesseract品質判定</dt><dd>{_esc(page.tesseract_quality or "-")}</dd>
        <dt>Tesseract処理時間</dt><dd>{page.tesseract_duration_seconds:.3f}s</dd>
        <dt>Apple Vision利用可否</dt><dd>{_esc("利用可能" if page.vision_available else "利用不可")}</dd>
        <dt>Apple Vision処理時間</dt><dd>{page.vision_duration_seconds:.3f}s</dd>
        <dt>全文類似度</dt><dd>{similarity}</dd>
        <dt>タイトル類似度</dt><dd>{title_similarity}</dd>
        <dt>行数差</dt><dd>{line_diff}</dd>
      </dl>
      {vision_warnings_html}
    </div>
    <div class="col text-col">
      <h3>Tesseract</h3>
      <pre class="ocr-text">{_esc(page.tesseract_text)}</pre>
      <h3>Apple Vision</h3>
      <pre class="ocr-text">{_esc(page.vision_text)}</pre>
    </div>
    <div class="col reason-col">
      <h3>不一致理由</h3>
      {reasons_html}
      <h3>人間確認欄</h3>
      <label><input type="checkbox"> 確認済み（Tesseract採用）</label><br>
      <label><input type="checkbox"> 確認済み（Apple Vision側が正しい）</label><br>
      <label><input type="checkbox"> 元画像を要再確認</label>
    </div>
  </div>
</section>
"""


def render_comparison_review_html(summary: ComparisonSummary) -> str:
    """全ページを目視確認できる自己完結型HTML（外部CDN/JS/CSS不使用）。

    ブラウザ上でのJSON編集・保存機能は今回対象外（目視確認用）。`output/assets/`の
    画像を相対パスで参照する（`output/ocr_comparison/review.html`から見て`../assets/`）。
    """
    pages_html = "".join(_render_page_section(page) for page in summary.pages)
    vision_status = (
        "利用可能" if summary.vision_helper_available else f"利用不可（{_esc(summary.vision_unavailable_reason)}）"
    )
    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OCRエンジン比較レビュー（Tesseract vs Apple Vision）</title>
<style>
  body {{ font-family: -apple-system, "Hiragino Sans", sans-serif; margin: 0; padding: 1.5rem; background: #f6f5f2; color: #222; }}
  h1 {{ font-size: 1.3rem; }}
  .summary {{ background: #fff; border: 1px solid #ddd; border-radius: 8px; padding: 1rem 1.2rem; margin-bottom: 1.5rem; }}
  .summary dl {{ display: grid; grid-template-columns: max-content 1fr; gap: 0.2rem 1rem; margin: 0.5rem 0 0; }}
  .page-card {{ background: #fff; border: 1px solid #ddd; border-radius: 8px; padding: 1rem 1.2rem; margin-bottom: 1.5rem; }}
  .page-head {{ display: flex; align-items: center; gap: 0.8rem; }}
  .badge {{ font-size: 0.75rem; padding: 0.15rem 0.6rem; border-radius: 999px; font-weight: 600; }}
  .badge-ok {{ background: #e5f3e9; color: #256a3e; }}
  .badge-review {{ background: #fbe8e6; color: #a3352b; }}
  .page-grid {{ display: grid; grid-template-columns: 260px 1fr 260px; gap: 1rem; margin-top: 0.8rem; }}
  .col img {{ max-width: 100%; border: 1px solid #ccc; border-radius: 4px; }}
  .stat-list {{ font-size: 0.82rem; margin-top: 0.6rem; }}
  .stat-list dt {{ color: #777; }}
  .stat-list dd {{ margin: 0 0 0.3rem; }}
  .ocr-text {{ white-space: pre-wrap; word-break: break-word; background: #f0efe9; border-radius: 4px; padding: 0.6rem; font-size: 0.82rem; max-height: 260px; overflow-y: auto; }}
  .reason-col ul {{ font-size: 0.82rem; padding-left: 1.1rem; }}
  @media (max-width: 900px) {{ .page-grid {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<h1>OCRエンジン比較レビュー（Tesseract vs Apple Vision）</h1>
<div class="summary">
  <dl>
    <dt>生成日時</dt><dd>{_esc(summary.generated_at)}</dd>
    <dt>Apple Vision</dt><dd>{vision_status}</dd>
    <dt>対象ページ数</dt><dd>{summary.total_pages}</dd>
    <dt>要確認ページ数</dt><dd>{len(summary.needs_review_pages)}</dd>
  </dl>
</div>
{pages_html}
</body>
</html>
"""
