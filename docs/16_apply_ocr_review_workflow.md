# 15 Claude Code画像照合レビュー候補の反映ワークフロー（`apply-ocr-review`）

> Phase 10.10でClaude Codeが元画像を正本として作成した`claude_review/candidates.json`（ページ全文の確定候補）を、`--dry-run`での分析→`--apply`での実反映という明示的な2段階操作を経て`output/editable/lesson_pages.json`へ安全に反映するコマンドです。

**このコマンドは[`docs/14_apply_ocr_corrections_workflow.md`](14_apply_ocr_corrections_workflow.md)の`apply-ocr-corrections`/`approve-ocr-candidates`とは完全に別のワークフローです。** `apply-ocr-corrections`はsubstring単位の補正候補（`ocr-check`が生成した`ocr_correction_candidates.json`）を対象にしますが、`apply-ocr-review`はページ全文単位の候補（Claude Codeが画像照合して作成した`claude_review/candidates.json`）を対象にします。候補スキーマ・安全条件は混在していません。

## 1. `apply-ocr-review`の目的

Phase 10.7〜10.10で、Tesseract/Apple Visionの比較・差分ハイライト・確定テキスト編集・Claude Code向け画像照合レビュー指示書までが整い、Claude Codeが`claude_review/candidates.json`（全ページの照合済み確定候補）を作成できるようになりました。しかし、この内容を`editable/lesson_pages.json`へ反映する手段が無く、人間が手作業で書き写す必要がありました。`apply-ocr-review`はこの反映作業を、検証→計画提示（dry-run）→明示的な実反映（apply）という手順で安全に行います。

## 2. 全体の流れ

```text
build-all --ocr-engine tesseract+vision で output/ocr_comparison/ 一式を生成する
↓
CLAUDE_OCR_REVIEW.md の指示に従って、別セッションのClaude Codeが元画像を照合する
↓
claude_review/candidates.json（全ページの確定候補）が生成される
↓
apply-ocr-review --output-dir <output-dir> --dry-run
↓
apply_report.md で反映予定ページ・反映不可ページ・変更内容を確認する
↓
問題が無ければ apply-ocr-review --output-dir <output-dir> --apply
↓
editable/lesson_pages.json が更新される（更新前にバックアップを自動作成）
↓
regenerate --input editable/lesson_pages.json --output-format all で完成outputを作り直す
```

## 3. 使い方・実行例

```bash
# 1. 分析のみ（書き込みなし）
python3 -m src.cli apply-ocr-review --output-dir output/ocr_engine_eval --dry-run

# 2. 内容を確認したうえで実反映
python3 -m src.cli apply-ocr-review --output-dir output/ocr_engine_eval --apply

# 3. 反映後、完成outputを作り直す（dry-run/apply成功後にコマンド例が表示される）
python3 -m src.cli regenerate --input output/ocr_engine_eval/editable/lesson_pages.json --output-format all
```

`--dry-run`と`--apply`は相互排他かつどちらか一方の指定が必須です。両方指定・どちらも未指定の場合はエラーで終了し、何も変更しません。

### 3.1 主なCLI引数

| 引数 | 説明 | 既定値 |
|---|---|---|
| `--output-dir`（必須） | `build-all`の出力先ディレクトリ | - |
| `--lesson-pages` | 入力`lesson_pages.json`の上書き指定 | `<output-dir>/editable/lesson_pages.json` |
| `--candidates` | 入力`candidates.json`の上書き指定 | `<output-dir>/ocr_comparison/claude_review/candidates.json` |
| `--report-dir` | レポート出力先ディレクトリの上書き指定 | `<output-dir>/ocr_comparison/claude_review` |
| `--pages` | 対象ページの絞り込み（例: `"1,4,7-11"`） | 省略時は`candidates.json`の全ページ |
| `--dry-run` | 実際には書き込まず、反映予定の内容だけレポートに出す | - |
| `--apply` | 検証に成功した場合に限り、実際に`lesson_pages.json`へ反映する | - |

通常の利用では`--output-dir`だけを指定すれば十分です。`--lesson-pages`/`--candidates`/`--report-dir`は、標準構成から外れたパス構成を使う場合の上書き用です。

## 4. `proposed_text`から各fieldへの反映ルール（最重要）

Claude Codeが作成する`proposed_text`は、ページ全体を1つの文字列にまとめた「確定候補」です。一方`LessonPage`には`title`/`body`/`summary`/`image_text`/`canva_prompt`/`video_scene`など複数の派生fieldがあり、`proposed_text`をどこか1つのfieldへ単純代入するだけでは他のfieldに古いOCR誤りが残ってしまいます。

`apply-ocr-review`は、**新しい独自の分割・派生ルールを実装せず**、既存のOCR取り込み・派生ロジックをそのまま再利用して以下のように反映します。

1. `proposed_text`を改行で分割し、空行を除いた各行を「1行=1件」として扱う（`src/import_source.py`の`_text_to_lines()`と同じロジック）
2. 先頭の空でない行を`title`候補にする（60文字まで切り詰め）。先頭2行を結合したものを`summary`候補にする（120文字まで切り詰め。`src/import_source.py`の`_derive_title_and_summary()`と同じロジック）
3. **`title`の行は`body`からは除外しない（重複させる）。** これは`import-source`が実際のOCR取り込み時に使っている仕様と同じであり、`apply-ocr-review`独自の判断ではない
4. 新しい`title`/`body`/`summary`を設定したうえで、`src/lesson_pages.py`の`_apply_derived_fields()`をそのまま呼び出し、`image_text`/`canva_prompt`/`video_scene`を再計算する（`title`/`body`/`summary`/`layout_instruction`/`notes`から機械的に再計算する既存ロジック）

### 4.1 変更されるfield・保持されるfield

| 分類 | field |
|---|---|
| `proposed_text`から再構築される | `title` / `body` / `summary` |
| 再構築後のtitle/body/summaryから再計算される | `image_text` / `canva_prompt` / `video_scene` |
| 変更されない（OCR本文ではないため） | `layout_instruction` |
| 変更されない（内部管理情報） | `source_image` / `source_assets` / `source_page_no` / `role` / `page_no` |
| 変更されない | `notes`（Canvaのメモ欄。OCR本文ではないため対象外） |
| 変更されない | `metadata`（`project_title`/`mode`等） |

### 4.2 受け入れ基準の例（実データで確認済み）

`output/ocr_engine_eval/`のPage1では、Tesseractの誤読「ますず」（正しくは「まず」）が反映前の`body`/`image_text`/`canva_prompt`/`video_scene`すべてに残っていました。`apply-ocr-review --apply`実行後、この4つのfieldすべてで「まず」に統一されていることを実データで確認しています（`docs/05_implementation_tasks.md`「Phase 10.11」参照）。

## 5. 入力検証・反映不可の扱い

`--dry-run`と`--apply`は同じ検証を行います（`--apply`は検証に成功した場合のみ実際に書き込みます）。

### 5.1 検証する内容

- `lesson_pages.json`・`candidates.json`のファイル存在・UTF-8 JSON妥当性
- `candidates.json`の`schema_version`（現時点で対応しているのは`1`のみ）・`source`（`claude_code_image_review`固定）
- ページ別候補JSON（`claude_review/pages/page_NNN.json`）が集約JSON（`candidates.json`）の同ページ内容と一致すること
- 比較元JSON（`ocr_comparison/pages/page_NNN.json`）との`page_no`/`source_image`整合性（`source_image`は絶対パス・パストラバーサル（`../`等）を拒否したうえで正規化して比較する）
- `--pages`省略時（全ページ対象時）のみ、`total_pages`/`completed_pages`/`decision_counts`の合計/`lesson_pages.json`のページ数/`progress.json`の整合を厳密にチェックする
- `progress.json`の`failed_pages`が空であること
- 対象ページの`decision`が許可値（`tesseract`/`apple_vision`/`merged`/`corrected`/`unresolved`）のいずれかで、かつ`unresolved`ではないこと
- 対象ページの`requires_human_review`が`false`であること
- 対象ページの`unresolved_spans`が空であること
- 対象ページの`proposed_text`が空文字・空白のみではないこと
- 対象ページが`progress.json`の`remaining_pages`に含まれていない（レビュー未完了ではない）こと

### 5.2 反映不可時の扱い（設計判断）

**対象ページ（`--pages`指定時はその範囲、既定では全ページ）のうち1件でも上記の条件を満たさない場合、そのページだけを除外するのではなく、対象範囲全体を反映不可として扱います。** `--allow-unresolved`のようなバイパスは提供していません。

該当ページは、Phase 10.9のレビューUI（`review.html`の確定テキスト編集機能）またはcandidates.jsonの手動修正で内容を確定させ、Claude Codeによる画像照合レビューを再実行してから、本コマンドを再実行してください。

この「部分的に良いページだけを黙って反映せず、範囲全体を止めて理由をレポートへ出す」という設計は、見えない未反映（利用者が気づかないまま一部ページだけ反映されない状態）を防ぐための安全側の判断です。範囲を絞りたい場合は`--pages`で明示的に対象を限定してください。

## 6. バックアップ・原子的書き込み・冪等性

- `--apply`実行時、書き込み前に`<output-dir>/editable/backups/<timestamp>_lesson_pages.before_ocr_review.json`へ現在の`lesson_pages.json`をバックアップします。既存の同名バックアップは上書きしません。
- 書き込みは一時ファイルへ書いてから`os.replace()`で置換する方式です（`src/verification_evidence.py`の検証エビデンス書き込みと同じ方式）。置換前に、書き込んだ内容をJSONとして再読込・検証します。書き込み途中で失敗した場合、元の`lesson_pages.json`は変更されません。
- 対象ページすべてが既に反映済みで変更が無い場合、`--apply`はバックアップも書き込みも行わず「変更なし」として正常終了します。同じ候補に対して`--apply`を繰り返しても、バックアップが際限なく増えることはありません。

## 7. レポートの読み方

`<output-dir>/ocr_comparison/claude_review/apply_report.json`（機械可読）・`apply_report.md`（人間可読）が、`--dry-run`/`--apply`どちらでも生成されます（検証に失敗した場合も、失敗理由を確認するために生成されます）。

Markdownレポートの構成:

1. 実行日時・モード（dry-run/apply）・判定（passed/failed）・入出力パス・対象ページ
2. 全体エラー（ファイル欠落・スキーマ不一致等、ページ個別の理由ではないもの）
3. サマリー（対象ページ数・反映可能/不可ページ数・変更あり/なしページ数）
4. 反映不可ページ一覧（Page番号・理由）
5. ページ別変更内容（`decision`・変更field・title/bodyの変更前後・主な修正内容。判定成功時のみ）
6. 次の操作（コピー可能なコマンド例）

## 8. CLI標準出力のバナー

```text
OCR_REVIEW_APPLY_DRY_RUN: passed
変更予定ページ: 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11
変更なしページ: なし
反映不可ページ: なし
レポート: output/ocr_engine_eval/ocr_comparison/claude_review/apply_report.md
次の操作:
python3 -m src.cli apply-ocr-review --output-dir output/ocr_engine_eval --apply
```

```text
OCR_REVIEW_APPLY: passed
反映ページ: 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11
変更なしページ: なし
バックアップ: output/ocr_engine_eval/editable/backups/20260712_090000_lesson_pages.before_ocr_review.json
レポート: output/ocr_engine_eval/ocr_comparison/claude_review/apply_report.md
次の操作:
python3 -m src.cli regenerate --input output/ocr_engine_eval/editable/lesson_pages.json --output-format all
```

反映不可ページがある場合は`OCR_REVIEW_APPLY_DRY_RUN: failed`/`OCR_REVIEW_APPLY: failed`となり、終了コードは非ゼロになります。

## 9. `apply`成功後の`regenerate`について

`apply-ocr-review`の責務は`lesson_pages.json`の更新までです。**`--apply`成功後、`regenerate`は自動実行しません。** 次に実行すべき`regenerate`コマンドを標準出力・レポートへ表示するだけに留めています。これは、`editable/lesson_pages.json`を更新した後の完成output再生成タイミングを利用者が制御できるようにするためです（既存の`apply-ocr-corrections`・手動編集ワークフローと同じ考え方）。

## 10. 今回の制限事項

- 部分反映（対象範囲のうち反映可能なページだけを反映し、反映不可ページだけ除外する方式）は採用していません（5.2節参照）
- 候補の"古さ"検出は、ページ番号・`source_image`・比較元JSONとの突き合わせ・`progress.json`の整合性チェックに留まります。ハッシュ値等による厳密なフィンガープリント方式は今回未実装です（将来追加する場合も、Phase 10.10の既存`candidates.json`スキーマとの後方互換性を維持できる範囲で追加することを推奨します）
- Phase 10.9のブラウザ側JSON書き出し（`review.html`の「レビュー結果をJSONで書き出す」ボタンが生成する、`adopted_source`/`final_text`等を持つ別スキーマのJSON）は今回の反映対象外です。`apply-ocr-review`が対象にするのは`claude_review/candidates.json`のみです
