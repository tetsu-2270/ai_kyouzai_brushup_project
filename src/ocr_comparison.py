from __future__ import annotations

import datetime
import difflib
import html
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from . import apple_vision_ocr, ocr_claude_review, ocr_compare
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
    `review.html`/（Apple Vision利用可能時のみ）`CLAUDE_OCR_REVIEW.md`/`claude_review/README.md`
    を書き出す。戻り値は生成した主要ファイルのパス一覧（実行ログ記録用）。
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

    paths: dict[str, Path] = {
        "summary_json": summary_json_path,
        "summary_md": summary_md_path,
        "review_html": review_html_path,
        "pages_dir": pages_dir,
    }

    claude_review_paths = ocr_claude_review.write_claude_review_entry_points(output_dir, summary)
    if claude_review_paths:
        paths.update(claude_review_paths)

    return paths


# --- 文字単位の差分ハイライト（review.html用。判定ロジック・正規化とは無関係） -----------------------
#
# `needs_review`判定（`src/ocr_compare.py`）が使う正規化・閾値とは別物。ここでの目的は
# 人間が目視で「どこが違うか」を素早く見つけられるようにすることだけであり、判定結果には
# 一切影響しない。Apple Visionを正解として扱わず、左（Tesseract）右（Apple Vision）を
# 対等に強調表示する（色の意味は「どちらの側にだけ存在するか／どちらの側が置換されたか」で
# あり、正誤の判定ではない）。

_DIFF_LEFT_DELETE_CLASS = "diff-tess-del"
_DIFF_LEFT_REPLACE_CLASS = "diff-tess-rep"
_DIFF_RIGHT_INSERT_CLASS = "diff-vision-ins"
_DIFF_RIGHT_REPLACE_CLASS = "diff-vision-rep"


def _normalize_diff_line_endings(text: str) -> str:
    """差分表示用に改行コードだけを`\\n`へ統一する。漢字・かな・句読点・長音・引用符・数字・
    空白は変更しない（`needs_review`判定用の`ocr_compare.normalize_for_comparison()`とは別物で、
    こちらは表示上の差分検出にそのまま使うため、改行コード以外は元の文字列を保持する）。
    """
    if not text:
        return ""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _wrap_diff_span(text: str, css_class: str, title: str) -> str:
    """差分断片を安全な`<mark>`要素として組み立てる。呼び出し側で既にHTMLエスケープ済みの
    生文字列（`text`）を渡すこと（本関数内では`text`自体はエスケープしない。属性値の`title`
    のみここでエスケープする）。
    """
    if not text:
        return ""
    return f'<mark class="{css_class}" title="{html.escape(title, quote=True)}">{text}</mark>'


def _render_text_diff(left: str, right: str) -> tuple[str, str]:
    """Tesseract全文(`left`)とApple Vision全文(`right`)を文字単位で比較し、安全な
    HTML断片`(left_html, right_html)`を返す。

    `difflib.SequenceMatcher`で**元の文字列を先に分割**してから、分割済みの各断片だけを
    個別に`html.escape()`する（エスケープ後の全文に対して文字位置を適用すると、
    `&`→`&amp;`等でインデックスがずれるため、必ずこの順序を守る）。生成する差分用タグは
    `<mark>`のみで、それ以外のタグをOCR文字列側から生成することはない。

    - `equal`: 通常表示（強調なし）
    - `delete`（Tesseractのみに存在）: 左側だけに`diff-tess-del`
    - `insert`（Apple Visionのみに存在）: 右側だけに`diff-vision-ins`
    - `replace`: 左側に`diff-tess-rep`、右側に`diff-vision-rep`

    一方が空文字の場合、`SequenceMatcher`は自動的に「もう一方の全文がinsert/delete」という
    単一のopcodeを返すため、特別な分岐は不要（存在する側の全文がその側だけの差分として
    強調される）。両方空の場合は`(OCRテキストなし)`という明確な表示を返す。
    """
    norm_left = _normalize_diff_line_endings(left)
    norm_right = _normalize_diff_line_endings(right)

    if not norm_left and not norm_right:
        empty = '<span class="diff-empty">(OCRテキストなし)</span>'
        return (empty, empty)

    matcher = difflib.SequenceMatcher(None, norm_left, norm_right, autojunk=False)
    left_parts: list[str] = []
    right_parts: list[str] = []
    for tag, a0, a1, b0, b1 in matcher.get_opcodes():
        left_chunk = norm_left[a0:a1]
        right_chunk = norm_right[b0:b1]
        if tag == "equal":
            left_parts.append(html.escape(left_chunk, quote=True))
            right_parts.append(html.escape(right_chunk, quote=True))
        elif tag == "delete":
            left_parts.append(
                _wrap_diff_span(html.escape(left_chunk, quote=True), _DIFF_LEFT_DELETE_CLASS, "Tesseractのみに存在")
            )
        elif tag == "insert":
            right_parts.append(
                _wrap_diff_span(html.escape(right_chunk, quote=True), _DIFF_RIGHT_INSERT_CLASS, "Apple Visionのみに存在")
            )
        elif tag == "replace":
            left_parts.append(
                _wrap_diff_span(
                    html.escape(left_chunk, quote=True), _DIFF_LEFT_REPLACE_CLASS, "Apple Visionと異なる（Tesseract側）"
                )
            )
            right_parts.append(
                _wrap_diff_span(
                    html.escape(right_chunk, quote=True), _DIFF_RIGHT_REPLACE_CLASS, "Tesseractと異なる（Apple Vision側）"
                )
            )

    return ("".join(left_parts), "".join(right_parts))


# --- 確定テキスト編集・採用判定・JSON書き出し（review.html。Phase 10.9） -----------------------------
#
# ここでの「採用」はあくまでレビュー用HTML内での作業であり、`output/editable/lesson_pages.json`
# （正式データ）へは一切書き込まない。書き出したJSONを正式データへ反映する処理は今回対象外
# （将来の別タスク）。採用優先順位・排他制御はJS側の`resolvePageAdoption()`（純粋関数）が担う。


def _safe_json_for_script(value: Any) -> str:
    """`<script>`タグ内へ安全に埋め込めるJSON文字列を組み立てる（`src/completion_report.py`の
    `_escape_for_script()`と同じ考え方）。`</script`・`<!--`断片を無害化し、OCR文字列に
    これらが含まれていてもスクリプト構造が壊れないようにする。
    """
    encoded = json.dumps(value, ensure_ascii=False)
    return encoded.replace("</script", "<\\/script").replace("<!--", "<\\!--")


# 採用判定ロジック（`resolvePageAdoption`）・ハッシュ（`simpleHash`）・保存キー組み立て
# （`buildMaterialId`/`buildStorageKey`）は、DOM・localStorage・確認ダイアログ等に一切依存しない
# 純粋関数として分離している。`tests/test_ocr_review_js.py`が`osascript -l JavaScript`
# （macOS標準搭載のJavaScriptCore）で実際にこのJSコードを実行してテストする。
_REVIEW_JS_PURE = """
function resolvePageAdoption(state) {
  var finalTextRaw = typeof state.finalText === "string" ? state.finalText : "";
  var finalText = finalTextRaw.trim();
  var tesseractSelected = !!state.tesseractSelected;
  var appleVisionSelected = !!state.appleVisionSelected;
  var bothSelected = tesseractSelected && appleVisionSelected;
  var reviewCompleted = !!state.reviewCompleted;

  var result = { adoptedSource: "unresolved", adoptedText: "", error: null, warning: null };

  if (finalText.length > 0) {
    result.adoptedSource = "edited";
    result.adoptedText = finalTextRaw;
    if (bothSelected) {
      result.warning = "Tesseract/Apple Visionが同時に採用指定されています（確定テキストを優先しました）";
    }
    return result;
  }

  if (bothSelected) {
    result.adoptedSource = "error";
    result.error = "Tesseract/Apple Visionが同時に採用指定されています";
    return result;
  }

  if (tesseractSelected) {
    result.adoptedSource = "tesseract";
    result.adoptedText = typeof state.tesseractText === "string" ? state.tesseractText : "";
    return result;
  }

  if (appleVisionSelected) {
    result.adoptedSource = "apple_vision";
    result.adoptedText = typeof state.appleVisionText === "string" ? state.appleVisionText : "";
    return result;
  }

  if (reviewCompleted) {
    result.warning = "確認完了と操作されていますが、採用結果が未確定です";
  }
  return result;
}

function simpleHash(input) {
  var str = String(input === undefined || input === null ? "" : input);
  var hash = 5381;
  for (var i = 0; i < str.length; i++) {
    hash = ((hash << 5) + hash) + str.charCodeAt(i);
    hash = hash & 0xffffffff;
  }
  return (hash >>> 0).toString(36);
}

function buildMaterialId(pageDataList) {
  var list = pageDataList || [];
  var fingerprint = list.map(function (p) { return (p && p.sourceImage) ? p.sourceImage : ""; }).join("|");
  return simpleHash(fingerprint || "ocr-comparison-review");
}

function buildStorageKey(materialId, pageNo) {
  return "ocr_review_state:" + materialId + ":page-" + pageNo;
}
"""

# DOM配線（イベント登録・localStorage保存/復元・コピー・書き出し）。`_REVIEW_JS_PURE`の
# 純粋関数だけを呼び出す薄い層に留め、判定ロジック自体はここへ書かない。
# `eval`/`new Function`は使用しない。`textContent`/`.value`のみを使い、OCR文字列・編集文字列を
# HTMLとして挿入することはない。
_REVIEW_JS_APP = """
(function () {
  "use strict";

  var pageDataEl = document.getElementById("ocr-review-page-data");
  var pageDataList = [];
  try {
    pageDataList = pageDataEl ? JSON.parse(pageDataEl.textContent) : [];
  } catch (e) {
    pageDataList = [];
  }
  var materialId = buildMaterialId(pageDataList);
  var pageDataByNo = {};
  pageDataList.forEach(function (p) { pageDataByNo[p.pageNo] = p; });

  function getEl(pageNo, role) {
    return document.querySelector('[data-page="' + pageNo + '"][data-role="' + role + '"]');
  }

  function storageKey(pageNo) {
    return buildStorageKey(materialId, pageNo);
  }

  function collectPageState(pageNo) {
    var finalTextEl = getEl(pageNo, "final-text");
    var tesseractRadio = getEl(pageNo, "adopt-tesseract");
    var visionRadio = getEl(pageNo, "adopt-vision");
    var reviewCheckbox = getEl(pageNo, "review-completed");
    var sourceCheckbox = getEl(pageNo, "requires-source-review");
    var data = pageDataByNo[pageNo] || {};
    return {
      finalText: finalTextEl ? finalTextEl.value : "",
      tesseractSelected: tesseractRadio ? tesseractRadio.checked : false,
      appleVisionSelected: visionRadio ? visionRadio.checked : false,
      requiresSourceReview: sourceCheckbox ? sourceCheckbox.checked : false,
      reviewCompleted: reviewCheckbox ? reviewCheckbox.checked : false,
      tesseractText: data.tesseractText || "",
      appleVisionText: data.appleVisionText || ""
    };
  }

  function updateSavedIndicator(pageNo, savedAt, failed) {
    var el = getEl(pageNo, "saved-indicator");
    if (!el) return;
    if (failed) {
      el.textContent = "保存に失敗しました";
      return;
    }
    el.textContent = savedAt ? ("保存済み " + String(savedAt).slice(11, 19)) : "未保存";
  }

  function saveState(pageNo) {
    var state = collectPageState(pageNo);
    var persisted = {
      finalText: state.finalText,
      tesseractSelected: state.tesseractSelected,
      appleVisionSelected: state.appleVisionSelected,
      requiresSourceReview: state.requiresSourceReview,
      reviewCompleted: state.reviewCompleted,
      savedAt: new Date().toISOString()
    };
    try {
      window.localStorage.setItem(storageKey(pageNo), JSON.stringify(persisted));
      updateSavedIndicator(pageNo, persisted.savedAt, false);
    } catch (e) {
      updateSavedIndicator(pageNo, null, true);
    }
  }

  function restoreState(pageNo) {
    var raw = null;
    try {
      raw = window.localStorage.getItem(storageKey(pageNo));
    } catch (e) {
      raw = null;
    }
    if (!raw) {
      updateSavedIndicator(pageNo, null, false);
      return;
    }
    var persisted;
    try {
      persisted = JSON.parse(raw);
    } catch (e) {
      return;
    }
    var finalTextEl = getEl(pageNo, "final-text");
    var tesseractRadio = getEl(pageNo, "adopt-tesseract");
    var visionRadio = getEl(pageNo, "adopt-vision");
    var reviewCheckbox = getEl(pageNo, "review-completed");
    var sourceCheckbox = getEl(pageNo, "requires-source-review");
    if (finalTextEl && typeof persisted.finalText === "string") finalTextEl.value = persisted.finalText;
    if (tesseractRadio) tesseractRadio.checked = !!persisted.tesseractSelected;
    if (visionRadio) visionRadio.checked = !!persisted.appleVisionSelected;
    if (reviewCheckbox) reviewCheckbox.checked = !!persisted.reviewCompleted;
    if (sourceCheckbox) sourceCheckbox.checked = !!persisted.requiresSourceReview;
    updateSavedIndicator(pageNo, persisted.savedAt || null, false);
  }

  function copyToFinal(pageNo, source) {
    var data = pageDataByNo[pageNo] || {};
    var text = source === "tesseract" ? (data.tesseractText || "") : (data.appleVisionText || "");
    var finalTextEl = getEl(pageNo, "final-text");
    if (!finalTextEl) return;
    if (finalTextEl.value.trim().length > 0) {
      var proceed = window.confirm("すでに確定欄に内容があります。上書きしますか？");
      if (!proceed) return;
    }
    finalTextEl.value = text;
    saveState(pageNo);
  }

  function clearAdoption(pageNo) {
    var tesseractRadio = getEl(pageNo, "adopt-tesseract");
    var visionRadio = getEl(pageNo, "adopt-vision");
    if (tesseractRadio) tesseractRadio.checked = false;
    if (visionRadio) visionRadio.checked = false;
    saveState(pageNo);
  }

  function resetAllState() {
    var proceed = window.confirm("すべてのページのレビュー状態を削除します。よろしいですか？");
    if (!proceed) return;
    pageDataList.forEach(function (p) {
      try {
        window.localStorage.removeItem(storageKey(p.pageNo));
      } catch (e) { /* ignore */ }
    });
    window.location.reload();
  }

  function exportReviewJson() {
    var errors = [];
    var pages = pageDataList.map(function (p) {
      var state = collectPageState(p.pageNo);
      var resolved = resolvePageAdoption(state);
      if (resolved.error) {
        errors.push("Page " + p.pageNo + ": " + resolved.error);
      }
      return {
        page_no: p.pageNo,
        adopted_source: resolved.adoptedSource,
        adopted_text: resolved.adoptedText,
        final_text: state.finalText,
        tesseract_selected: state.tesseractSelected,
        apple_vision_selected: state.appleVisionSelected,
        requires_source_review: state.requiresSourceReview,
        review_completed: state.reviewCompleted,
        error: resolved.error,
        warning: resolved.warning
      };
    });

    if (errors.length > 0) {
      window.alert("書き出しできない項目があります:\\n" + errors.join("\\n") + "\\n\\nTesseract/Apple Visionの採用指定を修正してください。");
      return;
    }

    var payload = {
      schema_version: 1,
      generated_at: new Date().toISOString(),
      source: "ocr_comparison_review",
      pages: pages
    };
    var jsonText = JSON.stringify(payload, null, 2);
    var blob = new Blob([jsonText], { type: "application/json" });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = "ocr_review_result.json";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  }

  function wirePage(pageNo) {
    var tesseractCopyBtn = getEl(pageNo, "copy-tesseract");
    var visionCopyBtn = getEl(pageNo, "copy-vision");
    var clearAdoptBtn = getEl(pageNo, "clear-adopt");
    if (tesseractCopyBtn) tesseractCopyBtn.addEventListener("click", function () { copyToFinal(pageNo, "tesseract"); });
    if (visionCopyBtn) visionCopyBtn.addEventListener("click", function () { copyToFinal(pageNo, "apple_vision"); });
    if (clearAdoptBtn) clearAdoptBtn.addEventListener("click", function () { clearAdoption(pageNo); });

    ["final-text", "adopt-tesseract", "adopt-vision", "review-completed", "requires-source-review"].forEach(function (role) {
      var el = getEl(pageNo, role);
      if (!el) return;
      var evt = role === "final-text" ? "input" : "change";
      el.addEventListener(evt, function () { saveState(pageNo); });
    });

    restoreState(pageNo);
  }

  pageDataList.forEach(function (p) { wirePage(p.pageNo); });

  var exportBtn = document.getElementById("ocr-review-export-btn");
  if (exportBtn) exportBtn.addEventListener("click", exportReviewJson);

  var resetBtn = document.getElementById("ocr-review-reset-btn");
  if (resetBtn) resetBtn.addEventListener("click", resetAllState);
})();
"""


# --- 全ページ目視確認Artifact（review.html） ---------------------------------------------------


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


_DIFF_LEGEND_HTML = """
    <div class="diff-legend">
      <span class="legend-item"><mark class="diff-tess-del" title="Tesseractのみに存在">例</mark> Tesseractのみ／削除相当（実線下線）</span>
      <span class="legend-item"><mark class="diff-tess-rep" title="Apple Visionと異なる（Tesseract側）">例</mark> Tesseract側の置換（破線下線）</span>
      <span class="legend-item"><mark class="diff-vision-ins" title="Apple Visionのみに存在">例</mark> Apple Visionのみ／追加相当（実線下線）</span>
      <span class="legend-item"><mark class="diff-vision-rep" title="Tesseractと異なる（Apple Vision側）">例</mark> Apple Vision側の置換（破線下線）</span>
      <span class="legend-item">背景なしの文字 = 一致</span>
    </div>"""


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

    tess_diff_html, vision_diff_html = _render_text_diff(page.tesseract_text, page.vision_text)
    page_no = page.page_no

    return f"""
<section class="page-card" id="page-{page_no}">
  <div class="page-head">
    <h2>Page {page_no}</h2>
    {badge}
  </div>
  {_DIFF_LEGEND_HTML}
  <div class="compare-grid">
    <div class="col image-col">
      {image_tag}
    </div>
    <div class="col tess-col">
      <div class="col-head">
        <h3>Tesseract（読み取り専用）</h3>
        <button type="button" class="copy-btn" data-page="{page_no}" data-role="copy-tesseract">確定欄へコピー</button>
      </div>
      <pre class="ocr-text diff-text">{tess_diff_html}</pre>
    </div>
    <div class="col vision-col">
      <div class="col-head">
        <h3>Apple Vision（読み取り専用）</h3>
        <button type="button" class="copy-btn" data-page="{page_no}" data-role="copy-vision">確定欄へコピー</button>
      </div>
      <pre class="ocr-text diff-text">{vision_diff_html}</pre>
    </div>
  </div>
  <div class="final-grid">
    <div class="col final-col">
      <div class="col-head">
        <h3>確定テキスト</h3>
        <span class="saved-indicator" data-page="{page_no}" data-role="saved-indicator">未保存</span>
      </div>
      <textarea class="final-text" data-page="{page_no}" data-role="final-text" rows="10"
        placeholder="上のコピーボタンでTesseract/Apple Visionの全文を入れるか、直接入力してください。内容があれば採用チェックより優先されます。"></textarea>
    </div>
    <div class="col adopt-col">
      <h3>採用判定</h3>
      <label><input type="radio" name="adopt-source-{page_no}" data-page="{page_no}" data-role="adopt-tesseract"> Tesseractを採用</label><br>
      <label><input type="radio" name="adopt-source-{page_no}" data-page="{page_no}" data-role="adopt-vision"> Apple Visionを採用</label><br>
      <button type="button" class="link-btn" data-page="{page_no}" data-role="clear-adopt">選択を解除</button>
      <hr>
      <label><input type="checkbox" data-page="{page_no}" data-role="requires-source-review"> 元画像を要再確認</label><br>
      <label><input type="checkbox" data-page="{page_no}" data-role="review-completed"> 確認完了</label>
    </div>
  </div>
  <div class="meta-grid">
    <div class="col stat-col">
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
    <div class="col reason-col">
      <h3>不一致理由</h3>
      {reasons_html}
    </div>
  </div>
</section>
"""


def render_comparison_review_html(summary: ComparisonSummary) -> str:
    """全ページを目視確認・確定テキスト編集ができる自己完結型HTML（外部CDN/JS/CSS不使用）。

    Tesseract/Apple Visionの表示欄は読み取り専用のまま維持し、編集可能な「確定テキスト」欄
    （`textarea`）を各ページに追加する。採用優先順位（確定テキスト＞採用チェック＞未確認）の
    判定と、レビュー状態の`localStorage`保存・復元、JSON書き出しはブラウザ上のJavaScript
    （`_REVIEW_JS_PURE`/`_REVIEW_JS_APP`）が行う。**このJSON書き出しは`output/editable/
    lesson_pages.json`・比較元の`summary.json`・ページ別JSON・Tesseract/Apple Vision結果の
    いずれも自動変更しない**（正式データへの反映は別タスク）。`output/assets/`の画像を
    相対パスで参照する（`output/ocr_comparison/review.html`から見て`../assets/`）。
    """
    pages_html = "".join(_render_page_section(page) for page in summary.pages)
    vision_status = (
        "利用可能" if summary.vision_helper_available else f"利用不可（{_esc(summary.vision_unavailable_reason)}）"
    )
    page_data = [
        {"pageNo": page.page_no, "tesseractText": page.tesseract_text, "appleVisionText": page.vision_text}
        for page in summary.pages
    ]
    page_data_json = _safe_json_for_script(page_data)
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
  .toolbar {{ display: flex; gap: 0.6rem; margin-top: 0.8rem; flex-wrap: wrap; }}
  .toolbar button {{ font-size: 0.85rem; padding: 0.45rem 0.9rem; border-radius: 6px; border: 1px solid #999; background: #fff; cursor: pointer; }}
  .toolbar button.primary {{ background: #2e6da4; color: #fff; border-color: #2e6da4; }}
  .toolbar button.danger {{ color: #a3352b; border-color: #c98f88; }}
  .page-card {{ background: #fff; border: 1px solid #ddd; border-radius: 8px; padding: 1rem 1.2rem; margin-bottom: 1.5rem; }}
  .page-head {{ display: flex; align-items: center; gap: 0.8rem; }}
  .badge {{ font-size: 0.75rem; padding: 0.15rem 0.6rem; border-radius: 999px; font-weight: 600; }}
  .badge-ok {{ background: #e5f3e9; color: #256a3e; }}
  .badge-review {{ background: #fbe8e6; color: #a3352b; }}
  .compare-grid {{ display: grid; grid-template-columns: 240px 1fr 1fr; gap: 1rem; margin-top: 0.6rem; }}
  .final-grid {{ display: grid; grid-template-columns: 2fr 1fr; gap: 1rem; margin-top: 1rem; }}
  .meta-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-top: 1rem; }}
  .col img {{ max-width: 100%; border: 1px solid #ccc; border-radius: 4px; }}
  .col-head {{ display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; }}
  .col-head h3 {{ margin: 0; }}
  .stat-list {{ font-size: 0.82rem; margin-top: 0.6rem; }}
  .stat-list dt {{ color: #777; }}
  .stat-list dd {{ margin: 0 0 0.3rem; }}
  .ocr-text {{ white-space: pre-wrap; word-break: break-word; background: #f0efe9; border-radius: 4px; padding: 0.6rem; font-size: 0.82rem; max-height: 320px; overflow-y: auto; }}
  .reason-col ul {{ font-size: 0.82rem; padding-left: 1.1rem; }}
  .diff-legend {{ display: flex; flex-wrap: wrap; gap: 0.4rem 1rem; font-size: 0.76rem; color: #555; margin-top: 0.6rem; }}
  .legend-item {{ display: inline-flex; align-items: center; gap: 0.3rem; }}
  mark.diff-tess-del, mark.diff-tess-rep {{
    background: #f8d7da; color: #7a1f1f; border-bottom: 2px solid #b0392f;
    padding: 0 1px; border-radius: 2px; text-decoration: none;
  }}
  mark.diff-tess-rep {{ border-bottom-style: dashed; }}
  mark.diff-vision-ins, mark.diff-vision-rep {{
    background: #d7e8fb; color: #1b3a63; border-bottom: 2px solid #2e6da4;
    padding: 0 1px; border-radius: 2px; text-decoration: none;
  }}
  mark.diff-vision-rep {{ border-bottom-style: dashed; }}
  .diff-empty {{ color: #999; font-style: italic; }}
  .copy-btn, .link-btn {{ font-size: 0.75rem; padding: 0.3rem 0.6rem; border-radius: 5px; border: 1px solid #999; background: #fff; cursor: pointer; }}
  .link-btn {{ border: none; background: none; color: #2e6da4; text-decoration: underline; padding: 0.2rem 0; cursor: pointer; }}
  .final-text {{ width: 100%; box-sizing: border-box; font-size: 0.82rem; font-family: inherit; padding: 0.6rem; border-radius: 4px; border: 1px solid #ccc; resize: vertical; }}
  .saved-indicator {{ font-size: 0.72rem; color: #777; }}
  .adopt-col label {{ font-size: 0.85rem; }}
  @media (max-width: 900px) {{
    .compare-grid {{ grid-template-columns: 1fr; }}
    .final-grid {{ grid-template-columns: 1fr; }}
    .meta-grid {{ grid-template-columns: 1fr; }}
  }}
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
  <div class="toolbar">
    <button type="button" class="primary" id="ocr-review-export-btn">レビュー結果をJSONで書き出す</button>
    <button type="button" class="danger" id="ocr-review-reset-btn">全レビュー状態をリセット</button>
  </div>
  <p class="raw-note" style="font-size:0.76rem;color:#777;">
    確定テキスト欄に内容があれば常に優先して採用されます。空の場合は採用チェックに従い、
    どちらも未選択なら未確認として扱われます。書き出したJSONは
    <code>output/editable/lesson_pages.json</code>等の既存データへ自動反映されません。
  </p>
</div>
{pages_html}
<script type="application/json" id="ocr-review-page-data">{page_data_json}</script>
<script>
{_REVIEW_JS_PURE}
{_REVIEW_JS_APP}
</script>
</body>
</html>
"""
