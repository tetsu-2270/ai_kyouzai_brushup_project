# 14 承認済みOCR補正候補の反映ワークフロー（`apply-ocr-corrections`）

> `ocr-check`が生成した`ocr_correction_candidates.json`のうち、人間が`status: approved`に変更した候補だけを`lesson_pages.json`へ安全に反映するコマンドです。プロジェクト方針（README.md「プロジェクト方針：外部API非依存・ローカルLLM移行前提」参照）のとおり、**OCR候補の自動承認は行いません**。あくまで人間が承認した候補だけを機械的に反映します。

## 1. `apply-ocr-corrections`の目的

`ocr-check`によってOCR崩れ候補は整理されましたが、それを`editable/lesson_pages.json`へ反映する作業はこれまで人間の手作業でした。`apply-ocr-corrections`は、**人間が承認した候補に限って**、この反映作業を機械的に行うためのコマンドです。

すべての候補を自動反映するわけではありません。人間が`ocr_correction_candidates.json`の`status`を確認し、`approved`にした候補だけが対象です。

## 2. `ocr-check`との関係

```text
build-all または lesson-pages で editable/lesson_pages.json を作る
↓
ocr-check で ocr_check_report.md と ocr_correction_candidates.json を生成する
↓
人間が ocr_correction_candidates.json を確認する
↓
反映してよい候補だけ status を approved に変更する
↓
apply-ocr-corrections を実行する
↓
approved の候補だけを反映した lesson_pages.ocr_fixed.json を生成する
↓
ocr_apply_report.md で反映結果・未反映理由・差分を確認する
↓
問題なければ、そのファイルを使って llm-handoff へ進む
```

## 3. `ocr_correction_candidates.json`のstatusの使い方

`ocr-check`が生成した直後は、すべての候補の`status`は`proposed`です。人間が候補ごとに以下のいずれかへ変更します。

| status | 意味 | `apply-ocr-corrections`での扱い |
|---|---|---|
| `approved` | 反映してよいと判断した候補 | **反映対象** |
| `proposed`（初期値） | まだ判断していない候補 | 反映しない |
| `rejected` | 反映しないと判断した候補 | 反映しない |
| `needs_image_check` | 元画像確認が必要と判断した候補 | 反映しない |

`approved`にした候補だけが反映されます。`proposed`のまま放置した候補、`rejected`/`needs_image_check`にした候補は反映されません。

## 4. 使い方・実行例

```bash
python3 -m src.cli apply-ocr-corrections \
  --input output/editable/lesson_pages.json \
  --candidates output/ocr_correction_candidates.json \
  --output output/editable/lesson_pages.ocr_fixed.json \
  --report output/ocr_apply_report.md
```

- `--input`: 補正対象の`lesson_pages.json`（**このファイルは上書きされません**）。
- `--candidates`: `ocr-check`が生成した`ocr_correction_candidates.json`。
- `--output`: 補正済み`lesson_pages.json`の出力先（既定: `output/editable/lesson_pages.ocr_fixed.json`）。
- `--report`: 反映結果レポートの出力先（既定: `output/ocr_apply_report.md`）。
- `--dry-run`: 実際には`--output`のJSONを生成せず、反映予定の内容だけレポートに出します。

反映対象になるstatusは、現時点では`approved`固定です（`--approved-status`のようなカスタマイズは今回未対応・TODO）。

## 5. 反映されるfield・されないfield

反映対象は`title`/`summary`/`body`/`notes`です。

**`layout_instruction`はstatusに関わらず自動反映しません。** `layout_instruction`は生成側のレイアウト指示・内部参照であり、OCR本文ではないためです（`ocr-check`側でも`layout_instruction`はOCR崩れ検出の主対象から除外しています。詳細は[`docs/13_ocr_quality_check_workflow.md`](13_ocr_quality_check_workflow.md)参照）。`layout_instruction`宛の候補が`approved`になっていても、`layout_instruction_skipped`として未反映扱いになり、人間が直接確認・編集する前提です。

## 6. 反映方法（置換ルール）

対象field内で`original`と一致する箇所を**すべて**`suggested`に置換します。同じ`original`がfield内に複数回出現する場合も全件を置換し、置換回数を`ocr_apply_report.md`に記録します（1回だけ置換する方式ではなく、全一致置換＋置換回数記録を採用しています）。

## 7. 元ファイルを上書きしないこと

`--input`で指定したファイルは変更されません。補正結果は`--output`で指定した**別のファイル**（既定では`lesson_pages.ocr_fixed.json`という別名）に出力されます。反映結果に問題があれば、元の`--input`ファイルはそのまま残っているため、やり直しが可能です。

## 8. `ocr_apply_report.md`の読み方

レポートは以下の構成です。

1. 目的 / 2. 実行条件
2. **全体サマリー**: 候補総数・approved候補数・反映成功件数・未反映件数（理由別内訳含む）
3. **反映された候補一覧**: `candidate_id`/Page/field/`original`/`suggested`/置換回数のテーブル
4. **反映されなかった候補一覧**: 上記に加えてstatus・未反映理由のテーブル
5. **未反映理由別サマリー**: 理由ごとの件数
6. **ページ別反映結果** / **field別反映結果**
7. **差分確認用メモ**: 候補ごとの変更前後・置換回数
8. **次に実行するコマンド例**: `llm-handoff`/`edit-plan-template`/`regenerate`への次工程コマンド
9. **注意事項**

## 9. 反映されない主な理由

| 未反映理由 | 意味 |
|---|---|
| `status_not_approved` | statusが`approved`ではない（`proposed`/`rejected`/`needs_image_check`） |
| `unknown_status` | statusが未知の値 |
| `suggested_missing` | `suggested`が空または未設定 |
| `suggested_requires_image_check` | `suggested`が「元画像確認」等の値で、断定できる修正候補ではない |
| `invalid_field` | `field`が反映対象外（`title`/`summary`/`body`/`notes`以外） |
| `field_missing` | 候補に`field`が設定されていない |
| `page_not_found` | `page_index`/`page_no`から対象ページを特定できない |
| `original_not_found` | 対象field内に`original`が見つからない（既に修正済み等） |
| `duplicate_or_already_applied` | 同一`candidate_id`が重複している |
| `layout_instruction_skipped` | `layout_instruction`は自動反映対象外 |

## 10. 反映後にllm-handoffへ進む流れ

OCR補正候補を承認・反映した場合は、`lesson_pages.ocr_fixed.json`を次工程の入力に使ってください。

```bash
python3 -m src.cli llm-handoff --input output/editable/lesson_pages.ocr_fixed.json --output output/llm_handoff.md
python3 -m src.cli edit-plan-template --input output/editable/lesson_pages.ocr_fixed.json --output output/edit_plan_template.md
python3 -m src.cli regenerate --input output/editable/lesson_pages.ocr_fixed.json --output-dir output/regenerated
```

## 11. 注意点

- **今回は自動承認しません。** `ocr_correction_candidates.json`の`status`変更は人間が行います。
- 反映後は`ocr_apply_report.md`の「反映された候補一覧」「差分確認用メモ」を必ず確認してください。
- `source_page_no`/`source_image`/`assets`/`metadata`、ページ数・ページ順は変更されません。
- 将来的には、候補承認を支援するUIや、ローカルLLMによる承認判断支援へつなげられる可能性があります（今回は未実装。詳細は[`docs/07_api_integration_design.md`](07_api_integration_design.md)参照）。
