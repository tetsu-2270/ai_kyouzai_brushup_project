# 14 承認済みOCR補正候補の反映ワークフロー（`apply-ocr-corrections`）

> `ocr-check`が生成した`ocr_correction_candidates.json`のうち、人間が`status: approved`に変更した候補だけを`lesson_pages.json`へ安全に反映するコマンドです。プロジェクト方針（README.md「プロジェクト方針：外部API非依存・ローカルLLM移行前提」参照）のとおり、**OCR候補の自動承認は行いません**。あくまで人間が承認した候補だけを機械的に反映します。
>
> **`apply-ocr-review`（[`docs/16_apply_ocr_review_workflow.md`](16_apply_ocr_review_workflow.md)）とは別のコマンドです。** このページで扱う`apply-ocr-corrections`はsubstring単位のOCR補正候補（`ocr-check`が生成したもの）を対象にしますが、`apply-ocr-review`はページ全文単位のClaude Code画像照合レビュー候補（`claude_review/candidates.json`）を対象にします。候補スキーマ・安全条件は混在していません。

## 1. `apply-ocr-corrections`の目的

`ocr-check`によってOCR崩れ候補は整理されましたが、それを`editable/lesson_pages.json`へ反映する作業はこれまで人間の手作業でした。`apply-ocr-corrections`は、**人間が承認した候補に限って**、この反映作業を機械的に行うためのコマンドです。

すべての候補を自動反映するわけではありません。人間が`ocr_correction_candidates.json`の`status`を確認し、`approved`にした候補だけが対象です。

## 2. `ocr-check`との関係

```text
build-all または lesson-pages で editable/lesson_pages.json を作る
↓
ocr-check で ocr_check_report.md と ocr_correction_candidates.json を生成する
↓
（任意）approve-ocr-candidates で明確な高重要度候補だけ一括approved化する（12節参照）
↓
人間が ocr_correction_candidates(.approved).json を確認する
↓
反映してよい候補だけ status を approved に変更する（一括approved化した分は済んでいる）
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
| `approved` | 反映してよいと判断した候補 | **反映対象**（ただし`action: delete`は対象外。6.1節参照） |
| `proposed`（初期値） | まだ判断していない候補 | 反映しない |
| `rejected` | 反映しないと判断した候補 | 反映しない |
| `needs_image_check` | 元画像確認が必要と判断した候補 | 反映しない |
| `needs_source_check` | 元資料（元画像・元テキスト）の確認が必要と判断した候補。推定修正候補・元画像確認必須候補（[`docs/13_ocr_quality_check_workflow.md`](13_ocr_quality_check_workflow.md)7.1節参照）の初期値 | 反映しない |
| `needs_human_review` | 改善案の妥当性そのものを人間が確認すべき候補。削除候補の初期値 | 反映しない |

`approved`にした候補だけが反映されます。それ以外のstatus（`proposed`のまま放置した候補、`rejected`/`needs_image_check`/`needs_source_check`/`needs_human_review`にした候補）は反映されません。

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

### 6.1 削除候補（`action: delete`）は今回は反映しないこと

`ocr-check`が出す候補には、`action`フィールドがあります（`replace`/`delete`/`source_check`。詳細は[`docs/13_ocr_quality_check_workflow.md`](13_ocr_quality_check_workflow.md)7.1節参照）。

このうち**`action: delete`（削除候補）は、`status`を`approved`に変更しても今回のバージョンでは反映されません**（未反映理由: `delete_action_not_supported`）。安全側の設計として、まずは削除候補を人間に提示するところまでとし、自動での本文削除は見送っています。削除する場合は、`output/editable/lesson_pages.json`を人間が直接編集してください。

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
| `delete_action_not_supported` | `action: delete`（削除候補）の反映は今回未対応 |

## 10. 反映後にllm-handoffへ進む流れ

OCR補正候補を承認・反映した場合は、`lesson_pages.ocr_fixed.json`を次工程の入力に使ってください。

```bash
python3 -m src.cli llm-handoff --input output/editable/lesson_pages.ocr_fixed.json --output output/llm_handoff.md
python3 -m src.cli edit-plan-template --input output/editable/lesson_pages.ocr_fixed.json --output output/edit_plan_template.md
python3 -m src.cli regenerate --input output/editable/lesson_pages.ocr_fixed.json --output-dir output/regenerated
```

## 11. 注意点

- **今回は自動承認しません。** `ocr_correction_candidates.json`の`status`変更は人間が行います。
- **削除候補（`action: delete`）は`approved`にしても反映されません。** 削除する場合は人間が直接編集してください（将来のバージョンで対応する可能性があります）。
- 反映後は`ocr_apply_report.md`の「反映された候補一覧」「差分確認用メモ」を必ず確認してください。
- `source_page_no`/`source_image`/`assets`/`metadata`、ページ数・ページ順は変更されません。
- 将来的には、候補承認を支援するUIや、ローカルLLMによる承認判断支援へつなげられる可能性があります（今回は未実装。詳細は[`docs/07_api_integration_design.md`](07_api_integration_design.md)参照）。

## 12. 高重要度OCR候補の一括approved化（`approve-ocr-candidates`）

`ocr_correction_candidates.json`の候補を1件ずつ手作業で`approved`に変更するのは手間がかかります。`approve-ocr-candidates`は、**条件に一致する明確な候補だけ**を一括で`status: approved`に変更するコマンドです。`editable/lesson_pages.json`への実際の反映は行いません（引き続き`apply-ocr-corrections`が行います）。

### 12.1 使い方・実行例

```bash
python3 -m src.cli approve-ocr-candidates \
  --input output/ocr_correction_candidates.json \
  --output output/ocr_correction_candidates.approved.json \
  --report output/ocr_approval_report.md \
  --severity high \
  --action replace \
  --confidence high
```

- `--input`: `ocr-check`が生成した`ocr_correction_candidates.json`（**このファイルは上書きされません**）。
- `--output`: approved化後のcandidates JSON出力先（既定: `output/ocr_correction_candidates.approved.json`）。
- `--report`: approved化レポートの出力先（省略時はレポートを生成しません）。
- `--severity`/`--action`/`--confidence`: 絞り込み条件（既定はそれぞれ`high`/`replace`/`high`。空文字を指定するとそのfieldでは絞り込みません）。
- `--detection-type`: `detection_type`での絞り込み（既定: 絞り込みなし）。
- `--dry-run`: 実際には`--output`のJSONを生成せず、approved化予定の件数だけレポートに出します。

その後、通常通り`apply-ocr-corrections`で反映します。

```bash
python3 -m src.cli apply-ocr-corrections \
  --input output/editable/lesson_pages.json \
  --candidates output/ocr_correction_candidates.approved.json \
  --output output/editable/lesson_pages.ocr_fixed.json \
  --report output/ocr_apply_report.md
```

### 12.2 安全条件（CLI引数の指定内容にかかわらず常に適用）

以下に該当する候補は、`--severity`/`--action`/`--confidence`にどのような値を指定しても**絶対に自動approved化されません**。

- `action: delete`（削除候補）
- `action: source_check`（元画像確認が必要な候補）
- `status: needs_source_check` / `needs_human_review` / `rejected`
- `detection_type`が`incomplete_sentence`/`source_check_required`/`inferred_ocr_correction`/`unusual_symbol`/`garbled_latin`/`ocr_noise_delete_candidate`のいずれか
- `suggested`または`original`が空

実質的に、今回の自動approved化対象は**辞書一致（`common_ocr_misread`）の高確信度replace候補だけ**です。

### 12.3 `summary.approval`

出力されるcandidates JSONの`summary`には、以下が追加されます。

```json
"approval": {
  "approved_by_command": true,
  "approved_count": 28,
  "criteria": { "severity": "high", "action": "replace", "confidence": "high", "detection_type": null }
}
```

### 12.4 `ocr_approval_report.md`の読み方

レポートは以下の構成です。

1. **サマリー**: 入力候補数・approved化対象件数・変更なし件数・入出力ファイル
2. **approved化した候補**: `candidate_id`/Page/field/`original`/`suggested`/severity/action/confidence/detection_typeのテーブル
3. **approved化しなかった候補**: 理由別の件数
4. **注意**: 自動approved対象外の条件一覧
5. **apply-ocr-correctionsとの関係**: 次工程コマンド例
