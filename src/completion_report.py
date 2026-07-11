from __future__ import annotations

import argparse
import html
import json
import re
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Claude Codeの完了報告を、コピー用ボタン付きの自己完結型HTML Artifactとして生成するモジュール。
# 目的は、Codex（別セッション・別ツール）へそのまま貼り付けられるMarkdown形式の完了レポートを、
# 外部CDN・外部JS・外部CSS・外部フォントに依存しない1枚のHTMLへ安全に埋め込むこと。
#
# レポート本文（Markdown）はコピー元として常にそのまま保持し、HTML表示用の装飾・タグを
# コピーされる本文へ混入させない。本文に`</script>`等が含まれてもスクリプト注入が起きないよう、
# JSON文字列化した後にスクリプト終了タグの断片をエスケープしてから埋め込む。
#
# 保存先は`output/reports/`（Git管理対象外）。実行ごとに新しいタイムスタンプ付きファイルを
# 生成し、過去の報告を上書きしない。`latest_claude_completion_report.html`は最新報告の複製。

_JUDGMENTS = ("完了", "条件付き完了", "未完了")

_DEFAULT_REPORTS_DIR = Path("output/reports")

_TIMESTAMPED_NAME_RE = re.compile(r"^\d{8}_\d{6}(?:_[0-9a-f]{4})?_claude_completion_report\.html$")


@dataclass
class CompletionReport:
    markdown: str
    work_name: str
    judgment: str
    generated_at: datetime

    def __post_init__(self) -> None:
        if self.judgment not in _JUDGMENTS:
            raise ValueError(f"judgmentは{_JUDGMENTS}のいずれかである必要があります: {self.judgment!r}")


def _escape_for_script(text: str) -> str:
    """JSON文字列化した後、`</script`断片を無害化してから<script>タグ内へ埋め込めるようにする。

    `json.dumps()`はデフォルトで`/`をエスケープしないため、本文に`</script>`が含まれていると、
    埋め込み先の<script>タグが本文の途中で終了してしまい、以降が生のHTMLとして解釈される
    （スクリプト注入・表示崩れの原因になる）。`<`の直後の`/script`をエスケープして防ぐ。
    """
    encoded = json.dumps(text, ensure_ascii=False)
    return encoded.replace("</script", "<\\/script").replace("<!--", "<\\!--")


# --- 簡易Markdown→HTML変換（このモジュールが生成する固定フォーマットの完了レポート専用） --------
# 汎用CommonMarkパーサーではない。「読みやすいレポート表示」用の軽量変換であり、
# 見出し・箇条書き・チェックボックス・表・コードブロック・太字・インラインコードのみ対応する。
# 変換前に必ずHTMLエスケープしてから構文を適用するため、任意の本文でHTMLが壊れることはない。


def _render_markdown_to_html(markdown_text: str) -> str:
    lines = markdown_text.split("\n")
    html_parts: list[str] = []
    in_code_block = False
    code_lines: list[str] = []
    list_open = False
    table_lines: list[str] = []

    def _flush_table() -> None:
        nonlocal table_lines
        if not table_lines:
            return
        rows = [
            [cell.strip() for cell in row.strip().strip("|").split("|")]
            for row in table_lines
            if not re.fullmatch(r"\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?", row.strip())
        ]
        if rows:
            html_parts.append('<div class="table-scroll"><table class="report-table">')
            html_parts.append("<thead><tr>" + "".join(f"<th>{_inline(c)}</th>" for c in rows[0]) + "</tr></thead>")
            html_parts.append("<tbody>")
            for row in rows[1:]:
                html_parts.append("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in row) + "</tr>")
            html_parts.append("</tbody></table></div>")
        table_lines = []

    def _close_list() -> None:
        nonlocal list_open
        if list_open:
            html_parts.append("</ul>")
            list_open = False

    def _inline(text: str) -> str:
        escaped = html.escape(text, quote=False)
        escaped = re.sub(r"`([^`]+)`", r'<code class="inline">\1</code>', escaped)
        escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
        return escaped

    for raw_line in lines:
        line = raw_line.rstrip()

        if line.strip().startswith("```"):
            if in_code_block:
                html_parts.append(
                    '<pre class="report-code"><code>' + html.escape("\n".join(code_lines)) + "</code></pre>"
                )
                code_lines = []
                in_code_block = False
            else:
                _close_list()
                _flush_table()
                in_code_block = True
            continue
        if in_code_block:
            code_lines.append(raw_line)
            continue

        if line.strip().startswith("|"):
            table_lines.append(line.strip())
            continue
        else:
            _flush_table()

        heading_match = re.match(r"^(#{1,4})\s+(.*)$", line)
        if heading_match:
            _close_list()
            level = min(len(heading_match.group(1)) + 1, 6)
            html_parts.append(f"<h{level}>{_inline(heading_match.group(2))}</h{level}>")
            continue

        checkbox_match = re.match(r"^-\s+\[( |x)\]\s+(.*)$", line)
        if checkbox_match:
            if not list_open:
                html_parts.append('<ul class="report-list">')
                list_open = True
            checked = checkbox_match.group(1) == "x"
            mark = "checked" if checked else "unchecked"
            html_parts.append(f'<li class="checkbox-{mark}">{_inline(checkbox_match.group(2))}</li>')
            continue

        bullet_match = re.match(r"^-\s+(.*)$", line)
        if bullet_match:
            if not list_open:
                html_parts.append('<ul class="report-list">')
                list_open = True
            html_parts.append(f"<li>{_inline(bullet_match.group(1))}</li>")
            continue

        _close_list()
        if not line.strip():
            continue
        html_parts.append(f"<p>{_inline(line)}</p>")

    _close_list()
    _flush_table()
    if in_code_block and code_lines:
        html_parts.append('<pre class="report-code"><code>' + html.escape("\n".join(code_lines)) + "</code></pre>")

    return "\n".join(html_parts)


_JUDGMENT_CLASS = {"完了": "judge-done", "条件付き完了": "judge-partial", "未完了": "judge-incomplete"}


def render_completion_report_html(report: CompletionReport) -> str:
    """自己完結型HTML Artifact全体を組み立てる。外部CDN・外部JS・外部CSS・外部フォントは使わない。"""
    rendered_body = _render_markdown_to_html(report.markdown)
    escaped_markdown_for_script = _escape_for_script(report.markdown)
    escaped_work_name = html.escape(report.work_name)
    escaped_judgment = html.escape(report.judgment)
    judgment_class = _JUDGMENT_CLASS.get(report.judgment, "judge-partial")
    generated_at_display = report.generated_at.isoformat(timespec="seconds")

    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Claude Code完了レポート: {escaped_work_name}</title>
<style>
{_STYLE_CSS}
</style>
</head>
<body>
<div class="topbar">
  <div class="topbar-info">
    <span class="label">Claude Code完了レポート</span>
    <span class="work-name">{escaped_work_name}</span>
  </div>
  <div class="topbar-actions">
    <span class="judge-badge {judgment_class}">{escaped_judgment}</span>
    <button class="copy-btn" id="copyBtn" onclick="copyReport()">全文をコピー</button>
    <button class="toggle-btn" id="toggleBtn" onclick="toggleRaw()">Markdown原文を表示</button>
  </div>
</div>
<div id="copyStatus" class="copy-status" role="status" aria-live="polite"></div>
<main class="wrap">
  <header class="meta">
    <div><span class="meta-label">作業名</span><span class="meta-value">{escaped_work_name}</span></div>
    <div><span class="meta-label">作成日時</span><span class="meta-value">{html.escape(generated_at_display)}</span></div>
    <div><span class="meta-label">判定</span><span class="meta-value judge-text {judgment_class}">{escaped_judgment}</span></div>
  </header>
  <section id="renderedView" class="report-body">
{rendered_body}
  </section>
  <section id="rawView" class="raw-view" hidden>
    <p class="raw-note">Markdown原文（JavaScript無効時やコピー操作が使えない場合は、この欄を選択してコピーしてください）。</p>
    <textarea id="rawTextarea" class="raw-textarea" readonly rows="20"></textarea>
  </section>
</main>
<noscript>
  <div class="noscript-note">JavaScriptが無効なため、コピーボタンは動作しません。上記のレポート本文をそのまま選択してコピーしてください。</div>
</noscript>
<script>
const reportMarkdown = {escaped_markdown_for_script};

document.getElementById('rawTextarea').value = reportMarkdown;

function copyReport() {{
  const status = document.getElementById('copyStatus');
  const btn = document.getElementById('copyBtn');
  const showSuccess = () => {{
    status.textContent = 'コピーしました。';
    status.className = 'copy-status success';
    btn.textContent = 'コピーしました';
    setTimeout(() => {{ btn.textContent = '全文をコピー'; status.textContent = ''; status.className = 'copy-status'; }}, 2200);
  }};
  const showFailure = () => {{
    status.textContent = '自動コピーに失敗しました。「Markdown原文を表示」から手動で選択・コピーしてください。';
    status.className = 'copy-status failure';
    toggleRaw(true);
  }};
  if (navigator.clipboard && navigator.clipboard.writeText) {{
    navigator.clipboard.writeText(reportMarkdown).then(showSuccess).catch(fallbackCopy);
  }} else {{
    fallbackCopy();
  }}
  function fallbackCopy() {{
    try {{
      const ta = document.getElementById('rawTextarea');
      ta.removeAttribute('hidden');
      document.getElementById('rawView').removeAttribute('hidden');
      ta.focus();
      ta.select();
      const ok = document.execCommand('copy');
      if (ok) {{ showSuccess(); }} else {{ showFailure(); }}
    }} catch (e) {{
      showFailure();
    }}
  }}
}}

function toggleRaw(forceShow) {{
  const rawView = document.getElementById('rawView');
  const toggleBtn = document.getElementById('toggleBtn');
  const shouldShow = forceShow === true ? true : rawView.hasAttribute('hidden');
  if (shouldShow) {{
    rawView.removeAttribute('hidden');
    toggleBtn.textContent = 'Markdown原文を隠す';
  }} else {{
    rawView.setAttribute('hidden', '');
    toggleBtn.textContent = 'Markdown原文を表示';
  }}
}}
</script>
</body>
</html>
"""


_STYLE_CSS = """
:root {
  --bg: #f5f3ee; --bg-elevated: #ffffff; --ink: #221f1a; --ink-soft: #57534a; --ink-faint: #8a8577;
  --accent: #35618f; --line: #ded8c9; --ok: #3f7a52; --ok-bg: #e7f1ea;
  --warn: #a3781f; --warn-bg: #f6ecd6; --danger: #b0392f; --danger-bg: #f5e2df; --code-bg: #ece7da;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #191b1e; --bg-elevated: #232629; --ink: #eae7e0; --ink-soft: #b3aea1; --ink-faint: #837d6e;
    --accent: #7fa8d4; --line: #363530; --ok: #7dbf92; --ok-bg: #223027;
    --warn: #d6b463; --warn-bg: #362c17; --danger: #e08277; --danger-bg: #3a2320; --code-bg: #272a24;
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink); font-family: -apple-system, "Hiragino Sans", "Hiragino Kaku Gothic ProN", "Yu Gothic", sans-serif; line-height: 1.7; }
.topbar { position: sticky; top: 0; z-index: 10; display: flex; justify-content: space-between; align-items: center; gap: 1rem; flex-wrap: wrap; padding: 0.7rem 1.2rem; background: color-mix(in srgb, var(--bg) 90%, transparent); backdrop-filter: blur(8px); border-bottom: 1px solid var(--line); }
.topbar-info { display: flex; flex-direction: column; }
.label { font-size: 0.72rem; letter-spacing: 0.06em; color: var(--ink-faint); text-transform: uppercase; }
.work-name { font-weight: 700; font-size: 0.95rem; }
.topbar-actions { display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap; }
.judge-badge { font-size: 0.78rem; font-weight: 700; padding: 0.25rem 0.7rem; border-radius: 999px; }
.judge-done { background: var(--ok-bg); color: var(--ok); }
.judge-partial { background: var(--warn-bg); color: var(--warn); }
.judge-incomplete { background: var(--danger-bg); color: var(--danger); }
.copy-btn, .toggle-btn { border: 1px solid var(--accent); background: var(--accent); color: #fff; padding: 0.45rem 0.9rem; border-radius: 6px; font-size: 0.82rem; cursor: pointer; font-weight: 600; }
.toggle-btn { background: transparent; color: var(--accent); }
.copy-status { min-height: 1.6rem; text-align: center; font-size: 0.82rem; padding: 0.2rem; }
.copy-status.success { color: var(--ok); }
.copy-status.failure { color: var(--danger); }
.wrap { max-width: 860px; margin: 0 auto; padding: 1rem 1.4rem 4rem; }
.meta { display: flex; gap: 1.5rem; flex-wrap: wrap; padding: 1rem 0; border-bottom: 1px solid var(--line); margin-bottom: 1.2rem; }
.meta-label { display: block; font-size: 0.72rem; color: var(--ink-faint); text-transform: uppercase; letter-spacing: 0.05em; }
.meta-value { font-size: 0.92rem; font-weight: 600; }
.judge-text.judge-done { color: var(--ok); }
.judge-text.judge-partial { color: var(--warn); }
.judge-text.judge-incomplete { color: var(--danger); }
.report-body h1 { font-size: 1.5rem; margin-top: 0; }
.report-body h2 { font-size: 1.2rem; margin-top: 1.6rem; padding-left: 0.6rem; border-left: 3px solid var(--accent); }
.report-body h3 { font-size: 1.02rem; margin-top: 1.2rem; color: var(--ink-soft); }
.report-body p { margin: 0.4rem 0; }
ul.report-list { list-style: none; margin: 0.5rem 0; padding: 0; display: flex; flex-direction: column; gap: 0.3rem; }
ul.report-list li { background: var(--bg-elevated); border: 1px solid var(--line); border-radius: 6px; padding: 0.45rem 0.75rem; font-size: 0.88rem; }
ul.report-list li.checkbox-checked::before { content: "\\2713  "; color: var(--ok); font-weight: 700; }
ul.report-list li.checkbox-unchecked::before { content: "\\25b3  "; color: var(--warn); font-weight: 700; }
.table-scroll { overflow-x: auto; border: 1px solid var(--line); border-radius: 8px; margin: 0.6rem 0; background: var(--bg-elevated); }
table.report-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; min-width: 420px; }
table.report-table th, table.report-table td { padding: 0.45rem 0.6rem; border-bottom: 1px solid var(--line); text-align: left; }
table.report-table th { color: var(--ink-faint); font-size: 0.72rem; text-transform: uppercase; }
code.inline { background: var(--code-bg); padding: 0.08rem 0.32rem; border-radius: 4px; font-size: 0.88em; }
pre.report-code { background: var(--code-bg); border-radius: 8px; padding: 0.8rem 1rem; overflow-x: auto; font-size: 0.82rem; }
.raw-view { margin-top: 1.5rem; border-top: 1px solid var(--line); padding-top: 1rem; }
.raw-note { font-size: 0.82rem; color: var(--ink-faint); }
.raw-textarea { width: 100%; font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 0.8rem; background: var(--code-bg); color: var(--ink); border: 1px solid var(--line); border-radius: 8px; padding: 0.8rem; }
.noscript-note { background: var(--warn-bg); color: var(--warn); padding: 0.8rem 1.2rem; text-align: center; font-size: 0.85rem; }
@media print {
  .topbar, .copy-status, .raw-view, .toggle-btn { display: none; }
  body { background: #fff; color: #000; }
}
"""


def _unique_timestamped_path(reports_dir: Path, generated_at: datetime) -> Path:
    """`実行ごとに上書きしないファイル`を生成するためのパスを決める。同一秒に複数回呼ばれても
    衝突しないよう、必要な場合だけ短いランダムサフィックスを付ける。"""
    base_timestamp = generated_at.strftime("%Y%m%d_%H%M%S")
    candidate = reports_dir / f"{base_timestamp}_claude_completion_report.html"
    if not candidate.exists():
        return candidate
    suffix = uuid.uuid4().hex[:4]
    return reports_dir / f"{base_timestamp}_{suffix}_claude_completion_report.html"


def write_completion_report(
    report: CompletionReport, reports_dir: Path | str = _DEFAULT_REPORTS_DIR
) -> tuple[Path, Path]:
    """完了レポートHTMLを、タイムスタンプ付きファイル（過去分は上書きしない）と
    `latest_claude_completion_report.html`（毎回更新）の両方へ書き出す。

    戻り値は`(タイムスタンプ付きファイルのパス, latestファイルのパス)`。
    """
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    html_content = render_completion_report_html(report)

    timestamped_path = _unique_timestamped_path(reports_dir, report.generated_at)
    timestamped_path.write_text(html_content, encoding="utf-8")

    latest_path = reports_dir / "latest_claude_completion_report.html"
    latest_path.write_text(html_content, encoding="utf-8")

    return timestamped_path, latest_path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Claude Codeの完了レポート（Markdown）を、コピー用ボタン付きの自己完結型HTMLへ変換して"
        "output/reports/へ保存する"
    )
    parser.add_argument("--work-name", required=True, help="作業名（レポートのタイトルに使う）")
    parser.add_argument("--judgment", required=True, choices=_JUDGMENTS, help="完了 / 条件付き完了 / 未完了")
    parser.add_argument(
        "--markdown-file", required=True, help="完了レポート本文（Markdown）を含むファイルのパス。'-'で標準入力"
    )
    parser.add_argument(
        "--reports-dir", default=str(_DEFAULT_REPORTS_DIR), help="保存先ディレクトリ（既定: output/reports）"
    )
    args = parser.parse_args(argv)

    if args.markdown_file == "-":
        markdown_text = sys.stdin.read()
    else:
        markdown_text = Path(args.markdown_file).read_text(encoding="utf-8")

    report = CompletionReport(
        markdown=markdown_text,
        work_name=args.work_name,
        judgment=args.judgment,
        generated_at=datetime.now().astimezone(),
    )
    timestamped_path, latest_path = write_completion_report(report, reports_dir=args.reports_dir)
    print(f"report: {timestamped_path}")
    print(f"latest: {latest_path}")


if __name__ == "__main__":
    main()
