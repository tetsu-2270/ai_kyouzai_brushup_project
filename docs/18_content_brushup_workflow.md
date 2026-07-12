# 18 教材本文ブラッシュアップワークフロー（`prepare-content-brushup` / `apply-content-brushup`）

> OCR確定原文を変更不能な証拠として保持したまま、教材本文を分かりやすくブラッシュアップし、人間の明示操作で`editable/lesson_pages.json`へ反映する機能です。

## 1. 最終目的とこの機能の位置づけ

```text
元教材画像 → 正確な原文を取得 → 教材本文を分かりやすく改善
→ 内容に合ったページ構成・画像デザインを作る → ブラッシュアップ済み教材を出力
```

Phase 10.7〜10.11で「正確な原文を取得」まで、Phase 10.12で「画像デザイン」の器が完成した。
Phase 10.12は明示的に「確定済み文字列を一字一句変更しない」という制約のもとで実装されたため、
実際に改善されたのは画像レイアウトだけで、文章表現そのものは評価・改善されていなかった。
本機能（Phase 10.13）はその欠けていた工程「教材本文を分かりやすく改善」を担う。

**本機能はページ数・ページ順・`source_page_no`・画像レイアウト・デザインJSONを一切変更しない。**
ページの統合・分割・順序変更等の構成のブラッシュアップは、既存の`restructure`モードまたは
別工程の役割であり、意図的にスコープ外としている。

## 2. OCR確定原文とブラッシュアップ済み本文の分離（最重要）

| | OCR確定原文 | ブラッシュアップ済み本文 |
|---|---|---|
| 実体 | `content_brushup/VERIFIED_OCR_SNAPSHOT.json` | `editable/lesson_pages.json`（`--apply`後） |
| 役割 | 元画像に何と書かれていたかを示す証拠 | 読みやすさを改善した最終的な教材本文 |
| 変更 | 本機能によって一切変更されない | `apply-content-brushup --apply`を人間が明示実行したときのみ更新 |

**OCR確定本文は、文章品質が完成していることを意味しません。** 元画像の転記として正確である
ことと、読みやすい文章であることは別の基準です。本機能はこの2つを明確に分離して扱います。

## 3. 全体の流れ（4段階）

```text
Step 1: prepare-content-brushup
  editable/lesson_pages.json から OCR確定原文スナップショットを保存し、
  AIエージェント向けの本文改善指示書（content_brushup/AI_CONTENT_BRUSHUP.md）を生成する
↓
Step 2: AI作業エージェント（Claude Code または Codex）による本文改善案の作成
  指示書を読んだAIエージェントが、ページごとに改善案（変更なしという判断を含む）を作成する
↓
Step 3: apply-content-brushup --dry-run
  改善案の妥当性・リスクを検証し、反映予定の内容をレポート・比較HTMLで確認する
↓
Step 4: apply-content-brushup --apply
  人間が内容を確認したうえで明示的に実行し、editable/lesson_pages.jsonへ反映する
↓
（本文が変わったため）prepare-image-brushup → render-brushup を再実行する
```

## 4. `prepare-content-brushup`（Step 1）

```bash
python3 -m src.cli prepare-content-brushup --output-dir output/ocr_engine_eval
```

生成物:

```text
content_brushup/
  VERIFIED_OCR_SNAPSHOT.json   # OCR確定原文の証拠（SHA-256付き）
  AI_CONTENT_BRUSHUP.md         # AIエージェント向け本文改善指示書
  README.md                     # content_brushup/の説明
```

### 4.1 OCR確定原文スナップショット

`editable/lesson_pages.json`の単純コピーではなく、「本文改善前の比較元である」ことを明示した
専用スキーマです。

```json
{
  "schema_version": 1,
  "created_at": "ISO 8601",
  "source": "verified_ocr_lesson_pages",
  "source_lesson_pages": "editable/lesson_pages.json",
  "source_sha256": "...",
  "metadata": {"mode": "proofread", "project_title": "...", "target_audience": "...", "tone": "..."},
  "pages": [{"page_no": 1, "source_page_no": [1], "source_image": "assets/page_001.jpeg",
             "title": "OCR確定タイトル", "body": "OCR確定本文", "summary": "OCR確定概要"}]
}
```

### 4.2 既存の作業中候補を保護する（黙って上書きしない）

`prepare-content-brushup`を再実行した際:

- 既存スナップショットが現在の`lesson_pages.json`と一致する場合 → スナップショットはそのまま
  据え置き、指示書・READMEだけを更新する（既存の`pages/`・`progress.json`・`candidates.json`は
  一切変更しない）
- 既存スナップショットが現在の`lesson_pages.json`と異なる場合（本文が他の作業で更新された等）
  → **自動的には上書きしない。** エラーで終了し、`--force`を指定しない限り何も変更しない
- `--force`を指定した場合のみスナップショットを作り直す（既存候補ファイル自体は削除しない。
  スナップショットが変わるため、それらは古い候補として扱われる）

## 5. AI作業エージェントによる本文改善案の作成（Step 2）

指示書は`AI_IMAGE_BRUSHUP.md`（Phase 10.12）と同様、Claude Code・Codexのどちらでも使える
製品非依存の自己完結した文書です。ページごとに元画像を視覚確認しながら、OCR確定原文を基に
改善案を作成します。

### 5.1 許可範囲・禁止事項

**許可**: 誤字脱字・表記ゆれの最終確認、不自然な日本語の修正、冗長表現の整理、長すぎる文の分割、
初心者向けの言い換え、主語・目的語の補完、箇条書き化、見出しの軽微な改善、指示文・質問文の
明確化、重複表現の整理、敬体・常体の統一、記号・空白・句読点の整理、情報階層の改善。

**禁止**: 主張・結論の変更、元教材にない事実の追加、数字・固有名詞・引用の捏造、ページの
削除・追加・順序変更・統合・分割、教材テーマ・読者層の無断変更、大幅な内容削除、元教材にない
例・ストーリーの追加、宣伝文句の追加、法的注意書き・転載禁止表記の削除、
`VERIFIED_OCR_SNAPSHOT.json`の変更。

判断に迷う変更は推測で行わず、`requires_human_review: true`にして人間確認へ回します。

### 5.2 ページ別候補JSON

保存先: `content_brushup/pages/page_NNN.json`

```json
{
  "schema_version": 1, "page_no": 1, "source_page_no": [1], "source_image": "assets/page_001.jpeg",
  "page_purpose": "キャラクター設定の導入",
  "original": {"title": "スナップショットと完全一致", "body": "...", "summary": "..."},
  "proposed": {"title": "...", "body": "...", "summary": "..."},
  "changes": [{"field": "body", "before": "完璧を求めない", "after": "完璧を目指さず、まずは素直に書いてみましょう",
               "reason": "読者が具体的に行動しやすい表現へ変更", "change_type": "clarify"}],
  "preserved_facts": ["全11問", "無断転載禁止（おとスタ）"],
  "risk_level": "low", "requires_human_review": false, "review_reasons": [],
  "reviewed_by": "ai_work_agent", "reviewed_at": "ISO 8601"
}
```

`original`はスナップショットの値と完全一致させる。変更が無いページでも`proposed`は空にせず、
`original`と同じ値を入れる（「変更なし」も正当な判断結果として明示的に記録するため）。

`change_type`の許可値: `typo` / `normalize` / `clarify` / `simplify` / `split_sentence` /
`remove_redundancy` / `heading` / `hierarchy` / `tone`。

`risk_level`: `low`（表記・句読点・明確な言い換え）/ `medium`（文の分割・箇条書き化・見出し変更）/
`high`（意味・事実・対象読者へ影響する可能性）。**`high`は必ず`requires_human_review: true`。**

### 5.3 全体集約JSON・進捗ファイル

`candidates.json`（`source_snapshot_sha256`でスナップショットとの対応関係を記録）と
`progress.json`（中断・再開用）を、Phase 10.10と同じ考え方でAIエージェントが作成します。
`review.html`・`review_summary.md`はAIエージェントが作成する必要はありません
（`apply-content-brushup`が自動生成します）。

## 6. `apply-content-brushup`（Step 3・4）

```bash
# 分析のみ（書き込みなし）
python3 -m src.cli apply-content-brushup --output-dir output/ocr_engine_eval --dry-run

# 内容を確認したうえで実反映
python3 -m src.cli apply-content-brushup --output-dir output/ocr_engine_eval --apply
```

`--dry-run`/`--apply`は相互排他かつ必須です。`--pages "1,4,7-11"`で対象ページを絞り込めます。

### 6.1 反映不可条件（対象範囲全体を停止する）

Phase 10.11の`apply-ocr-review`・Phase 10.12の設計判断を踏襲し、対象範囲内で1ページでも
以下の条件を満たす場合、そのページだけを除外するのではなく**対象範囲全体を反映不可**として
扱います。`--allow-high-risk`のようなバイパスは提供しません。

- スキーマ不正（`original`不一致・`proposed`空・不明な`change_type`・`before`/`after`が
  対象文字列内に見つからない等）
- `risk_level: high`
- `requires_human_review: true`
- `progress.json`の`failed_pages`が空でない／対象ページが`remaining_pages`に含まれる
- `candidates.json`の`source_snapshot_sha256`がスナップショットと一致しない

反映不可のページは、候補JSONを手動修正するかAIエージェントに再作成させてから、
`apply-content-brushup`を再実行してください。

### 6.2 冪等性の実現方法（技術的注記）

スナップショットの`source_sha256`は`--apply`成功後の`lesson_pages.json`とは一致しなくなります
（本文が意図的に更新されるため）。そのため、`lesson_pages.json`全体のハッシュをスナップショットと
単純比較する方式は採用していません。代わりに、対象ページごとに「現在の値が原文と一致する
（未反映）」か「現在の値が改善案と一致する（反映済み＝冪等）」かを個別に確認し、どちらでもない
場合だけ他の変更との競合として拒否します。これにより、同じ候補に対する2回目以降の
`--dry-run`/`--apply`も正しく成功します。

### 6.3 反映対象・保持対象

| 分類 | field |
|---|---|
| 更新される | `title` / `body` / `summary` |
| 更新後に再計算される | `image_text` / `canva_prompt` / `video_scene`（`lesson_pages._apply_derived_fields()`を再利用） |
| 保持される | `page_no` / `source_page_no` / `source_image` / `source_assets` / `role` / `layout_instruction` / `notes` / `metadata` / OCR確定原文スナップショット |

### 6.4 バックアップ・原子的書き込み

`--apply`時、書き込み前に`editable/backups/<timestamp>_lesson_pages.before_content_brushup.json`
へバックアップを作成します（既存バックアップは上書きしません）。書き込みは一時ファイルへ書いて
から`os.replace()`で置換する方式です（Phase 10.11の`apply-ocr-review`と同じ方式）。

### 6.5 review.html・review_summary.md

`apply-content-brushup`実行のたびに、`content_brushup/review.html`（原文と改善案を並べた
文字単位の差分表示。Phase 10.8と同じ安全なエスケープ手順を踏襲）と`review_summary.md`
（リスク別件数・人間確認ページ・主な言い換え）を再生成します。

## 7. Phase 10.12との接続（本文変更後の古いデザイン拒否）

本文が更新されると、文字量・行数が変わり、既存のデザインJSON（Phase 10.12で作成したもの）が
前提としていたレイアウトと食い違う可能性があります。これを防ぐため:

- `prepare-image-brushup`は、実行時点の`lesson_pages.json`のSHA-256を計算し、指示書へ埋め込む
- AIエージェントは、その値を`design_manifest.json`の`source_lesson_pages_sha256`として記録する
- `render-brushup`は、現在の`lesson_pages.json`のハッシュと`design_manifest.json`の
  `source_lesson_pages_sha256`を突き合わせ、一致しない場合は**古いデザインでの描画を拒否**する
  （`prepare-image-brushup`の再実行を促すメッセージを表示する）

`apply-content-brushup --apply`が本文を変更した場合、次の操作として
`prepare-image-brushup --output-dir <output-dir>`を実行するよう画面に案内が表示されます。

## 8. 既存機能との関係

- `llm-handoff`/`apply-llm-suggestions`（ChatGPT/Claude等の自由形式の回答を構造化するワーク
  フロー）とは別物です。`apply-llm-suggestions`は候補JSONを生成するだけで`lesson_pages.json`へは
  反映しませんが、本機能（`apply-content-brushup`）は明示操作で実際に反映します。候補スキーマも
  混在させていません。
- `ocr-check`/`apply-ocr-corrections`（substring単位のOCR補正候補）・`apply-ocr-review`
  （Phase 10.10のClaude画像照合レビュー候補）ともスキーマ・安全条件は独立しています。
- Phase 10.8の文字単位差分ハイライト、Phase 10.9のレビューUIの考え方（原文は読み取り専用、
  改善案側だけ編集可能）を踏襲していますが、本機能は既存のOCR比較用差分関数
  （Tesseract/Apple Vision向けの文言）をそのまま流用せず、原文・改善案という文脈に合わせた
  独自の軽量な差分関数を実装しています（安全なエスケープ手順は同一）。

## 9. 今回の制限事項

- 候補JSONの`before`/`after`が対象フィールド内に実在するかは機械検証しますが、`changes`に
  記録されなかった箇所の変更（記録漏れ）を検出する仕組みはありません
- `preserved_facts`は候補JSON内の申告であり、実際に改善後の本文へ含まれているかを機械的に
  検証する仕組みは今回未実装です（人間がreview.htmlで確認する前提）
- 本文の質的な良し悪し（読みやすくなったかどうか）を自動評価する仕組みはなく、`risk_level`は
  AIエージェントの自己申告に依存します
- ページ構成（統合・分割・順序）のブラッシュアップは意図的にスコープ外です
