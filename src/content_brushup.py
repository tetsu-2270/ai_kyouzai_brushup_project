from __future__ import annotations

import difflib
import hashlib
import html
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .lesson_pages import LessonDocument, LessonPage

# Phase 10.13: OCR確定原文（editable/lesson_pages.json）を変更不能な証拠として保持したまま、
# 教材本文を分かりやすくブラッシュアップするための「準備（スナップショット・指示書生成）」と
# 「候補JSON検証・レビューHTML生成」を担当するモジュール。
#
# 最終目的（このプロジェクト全体）:
#   元教材画像 → 正確な原文を取得 → 教材本文を分かりやすく改善
#   → 内容に合ったページ構成・画像デザインを作る → ブラッシュアップ済み教材を出力
# Phase 10.7〜10.11で「正確な原文を取得」まで、Phase 10.12で「画像デザイン」の器が完成した。
# 本Phaseは「教材本文を分かりやすく改善」を担う。
#
# 重要な設計方針:
# - OCR確定原文（VERIFIED_OCR_SNAPSHOT.json）は本文ブラッシュアップによって一切変更されない。
#   比較元・証拠として保存するだけの読み取り専用ファイル。
# - 実際の反映（editable/lesson_pages.jsonの更新）は本モジュールでは行わない
#   （`content_brushup_apply.py`の役割）。
# - ページ数・ページ順・source_page_no・画像レイアウト・デザインJSONは一切変更しない
#   （構成のブラッシュアップは既存restructureモードまたは別工程の役割）。

CONTENT_BRUSHUP_DIR_NAME = "content_brushup"
SNAPSHOT_FILENAME = "VERIFIED_OCR_SNAPSHOT.json"
INSTRUCTIONS_FILENAME = "AI_CONTENT_BRUSHUP.md"
README_FILENAME = "README.md"
PROGRESS_FILENAME = "progress.json"
CANDIDATES_FILENAME = "candidates.json"
REVIEW_SUMMARY_FILENAME = "review_summary.md"
REVIEW_HTML_FILENAME = "review.html"

_SNAPSHOT_SOURCE = "verified_ocr_lesson_pages"
_CANDIDATES_SOURCE = "ai_content_brushup"
_ALLOWED_CHANGE_TYPES = (
    "typo", "normalize", "clarify", "simplify", "split_sentence",
    "remove_redundancy", "heading", "hierarchy", "tone",
)
_ALLOWED_RISK_LEVELS = ("low", "medium", "high")
_EDITABLE_FIELDS = ("title", "body", "summary")


# --- パス解決 -----------------------------------------------------------------------------


@dataclass
class ContentBrushupPaths:
    output_dir: Path
    lesson_pages_path: Path
    content_dir: Path
    snapshot_path: Path
    instructions_path: Path
    readme_path: Path
    progress_path: Path
    candidates_path: Path
    review_summary_path: Path
    review_html_path: Path
    pages_dir: Path
    backups_dir: Path


def resolve_paths(output_dir: str | Path) -> ContentBrushupPaths:
    base = Path(output_dir)
    content_dir = base / CONTENT_BRUSHUP_DIR_NAME
    return ContentBrushupPaths(
        output_dir=base,
        lesson_pages_path=base / "editable" / "lesson_pages.json",
        content_dir=content_dir,
        snapshot_path=content_dir / SNAPSHOT_FILENAME,
        instructions_path=content_dir / INSTRUCTIONS_FILENAME,
        readme_path=content_dir / README_FILENAME,
        progress_path=content_dir / PROGRESS_FILENAME,
        candidates_path=content_dir / CANDIDATES_FILENAME,
        review_summary_path=content_dir / REVIEW_SUMMARY_FILENAME,
        review_html_path=content_dir / REVIEW_HTML_FILENAME,
        pages_dir=content_dir / "pages",
        backups_dir=base / "editable" / "backups",
    )


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative_output_dir(output_dir: Path) -> str:
    from .ocr_claude_review import _relative_output_dir as _rel

    return _rel(output_dir)


def format_page_number_ranges(page_numbers: list[int]) -> str:
    from .ocr_claude_review import format_page_number_ranges as _format

    return _format(page_numbers)


# --- OCR確定原文スナップショット ---------------------------------------------------------------


def build_snapshot(document: LessonDocument, lesson_pages_path: Path) -> dict[str, Any]:
    """`editable/lesson_pages.json`から、本文ブラッシュアップの比較元となるスナップショットを作る。

    単純なファイルコピーではなく、「本文改善前の比較元である」ことを明示した専用スキーマにする
    （`source`フィールド・`source_sha256`により、後から`apply-content-brushup`が現在の
    `lesson_pages.json`と整合しているかを機械的に検証できる）。
    """
    return {
        "schema_version": 1,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": _SNAPSHOT_SOURCE,
        "source_lesson_pages": "editable/lesson_pages.json",
        "source_sha256": file_sha256(lesson_pages_path),
        "metadata": {
            "mode": document.metadata.mode,
            "project_title": document.metadata.project_title,
            "target_audience": document.metadata.target_audience,
            "tone": document.metadata.tone,
        },
        "pages": [
            {
                "page_no": page.page_no,
                "source_page_no": list(page.source_page_no),
                "source_image": page.source_image,
                "title": page.title,
                "body": page.body,
                "summary": page.summary,
            }
            for page in document.pages
        ],
    }


def write_snapshot(path: Path, snapshot: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


@dataclass
class SnapshotStatus:
    exists: bool
    stale: bool
    snapshot: dict[str, Any] | None
    current_sha256: str


def check_snapshot_status(paths: ContentBrushupPaths) -> SnapshotStatus:
    """既存スナップショットが現在の`lesson_pages.json`と一致しているかを確認する。

    既存の作業中候補（pages/progress/candidates）を`prepare-content-brushup`が黙って破棄しない
    ようにするため、スナップショットが最新の場合は再生成せず、古い場合は明確に警告する
    （実際に上書きするかどうかはCLI側の`--force`判断に委ねる）。
    """
    current_sha256 = file_sha256(paths.lesson_pages_path)
    if not paths.snapshot_path.exists():
        return SnapshotStatus(exists=False, stale=False, snapshot=None, current_sha256=current_sha256)
    snapshot = json.loads(paths.snapshot_path.read_text(encoding="utf-8"))
    stale = snapshot.get("source_sha256") != current_sha256
    return SnapshotStatus(exists=True, stale=stale, snapshot=snapshot, current_sha256=current_sha256)


# --- 指示書生成 -----------------------------------------------------------------------------


def render_ai_content_brushup_instructions(document: LessonDocument, output_dir: Path, snapshot_sha256: str) -> str:
    """`AI_CONTENT_BRUSHUP.md`（Claude Code/Codex双方で使える製品非依存の指示書）を組み立てる。

    実データから埋め込むのは、ページ総数・ページ番号一覧・相対パス・対象読者/トーン・
    スナップショットのSHA-256等の構造情報のみ。本文（title/body/summary）はここへ複製しない
    （AIエージェントは`VERIFIED_OCR_SNAPSHOT.json`を直接読む設計のため）。
    """
    rel_dir = _relative_output_dir(output_dir)
    content_rel = f"{rel_dir}/{CONTENT_BRUSHUP_DIR_NAME}"
    page_numbers = [p.page_no for p in document.pages]
    page_range_text = format_page_number_ranges(page_numbers)
    first_page = page_numbers[0] if page_numbers else 1

    lines: list[str] = []
    a = lines.append

    a("# AI教材本文ブラッシュアップ指示書")
    a("")
    a("（`prepare-content-brushup`が自動生成。Claude Code・Codexのどちらでも同じ手順で使えます）")
    a("")
    a("このファイルは自己完結した作業指示書です。**このファイルを読むだけで、追加の質問をせず")
    a("最後まで作業を進めてください。**")
    a("")

    a("## 0. 最終目的とこの作業の位置づけ（最重要）")
    a("")
    a("```text")
    a("元教材画像 → 正確な原文を取得 → 教材本文を分かりやすく改善")
    a("→ 内容に合ったページ構成・画像デザインを作る → ブラッシュアップ済み教材を出力")
    a("```")
    a("")
    a("**OCR確定本文は、元画像に何と書かれていたかを示す正確な転記であり、文章品質が")
    a("完成していることを意味しません。**")
    a("")
    a("OCR確定本文は証拠として保持します。その複製を基に、元教材の主旨・結論・事実を")
    a("変えない範囲で、読みやすさ・分かりやすさ・簡潔さ・情報階層を改善してください。")
    a("")
    a("**最終画像には、OCR確定原文ではなく、人間が承認したブラッシュアップ済み本文を")
    a("使用します。**")
    a("")
    a("**あなたが行わないこと:**")
    a("")
    a("- ページ数・ページ順・`source_page_no`の変更（構成の変更は別工程の役割です）")
    a("- 複数ページの統合・1ページの分割")
    a("- 画像レイアウト・デザインJSONの変更")
    a("- `editable/lesson_pages.json`への直接書き込み（`apply-content-brushup`の役割です）")
    a("- `VERIFIED_OCR_SNAPSHOT.json`の変更（証拠ファイルです）")
    a("- Claude API等の外部呼び出し")
    a("")

    a("## 1. 対象情報")
    a("")
    a(f"- 対象ページ総数: {len(page_numbers)}")
    a(f"- ページ番号一覧: {page_range_text}")
    a(f"- OCR確定原文スナップショット: `{content_rel}/{SNAPSHOT_FILENAME}`")
    a(f"- スナップショットのSHA-256: `{snapshot_sha256}`")
    a(f"- 対象読者: {document.metadata.target_audience or '(未設定)'}")
    a(f"- トーン: {document.metadata.tone or '(未設定)'}")
    a(f"- 元画像ディレクトリ: `{rel_dir}/assets/`（各ページの元画像パスはスナップショットの")
    a("  `source_image`を参照）")
    a(f"- 候補出力先: `{content_rel}/pages/page_XXX.json`（XXXはページ番号3桁ゼロ埋め。")
    a(f"  例: ページ{first_page} → `page_{first_page:03d}.json`）")
    a(f"- 進捗ファイル: `{content_rel}/{PROGRESS_FILENAME}`（あなたが作成・更新する）")
    a(f"- 全体集約ファイル: `{content_rel}/{CANDIDATES_FILENAME}`（あなたが作成する）")
    a(f"- 人間確認用サマリー: `{content_rel}/{REVIEW_SUMMARY_FILENAME}`（あなたが作成する）")
    a("")
    a("**本文全文はこの指示書に埋め込まれていません。** 各ページの`title`/`body`/`summary`は")
    a(f"`{content_rel}/{SNAPSHOT_FILENAME}`を直接読んでください。")
    a("")

    a("## 2. ページごとの作業手順")
    a("")
    a(f"対象ページ（{page_range_text}）それぞれについて、以下を順番に実行してください。")
    a("固定のバッチ件数は前提にせず、ページ数が多い場合は自分で扱いやすい単位に分けて構いません。")
    a("")
    a("1. スナップショットから、そのページのOCR確定`title`/`body`/`summary`を読む")
    a("2. `source_image`が指す元画像を実際に開き、視覚確認する")
    a("3. ページの目的を判断する")
    a("4. 読者に伝わりにくい箇所を特定する")
    a("5. 意味・主張・結論・事実を変えずに改善案を作る（3節の許可範囲・禁止事項を厳守する）")
    a("6. 変更した箇所ごとに、変更理由を具体的に記録する（「読みやすくした」だけで済ませない）")
    a("7. 変更による意味・事実・トーンへの影響リスクを評価する（6節の`risk_level`）")
    a("8. 数字・固有名詞・注意書き等、保持すべき重要情報を`preserved_facts`へ記録する")
    a("9. 判断に迷う場合は無理に決めず`requires_human_review: true`にする")
    a("10. ページ別候補JSON（5節の形式）を`pages/page_XXX.json`へ保存する")
    a("11. 保存できたら次のページへ進む（全ページ確認後にまとめて保存しない）")
    a("")

    a("## 3. 本文ブラッシュアップの許可範囲・禁止事項")
    a("")
    a("### 許可")
    a("")
    a("- 誤字脱字・表記ゆれの最終確認")
    a("- 不自然な日本語の修正")
    a("- 冗長表現の整理")
    a("- 長すぎる文の分割")
    a("- 初心者向けの分かりやすい言い換え")
    a("- 主語・目的語の補完")
    a("- 箇条書き化")
    a("- 見出しの軽微な改善")
    a("- 指示文・質問文の明確化")
    a("- 読者が行動しやすい表現への改善")
    a("- 重複表現の整理")
    a("- 敬体・常体の統一")
    a("- 記号・空白・句読点の整理")
    a("- ページ内の情報階層改善")
    a("")
    a("### 禁止")
    a("")
    a("- 主張・結論の変更")
    a("- 元教材にない事実の追加")
    a("- 数字・固有名詞・引用の捏造")
    a("- ページの削除・追加・順序変更・統合・分割")
    a("- 教材テーマ・読者層の無断変更")
    a("- 大幅な内容削除")
    a("- 元教材にない例・ストーリーの追加")
    a("- 宣伝文句の追加")
    a("- 法的注意書き・転載禁止表記の削除")
    a("- `VERIFIED_OCR_SNAPSHOT.json`の変更")
    a("")
    a("**判断できない変更は推測で行わず、`requires_human_review: true`にして人間確認へ")
    a("回してください。**")
    a("")

    a("## 4. `change_type`（許可値）")
    a("")
    for ct in _ALLOWED_CHANGE_TYPES:
        a(f"- `{ct}`")
    a("")
    a("未知の値は使用できません。")
    a("")

    a("## 5. ページ別候補JSON仕様")
    a("")
    a(f"保存先: `{content_rel}/pages/page_XXX.json`（XXXはページ番号3桁ゼロ埋め）")
    a("")
    a("```json")
    a("{")
    a('  "schema_version": 1,')
    a('  "page_no": 1,')
    a('  "source_page_no": [1],')
    a('  "source_image": "assets/page_001.jpeg",')
    a('  "page_purpose": "キャラクター設定の導入",')
    a('  "original": {')
    a('    "title": "スナップショットのtitleと完全一致させる",')
    a('    "body": "スナップショットのbodyと完全一致させる",')
    a('    "summary": "スナップショットのsummaryと完全一致させる"')
    a("  },")
    a('  "proposed": {')
    a('    "title": "改善後のタイトル",')
    a('    "body": "改善後の本文",')
    a('    "summary": "改善後の概要"')
    a("  },")
    a('  "changes": [')
    a("    {")
    a('      "field": "body",')
    a('      "before": "完璧を求めない",')
    a('      "after": "完璧を目指さず、まずは素直に書いてみましょう",')
    a('      "reason": "読者が具体的に行動しやすい表現へ変更",')
    a('      "change_type": "clarify"')
    a("    }")
    a("  ],")
    a('  "preserved_facts": ["全11問", "無断転載禁止（おとスタ）"],')
    a('  "risk_level": "low",')
    a('  "requires_human_review": false,')
    a('  "review_reasons": [],')
    a('  "reviewed_by": "ai_work_agent",')
    a('  "reviewed_at": "ISO 8601"')
    a("}")
    a("```")
    a("")
    a("要件:")
    a("")
    a("- `original`はスナップショットの値と完全一致させる（改変しない）")
    a("- `proposed`は空にしない（変更が無いページでも、`proposed`にoriginalと同じ値を入れる）")
    a("- 変更したfieldは`changes`へ記録する。`before`は`original`の該当field内に実在する")
    a("  部分文字列、`after`は`proposed`の該当field内に実在する部分文字列にする")
    a("- 本文全文を`changes`へ重複掲載しない（変更箇所の抜粋にとどめる）")
    a("- `risk_level`が`high`の場合、`requires_human_review`は必ず`true`にする")
    a("- 絶対パス・秘密情報は含めない")
    a("")

    a("## 6. `risk_level`の目安")
    a("")
    a("- `low` — 表記・句読点・明確な言い換え")
    a("- `medium` — 文の分割、箇条書き化、見出し変更")
    a("- `high` — 意味・事実・対象読者へ影響する可能性がある変更")
    a("")

    a("## 7. 進捗・中断・再開")
    a("")
    a("ページ数が多い場合でも、1回のコンテキストへ全ページを読み込もうとしないでください。")
    a("")
    a("- ページを順番に処理する")
    a("- 必要に応じて自分で扱いやすい単位へ分けて進めてよい")
    a("- 1ページ確認するたびに、その場でページ別候補JSONを保存する")
    a("- 既に正常な候補JSON（`schema_version`が正しく、スナップショットのSHA-256より新しい")
    a("  ＝スナップショットが変わっていない）が存在するページはスキップしてよい")
    a("- スナップショットが変わっている場合、既存候補は再利用せず作り直す")
    a("- 未処理のページから再開する")
    a("- 作業を中断する前に、必ず進捗ファイルを更新する")
    a("")
    a(f"進捗ファイル: `{content_rel}/{PROGRESS_FILENAME}`")
    a("")
    a("```json")
    a("{")
    a('  "schema_version": 1,')
    a('  "total_pages": 100,')
    a('  "completed_pages": [1, 2, 3],')
    a('  "requires_human_review_pages": [3],')
    a('  "failed_pages": [],')
    a('  "remaining_pages": [4, 5, 6],')
    a('  "updated_at": "ISO 8601"')
    a("}")
    a("```")
    a("")

    a("## 8. 全体集約JSON")
    a("")
    a("全ページの処理が完了したら、以下を生成してください。")
    a("")
    a(f"保存先: `{content_rel}/{CANDIDATES_FILENAME}`")
    a("")
    a("```json")
    a("{")
    a('  "schema_version": 1,')
    a('  "generated_at": "ISO 8601",')
    a(f'  "source": "{_CANDIDATES_SOURCE}",')
    a(f'  "source_snapshot_sha256": "{snapshot_sha256}",')
    a('  "total_pages": 100,')
    a('  "completed_pages": 100,')
    a('  "requires_human_review_pages": [],')
    a('  "risk_counts": {"low": 70, "medium": 25, "high": 5},')
    a('  "pages": []')
    a("}")
    a("```")
    a("")
    a("集約時に以下を検証してください（満たさない場合は先に修正してから集約する）。")
    a("")
    a("- ページ欠落・重複が無い")
    a("- `pages`の順序がページ番号順に正しく並んでいる")
    a("- 各ページの`original`がスナップショットと一致している")
    a("- `risk_counts`の合計が完了ページ数と一致する")
    a("- `risk_level: high`のページがすべて`requires_human_review: true`になっている")
    a("")

    a("## 9. 人間確認用サマリー・レビューHTML")
    a("")
    a(f"- `{content_rel}/{REVIEW_SUMMARY_FILENAME}` — 全体件数・リスク別件数・人間確認ページ・")
    a("  主な言い換え・保持した重要情報・次に実行するdry-runコマンドを含むMarkdown")
    a(f"- `{content_rel}/{REVIEW_HTML_FILENAME}` — 原文と改善案を並べた比較確認画面")
    a("")
    a("**この2つは`apply-content-brushup`（次工程）が自動生成するため、あなたが作成する")
    a("必要はありません。** あなたが作成するのは`pages/`・`progress.json`・`candidates.json`")
    a("までです。")
    a("")

    a("## 10. 完了条件")
    a("")
    a("- [ ] 対象の全ページについて、ページ別候補JSONが存在する")
    a("- [ ] 全候補JSONの`original`がスナップショットと完全一致している")
    a("- [ ] 全ページについて、実際に元画像を視覚確認している")
    a("- [ ] 意味・主張・結論・事実を変えていない（変えた場合は正直に`risk_level: high`と")
    a("  `requires_human_review: true`にしている）")
    a("- [ ] `progress.json`の`remaining_pages`が空である")
    a(f"- [ ] `{CANDIDATES_FILENAME}`が生成され、8節の検証項目をすべて満たしている")
    a("- [ ] `editable/lesson_pages.json`・`VERIFIED_OCR_SNAPSHOT.json`・元画像を変更していない")
    a("")

    a("## 11. 禁止事項（安全性の再確認）")
    a("")
    a("- Claude API・その他の外部APIを呼び出さない")
    a("- 画像やテキストを外部へ送信しない")
    a("- `editable/lesson_pages.json`・`VERIFIED_OCR_SNAPSHOT.json`・元画像・`assets/`を変更しない")
    a("- ページ数・ページ順・`source_page_no`を変更しない")
    a(f"- `{content_rel}/pages/`・`{PROGRESS_FILENAME}`・`{CANDIDATES_FILENAME}`以外へ書き込まない")
    a("- Git commit・tag・push、ステージングは行わない（このタスクの範囲外）")
    a("")

    a("## 12. 次のステップ")
    a("")
    a("全ページの候補JSONと`candidates.json`を作成したら、作業完了です。")
    a("人間が次のコマンドで内容を確認します（あなたが実行する必要はありません）。")
    a("")
    a("```bash")
    a(f"python3 -m src.cli apply-content-brushup --output-dir {rel_dir} --dry-run")
    a("```")
    a("")

    return "\n".join(lines) + "\n"


def render_content_brushup_readme() -> str:
    return f"""# {CONTENT_BRUSHUP_DIR_NAME}/ ディレクトリについて

このディレクトリは、教材本文のブラッシュアップ（分かりやすさの改善）に関するファイルを
保存する場所です。

## OCR確定原文とブラッシュアップ済み本文の違い

- **OCR確定原文**（`{SNAPSHOT_FILENAME}`）: 元画像に何と書かれていたかを示す正確な転記。
  証拠として保存し、本文ブラッシュアップによって変更されません。
- **ブラッシュアップ済み本文**（`candidates.json`の`proposed`）: OCR確定原文を基に、
  元教材の主旨・結論・事実を維持しつつ読みやすさを改善した本文候補。人間の明示操作
  （`apply-content-brushup --apply`）を経て初めて`editable/lesson_pages.json`へ反映されます。

## `prepare-content-brushup`実行時点で存在するもの

`{SNAPSHOT_FILENAME}`・`{INSTRUCTIONS_FILENAME}`・`{README_FILENAME}`（このファイル）だけです。
`pages/`・`{PROGRESS_FILENAME}`・`{CANDIDATES_FILENAME}`は、指示書を読んだAIエージェントが
作成します。`{REVIEW_SUMMARY_FILENAME}`・`{REVIEW_HTML_FILENAME}`は`apply-content-brushup`が
自動生成します。

## 自動反映されないこと

このディレクトリの候補は、`apply-content-brushup --apply`を人間が明示的に実行するまで
`editable/lesson_pages.json`へ反映されません。`--dry-run`で内容を確認してから`--apply`して
ください。

## Git管理対象外

このディレクトリは`output/`配下にあるため、プロジェクトの既存方針によりGit管理対象外です。
"""


def write_prepare_entry_points(paths: ContentBrushupPaths, document: LessonDocument) -> dict[str, Path]:
    """`VERIFIED_OCR_SNAPSHOT.json`（未作成またはforce時のみ）・`AI_CONTENT_BRUSHUP.md`・
    `README.md`を書き出す（`prepare-content-brushup`本体）。呼び出し側でスナップショットの
    新規作成/据え置きを判断済みである前提（本関数は常に3ファイルを書き出す）。
    """
    paths.content_dir.mkdir(parents=True, exist_ok=True)
    snapshot = build_snapshot(document, paths.lesson_pages_path)
    write_snapshot(paths.snapshot_path, snapshot)
    paths.instructions_path.write_text(
        render_ai_content_brushup_instructions(document, paths.output_dir, snapshot["source_sha256"]),
        encoding="utf-8",
    )
    paths.readme_path.write_text(render_content_brushup_readme(), encoding="utf-8")
    return {"snapshot": paths.snapshot_path, "instructions": paths.instructions_path, "readme": paths.readme_path}


# --- 候補JSON・集約JSON検証 -------------------------------------------------------------------


def _normalize_page_dict(page: LessonPage) -> dict[str, str]:
    return {"title": page.title, "body": page.body, "summary": page.summary}


def validate_candidate_page(
    data: Any, *, expected_page_no: int, snapshot_page: dict[str, Any],
) -> list[str]:
    """ページ別候補JSON1件を検証し、問題点のリストを返す（空リストなら問題なし）。"""
    errors: list[str] = []
    if not isinstance(data, dict):
        return [f"page_no={expected_page_no}: 候補JSONがオブジェクト形式ではありません"]

    if data.get("schema_version") != 1:
        errors.append(f"page_no={expected_page_no}: schema_versionが未対応です: {data.get('schema_version')!r}")
    if data.get("page_no") != expected_page_no:
        errors.append(f"page_no={expected_page_no}: page_noが一致しません: {data.get('page_no')!r}")
    if data.get("source_image") != snapshot_page.get("source_image"):
        errors.append(f"page_no={expected_page_no}: source_imageがスナップショットと一致しません")

    original = data.get("original")
    if not isinstance(original, dict):
        errors.append(f"page_no={expected_page_no}: originalがオブジェクト形式ではありません")
        original = {}
    for field_name in _EDITABLE_FIELDS:
        if original.get(field_name) != snapshot_page.get(field_name):
            errors.append(f"page_no={expected_page_no}: original.{field_name}がスナップショットと一致しません")

    proposed = data.get("proposed")
    if not isinstance(proposed, dict):
        errors.append(f"page_no={expected_page_no}: proposedがオブジェクト形式ではありません")
        proposed = {}
    for field_name in _EDITABLE_FIELDS:
        value = proposed.get(field_name)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"page_no={expected_page_no}: proposed.{field_name}が空です")

    changes = data.get("changes", [])
    if not isinstance(changes, list):
        errors.append(f"page_no={expected_page_no}: changesがリスト形式ではありません")
        changes = []
    for i, change in enumerate(changes):
        if not isinstance(change, dict):
            errors.append(f"page_no={expected_page_no}: changes[{i}]がオブジェクト形式ではありません")
            continue
        field_name = change.get("field")
        if field_name not in _EDITABLE_FIELDS:
            errors.append(f"page_no={expected_page_no}: changes[{i}].fieldが不正です: {field_name!r}")
            continue
        before = change.get("before")
        after = change.get("after")
        if not isinstance(before, str) or not before or before not in original.get(field_name, ""):
            errors.append(f"page_no={expected_page_no}: changes[{i}].beforeがoriginal.{field_name}内に見つかりません")
        if not isinstance(after, str) or not after or after not in proposed.get(field_name, ""):
            errors.append(f"page_no={expected_page_no}: changes[{i}].afterがproposed.{field_name}内に見つかりません")
        if not change.get("reason"):
            errors.append(f"page_no={expected_page_no}: changes[{i}].reasonが空です")
        if change.get("change_type") not in _ALLOWED_CHANGE_TYPES:
            errors.append(f"page_no={expected_page_no}: changes[{i}].change_typeが不正です: {change.get('change_type')!r}")

    risk_level = data.get("risk_level")
    if risk_level not in _ALLOWED_RISK_LEVELS:
        errors.append(f"page_no={expected_page_no}: risk_levelが不正です: {risk_level!r}")
    requires_human_review = data.get("requires_human_review")
    if not isinstance(requires_human_review, bool):
        errors.append(f"page_no={expected_page_no}: requires_human_reviewは真偽値で指定してください")
    elif risk_level == "high" and not requires_human_review:
        errors.append(f"page_no={expected_page_no}: risk_level=highはrequires_human_review=trueが必須です")

    preserved_facts = data.get("preserved_facts", [])
    if not isinstance(preserved_facts, list) or not all(isinstance(f, str) for f in preserved_facts):
        errors.append(f"page_no={expected_page_no}: preserved_factsは文字列のリストで指定してください")

    return errors


def validate_candidates_aggregate(
    candidates_data: Any, *, expected_page_numbers: list[int], expected_snapshot_sha256: str,
) -> list[str]:
    """全体集約JSON（`candidates.json`）のトップレベル項目を検証する。"""
    errors: list[str] = []
    if not isinstance(candidates_data, dict):
        return ["candidates.jsonがオブジェクト形式ではありません"]

    if candidates_data.get("schema_version") != 1:
        errors.append(f"candidates.jsonのschema_versionが未対応です: {candidates_data.get('schema_version')!r}")
    if candidates_data.get("source") != _CANDIDATES_SOURCE:
        errors.append(
            f"candidates.jsonのsourceが本文ブラッシュアップ由来ではありません: {candidates_data.get('source')!r}"
        )
    if candidates_data.get("source_snapshot_sha256") != expected_snapshot_sha256:
        errors.append("candidates.jsonのsource_snapshot_sha256が現在のスナップショットと一致しません（古い可能性）")

    raw_pages = candidates_data.get("pages")
    if not isinstance(raw_pages, list):
        errors.append("candidates.jsonのpagesがリスト形式ではありません")
        raw_pages = []

    page_nos = []
    for entry in raw_pages:
        if isinstance(entry, dict) and "page_no" in entry:
            page_nos.append(entry["page_no"])
    duplicates = sorted({n for n in page_nos if page_nos.count(n) > 1})
    if duplicates:
        errors.append(f"candidates.jsonのpagesにpage_noの重複があります: {duplicates}")

    risk_counts = candidates_data.get("risk_counts", {})
    if isinstance(risk_counts, dict):
        risk_sum = sum(v for v in risk_counts.values() if isinstance(v, int))
        if risk_sum != len(raw_pages):
            errors.append(f"risk_countsの合計({risk_sum})とpagesの件数({len(raw_pages)})が一致しません")
    else:
        errors.append("candidates.jsonのrisk_countsがオブジェクト形式ではありません")

    return errors


# --- レビューHTML・サマリー ---------------------------------------------------------------------

_DIFF_DELETE_CLASS = "diff-original-del"
_DIFF_REPLACE_LEFT_CLASS = "diff-original-rep"
_DIFF_INSERT_CLASS = "diff-proposed-ins"
_DIFF_REPLACE_RIGHT_CLASS = "diff-proposed-rep"


def _wrap_diff_span(text: str, css_class: str, title: str) -> str:
    if not text:
        return ""
    return f'<mark class="{css_class}" title="{html.escape(title, quote=True)}">{text}</mark>'


def render_content_diff(original: str, proposed: str) -> tuple[str, str]:
    """OCR確定原文(`original`)とブラッシュアップ済み本文候補(`proposed`)を文字単位で比較し、
    安全なHTML断片`(original_html, proposed_html)`を返す。

    `src/ocr_comparison.py`の`_render_text_diff()`（Phase 10.8）と同じ安全な手順
    （`difflib.SequenceMatcher`で元の文字列を先に分割してから、断片ごとに`html.escape()`する）
    を踏襲する。OCR確定原文・改善案という文脈にラベルを合わせるため、関数自体は本モジュールに
    独立して定義している（Tesseract/Apple Vision向けの文言をそのまま流用すると誤解を招くため）。
    """
    norm_original = original.replace("\r\n", "\n").replace("\r", "\n") if original else ""
    norm_proposed = proposed.replace("\r\n", "\n").replace("\r", "\n") if proposed else ""

    if not norm_original and not norm_proposed:
        empty = '<span class="diff-empty">(本文なし)</span>'
        return (empty, empty)

    matcher = difflib.SequenceMatcher(None, norm_original, norm_proposed, autojunk=False)
    original_parts: list[str] = []
    proposed_parts: list[str] = []
    for tag, a0, a1, b0, b1 in matcher.get_opcodes():
        left_chunk = norm_original[a0:a1]
        right_chunk = norm_proposed[b0:b1]
        if tag == "equal":
            original_parts.append(html.escape(left_chunk, quote=True))
            proposed_parts.append(html.escape(right_chunk, quote=True))
        elif tag == "delete":
            original_parts.append(_wrap_diff_span(html.escape(left_chunk, quote=True), _DIFF_DELETE_CLASS, "改善案では削除"))
        elif tag == "insert":
            proposed_parts.append(_wrap_diff_span(html.escape(right_chunk, quote=True), _DIFF_INSERT_CLASS, "改善案で追加"))
        elif tag == "replace":
            original_parts.append(
                _wrap_diff_span(html.escape(left_chunk, quote=True), _DIFF_REPLACE_LEFT_CLASS, "改善案と異なる（原文側）")
            )
            proposed_parts.append(
                _wrap_diff_span(html.escape(right_chunk, quote=True), _DIFF_REPLACE_RIGHT_CLASS, "原文と異なる（改善案側）")
            )

    return ("".join(original_parts), "".join(proposed_parts))


def _safe_json_for_script(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False).replace("</script", "<\\/script").replace("<!--", "<\\!--")


def render_review_html(
    document: LessonDocument, snapshot: dict[str, Any], candidate_pages: dict[int, dict[str, Any]], output_dir: Path,
) -> str:
    """外部CDN・外部CSS・外部JavaScriptを使わない自己完結型のreview.htmlを生成する。"""
    snapshot_by_no = {p["page_no"]: p for p in snapshot["pages"]}

    def esc(s: str) -> str:
        return html.escape(s or "")

    changed_count = 0
    human_review_count = 0
    sections = []
    for page in document.pages:
        candidate = candidate_pages.get(page.page_no)
        snap = snapshot_by_no.get(page.page_no, {})
        source_rel = page.source_image
        if candidate is None:
            sections.append(f"""
<section class="page-review missing">
  <h2>Page {page.page_no}</h2>
  <p class="missing-note">候補が見つかりません（未処理）。</p>
</section>
""")
            continue

        has_changes = bool(candidate.get("changes"))
        if has_changes:
            changed_count += 1
        if candidate.get("requires_human_review"):
            human_review_count += 1

        title_o, title_p = render_content_diff(snap.get("title", ""), candidate["proposed"]["title"])
        body_o, body_p = render_content_diff(snap.get("body", ""), candidate["proposed"]["body"])
        summary_o, summary_p = render_content_diff(snap.get("summary", ""), candidate["proposed"]["summary"])

        changes_html = "".join(
            f"<li><strong>{esc(c.get('field',''))}</strong>（{esc(c.get('change_type',''))}）: "
            f"「{esc(c.get('before',''))}」→「{esc(c.get('after',''))}」<br>"
            f"<span class='reason'>理由: {esc(c.get('reason',''))}</span></li>"
            for c in candidate.get("changes", [])
        )
        preserved_html = "".join(f"<li>{esc(f)}</li>" for f in candidate.get("preserved_facts", []))
        risk = candidate.get("risk_level", "")

        sections.append(f"""
<section class="page-review risk-{esc(risk)}">
  <h2>Page {page.page_no}</h2>
  <div class="meta-row">
    <span class="badge risk-{esc(risk)}">risk: {esc(risk)}</span>
    <span class="badge">{'要人間確認' if candidate.get('requires_human_review') else '確認不要'}</span>
    <img class="thumb" src="../{esc(source_rel)}" alt="元画像 page {page.page_no}">
  </div>
  <dl>
    <dt>title（原文 → 改善案）</dt><dd class="diff-cell"><span class="diff-original">{title_o}</span> → <span class="diff-proposed">{title_p}</span></dd>
    <dt>summary（原文 → 改善案）</dt><dd class="diff-cell"><span class="diff-original">{summary_o}</span> → <span class="diff-proposed">{summary_p}</span></dd>
    <dt>body（原文 → 改善案）</dt><dd class="diff-cell body-diff"><div class="diff-original">{body_o}</div><div class="diff-proposed">{body_p}</div></dd>
  </dl>
  {f'<div class="changes"><h3>変更箇所</h3><ul>{changes_html}</ul></div>' if changes_html else '<p class="no-changes">変更なし</p>'}
  {f'<div class="preserved"><h3>保持した重要情報</h3><ul>{preserved_html}</ul></div>' if preserved_html else ''}
  <label class="check"><input type="checkbox"> このページを確認済み</label>
</section>
""")

    body_html = "\n".join(sections)
    return f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<title>教材本文ブラッシュアップ 比較確認</title>
<style>
body {{ font-family: sans-serif; margin: 24px; background: #f4f4f2; color: #202522; }}
.page-review {{ background: #fff; border-radius: 12px; padding: 20px; margin-bottom: 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
.meta-row {{ display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }}
.thumb {{ max-height: 60px; border: 1px solid #ddd; margin-left: auto; }}
.badge {{ font-size: 0.8em; padding: 2px 8px; border-radius: 999px; background: #eee; }}
.badge.risk-low {{ background: #dff0d8; }}
.badge.risk-medium {{ background: #fcf3cf; }}
.badge.risk-high {{ background: #f5c6cb; }}
dt {{ font-weight: bold; margin-top: 10px; }}
dd {{ margin: 4px 0 0 12px; white-space: pre-wrap; }}
.body-diff {{ display: flex; gap: 16px; }}
.body-diff > div {{ flex: 1; max-height: 220px; overflow-y: auto; padding: 8px; background: #fafafa; border-radius: 6px; }}
mark.diff-original-del, mark.diff-original-rep {{ background: #f8d7da; text-decoration: line-through; }}
mark.diff-proposed-ins, mark.diff-proposed-rep {{ background: #d4edda; }}
.changes ul, .preserved ul {{ margin: 4px 0; padding-left: 20px; }}
.reason {{ color: #6b746f; font-size: 0.85em; }}
.no-changes {{ color: #6b746f; }}
.missing-note {{ color: #a15c00; }}
</style>
</head>
<body>
<h1>教材本文ブラッシュアップ 比較確認</h1>
<p><strong>OCR確定原文（スナップショット）は変更されていません。</strong>
以下は原文とブラッシュアップ済み本文候補の比較です。反映は別途
<code>apply-content-brushup --apply</code>を実行するまで行われません。</p>
<p>対象ページ数: {len(document.pages)}　変更ありページ: {changed_count}　要人間確認: {human_review_count}</p>
<p>スナップショットSHA-256: <code>{esc(snapshot.get("source_sha256", ""))}</code></p>
{body_html}
</body></html>
"""


def render_review_summary_markdown(
    document: LessonDocument, candidates_data: dict[str, Any], *, next_command: str,
) -> str:
    pages = candidates_data.get("pages", [])
    changed_pages = [p["page_no"] for p in pages if p.get("changes")]
    unchanged_pages = [p["page_no"] for p in pages if not p.get("changes")]
    human_review_pages = candidates_data.get("requires_human_review_pages", [])
    risk_counts = candidates_data.get("risk_counts", {})

    lines = ["# 教材本文ブラッシュアップ 人間確認用サマリー", ""]
    lines.append(f"- 対象ページ数: {len(document.pages)}")
    lines.append(f"- 完了ページ数: {candidates_data.get('completed_pages', 0)}")
    lines.append(f"- 変更ありページ: {format_page_number_ranges(changed_pages) if changed_pages else '(なし)'}")
    lines.append(f"- 変更なしページ: {format_page_number_ranges(unchanged_pages) if unchanged_pages else '(なし)'}")
    lines.append(f"- リスク別件数: low={risk_counts.get('low',0)} / medium={risk_counts.get('medium',0)} / high={risk_counts.get('high',0)}")
    lines.append(f"- 人間確認が必要なページ: {format_page_number_ranges(human_review_pages) if human_review_pages else '(なし)'}")
    lines.append("")

    lines.append("## ページ別変更概要")
    lines.append("")
    for p in pages:
        if not p.get("changes"):
            continue
        lines.append(f"### Page {p['page_no']}")
        lines.append("")
        for c in p.get("changes", [])[:5]:
            lines.append(f"- [{c.get('change_type')}] 「{c.get('before')}」→「{c.get('after')}」（{c.get('reason')}）")
        lines.append("")

    lines.append("## 次に実行するコマンド")
    lines.append("")
    lines.append("```bash")
    lines.append(next_command)
    lines.append("```")
    lines.append("")

    return "\n".join(lines)
