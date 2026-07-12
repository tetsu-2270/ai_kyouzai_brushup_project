from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .lesson_pages import LessonDocument

# Phase 10.12: 確定済みOCR本文（output/editable/lesson_pages.json）と元画像の視覚情報を使い、
# ブラッシュアップ済み教材画像を生成するための「デザイン指示書生成」と「デザインJSON検証」を
# 担当するモジュール。
#
# 最終目的（このプロジェクト全体）:
#   元教材画像 → 正確な本文を取得 → 内容・構成・視認性を改善 → ブラッシュアップ済み教材画像を生成
# Phase 10.7〜10.11で「正確な本文」までは確定した。このPhaseはその先、実際に見た目を
# 再設計した画像を生成する段階を担う。
#
# 重要な設計制約:
# - デザインJSON（pages/page_NNN.json）は、教材本文を「複製」してはいけない。各ブロックは
#   source_field（title/body/summary）でlesson_pages.jsonの値を参照するだけにする。これにより、
#   デザインを考えるAIエージェント（Claude Code/Codex）が本文を誤記・改変するリスクを構造的に防ぐ。
# - 任意コード・任意HTML・任意CSS・任意PythonをデザインJSONへ埋め込む設計にはしない
#   （テンプレート名・ブロック種別・色コード・数値のみの限定的なスキーマ）。
# - このモジュール自体はClaude API等を呼び出さない。指示書はここで生成する静的な文書のみで、
#   実際のデザイン判断（pages/page_NNN.json作成）は指示書を読んだ別セッションのAIエージェントが行う。

_ALLOWED_TEMPLATES = (
    "title_body", "title_summary_body", "checklist", "question",
    "two_column", "quote", "summary", "steps",
)

_ALLOWED_BLOCK_TYPES = (
    "title", "summary", "body", "note", "checklist", "steps", "quote", "divider", "spacer", "group",
)

# groupブロック（複数の子ブロックを1つの共有背景の中へ積み重ねて描画する）の子として許可するtype。
# 元画像は「問いかけ（大・太字）」と「補足説明（小・通常）」が同じ1枚のカードに収まっているため、
# 子ブロックを分けず1つのnote等に押し込めると、文字サイズを変えられず情報階層を再現できない。
# 逆に子ブロックを完全に独立させ各々へ背景を付けると、1枚のカードだったものが複数の浮いた要素に
# 分裂して見える。groupはこの両方を避けるための機構（詳細はdocs/17「5.7」参照）。
_ALLOWED_GROUP_CHILD_TYPES = ("title", "summary", "body")

# 任意コード埋め込みを避けるため、blockが参照できるのはLessonPageの この3fieldに限定する
# （教材本文はここから取得し、デザインJSON内へ複製しない）。
_ALLOWED_SOURCE_FIELDS = ("title", "body", "summary")

_BLOCK_TYPES_REQUIRING_SOURCE_FIELD = (
    "title", "summary", "body", "note", "checklist", "steps", "quote",
)

_ALLOWED_FONT_WEIGHTS = ("regular", "bold")
_ALLOWED_ALIGNMENTS = ("left", "center", "right")

_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

_MIN_CANVAS_SIZE = 200
_MAX_CANVAS_SIZE = 4000
_MIN_FONT_SIZE = 8
_MAX_FONT_SIZE = 200

DESIGN_DIR_NAME = "brushup_design"
INSTRUCTIONS_FILENAME = "AI_IMAGE_BRUSHUP.md"
README_FILENAME = "README.md"
MANIFEST_FILENAME = "design_manifest.json"
PROGRESS_FILENAME = "progress.json"
RENDERED_BRUSHUP_DIR_NAME = "rendered_brushup"


# --- パス解決 -----------------------------------------------------------------------------


@dataclass
class ImageBrushupPaths:
    output_dir: Path
    lesson_pages_path: Path
    assets_dir: Path
    design_dir: Path
    instructions_path: Path
    readme_path: Path
    manifest_path: Path
    progress_path: Path
    pages_dir: Path
    rendered_brushup_dir: Path
    comparison_html_path: Path
    render_report_json_path: Path
    render_report_md_path: Path


def resolve_paths(output_dir: str | Path) -> ImageBrushupPaths:
    base = Path(output_dir)
    design_dir = base / DESIGN_DIR_NAME
    return ImageBrushupPaths(
        output_dir=base,
        lesson_pages_path=base / "editable" / "lesson_pages.json",
        assets_dir=base / "assets",
        design_dir=design_dir,
        instructions_path=design_dir / INSTRUCTIONS_FILENAME,
        readme_path=design_dir / README_FILENAME,
        manifest_path=design_dir / MANIFEST_FILENAME,
        progress_path=design_dir / PROGRESS_FILENAME,
        pages_dir=design_dir / "pages",
        rendered_brushup_dir=base / RENDERED_BRUSHUP_DIR_NAME,
        comparison_html_path=design_dir / "comparison.html",
        render_report_json_path=design_dir / "render_report.json",
        render_report_md_path=design_dir / "render_report.md",
    )


def lesson_pages_sha256(lesson_pages_path: Path) -> str:
    """`lesson_pages.json`のSHA-256を計算する（`brushup_renderer._file_sha256`と同じ一行慣用句）。

    Phase 10.13で本文ブラッシュアップが反映された後、古いデザインJSON（反映前の文字量・行数を
    前提にレイアウトされたもの）でそのまま描画してしまうことを防ぐため、デザイン指示書
    生成時点の`lesson_pages.json`のハッシュを`design_manifest.json`へ記録させ、
    `render-brushup`実行時に現在のハッシュと突き合わせる（`check_manifest_freshness()`参照）。
    """
    return hashlib.sha256(lesson_pages_path.read_bytes()).hexdigest()


def check_manifest_freshness(manifest: Any, *, current_lesson_pages_sha256: str) -> str | None:
    """`design_manifest.json`が現在の`lesson_pages.json`を前提に作られたものかを確認する。

    問題が無ければ`None`、問題があればエラーメッセージ文字列を返す。
    `source_lesson_pages_sha256`が無い場合（Phase 10.13より前に生成された古いmanifest）も、
    本文と一致する保証が無いため安全側でエラー扱いにする。
    """
    if not isinstance(manifest, dict):
        return None
    recorded = manifest.get("source_lesson_pages_sha256")
    if not recorded:
        return (
            "design_manifest.jsonにsource_lesson_pages_sha256が記録されていません"
            "（Phase 10.13より前に生成された可能性があります）。"
            "prepare-image-brushupを再実行してデザインを作り直してください"
        )
    if recorded != current_lesson_pages_sha256:
        return (
            "design_manifest.jsonは現在のlesson_pages.jsonとは異なる内容を前提に作られています"
            "（本文ブラッシュアップ等で内容が更新された可能性があります）。"
            "prepare-image-brushupを再実行してデザインを作り直してください"
        )
    return None


# --- ページ番号表記（ocr_claude_review.pyと同じ圧縮表記ロジックを再利用） -----------------------


def format_page_number_ranges(page_numbers: list[int]) -> str:
    from .ocr_claude_review import format_page_number_ranges as _format

    return _format(page_numbers)


def _relative_output_dir(output_dir: Path) -> str:
    from .ocr_claude_review import _relative_output_dir as _rel

    return _rel(output_dir)


# --- 指示書生成 -----------------------------------------------------------------------------


def render_ai_image_brushup_instructions(
    document: "LessonDocument", output_dir: Path, *, lesson_pages_sha256_value: str | None = None,
) -> str:
    """`AI_IMAGE_BRUSHUP.md`（Claude Code/Codex双方で使える製品非依存の指示書）を組み立てる。

    実データから埋め込むのは、ページ総数・ページ番号一覧・相対パス・生成日時・
    `lesson_pages.json`のSHA-256等の構造情報のみ。本文（title/body/summary）はここへ複製しない
    （デザインJSON側でも複製禁止と同じ理由）。

    `lesson_pages_sha256_value`（Phase 10.13で追加）は、このデザイン指示書が前提とする時点の
    `lesson_pages.json`の内容を示すハッシュ。AIエージェントが作成する`design_manifest.json`へ
    この値を`source_lesson_pages_sha256`として記録させることで、後から本文ブラッシュアップ等で
    本文が更新された場合に、`render-brushup`が古いデザインでの描画を拒否できるようにする
    （`check_manifest_freshness()`参照）。
    """
    rel_dir = _relative_output_dir(output_dir)
    design_rel = f"{rel_dir}/{DESIGN_DIR_NAME}"
    page_numbers = [p.page_no for p in document.pages]
    page_range_text = format_page_number_ranges(page_numbers)
    first_page = page_numbers[0] if page_numbers else 1

    lines: list[str] = []
    a = lines.append

    a("# AI画像ブラッシュアップ デザイン指示書")
    a("")
    a("（`prepare-image-brushup`が自動生成。Claude Code・Codexのどちらでも同じ手順で使えます）")
    a("")
    a("このファイルは自己完結した作業指示書です。**このファイルを読むだけで、追加の質問をせず")
    a("最後まで作業を進めてください。**")
    a("")

    a("## 0. 最終目的とこの作業の位置づけ")
    a("")
    a("このプロジェクトの最終目的は、OCRで文字を読み取ることではありません。")
    a("")
    a("```text")
    a("元教材画像 → 正確な本文を取得 → 内容・構成・視認性を改善 → ブラッシュアップ済み教材画像を生成")
    a("```")
    a("")
    a("正確な本文はすでに確定済みです（`editable/lesson_pages.json`）。あなたの役割は、")
    a("**本文を1文字も変えずに**、ページごとに見やすく再設計されたレイアウトを設計することです。")
    a("実際の画像描画（PNG生成）はこの指示書を読むあなたの役割ではありません。あなたが作った")
    a("デザインJSONを元に、決定論的なレンダラー（`render-brushup`コマンド）が正確に描画します。")
    a("")
    a("**あなたが行わないこと:**")
    a("")
    a("- 本文の作成・修正・要約・言い換え（本文はすでに確定済みです）")
    a("- 画像のPNG描画そのもの（レンダラーが行います）")
    a("- Claude API等の外部呼び出し")
    a("")

    a("## 1. 対象情報")
    a("")
    a(f"- 対象ページ総数: {len(page_numbers)}")
    a(f"- ページ番号一覧: {page_range_text}")
    a(f"- 確定済み本文: `{rel_dir}/editable/lesson_pages.json`")
    if lesson_pages_sha256_value:
        a(f"- 現在のlesson_pages.jsonのSHA-256: `{lesson_pages_sha256_value}`（**7節の`design_manifest.json`へ")
        a("  `source_lesson_pages_sha256`として必ず記録してください**。本文が後で更新された際に、")
        a("  古いデザインでの描画を防ぐために使われます）")
    a(f"- 元画像ディレクトリ: `{rel_dir}/assets/`（各ページの元画像パスは`lesson_pages.json`の`source_image`を参照）")
    a(f"- デザインJSON保存先: `{design_rel}/pages/page_XXX.json`（XXXはページ番号3桁ゼロ埋め。")
    a(f"  例: ページ{first_page} → `page_{first_page:03d}.json`）")
    a(f"- 進捗ファイル: `{design_rel}/{PROGRESS_FILENAME}`（あなたが作成・更新する）")
    a(f"- 全体manifest: `{design_rel}/{MANIFEST_FILENAME}`（あなたが作成する）")
    a("")
    a("**本文全文はこの指示書に埋め込まれていません。** 各ページの`title`/`body`/`summary`は")
    a("`lesson_pages.json`を直接読んでください。")
    a("")

    a("## 2. ページごとの作業手順")
    a("")
    a(f"対象ページ（{page_range_text}）それぞれについて、以下を順番に実行してください。")
    a("固定のバッチ件数は前提にせず、ページ数が多い場合は自分で扱いやすい単位に分けて構いません。")
    a("")
    a("1. `lesson_pages.json`から、そのページの`title`/`body`/`summary`/`source_image`を読む")
    a("2. `source_image`が指す元画像を実際に開き、視覚確認する（読み飛ばさない）")
    a("3. 元画像から、縦横比・配色傾向・タイトル位置・情報ブロックの種類（2段組み・チェック")
    a("   リスト・質問・注意書き等）・アイコンや写真等の装飾の有無を把握する")
    a("4. ページの目的（導入・説明・実践・チェックリスト・まとめ等）を判断する")
    a("5. 元画像の良い点（維持すべき構成）と、改善したい点（余白不足・情報階層不足等）を")
    a("   `design_intent.preserve`/`design_intent.improve`として言語化する")
    a("6. 3節のテンプレート一覧から、そのページに最も合うものを1つ選ぶ")
    a("7. 4節の仕様に従い、`blocks`（表示するブロックの並び）を設計する。**本文の複製は禁止**")
    a("   です。各ブロックは`source_field`で`title`/`body`/`summary`のいずれかを参照するだけに")
    a("   してください")
    a("8. 配色（`theme`）を、元画像の配色傾向を踏まえつつ、ページ間で統一感が出るように決める")
    a("9. デザインJSON（4節の形式）を`pages/page_XXX.json`へ保存する")
    a("10. 保存できたら次のページへ進む（全ページ確認後にまとめて保存しない。1ページごとに保存する）")
    a("")

    a("## 3. 許可テンプレート一覧（`template`）")
    a("")
    a("| テンプレート | 用途の目安 |")
    a("|---|---|")
    a("| `title_body` | タイトル＋本文の基本構成 |")
    a("| `title_summary_body` | タイトル＋要約＋本文 |")
    a("| `checklist` | チェック項目の列挙 |")
    a("| `question` | 質問形式・自問形式のページ |")
    a("| `two_column` | 2段組みのページ（元画像が左右2列構成の場合） |")
    a("| `quote` | 引用・強調したい一節が中心のページ |")
    a("| `summary` | まとめ・振り返りページ |")
    a("| `steps` | 手順・ステップの列挙 |")
    a("")
    a("`template`はレンダラーの分類・集計用の情報です。実際の見た目は`blocks`の並びで決まります。")
    a("")

    a("## 4. デザインJSON仕様（`pages/page_XXX.json`）")
    a("")
    a("```json")
    a("{")
    a('  "schema_version": 1,')
    a('  "page_no": 1,')
    a('  "source_image": "assets/page_001.jpeg",')
    a('  "canvas": {"width": 900, "height": 1200, "background_color": "#F8F7F2"},')
    a('  "design_intent": {')
    a('    "page_purpose": "導入・実践案内",')
    a('    "preserve": ["縦長構成", "タイトルの強調"],')
    a('    "improve": ["余白を増やす", "本文の行間を広げる"]')
    a("  },")
    a('  "theme": {')
    a('    "primary_color": "#2F6655", "secondary_color": "#E8F1EC",')
    a('    "accent_color": "#D9973D", "text_color": "#202522", "muted_text_color": "#6B746F"')
    a("  },")
    a('  "template": "title_body",')
    a('  "blocks": [')
    a("    {")
    a('      "id": "title", "type": "title", "source_field": "title",')
    a('      "style": {"font_size": 44, "font_weight": "bold", "alignment": "center",')
    a('                "color": "#202522", "background_color": null, "padding": 20}')
    a("    },")
    a("    {")
    a('      "id": "body", "type": "body", "source_field": "body",')
    a('      "style": {"font_size": 28, "font_weight": "regular", "alignment": "left",')
    a('                "color": "#202522", "background_color": "#FFFFFF", "padding": 16}')
    a("    }")
    a("  ],")
    a('  "footer": {"show_page_number": true, "show_source_notice": true},')
    a('  "review_notes": "",')
    a('  "designed_by": "ai_work_agent",')
    a('  "designed_at": "ISO 8601"')
    a("}")
    a("```")
    a("")
    a("### 4.1 `blocks[].type`（許可値）")
    a("")
    a("- `title` / `summary` / `body` — 通常のテキストブロック")
    a("- `note` — 枠で囲んだ注意書き・補足ボックス")
    a("- `checklist` — `source_field`の内容を1行ずつチェック項目として列挙")
    a("- `steps` — `source_field`の内容を1行ずつ番号付き手順として列挙")
    a("- `quote` — `source_field`の内容を左アクセントバー付きの引用として表示")
    a("- `divider` — 区切り線（`source_field`不要）")
    a("- `spacer` — 余白（`source_field`不要）")
    a('- `group` — 複数の子ブロック（`title`/`summary`/`body`）を1つの共有背景の中へ積み重ねて')
    a("  表示する（`source_field`不要。代わりに`blocks`を持つ。詳細は4.4.1節）")
    a("")
    a("### 4.2 `blocks[].source_field`（最重要）")
    a("")
    a("`title`/`summary`/`body`のいずれかのみ許可します。それ以外の値は拒否されます。")
    a("")
    a("**`text`のような、本文を直接書き込むフィールドは存在しません。** 本文を複製しようとした")
    a("デザインJSONは`render-brushup`実行時に拒否されます。")
    a("")
    a("### 4.3 `blocks[].columns`（任意・2段組み用）")
    a("")
    a('`type: "body"`のブロックに`"columns": 2`を指定すると、その内容を2段組みで描画します。')
    a("`two_column`テンプレートで元画像が左右2列構成の場合に使ってください。段落（改行区切りの")
    a("1行）の途中で列をまたぐことはありません。既定では行数がなるべく均等になる段落境界を")
    a("自動選択しますが、`split_at`（後述）で明示的に分割位置を指定できます。")
    a("")
    a("### 4.4 `blocks[].line_range`（任意・段落の一部だけを参照する）")
    a("")
    a("`[start, end]`（0始まり、`end`は`null`で末尾まで）を指定すると、`source_field`の段落")
    a("（bodyの場合は改行区切りの1行=1段落）のうち、その範囲だけをそのブロックで描画します。")
    a("**既存の行を並べ替えたり複製したりするものではありません**。同じ本文の異なる部分を")
    a("複数のブロックへ分けて、文字サイズ・強調・箱の有無を変え、情報の優先順位（見た目の")
    a("メリハリ）を表現するために使います。")
    a("")
    a("**重要: 元画像で大きく強調されている部分（見出し的な問いかけ等）は、`line_range`で")
    a("抜き出して大きく太字のブロックにし、補足説明は小さめの通常ブロックにするなど、")
    a("元画像の情報階層（メリハリ）を再現してください。すべての行を同じ文字サイズ・")
    a("同じ枠に均一に詰め込むと、単なるレイアウト崩しになり「ブラッシュアップ」になりません。**")
    a("")
    a("**同時に重要: 問いかけと補足説明が元画像で同じ1枚のカードに収まっている場合、")
    a("文字サイズを分けるために別々の`note`ブロックへ分割し、それぞれへ別の背景を描画しては")
    a("いけません。** 見た目が「本文の外に浮いた独立要素」に分裂してしまい、「問いかけの")
    a("部分が本文から外へ出てしまっている」という不自然さの原因になります。文字サイズは")
    a("変えつつ背景は1つだけにしたい場合は、次の`group`ブロック（4.4.1節）を使ってください。")
    a("")
    a("### 4.4.1 `blocks[].type: \"group\"`（複数ブロックを1つの共有背景へ積み重ねる）")
    a("")
    a('`group`は、`blocks`（子ブロックのリスト。`title`/`summary`/`body`のみ）を1つの共有背景')
    a("（`style.background_color`・`style.padding`）の中へ上から順に積み重ねて描画します。")
    a("子ブロックそれぞれに`line_range`・別々の`font_size`/`font_weight`/`color`を設定できますが、")
    a("子ブロック自身には背景・`columns`・`split_at`は設定できません（共有背景はgroup全体で1つ）。")
    a("")
    a("例（1ページのbodyが8行あり、1行目=タイトル重複、2〜3行目=強調したい問いかけ、")
    a("4〜7行目=補足説明、8行目=注記の場合）:")
    a("")
    a("```json")
    a('"blocks": [')
    a('  {"id": "card", "type": "group", "style": {"background_color": "#E8F1EC", "padding": 20},')
    a('   "blocks": [')
    a('     {"id": "question", "type": "body", "source_field": "body", "line_range": [1, 3],')
    a('      "style": {"font_size": 38, "font_weight": "bold", "color": "#202522", "padding": 0}},')
    a('     {"id": "explanation", "type": "body", "source_field": "body", "line_range": [3, 7],')
    a('      "style": {"font_size": 24, "font_weight": "regular", "color": "#202522", "padding": 0}}')
    a("   ]},")
    a('  {"id": "notice", "type": "body", "source_field": "body", "line_range": [7, null],')
    a('   "style": {"font_size": 16, "font_weight": "regular", "color": "#6B746F", "padding": 8}}')
    a("]")
    a("```")
    a("")
    a("子ブロックの`style.padding`は`0`にしてください（groupの外側`padding`だけで余白を作り、")
    a("二重の余白にしないため）。注記（`notice`）のように元画像でも明確に独立して小さく")
    a("表示されている要素は、groupに含めず独立したブロックのままで構いません。")
    a("")
    a("1行目（タイトル重複行）を`title`ブロックと別に描画すると見た目が二重になるため、")
    a("`body`を参照するブロック（`line_range`が無いもの・groupの子ブロック含む）は基本的に")
    a("`line_range: [1, null]`（1行目を除く）から始めることを推奨します。")
    a("")
    a("### 4.5 `blocks[].split_at` / `blocks[].column_ratio`（任意・2段組みの調整）")
    a("")
    a('`columns: 2`と併用します。`split_at`は`line_range`適用後の段落インデックス（0始まり）を')
    a("指定すると、そのインデックスの直前で厳密に列を分けます（例: 「例1」に関する段落群と")
    a("「例2」に関する段落群のように、意味的なまとまりを保ったまま左右に分けたい場合に使う）。")
    a("省略時は自動で行数が均等になる境界を選びますが、内容のまとまりを無視して機械的に")
    a("半分に割ってしまうことがあるため、**2段組みで元画像に明確な意味区切り（例1/例2等）が")
    a("ある場合は必ず`split_at`で明示してください**。")
    a("")
    a('`column_ratio`（既定`0.5`＝均等。`0.1`〜`0.9`）は左列の幅比率です。左右で段落の長さが')
    a("明らかに異なる場合、均等割りだと片方の列で不自然な位置（読点や閉じ括弧の直前等）で")
    a("改行されることがあります。その場合は、内容が長い側の列を広げるよう`column_ratio`を")
    a("調整してください（例: 左列の内容が長ければ`0.58`前後）。")
    a("")
    a("### 4.6 色コード")
    a('`"#RRGGBB"`形式（6桁16進）のみ許可します。`background_color`は`null`も許可します。')
    a("")
    a("### 4.7 フォント・配置")
    a('`font_weight`は`"regular"`/`"bold"`、`alignment`は`"left"`/`"center"`/`"right"`のみ許可します。')
    a("")

    a("## 5. デザイン判断基準")
    a("")
    a("- **元画像で文字サイズ・太さが大きく変えられている箇所（強調されている問いかけ・")
    a("  見出し等）は、`line_range`で切り出して大きく太字のブロックにし、補足説明・注記は")
    a("  それより明確に小さいブロックにする。1ページの全行を同じ文字サイズ・同じ箱に")
    a("  均一に詰め込むこと（メリハリの無いレイアウト）は禁止する**（4.4節参照）")
    a("- タイトルを`title`ブロックで別枠表示する場合、`body`ブロック側の`line_range`は")
    a("  1行目（タイトル重複行）を除いた範囲にする（見た目の二重表示を避ける）")
    a("- 元画像の良い点は維持する")
    a("- 読みにくさ・余白不足・情報階層不足を改善する")
    a("- タイトル・本文・補足・注意書きの優先順位を明確にする")
    a("- スマートフォンで読める文字サイズを確保する（本文は目安24px以上。注記等の補足的な")
    a("  文字は元画像でも小さいため、この限りではない）")
    a("- 色数を増やしすぎない（`theme`の5色を基本とする）")
    a("- コントラストを確保する")
    a("- ページ間で統一感を持たせる（基本フォント・基本配色・角丸/罫線等の装飾体系・")
    a("  ページ番号表示の位置は揃える）")
    a("- 内容に合わない装飾を追加しない")
    a("- **余白（`style.padding`）は必要以上に大きくしない。** 余白を広げすぎると、収める")
    a("  ためにレンダラー側が文字サイズを縮小せざるを得なくなり、かえって読みにくくなる")
    a("- 元教材の意味を変えない・本文を要約/言い換え/省略しない（`source_field`参照のみ）")
    a("- テキストが収まらない場合はレンダラー側がレイアウト・文字サイズ・余白を調整します。")
    a("  あなたが収めるために本文を削る必要はありません（そもそも本文はここでは扱いません）")
    a("- 2段組み（`columns: 2`）で元画像に「例1/例2」のような明確な意味区切りがある場合、")
    a("  自動分割に任せず`split_at`で意味区切りの位置を明示する（4.5節参照）")
    a("- 元画像内の文字をそのまま画像素材として再利用しない（誤字が残るため）。文字を含まない")
    a("  写真・イラスト等の再利用は今回のバージョンでは未対応です")
    a("")

    a("## 6. 進捗・中断・再開")
    a("")
    a("ページ数が多い場合でも、1回のコンテキストへ全画像を読み込もうとしないでください。")
    a("")
    a("- ページを順番に処理する")
    a("- 必要に応じて自分で扱いやすい単位（例: 10〜20ページごと）へ分けて進めてよい")
    a("- 1ページ確認するたびに、その場でページ別デザインJSONを保存する")
    a("- 既に正常なページ別デザインJSON（`schema_version`が正しいもの）が存在するページは、")
    a("  処理済みとして扱いスキップしてよい")
    a("- 未処理のページから再開する")
    a("- 作業を中断する前に、必ず進捗ファイルを更新する")
    a("")
    a(f"進捗ファイル: `{design_rel}/{PROGRESS_FILENAME}`")
    a("")
    a("```json")
    a("{")
    a('  "schema_version": 1,')
    a('  "total_pages": 100,')
    a('  "completed_pages": [1, 2, 3],')
    a('  "failed_pages": [],')
    a('  "remaining_pages": [4, 5, 6],')
    a('  "updated_at": "ISO 8601"')
    a("}")
    a("```")
    a("")

    a("## 7. 全体manifest")
    a("")
    a("全ページの処理が完了したら、以下を生成してください。")
    a("")
    a(f"保存先: `{design_rel}/{MANIFEST_FILENAME}`")
    a("")
    a("```json")
    a("{")
    a('  "schema_version": 1,')
    a('  "generated_at": "ISO 8601",')
    a('  "source": "ai_image_brushup_design",')
    a(f'  "source_lesson_pages_sha256": "{lesson_pages_sha256_value or "(1節に記載のSHA-256をそのまま記録)"}",')
    a('  "total_pages": 100,')
    a('  "completed_pages": 100,')
    a('  "template_counts": {"title_body": 30, "question": 40, "two_column": 20, "summary": 10},')
    a('  "pages": [')
    a('    {"page_no": 1, "design_file": "pages/page_001.json", "template": "title_body"}')
    a("  ]")
    a("}")
    a("```")
    a("")
    a("**`source_lesson_pages_sha256`は必須項目です。** 1節に記載した現在の`lesson_pages.json`の")
    a("SHA-256をそのまま記録してください。")
    a("")
    a("集約時に以下を検証してください（満たさない場合は先に修正してから集約する）。")
    a("")
    a("- 対象ページの欠落が無い（1節の対象ページ総数・ページ番号一覧と一致する）")
    a("- ページ番号の重複が無い")
    a("- 各ページの`design_file`が実在し、4節のスキーマを満たしている")
    a("")

    a("## 8. 完了条件")
    a("")
    a("以下をすべて満たしたときに限り、作業完了として報告してください。")
    a("")
    a("- [ ] 対象の全ページについて、ページ別デザインJSONが存在する")
    a("- [ ] 全デザインJSONのスキーマが4節の仕様を満たしている")
    a("- [ ] 全ページについて、実際に元画像を視覚確認している")
    a("- [ ] 本文（title/body/summary）をデザインJSONへ複製していない（`source_field`参照のみ）")
    a("- [ ] `progress.json`の`remaining_pages`が空である")
    a(f"- [ ] `{MANIFEST_FILENAME}`が生成され、7節の検証項目をすべて満たしている")
    a("- [ ] `editable/lesson_pages.json`・元画像を変更していない")
    a("")

    a("## 9. 禁止事項（安全性の再確認）")
    a("")
    a("- Claude API・その他の外部APIを呼び出さない")
    a("- 画像やテキストを外部へ送信しない")
    a("- `editable/lesson_pages.json`・元画像・`assets/`を変更しない")
    a("- 本文（title/body/summary）をデザインJSONへ複製しない")
    a("- 任意コード・任意HTML・任意CSS・任意PythonをデザインJSONへ埋め込まない")
    a(f"- `{design_rel}/pages/`・`{PROGRESS_FILENAME}`・`{MANIFEST_FILENAME}`以外へ書き込まない")
    a(f"  （PNG画像の生成は`render-brushup`コマンドの役割であり、あなたの役割ではありません）")
    a("- Git commit・tag・push、ステージングは行わない（このタスクの範囲外）")
    a("")

    a("## 10. 次のステップ")
    a("")
    a("全ページのデザインJSONと`design_manifest.json`を作成したら、作業完了です。")
    a("実際のPNG画像生成は、人間が次のコマンドを実行します（あなたが実行する必要はありません）。")
    a("")
    a("```bash")
    a(f"python3 -m src.cli render-brushup --output-dir {rel_dir}")
    a("```")
    a("")

    return "\n".join(lines) + "\n"


def render_design_readme() -> str:
    return f"""# {DESIGN_DIR_NAME}/ ディレクトリについて

このディレクトリは、`{INSTRUCTIONS_FILENAME}`の指示に従ってAIエージェント（Claude Code/Codex）が
設計したページデザインを保存する場所です。

## 保存されるもの（指示書実行時にAIエージェントが作成）

- `pages/page_NNN.json` — ページごとのデザインJSON（1ページ1ファイル）
- `{PROGRESS_FILENAME}` — 全体の進捗（完了ページ・未処理ページ）
- `{MANIFEST_FILENAME}` — 全ページの集約manifest

## `prepare-image-brushup`実行時点で存在するもの

`{INSTRUCTIONS_FILENAME}`と`{README_FILENAME}`（このファイル）だけです。`pages/`・
`{PROGRESS_FILENAME}`・`{MANIFEST_FILENAME}`は、指示書を読んだAIエージェントが作成します。

## 実際の画像生成について

このディレクトリのデザインJSONは、まだPNG画像ではありません。`render-brushup`コマンドを
実行すると、`{MANIFEST_FILENAME}`とデザインJSON、`editable/lesson_pages.json`の確定済み本文を
元に、決定論的なレンダラーがブラッシュアップ済み画像（`{RENDERED_BRUSHUP_DIR_NAME}/page_NNN.png`）
を生成します。

```bash
python3 -m src.cli render-brushup --output-dir <output-dir>
```

## デザインJSONに本文が含まれない理由

デザインJSONの各ブロックは`source_field`（`title`/`body`/`summary`のいずれか）で
`editable/lesson_pages.json`の値を参照するだけで、本文そのものを複製しません。これにより、
デザインを考えるAIエージェントが本文を誤記・改変するリスクを構造的に防いでいます。

## Git管理対象外

このディレクトリは`output/`配下にあるため、プロジェクトの既存方針によりGit管理対象外です。
"""


def write_design_entry_points(output_dir: Path, document: "LessonDocument") -> dict[str, Path]:
    """`AI_IMAGE_BRUSHUP.md`と`brushup_design/README.md`を書き出す（`prepare-image-brushup`本体）。"""
    paths = resolve_paths(output_dir)
    paths.design_dir.mkdir(parents=True, exist_ok=True)
    current_hash = lesson_pages_sha256(paths.lesson_pages_path) if paths.lesson_pages_path.exists() else None
    paths.instructions_path.write_text(
        render_ai_image_brushup_instructions(document, output_dir, lesson_pages_sha256_value=current_hash),
        encoding="utf-8",
    )
    paths.readme_path.write_text(render_design_readme(), encoding="utf-8")
    return {"instructions": paths.instructions_path, "readme": paths.readme_path}


# --- デザインJSON検証 ------------------------------------------------------------------------


def _normalize_relative_path(raw: str, *, label: str) -> str:
    if not raw or not raw.strip():
        raise ValueError(f"{label}が空です")
    posix_raw = raw.strip().replace("\\", "/")
    candidate = PurePosixPath(posix_raw)
    if candidate.is_absolute():
        raise ValueError(f"{label}に絶対パスは使用できません: {raw!r}")
    if any(part in ("..", "") for part in candidate.parts if part != "."):
        raise ValueError(f"{label}にパストラバーサルは使用できません: {raw!r}")
    return candidate.as_posix()


def _validate_hex_color(value: Any, *, label: str, allow_none: bool = False) -> None:
    if value is None and allow_none:
        return
    if not isinstance(value, str) or not _HEX_COLOR_RE.match(value):
        raise ValueError(f"{label}は#RRGGBB形式で指定してください: {value!r}")


def _validate_canvas(canvas: Any) -> None:
    if not isinstance(canvas, dict):
        raise ValueError("canvasがオブジェクト形式ではありません")
    width, height = canvas.get("width"), canvas.get("height")
    for name, value in (("width", width), ("height", height)):
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"canvas.{name}は整数で指定してください: {value!r}")
        if not (_MIN_CANVAS_SIZE <= value <= _MAX_CANVAS_SIZE):
            raise ValueError(f"canvas.{name}は{_MIN_CANVAS_SIZE}〜{_MAX_CANVAS_SIZE}の範囲で指定してください: {value!r}")
    _validate_hex_color(canvas.get("background_color"), label="canvas.background_color")


def _validate_theme(theme: Any) -> None:
    if not isinstance(theme, dict):
        raise ValueError("themeがオブジェクト形式ではありません")
    for key in ("primary_color", "secondary_color", "accent_color", "text_color", "muted_text_color"):
        _validate_hex_color(theme.get(key), label=f"theme.{key}")


def _validate_style(style: Any, *, block_id: str) -> None:
    if not isinstance(style, dict):
        raise ValueError(f"block[{block_id}].styleがオブジェクト形式ではありません")
    font_size = style.get("font_size")
    if not isinstance(font_size, int) or isinstance(font_size, bool) or not (_MIN_FONT_SIZE <= font_size <= _MAX_FONT_SIZE):
        raise ValueError(f"block[{block_id}].style.font_sizeは{_MIN_FONT_SIZE}〜{_MAX_FONT_SIZE}の整数で指定してください: {font_size!r}")
    font_weight = style.get("font_weight", "regular")
    if font_weight not in _ALLOWED_FONT_WEIGHTS:
        raise ValueError(f"block[{block_id}].style.font_weightが不正です: {font_weight!r}")
    alignment = style.get("alignment", "left")
    if alignment not in _ALLOWED_ALIGNMENTS:
        raise ValueError(f"block[{block_id}].style.alignmentが不正です: {alignment!r}")
    _validate_hex_color(style.get("color"), label=f"block[{block_id}].style.color", allow_none=True)
    _validate_hex_color(style.get("background_color"), label=f"block[{block_id}].style.background_color", allow_none=True)
    padding = style.get("padding", 0)
    if not isinstance(padding, int) or isinstance(padding, bool) or padding < 0 or padding > 200:
        raise ValueError(f"block[{block_id}].style.paddingは0〜200の整数で指定してください: {padding!r}")


def _validate_group_style(style: Any, *, block_id: str) -> None:
    """groupブロック自体のstyleは共有背景の見た目（padding/background_color）だけを持つ。

    実際の文字はgroup.blocksの各子blockが持つため、font_size等の文字関連プロパティは不要。
    """
    if not isinstance(style, dict):
        raise ValueError(f"block[{block_id}].styleがオブジェクト形式ではありません")
    _validate_hex_color(style.get("background_color"), label=f"block[{block_id}].style.background_color", allow_none=True)
    padding = style.get("padding", 16)
    if not isinstance(padding, int) or isinstance(padding, bool) or padding < 0 or padding > 200:
        raise ValueError(f"block[{block_id}].style.paddingは0〜200の整数で指定してください: {padding!r}")


def _validate_block(block: Any) -> None:
    if not isinstance(block, dict):
        raise ValueError(f"blocksの要素がオブジェクト形式ではありません: {block!r}")
    block_id = block.get("id", "(不明)")
    block_type = block.get("type")
    if block_type not in _ALLOWED_BLOCK_TYPES:
        raise ValueError(f"block[{block_id}].typeが不正です: {block_type!r}")
    if block_type == "group":
        _validate_group_style(block.get("style", {}), block_id=block_id)
        children = block.get("blocks")
        if not isinstance(children, list) or not children:
            raise ValueError(f"block[{block_id}].blocksは1件以上の配列で指定してください")
        for child in children:
            if not isinstance(child, dict):
                raise ValueError(f"block[{block_id}]の子blockがオブジェクト形式ではありません: {child!r}")
            child_type = child.get("type")
            if child_type not in _ALLOWED_GROUP_CHILD_TYPES:
                raise ValueError(
                    f"block[{block_id}]の子block.typeは{_ALLOWED_GROUP_CHILD_TYPES}のいずれかで"
                    f"指定してください（groupの入れ子・checklist等は未対応）: {child_type!r}"
                )
            if child.get("columns", 1) != 1:
                raise ValueError(f"block[{block_id}]の子blockはcolumnsを指定できません")
            _validate_block(child)
        return
    if block_type in _BLOCK_TYPES_REQUIRING_SOURCE_FIELD:
        source_field = block.get("source_field")
        if source_field not in _ALLOWED_SOURCE_FIELDS:
            raise ValueError(
                f"block[{block_id}].source_fieldは{_ALLOWED_SOURCE_FIELDS}のいずれかで指定してください: {source_field!r}"
            )
        # 本文の直接埋め込み（"text"キー等での複製）を明示的に拒否する。
        for forbidden_key in ("text", "content", "value", "html", "code"):
            if forbidden_key in block:
                raise ValueError(
                    f"block[{block_id}]で本文を複製するフィールド（{forbidden_key!r}）は使用できません。"
                    "source_fieldでlesson_pages.jsonの値を参照してください"
                )
    if "style" in block:
        _validate_style(block["style"], block_id=block_id)
    columns = block.get("columns", 1)
    if columns not in (1, 2):
        raise ValueError(f"block[{block_id}].columnsは1または2で指定してください: {columns!r}")
    if "line_range" in block and block["line_range"] is not None:
        _validate_line_range(block["line_range"], block_id=block_id)
    if "split_at" in block and block["split_at"] is not None:
        split_at = block["split_at"]
        if not isinstance(split_at, int) or isinstance(split_at, bool) or split_at < 0:
            raise ValueError(f"block[{block_id}].split_atは0以上の整数で指定してください: {split_at!r}")
    if "column_ratio" in block and block["column_ratio"] is not None:
        column_ratio = block["column_ratio"]
        if isinstance(column_ratio, bool) or not isinstance(column_ratio, (int, float)) or not (0.1 <= column_ratio <= 0.9):
            raise ValueError(f"block[{block_id}].column_ratioは0.1〜0.9の数値で指定してください: {column_ratio!r}")


def _validate_line_range(line_range: Any, *, block_id: str) -> None:
    """`line_range`（`[start, end]`。0始まり、endはNoneで末尾まで）を検証する。

    既存の行を並べ替えたり複製したりせず、対象fieldの一部だけを参照するための機構
    （本文の改変・複製ではない）。startは0以上の整数、endはNoneまたはstartより大きい整数。
    """
    if not isinstance(line_range, list) or not (1 <= len(line_range) <= 2):
        raise ValueError(f"block[{block_id}].line_rangeは[start]または[start, end]の配列で指定してください: {line_range!r}")
    start = line_range[0]
    if not isinstance(start, int) or isinstance(start, bool) or start < 0:
        raise ValueError(f"block[{block_id}].line_range[0]は0以上の整数で指定してください: {start!r}")
    if len(line_range) == 2 and line_range[1] is not None:
        end = line_range[1]
        if not isinstance(end, int) or isinstance(end, bool) or end <= start:
            raise ValueError(f"block[{block_id}].line_range[1]はline_range[0]より大きい整数またはnullで指定してください: {end!r}")


def validate_design_page(
    data: Any, *, expected_page_no: int, expected_source_image: str
) -> None:
    """デザインJSON1ページ分を検証する。問題があれば`ValueError`を送出する。"""
    if not isinstance(data, dict):
        raise ValueError("デザインJSONがオブジェクト形式ではありません")

    if data.get("schema_version") != 1:
        raise ValueError(f"schema_versionが未対応です: {data.get('schema_version')!r}")

    if data.get("page_no") != expected_page_no:
        raise ValueError(f"page_noが一致しません: {data.get('page_no')!r} != {expected_page_no!r}")

    normalized_expected = _normalize_relative_path(expected_source_image, label="lesson_pages.jsonのsource_image")
    normalized_actual = _normalize_relative_path(
        str(data.get("source_image", "")), label=f"Page{expected_page_no}のデザインJSONのsource_image"
    )
    if normalized_actual != normalized_expected:
        raise ValueError(
            f"source_imageがlesson_pages.jsonと一致しません: {normalized_actual!r} != {normalized_expected!r}"
        )

    _validate_canvas(data.get("canvas"))
    _validate_theme(data.get("theme"))

    template = data.get("template")
    if template not in _ALLOWED_TEMPLATES:
        raise ValueError(f"templateが不正です: {template!r}")

    blocks = data.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        raise ValueError("blocksは1件以上の配列で指定してください")
    for block in blocks:
        _validate_block(block)

    footer = data.get("footer", {})
    if not isinstance(footer, dict):
        raise ValueError("footerがオブジェクト形式ではありません")
    for key in ("show_page_number", "show_source_notice"):
        if key in footer and not isinstance(footer[key], bool):
            raise ValueError(f"footer.{key}は真偽値で指定してください: {footer[key]!r}")


def validate_manifest(manifest: Any, *, expected_page_numbers: list[int]) -> list[str]:
    """`design_manifest.json`を検証し、問題点のリストを返す（空リストなら問題なし）。"""
    errors: list[str] = []
    if not isinstance(manifest, dict):
        return ["design_manifest.jsonがオブジェクト形式ではありません"]

    if manifest.get("schema_version") != 1:
        errors.append(f"schema_versionが未対応です: {manifest.get('schema_version')!r}")

    raw_pages = manifest.get("pages")
    if not isinstance(raw_pages, list):
        errors.append("pagesがリスト形式ではありません")
        raw_pages = []

    page_numbers: list[int] = []
    for entry in raw_pages:
        if not isinstance(entry, dict) or "page_no" not in entry:
            errors.append(f"pagesの要素が不正です: {entry!r}")
            continue
        page_numbers.append(entry["page_no"])
        if entry.get("template") not in _ALLOWED_TEMPLATES:
            errors.append(f"page_no={entry.get('page_no')}のtemplateが不正です: {entry.get('template')!r}")
        if "design_file" not in entry or not isinstance(entry["design_file"], str):
            errors.append(f"page_no={entry.get('page_no')}のdesign_fileが指定されていません")

    duplicates = sorted({n for n in page_numbers if page_numbers.count(n) > 1})
    if duplicates:
        errors.append(f"pagesにpage_noの重複があります: {duplicates}")

    missing = sorted(set(expected_page_numbers) - set(page_numbers))
    if missing:
        errors.append(f"pagesにページ欠落があります: {missing}")

    extra = sorted(set(page_numbers) - set(expected_page_numbers))
    if extra:
        errors.append(f"pagesにlesson_pages.jsonに存在しないページ番号があります: {extra}")

    return errors
