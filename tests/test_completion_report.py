import re
from datetime import datetime

import pytest

from src.completion_report import CompletionReport, render_completion_report_html, write_completion_report


def _report(markdown="# タイトル\n\n内容", work_name="テスト作業", judgment="完了"):
    return CompletionReport(
        markdown=markdown, work_name=work_name, judgment=judgment, generated_at=datetime(2026, 7, 11, 12, 0, 0)
    )


def test_write_completion_report_generates_html_files(tmp_path):
    ts_path, latest_path = write_completion_report(_report(), reports_dir=tmp_path)
    assert ts_path.exists()
    assert latest_path.exists()
    assert ts_path.read_text(encoding="utf-8") == latest_path.read_text(encoding="utf-8")


def test_write_completion_report_does_not_overwrite_timestamped_files(tmp_path):
    report1 = _report(markdown="1回目のレポート")
    report2 = _report(markdown="2回目のレポート")

    ts_path1, _ = write_completion_report(report1, reports_dir=tmp_path)
    ts_path2, _ = write_completion_report(report2, reports_dir=tmp_path)

    assert ts_path1 != ts_path2
    assert ts_path1.exists()
    assert ts_path2.exists()
    assert "1回目のレポート" in ts_path1.read_text(encoding="utf-8")
    assert "2回目のレポート" in ts_path2.read_text(encoding="utf-8")


def test_write_completion_report_updates_latest_file(tmp_path):
    write_completion_report(_report(markdown="古いレポート"), reports_dir=tmp_path)
    _ts_path, latest_path = write_completion_report(_report(markdown="新しいレポート"), reports_dir=tmp_path)

    content = latest_path.read_text(encoding="utf-8")
    assert "新しいレポート" in content
    assert "古いレポート" not in content


def test_markdown_source_is_preserved_verbatim_for_copy(tmp_path):
    markdown = "# 見出し\n\n- 項目1\n- 項目2\n\n特殊文字 & < > \" ' のテスト"
    ts_path, _ = write_completion_report(_report(markdown=markdown), reports_dir=tmp_path)
    content = ts_path.read_text(encoding="utf-8")

    match = re.search(r"const reportMarkdown = (\".*?\");\n", content, re.DOTALL)
    assert match is not None
    import json

    recovered = json.loads(match.group(1).replace("<\\/script", "</script"))
    assert recovered == markdown


def test_html_special_characters_do_not_break_output(tmp_path):
    markdown = "本文に <b>タグ</b> や & 記号、\"引用符\" が含まれる"
    ts_path, _ = write_completion_report(_report(markdown=markdown), reports_dir=tmp_path)
    content = ts_path.read_text(encoding="utf-8")

    # 表示用ペイン（renderedView）に限っては、<b>タグが生のまま混入していない（エスケープされている）。
    # スクリプト内のMarkdown原文（コピー用）には元のタグがそのまま残るのが正しい仕様のため、
    # HTML全体ではなくrenderedViewセクションだけを対象に確認する。
    rendered_section = content.split('id="renderedView"')[1].split('id="rawView"')[0]
    assert "<b>タグ</b>" not in rendered_section
    assert "&lt;b&gt;タグ&lt;/b&gt;" in rendered_section
    # HTML全体としての基本構造が壊れていない。
    assert content.count("<html") == 1
    assert content.count("</html>") == 1


def test_script_injection_via_report_body_is_neutralized(tmp_path):
    """本文に</script>を含めても、埋め込み先の<script>タグが途中で終了しない
    （スクリプト注入・表示崩れを防ぐ）ことを確認する。"""
    import json as json_module

    markdown = '本文中に</script><script>alert("xss")</script>を含む'
    ts_path, _ = write_completion_report(_report(markdown=markdown), reports_dir=tmp_path)
    content = ts_path.read_text(encoding="utf-8")

    scripts = re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>", content, re.DOTALL)
    # スクリプトタグが本文の途中の</script>で誤って終了していれば、
    # 埋め込み用の1個だけのはずが複数、または壊れた分割になる。
    assert len(scripts) == 1
    assert "<\\/script" in scripts[0]

    # 埋め込まれたJSON文字列をデコードすると、元のMarkdown本文が完全に復元できる
    # （エスケープはコピー用の値を壊さない）ことを確認する。
    match = re.search(r"const reportMarkdown = (\".*?\");\n", content, re.DOTALL)
    recovered = json_module.loads(match.group(1).replace("<\\/script", "</script"))
    assert recovered == markdown


def test_copy_button_and_javascript_have_no_external_dependencies(tmp_path):
    ts_path, _ = write_completion_report(_report(), reports_dir=tmp_path)
    content = ts_path.read_text(encoding="utf-8")

    assert "全文をコピー" in content
    assert "navigator.clipboard" in content
    assert "execCommand" in content  # フォールバック
    assert "http://" not in content
    assert "https://" not in content
    assert "cdn." not in content.lower()


def test_secrets_are_not_specially_handled_but_caller_must_mask_before_calling():
    """completion_report自体は秘密情報のマスクを行わない（呼び出し側の責務）。
    このテストは、モジュールが本文をそのまま保持する（改変しない）仕様を明示する回帰テスト。"""
    markdown = "token=sk-should-be-masked-by-caller"
    report = _report(markdown=markdown)
    assert report.markdown == markdown


def test_output_dir_is_not_under_git_managed_paths_by_default():
    from src.completion_report import _DEFAULT_REPORTS_DIR

    assert str(_DEFAULT_REPORTS_DIR).startswith("output/")


def test_invalid_judgment_raises_clear_error():
    with pytest.raises(ValueError, match="judgment"):
        _report(judgment="不明")


def test_render_completion_report_html_includes_work_name_and_timestamp_and_judgment():
    report = _report(work_name="OCR品質改善", judgment="条件付き完了")
    rendered = render_completion_report_html(report)
    assert "OCR品質改善" in rendered
    assert "2026-07-11T12:00:00" in rendered
    assert "条件付き完了" in rendered


def test_render_completion_report_html_renders_checkbox_list_and_table():
    markdown = "## 完了条件\n- [x] できた\n- [ ] できなかった\n\n| a | b |\n|---|---|\n| 1 | 2 |\n"
    report = _report(markdown=markdown)
    rendered = render_completion_report_html(report)
    assert 'class="checkbox-checked"' in rendered
    assert 'class="checkbox-unchecked"' in rendered
    assert "report-table" in rendered


def test_render_completion_report_html_is_readable_without_javascript():
    """noscript環境でも、レポート本文（rendered_body）が最初から表示要素として存在する
    （JS実行後に初めて中身が挿入される構造ではない）ことを確認する。"""
    report = _report(markdown="# 見出し\n\n本文がここに入る")
    rendered = render_completion_report_html(report)
    assert 'id="renderedView"' in rendered
    assert "本文がここに入る" in rendered
    assert "<noscript>" in rendered


def test_write_completion_report_creates_reports_dir_if_missing(tmp_path):
    nested = tmp_path / "does" / "not" / "exist" / "reports"
    ts_path, latest_path = write_completion_report(_report(), reports_dir=nested)
    assert ts_path.exists()
    assert latest_path.exists()
