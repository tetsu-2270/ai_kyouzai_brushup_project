# 13 OCR品質チェック・補正候補データ生成ワークフロー（`ocr-check`）

> `llm-handoff`でChatGPT/Claude等へ教材改善を依頼する**前**に、OCR結果の誤認識・文字化け・不自然な表記の可能性がある箇所をシステム側で検出し、修正候補・重要度を人間が判断しやすい形にまとめるコマンドです。プロジェクト方針（README.md「プロジェクト方針：外部API非依存・ローカルLLM移行前提」参照）のとおり、**OCRエンジンの再実行・自動修正・`editable/lesson_pages.json`への自動反映は行いません**。

## 1. OCR品質チェックの目的

実データで`llm-handoff`を試したところ、ChatGPT/Claude等からの回答の多くが教材の構成・文章改善ではなく、OCR誤認識の指摘になってしまうケースが確認されました。

例：

- 一買 → 一貫
- アウトブット → アウトプット
- 右労 → 苦労
- 革細 → 些細
- 実貴 → 実践
- 共通説識 → 共通認識
- `RSS` / `Ps` / `ERRh se rel Cee oe` などの意味不明な文字列

このように、OCR結果の品質が低いままLLMに投入すると、本来依頼したい「教材改善」より先に「誤字修正」がLLMの回答の大部分を占めてしまいます。`ocr-check`は、この問題を先に解消するため、LLM投入前にシステム側でOCR崩れ候補を検出する工程です。

## 2. なぜLLM投入前にOCR確認が必要か

- OCR誤字が多い状態でLLMに構成チェック・文章改善を依頼すると、回答が誤字修正の指摘に埋もれてしまう。
- OCR誤字の検出・修正候補提示は、ルールベース（辞書一致・パターンマッチ）でシステム側が先に行える。
- 先にOCR品質を整えることで、`llm-handoff`後のLLM回答が教材内容の改善（構成・文章）に集中しやすくなる。

## 3. `ocr-check`の使い方

```bash
python3 -m src.cli ocr-check --input output/editable/lesson_pages.json --output output/ocr_check_report.md --candidates-output output/ocr_correction_candidates.json
```

- `--input`: `lesson_pages.json`形式（`output/editable/lesson_pages.json`を想定）。
- `--output`: Markdownレポートの出力先（省略時は`output/ocr_check_report.md`）。
- `--candidates-output`: 補正候補JSONの出力先（省略時は`output/ocr_correction_candidates.json`）。

確認対象は`title`/`summary`/`body`/`notes`/`layout_instruction`です。存在しない項目があってもエラーにはならず、可能な範囲でレポート・候補JSONを生成します。

## 4. 運用フロー全体における位置づけ

```text
build-all または lesson-pages で editable/lesson_pages.json を作る
↓
ocr-check で OCR崩れ・文字化け・不自然な文字列を検出する
↓
ocr_check_report.md / ocr_correction_candidates.json を確認する
↓
人間が採用する修正・不採用・元画像確認が必要な箇所を判断する
↓
（現段階では）人間が必要に応じてeditable/lesson_pages.jsonを補正する
↓
llm-handoff でLLM投入用Markdownを作る
↓
ChatGPT/Claude等へ貼って構成チェック・文章改善案を得る
↓
edit-plan-template で採用判断を整理する
↓
regenerate で再出力する
```

## 5. `ocr_check_report.md`の読み方

レポートは以下の構成です。

1. 目的 / 2. 使い方
2. **全体サマリー**: ページ数・要確認ページ数・検出件数・重要度別件数など
3. **システム検出結果サマリー**: 検出種別ごとの件数（`common_ocr_misread`/`garbled_latin`/`unusual_symbol`/`incomplete_sentence`/`spacing`）
4. **重要度別の要確認候補一覧**: 高・中・低ごとに候補を列挙
5. **OCR崩れの可能性があるページ一覧**
6. **ページ別の確認結果**: ページごとの基本情報・検出結果・修正候補・修正メモ欄
7. **よくあるOCR誤認識候補**: 辞書一致した候補の一覧
8. **修正候補**: 全候補のテーブル
9. **元画像確認が必要そうな箇所**
10. **人間が最終判断すべき箇所**（ガイド文）
11. **補正候補JSONの使い方**（ガイド文）
12. **修正作業の進め方**（ガイド文）
13. **llm-handoffへ進む前のチェックリスト**

## 6. `ocr_correction_candidates.json`の読み方

```json
{
  "version": 1,
  "source_file": "output/editable/lesson_pages.json",
  "generated_at": "2026-07-09T12:00:00+09:00",
  "mode": "proofread",
  "summary": { "total_pages": 5, "total_candidates": 8, "high": 4, "medium": 3, "low": 1 },
  "candidates": [
    {
      "candidate_id": "ocr-0001",
      "page_no": 2,
      "page_index": 1,
      "field": "body",
      "original": "一買",
      "suggested": "一貫",
      "action": "replace",
      "severity": "high",
      "reason": "OCR誤認識辞書に一致します（一買 → 一貫）",
      "detection_type": "common_ocr_misread",
      "source_page_no": [2],
      "source_image": "page_002.png",
      "confidence": "high",
      "requires_image_check": false,
      "status": "proposed",
      "human_note": ""
    }
  ]
}
```

候補1件ごとの主なフィールド：

| フィールド | 意味 |
|---|---|
| `candidate_id` | 候補の一意なID（例: `ocr-0001`） |
| `page_no` / `page_index` | 表示上のページ番号 / `pages`配列上のindex（`apply-ocr-corrections`の反映処理で使用） |
| `field` | 検出元の項目（`title`/`summary`/`body`/`notes`/`layout_instruction`） |
| `original` / `suggested` | 検出された元の文字列 / 修正候補（断定できない場合は`null`） |
| `action` | `replace`（置換）/`delete`（削除候補）/`source_check`（元画像確認が必須。詳細は7.1節） |
| `severity` | `high`/`medium`/`low` |
| `confidence` | `high`/`medium`/`low`（推定の確からしさ） |
| `reason` | 検出理由 |
| `detection_type` | `common_ocr_misread`/`inferred_ocr_correction`/`source_check_required`/`garbled_latin`/`unusual_symbol`/`incomplete_sentence`/`spacing` |
| `requires_image_check` | 元画像確認を推奨するかどうか |
| `status` | 初期値は検出内容により異なる（4.1節参照）。人間が`approved`/`rejected`等へ変更する |
| `human_note` | 人間がメモを書くための欄。推定修正候補・削除候補には検出時点の注記が入っていることがある |

**このJSONは今回は自動反映されません。** 人間が`status`を`approved`に変更した候補だけ、[`apply-ocr-corrections`](14_apply_ocr_corrections_workflow.md)で`editable/lesson_pages.json`へ反映できます（ただし`action: delete`の候補は`apply-ocr-corrections`側でも今回は反映されません。7.1節参照）。

## 7. 重要度の見方

| 重要度 | 目安 |
|---|---|
| 高 | 本文の意味を大きく損ねる可能性が高い／OCR誤認識辞書に一致／文が途中で切れている可能性が高い |
| 中 | 不自然な英字・記号列／番号崩れ／元画像確認を推奨する箇所 |
| 低 | 軽微な表記ゆれ／余計な空白／そのままでも読めるが整えた方がよい箇所 |

### 7.1 削除候補・推定修正候補・元画像確認必須候補の分類

「OCR崩れであることは明確だが、正しい復元後の文字列を断定できない」候補を、単に「元画像確認」として一括りにするのではなく、以下の4分類で扱います。実運用（実データでの検証）を踏まえた改善です。

| 分類 | `action` | 初期`status` | `confidence` | 例 |
|---|---|---|---|---|
| high confidence correction | `replace` | `proposed` | `high` | 共通説識→共通認識、一買→一貫、有崩す→崩す、生んな経験→そんな経験、どいう→という 等 |
| deletion candidate（削除候補） | `delete` | `needs_human_review` | `medium` | `ae`/`BQ`/`Ps`/`RSS`のような、日本語教材本文として不自然な短い英字ノイズ |
| inferred correction candidate（推定修正候補） | `replace` | `needs_source_check` | `low` | 時 9ま1よう→決めましょう、六坂載祭上→※無断転載禁止 等（復元に推測が入るため断定しない） |
| source check required（元画像確認必須） | `source_check` | `needs_source_check` | `low` | マチオロウーざん、ERRh se rel Cee oe、SAAT こコ全わった等（正しい復元が難しい） |

**削除候補（`action: delete`）について**: 英字だけの短いノイズ・意味のない英数字断片を対象にしますが、固有名詞やURLの可能性がある語句を過検出しすぎないよう、`Instagram`/`SNS`/`AI`/`URL`/`ID`/`OK`/`NG`/`PDF`/`JSON`/`CSV`/`API`/`LLM`等は通常語として許可リストに含めています（`_LATIN_ALLOWLIST`参照）。

**いずれの分類も自動反映はしません。** `status`が`approved`にならない限り[`apply-ocr-corrections`](14_apply_ocr_corrections_workflow.md)では反映されず、さらに`action: delete`の候補は`approved`にしても今回のバージョンでは反映されません（安全側の設計。将来のバージョンで対応検討）。

## 8. よくあるOCR誤認識例（検出辞書）

現時点の初期辞書（`src/ocr_check.py`の`_OCR_MISREAD_DICTIONARY`、将来拡張可能）。各エントリは重要度も持っており、内容を大きく損ねない軽微な誤認識（「1 つ → 1つ」）は低重要度にしています：

- 一買 → 一貫（高）
- アウトブット → アウトプット（高）
- 右労 → 苦労（高）
- 革細 → 些細（高）
- 実貴 → 実践（高）
- 共通説識 → 共通認識（高）
- 人帳面 → 几帳面（高）
- 叱嘘激励 → 叱咤激励（高）
- 全1 1問 / 全1 1 問 → 全11問（高）
- 有崩す → 崩す（高）
- 生んな経験 → そんな経験（高）
- どいう → という（高）
- 1 つ → 1つ（低）

推定修正候補の辞書（`_INFERRED_CORRECTION_DICTIONARY`。復元に推測が入るため`confidence: low`・`status: needs_source_check`）：

- 時 9ま1よう → 決めましょう
- ベネフィット計理想の未来 → ベネフィット＝理想の未来
- 六坂載祭上 → ※無断転載禁止

元画像確認が必須の候補（`_SOURCE_CHECK_REQUIRED_PHRASES`。`suggested`は空のまま）：

- マチオロウーざん
- ERRh se rel Cee oe
- SAAT こコ全わった

## 9. システムが検出する内容

- よくあるOCR誤認識（辞書一致）
- 意味不明な英字・記号列（`URL`/`SNS`/`Instagram`/`Canva`/`PDF`/`DOCX`/`PNG`/`AI`/`LLM`/`OCR`/`OK`/`NG`/`ID`等は許可語として除外し、過検出を抑える）
- 不自然な記号・番号崩れ（「(⑤」「〈④」「③②」、半角始まり全角終わりの括弧崩れ「[〜】」等）
- タイトル特有の記号混入（`|`/`°`/`@`等）
- 文が途中で切れていそうな箇所（フィールド末尾の行のみを対象とし、「〜たら」「〜ので」等で終わる場合。次に続く行がある場合は対象にしない）
- 数字と日本語の間の不自然な空白、数字とかな・カタカナがタイトに交互する不自然な混在（例:「9ま1よう」）
- 日付・分数のような数字/数字表記（誤って断定的に修正しないよう元画像確認候補にする）

いずれもルールベースの検出であり、完全な自然言語判定は行いません。過検出（実際は問題ない箇所を候補として出す）が起こり得ることを前提に、「疑わしい候補」として提示します。

### 9.1 検出対象外にしている箇所（過検出抑制）

`layout_instruction`は生成側のレイアウト指示・内部参照（`assets`/`page`等）が入ることがあり、OCR本文ではありません。そのため、`layout_instruction`は**辞書一致（よくあるOCR誤認識）のみ**を確認し、意味不明な英字・記号列や不自然な空白等の検出対象からは除外しています。これにより、`layout_instruction`に含まれる`assets`/`page`等の内部語句が毎ページ検出されてしまう問題を避けています。

また、意味不明な英字・記号列の検出では、`assets`/`page`/`image`/`source_image`/`rendered`/`output`/`input`/`editable`/`layout`/`instruction`等のシステム内部語句・レイアウト指示由来の語句も許可語として除外しています。

「元画像確認が必要そうなページ数」も、`layout_instruction`由来の候補だけでは加算されません。`title`/`summary`/`body`/`notes`に候補がある場合のみ、元画像確認が必要そうなページとしてカウントします。

## 10. 人間が最終判断する内容

- 各候補の`status`を`approved`（採用）/`rejected`（不採用）/`needs_source_check`（元資料確認）/`needs_human_review`（内容確認）に振り分ける。
- 修正候補（`suggested`）が空、または断定できない候補は、元画像と照らし合わせて判断する。
- 削除候補（`action: delete`）は、固有名詞やURLの可能性がないか文脈を確認してから判断する。
- 数字・日付・地名・固有名詞に関わる候補は特に慎重に判断する。

## 11. 現段階では自動修正しないこと

- OCRエンジンの再実行は行いません。
- 検出した候補の自動置換・自動反映は行いません。
- `editable/lesson_pages.json`への反映は、現段階では人間が`title`/`summary`/`body`/`notes`/`layout_instruction`を確認して行います。`source_page_no`/`source_image`/`assets`は通常編集しません。

## 12. 採用済み候補をシステム反映する方針

`ocr_correction_candidates.json`の`status`を`approved`に変更した候補は、[`apply-ocr-corrections`](14_apply_ocr_corrections_workflow.md)コマンドで`editable/lesson_pages.json`へ反映できます。ただし`action: delete`の削除候補は、`approved`にしても今回のバージョンでは反映されません（安全側の設計。7.1節参照）。将来的には、削除候補の反映にも対応する可能性があります。

## 13. OCR補正後にllm-handoffへ進む流れ

```bash
# 1. OCR品質を確認する
python3 -m src.cli ocr-check --input output/editable/lesson_pages.json --output output/ocr_check_report.md --candidates-output output/ocr_correction_candidates.json

# 2. 高重要度の候補を中心に、必要なら output/editable/lesson_pages.json を人間が補正する

# 3. OCR補正後にLLM投入用Markdownを作る
python3 -m src.cli llm-handoff --input output/editable/lesson_pages.json --output output/llm_handoff.md
```

その後は[`docs/11_llm_handoff_workflow.md`](11_llm_handoff_workflow.md)・[`docs/12_llm_review_apply_workflow.md`](12_llm_review_apply_workflow.md)の流れ（ChatGPT/Claude等への投入 →`edit-plan-template`→`regenerate`）に進みます。`edit_plan_template.md`にも、OCR確認が済んでいるかのチェック項目が含まれます。

## 14. 今後の発展の可能性

将来的には、以下のような発展を検討する余地があります。

- OCR誤認識辞書の拡充・外部化（教材ジャンルごとの辞書切り替え等）
- 採用済み候補を`editable/lesson_pages.json`へ反映する`apply-ocr-corrections`の実装
- ローカルLLMを使った、辞書ベースでは検出しきれない誤認識・不自然な表現の検出支援

いずれも今回のスコープには含まれません。詳細な方針は[`docs/07_api_integration_design.md`](07_api_integration_design.md)を参照してください。
