# 13 OCR品質チェック・補正候補データ生成ワークフロー（`ocr-check`）

> `llm-handoff`でChatGPT/Claude等へ教材改善を依頼する**前**に、OCR結果の誤認識・文字化け・不自然な表記の可能性がある箇所をシステム側で検出し、修正候補・重要度を人間が判断しやすい形にまとめるコマンドです。プロジェクト方針（README.md「プロジェクト方針：外部API非依存・ローカルLLM移行前提」参照）のとおり、**OCRエンジンの再実行・自動修正・`editable/lesson_pages.json`への自動反映は行いません**。

**取り込み時点のOCR品質そのものは`src/ocr_engine.py`が改善しています**（複数前処理・複数PSM・品質スコアによる最良候補選択・低品質時の再試行。詳細は`docs/02_architecture.md`「`src/ocr_engine.py`」参照）。これにより本節が挙げるような明らかな誤認識・ノイズは以前より減りますが、Tesseract自体の限界により完全には無くなりません。本コマンド（`ocr-check`）は、取り込み後に残った崩れを検出する二段構えの安全網として引き続き必要です。

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
- `--ocr-patterns`: OCRパターン外部辞書のパス（省略時は`config/ocr_patterns.json`。存在しなければ組み込みデフォルトのみ使用）。辞書の育て方は16節を参照。

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

これらの辞書は`src/ocr_patterns.py`が管理する**組み込みデフォルト**であり、`config/ocr_patterns.json`（外部辞書）で追加・上書きできます。詳細は16節を参照してください。

高確信度の修正辞書（`high_confidence_replacements`）。各エントリは重要度も持っており、内容を大きく損ねない軽微な誤認識（「1 つ → 1つ」）は低重要度にしています：

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
- ベネフィット計理想の未来 → ベネフィット＝理想の未来（高）
- 1 つ → 1つ（低）

削除候補の辞書（`delete_candidates`。日本語教材本文として不自然な短い英字ノイズ）：

- ae / BQ / Ps / RSS

推定修正候補の辞書（`inferred_candidates`。復元に推測が入るため`confidence: low`・`status: needs_source_check`）：

- 時 9ま1よう → 決めましょう
- 六坂載祭上 → ※無断転載禁止

元画像確認が必須の候補（`source_check_required`。`suggested`は空のまま）：

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

## 14. OCR候補の重複抑制

同じOCR崩れから複数の検出器が重なって候補を出すことがあります。例えば「時 9ま1よう」という崩れに対して、辞書一致（推定修正候補）が「時 9ま1よう → 決めましょう」を出す一方、汎用パターン検出（数字とかなの混在検出）が部分文字列の「9ま1よう」や、前後を含む「を\n: 時 9ま1よう」も候補として出してしまうことがあります。

検出の網羅性は落とさずに、レポート上の重複だけを整理するため、候補生成後に**重複抑制**を行っています。

### 14.1 抑制の単位と優先順位

同一`page_no`・同一`field`内の候補だけを比較します（別ページ・別fieldの候補は比較しません）。

1. **完全重複**（同一`original`・同一`detection_type`）は、優先度の高い方を1件だけ残します。
2. `spacing`/`garbled_latin`/`ocr_noise_delete_candidate`のような**断片的・機械的な検出**（低価値な検出種別）は、同じグループ内の別候補と`original`が重複・包含関係にあり、その別候補の優先度が同等以上であれば抑制します。

優先度は以下の順で判定します（`candidate_priority_score`関数）。

1. `action`: `replace` > `source_check` > `delete`
2. `status`: `proposed` > `needs_source_check` > `needs_human_review` > `rejected`
3. `confidence`: `high` > `medium` > `low`
4. `severity`: `high` > `medium` > `low`
5. `original`の長さ（長い方を優先）
6. `suggested`の有無

### 14.2 抑制しないもの

`common_ocr_misread`（辞書一致）・`inferred_ocr_correction`（推定修正候補）・`source_check_required`（元画像確認必須）・`unusual_symbol`（記号・括弧崩れ）・`incomplete_sentence`（未完文）は、他の候補と重複していても自動では抑制しません。これらは断片的な検出ではなく、それぞれ独立した判断材料になるためです。

例えば「実貴 → 実践」（辞書一致・高確信度）と「[キャラ設定実貴タイム】」（括弧崩れ）が同じタイトルから両方検出された場合、前者は自動反映候補として、後者は構造確認候補として、それぞれ別の観点で有用なため**両方残ります**（単純な文字列の包含関係だけでは抑制しません）。

### 14.3 レポート・candidates JSONでの見え方

`ocr_check_report.md`の「3. 全体サマリー」に以下が追加されます。

```text
- 検出された疑わしい語句・候補の総数: 61
- 重複抑制前の候補数: 66
- 重複抑制された候補数: 5
```

`ocr_correction_candidates.json`の`summary`には`candidates_before_dedupe`/`suppressed_duplicate_candidates`が、トップレベルには`dedupe`（`before`/`after`/`suppressed`）が追加されます。`candidates`配列には重複抑制後の候補だけが出力され、`candidate_id`は抑制後に連番で振り直されます。

## 15. OCRパターン外部辞書（`config/ocr_patterns.json`）の育て方

OCR崩れ検出・修正候補生成に使う辞書（誤認識辞書・削除候補・推定修正候補・元画像確認必須候補・許可語）は、`src/ocr_check.py`のコードに直接埋め込むのではなく、`src/ocr_patterns.py`が管理する組み込みデフォルトと、`config/ocr_patterns.json`（外部辞書）をマージして使う設計になっています。**実データを処理するたびに新しいOCR崩れパターンを見つけても、コードを変更せずに`config/ocr_patterns.json`を編集するだけで辞書を育てられます。**

### 15.1 `config/ocr_patterns.json`が無くても動くこと

`config/ocr_patterns.json`が存在しない場合、`ocr-check`は組み込みデフォルトのみで従来通り動作します。ファイルが存在する場合は、組み込みデフォルトとマージして使用します（`ocr_check_report.md`の「15. 使用したOCRパターン辞書」節で、読み込み結果を確認できます）。

### 15.2 各セクションの意味と育て方

`config/ocr_patterns.json`は以下の5セクションを持ちます。

**`high_confidence_replacements`**（高確信度の修正候補）

```json
"high_confidence_replacements": {
  "誤認識文字列": "修正候補",
  "1 つ": { "suggested": "1つ", "severity": "low" }
}
```

修正後がほぼ一意に近い、明確な誤字を追加します。単純な文字列でもよく（重要度は自動的に`high`になります）、内容を大きく損ねない軽微な誤認識は`{"suggested": ..., "severity": "low"}`の形式で重要度を下げられます。外部辞書が既存デフォルトと同じkeyを持つ場合は、外部辞書の値で上書きされます。

**`delete_candidates`**（削除候補）

```json
"delete_candidates": ["削除候補文字列"]
```

日本語教材本文として不自然な短い英字ノイズ等を追加します。`allowed_words`に含まれる語句は、`delete_candidates`に入っていても除外されます（許可語が優先）。

**`inferred_candidates`**（推定修正候補）

```json
"inferred_candidates": {
  "OCR崩れ文字列": {
    "suggested": "推定修正候補",
    "confidence": "low",
    "status": "needs_source_check",
    "human_note": "推定修正候補。元画像確認推奨。"
  }
}
```

OCR崩れであることは明確だが、復元に推測が入るものを追加します。`confidence`/`status`/`human_note`は省略可能で、省略時はそれぞれ`low`/`needs_source_check`/「推定修正候補。元画像確認推奨。」になります。

**`source_check_required`**（元画像確認必須の候補）

```json
"source_check_required": ["元画像確認必須文字列"]
```

正しい復元が難しい候補を追加します。`suggested`は常に空になります。

**`allowed_words`**（許可語）

```json
"allowed_words": ["AI", "SNS", "API"]
```

短い英字ノイズ検出（削除候補）の除外語です。大文字小文字は区別されません（`API`と`api`は同じ扱い）。既存デフォルトの許可語一覧は8節・[`src/ocr_patterns.py`](../src/ocr_patterns.py)を参照してください。

### 15.3 追加時の注意点

- **自動修正しすぎないこと**: `config/ocr_patterns.json`に追加した`high_confidence_replacements`は、`ocr-check`実行時に候補として提示されるだけで、自動的に`editable/lesson_pages.json`へ反映されるわけではありません（`apply-ocr-corrections`で`status: approved`にした候補のみ反映）。
- **固有名詞・URL・商品名・人名・地名・数値は慎重に扱うこと**: これらは教材ごとに正しい表記が異なるため、`high_confidence_replacements`（断定的な修正候補）に安易に追加せず、`inferred_candidates`や`source_check_required`（元画像確認を促す分類）に入れることを検討してください。
- 辞書に追加した語句は、追加した教材だけでなく**以後すべての教材**に適用されます。ある教材固有の固有名詞を`delete_candidates`に追加すると、他の教材で同じ語句が正当に使われていても削除候補として提示されてしまう可能性があります。
- JSONとして不正な場合、`ocr-check`はエラーメッセージ（`OCR pattern config is invalid: config/ocr_patterns.json`）を出して終了します。編集後は`python3 -m json.tool config/ocr_patterns.json`等で構文を確認してください。

## 16. 今後の発展の可能性

将来的には、以下のような発展を検討する余地があります。

- OCRパターン外部辞書の教材ジャンルごとの切り替え（複数の`config/ocr_patterns_*.json`を使い分ける等）
- 削除候補（`action: delete`）の`apply-ocr-corrections`での反映対応
- ローカルLLMを使った、辞書ベースでは検出しきれない誤認識・不自然な表現の検出支援

いずれも今回のスコープには含まれません。詳細な方針は[`docs/07_api_integration_design.md`](07_api_integration_design.md)を参照してください。

## 17. Apple Vision OCRとの比較（`--ocr-engine tesseract+vision`。macOS専用・任意）

`src/ocr_engine.py`によるTesseract自身の複数前処理・複数PSM・品質スコアリングだけでは検出できない誤認識が存在します（例: 実データPage7で、Tesseractが`quality: ok`と判定したページに「苦労」→「店労」、「些細」→「性細」等の重大な漢字誤読が複数残っていたが、Tesseract自身の信頼度スコアはこれを検知できなかった）。これは単一エンジンの自己信頼度だけでは原理的に限界があるためで、独立した第二のOCRエンジンとの不一致を追加のシグナルとして使うことで補える。

### 17.1 基本方針

- Tesseractは既存の唯一の取り込み用OCRエンジンとして維持する（`output/editable/lesson_pages.json`は引き続きTesseract結果ベース）。
- macOS標準のVisionフレームワーク（`VNRecognizeTextRequest`）を、比較用の独立した第二のOCRエンジンとして追加する。
- 2つの結果を比較し、不一致が大きいページだけを`needs_review`として人間確認に回す。**Apple Vision結果を自動採用（`editable/lesson_pages.json`への反映）することは今回行わない。**
- Apple Visionが使えない環境（macOS以外、ヘルパー未ビルド等）では、エンジン不一致を理由に全ページを`needs_review`にはしない（既存のTesseract自身の品質判定のみを使う）。

### 17.2 使い方

```bash
# 事前に一度だけ、Apple Vision OCRヘルパーをローカルビルドする（macOS + Xcode Command Line Toolsが必要）
bash scripts/build_apple_vision_ocr.sh

# --ocr-engine tesseract+vision を指定してbuild-allを実行する
python3 -m src.cli build-all \
  --input input/source --mode proofread --output-dir output \
  --output-format image --ocr-engine tesseract+vision
```

`--ocr-engine`は`tesseract`（既定。省略時と同じ。従来通りTesseractのみ）と`tesseract+vision`のいずれかを選べる。`tesseract+vision`は画像inputの場合のみ有効（PDF/PPTXはネイティブテキスト抽出のため対象外）。

### 17.3 構成

```text
Tesseract OCR（src/ocr_engine.py）        … 既存の取り込み用OCR結果
Apple Vision OCR（src/apple_vision_ocr.py） … 比較用の独立した第二のOCR結果
  ↑ tools/apple_vision_ocr/ のSwift製ローカルヘルパー（apple-vision-ocr）を安全に呼び出す
比較器（src/ocr_compare.py）              … 正規化・類似度・行数差・読み順差等の指標を計算
比較オーケストレーション（src/ocr_comparison.py） … ページごとに比較を実行し、結果を保存・HTML化
```

Apple Visionヘルパー（`tools/apple_vision_ocr/`）はSwift Package Managerで構成されたCLIツールで、標準出力へJSON（`engine`/`available`/`language`/`duration_seconds`/`observations`[座標・信頼度・複数候補付き]/`text`/`warnings`）を出力する。Python側（`src/apple_vision_ocr.py`）は`subprocess`で引数配列として安全に呼び出し（`shell=True`は使用しない）、macOS以外・ヘルパー未ビルド・タイムアウト・不正なJSON出力等、あらゆる失敗時に例外を投げず`available: false`を返してTesseractのみの処理へ安全にフォールバックする。

### 17.4 比較指標と`needs_review`判定

比較前に正規化するのは「改行差・連続する空白（半角/全角）・連続する空行」等、表示上だけの差に限定する。**漢字・句読点・長音・引用符・数字は正規化せず保持する**（これらの差はOCR誤認識の可能性があるため）。

主な比較指標（`src/ocr_compare.py`）: 全文類似度・タイトル類似度・行数差・有効文字数差・一方にしか存在しない行・編集比率・読み順の差（2段組みの読み順混在等を検出）・英字/記号ノイズトークン数の差・重要語句差（漢字を含む置換/削除/追加箇所の抽出）。閾値はすべて`src/ocr_compare.py`のモジュール定数として管理し、テスト可能。

最初は保守的に設計しており、いずれか1つでも条件に該当すれば`needs_review`にする（自動的にどちらか一方の結果を正しいと断定して置き換えることはしない）。

### 17.5 保存先・レビュー用HTML

比較結果は`output/ocr_comparison/`（Git管理対象外）へ保存する。

```text
output/ocr_comparison/
  summary.json   # 全体サマリー（機械可読）
  summary.md     # 全体サマリー（人間可読）
  pages/page_NNN.json  # ページごとの両エンジン結果・比較指標・不一致理由
  review.html    # 元画像・両エンジン結果・不一致理由を1ページずつ並べた自己完結型HTML
```

`review.html`は外部CDN・外部JS・外部CSSを使用せず、既存の`output/assets/`の画像を相対パスで参照する（画像を重複コピーしない）。ブラウザ上でのJSON編集・保存機能は無く、目視確認専用。

各ページは「元画像 / Tesseract / Apple Vision」の3列（狭い画面では縦並び）で構成し、Tesseract全文とApple Vision全文は`difflib.SequenceMatcher`による**文字単位の差分ハイライト**付きで並べて表示する（Phase 10.8）。詳細は17.7節を参照。

### 17.6 実行ログへの記録

`--ocr-engine tesseract+vision`時、`build-all`の実行ログに`OCR_COMPARISON`セクションが追加され、Apple Vision利用可否・比較対象ページ数・`needs_review`ページ一覧（Tesseractのみ要確認／Apple Vision不一致のみ要確認／両方の理由で要確認、を区別）が記録される。

### 17.7 差分ハイライト（Phase 10.8・review.html表示専用）

Tesseract全文とApple Vision全文をそのまま並べるだけでは、どの文字が違うのか目視で探す必要があり確認しづらかったため、`review.html`のTesseract/Apple Vision列に、`difflib.SequenceMatcher`による文字単位の差分ハイライトを追加した。**判定ロジック（`src/ocr_compare.py`の正規化・閾値・`needs_review`判定）やJSON形式（`summary.json`/ページ別JSON）は一切変更していない**。あくまで`review.html`の表示だけを改善するもの。

- `src/ocr_comparison.py`の`_render_text_diff(left, right)`が、`SequenceMatcher.get_opcodes()`の`equal`/`replace`/`delete`/`insert`を、`<mark>`要素の異なるCSSクラスへ変換する。
  - `delete`（Tesseractのみに存在）: 左側だけに`diff-tess-del`
  - `insert`（Apple Visionのみに存在）: 右側だけに`diff-vision-ins`
  - `replace`: 左側に`diff-tess-rep`、右側に`diff-vision-rep`（`delete`/`insert`とは下線スタイル（実線/破線）で区別し、色だけに依存しない）
- 色の意味は「どちらの側にだけ存在するか／置換されたか」であり、**Apple Visionを正解として自動判定する意味付けはしていない**（人間が元画像を見て判断する設計を維持）。
- HTML安全性: 元の文字列を先に`SequenceMatcher`で分割してから、分割済みの断片だけを個別に`html.escape()`する（エスケープ後の全文に対して文字位置を適用するとインデックスがずれるため）。`<script>`・`</span>`・`&`・引用符等を含むOCR文字列でもHTML構造を壊さない。
- 各ページ冒頭に凡例（`diff-legend`）を表示し、色以外に`title`属性・下線スタイルでも意味を判別できるようにしている。
- 比較不能時（Apple Vision利用不可・片側または両側が空・非常に長い文字列・絵文字等）でもHTML生成が失敗しないようにしている。片側が空の場合はもう一方の全文がその側だけの差分として強調され、両方空の場合は「(OCRテキストなし)」と表示する。

### 17.8 確定テキスト編集・採用判定・JSON書き出し（Phase 10.9・review.html内で完結）

Tesseract/Apple Visionの表示欄（読み取り専用）に加え、`review.html`に編集可能な「確定テキスト」欄を追加し、レビュー結果をブラウザ内で完結させたJSONとして書き出せるようにした。**この操作はすべて`review.html`内のブラウザローカルの状態であり、`output/editable/lesson_pages.json`・`summary.json`・ページ別JSON・Tesseract/Apple Vision結果本体のいずれも自動変更しない**（正式データへの反映は別タスク）。

#### 操作の流れ

1. 各ページのTesseract/Apple Visionパネル上部にある「確定欄へコピー」ボタンで、そのページの全文（プレーンテキスト、差分ハイライトの`<mark>`タグは含まない）を「確定テキスト」欄へコピーする。確定欄に既に内容がある場合は上書き確認ダイアログが出る。
2. コピー後、確定欄を自由に手修正できる（Tesseract/Apple Visionの表示自体は変更されない）。
3. 確定欄に何も入力しない場合は、「採用判定」の「Tesseractを採用」／「Apple Visionを採用」のいずれかを選ぶ（同時選択は不可。「選択を解除」で未選択に戻せる）。
4. 「元画像を要再確認」／「確認完了」は採用元とは独立したチェック項目。
5. 編集内容・採用指定・チェック状態は、入力するたびにブラウザの`localStorage`へ自動保存される（保存状態はページごとに「保存済み HH:MM:SS」と表示）。ページを再読み込みしても保持される。
6. ページ上部の「レビュー結果をJSONで書き出す」でJSONファイルをダウンロードする。「全レビュー状態をリセット」で保存済みの状態をすべて削除できる（実行前に確認ダイアログが出る）。

#### 採用優先順位（`resolvePageAdoption()`。固定ロジック）

1. 確定テキスト欄に空白以外の内容がある → その内容を採用（`adopted_source: "edited"`）。Tesseract/Apple Visionの採用指定より常に優先
2. 確定欄が空、Tesseract採用が選択されている → Tesseract全文を採用（`"tesseract"`）
3. 確定欄が空、Apple Vision採用が選択されている → Apple Vision全文を採用（`"apple_vision"`）
4. 確定欄が空、どちらも未選択 → 未確定（`"unresolved"`）

Tesseract/Apple Visionの採用ラジオはページごとに同じ`name`属性を持つため、通常のブラウザ操作では同時選択できない。読み込んだ状態データ等により同時選択状態が発生した場合、確定欄が空なら書き出し時にエラー（`adopted_source: "error"`）として明示し、確定欄に内容があれば`edited`を優先しつつ警告を添える。「確認完了」が選択されているのに採用結果が`unresolved`の場合も警告する。

#### 保存キーの一意性（`localStorage`）

保存キーは`ocr_review_state:<materialId>:page-<ページ番号>`の形式。`materialId`は、そのページ一式の`source_image`一覧から算出した簡易ハッシュ（`simpleHash()`/`buildMaterialId()`）で、対象教材ごとに異なる値になる。別の教材・別の`output`で生成した`review.html`を同じブラウザで開いても、保存状態が混ざらない。

#### 書き出しJSONの形式

```json
{
  "schema_version": 1,
  "generated_at": "ISO 8601",
  "source": "ocr_comparison_review",
  "pages": [
    {
      "page_no": 1,
      "adopted_source": "edited",
      "adopted_text": "確定した本文",
      "final_text": "確定欄の本文",
      "tesseract_selected": false,
      "apple_vision_selected": false,
      "requires_source_review": false,
      "review_completed": true,
      "error": null,
      "warning": null
    }
  ]
}
```

絶対パス・秘密情報は含めない。`error`が1件でもある場合、書き出しは中断され、該当ページを示すアラートが表示される。

#### HTML・JavaScript安全性

- 外部CDN・外部JavaScript・外部CSSは使用しない
- OCR文字列・編集文字列をHTMLとして挿入しない（`textContent`/`.value`のみを使用）。差分ハイライトの`<mark>`タグ（`_render_text_diff`）とは別に、コピー元の全文はプレーンテキストとして`<script type="application/json">`ブロックへ安全に埋め込む（`</script`断片は無害化。`src/completion_report.py`と同じ考え方）
- `eval`・`new Function`は使用しない
- 採用判定ロジック（`resolvePageAdoption`）・保存キー生成（`simpleHash`/`buildMaterialId`/`buildStorageKey`）は、DOM・`localStorage`に依存しない純粋関数として分離している（`src/ocr_comparison.py`の`_REVIEW_JS_PURE`）

### 17.9 Claude Codeレビュー指示書（`CLAUDE_OCR_REVIEW.md`。Phase 10.10）

比較結果を人間が1ページずつ目視確認する（17.5節）だけでなく、Claude Code（本ツールとは別セッション）に元画像とTesseract/Apple Vision結果を照合させ、ページごとの候補を作らせるための自己完結した作業指示書を自動生成できる。**このPhaseではClaude API等の外部API呼び出し・自動起動は行わない。** 指示書を読んだ人間が、別途Claude Codeセッションでその指示書を実行する運用を想定している。

#### 使い方

```bash
python3 -m src.cli build-all \
  --input input/source --mode proofread --output-dir output \
  --output-format image --ocr-engine tesseract+vision
```

Apple Visionが利用できた場合、実行後に次が標準出力へ表示される。

```text
CLAUDE_OCR_REVIEW
指示書: output/ocr_comparison/CLAUDE_OCR_REVIEW.md

Claude Codeへ次の1文を渡してください:
output/ocr_comparison/CLAUDE_OCR_REVIEW.md を読み、記載された手順を最後まで実行してください。
```

利用者は、上記の最後の1文をそのままコピーして別のClaude Codeセッションへ渡すだけでよい。ページ数（数ページ〜100ページ以上）を意識した固定文言を毎回考える必要はない。

Apple Visionが利用できなかった場合（未ビルド・macOS以外等）は、指示書自体を生成せず、理由と再実行方法（`bash scripts/build_apple_vision_ocr.sh`でのビルド）を表示する（中身の伴わない指示書を「照合できる」ように見せかけない）。

#### 生成されるファイル

```text
output/ocr_comparison/
  CLAUDE_OCR_REVIEW.md          # Claude Code向けの自己完結した作業指示書（build-allが生成）
  claude_review/
    README.md                    # このディレクトリの説明（build-allが生成）
    pages/page_NNN.json          # ページ別の照合結果（指示書を実行したClaude Codeが作成）
    progress.json                # 進捗（同上）
    candidates.json              # 全ページの集約結果（同上）
    review_summary.md            # 人間確認用サマリー（同上）
```

`build-all`実行時点では`CLAUDE_OCR_REVIEW.md`と`claude_review/README.md`だけが生成され、`pages/`以下・`progress.json`・`candidates.json`・`review_summary.md`は生成されない（指示書を読んだClaude Codeが作業を進めながら作成する）。

#### 指示書の内容

`CLAUDE_OCR_REVIEW.md`は、その回の実データ（`ComparisonSummary`）から対象ページ総数・ページ番号一覧・各種相対パス・Apple Vision利用可否・`needs_review`ページ・生成日時を埋め込むが、**OCR全文・画像バイナリは埋め込まない**（Claude Codeが既存のページ別比較JSON・元画像を直接読む設計）。絶対パスも埋め込まない。

指示書には以下を明記する。

- 元画像を唯一の正本として扱う採用判断基準（多数決で決めない、片方が正しければ採用、部分ごとの統合、両方誤りなら画像に基づいて修正、画像に無い文字を推測しない）
- 判断区分`decision`（`tesseract`/`apple_vision`/`merged`/`corrected`/`unresolved`の5種類に限定）
- ページ別候補JSON・進捗JSON・全体集約JSON・人間確認用サマリーの仕様（下記）
- ページ単位で保存しながら進める中断・再開の手順（100ページ以上でも1回のコンテキストへ全画像を読み込もうとしない）
- Claude Codeが「作業完了」と報告してよい条件（10節参照）

#### ページ別候補JSON（`claude_review/pages/page_NNN.json`）

```json
{
  "schema_version": 1,
  "page_no": 7,
  "source_image": "assets/page_007.jpeg",
  "decision": "merged",
  "proposed_text": "元画像と照合して統合したページ全文",
  "corrections": [
    {"location": "本文1行目", "tesseract": "店労したこと", "apple_vision": "苦労したこと",
     "adopted": "苦労したこと", "reason": "元画像では「苦労」と読める"}
  ],
  "unresolved_spans": [],
  "requires_human_review": false,
  "review_notes": "",
  "reviewed_by": "claude_code",
  "reviewed_at": "ISO 8601"
}
```

`unresolved_spans`が1件でもあるページは、必ず`requires_human_review: true`にする。

#### 進捗JSON（`claude_review/progress.json`）

```json
{
  "schema_version": 1,
  "total_pages": 100,
  "completed_pages": [1, 2, 3],
  "unresolved_pages": [3],
  "failed_pages": [],
  "remaining_pages": [4, 5, 6],
  "updated_at": "ISO 8601"
}
```

既に正常な候補JSON（スキーマが正しく、対象の比較JSONより新しい）が存在するページは処理済みとして扱い、未処理のページから再開できる。

#### 全体集約JSON（`claude_review/candidates.json`）

```json
{
  "schema_version": 1,
  "generated_at": "ISO 8601",
  "source": "claude_code_image_review",
  "total_pages": 100,
  "completed_pages": 100,
  "requires_human_review_pages": [3, 18],
  "decision_counts": {"tesseract": 10, "apple_vision": 60, "merged": 20, "corrected": 8, "unresolved": 2},
  "pages": []
}
```

集約時に、ページ欠落・重複・順序・必須フィールド・`decision`の許可値・`unresolved_spans`と`requires_human_review`の整合・件数集計の一致を検証する。

#### 人間確認用サマリー（`claude_review/review_summary.md`）

対象ページ数・完了ページ数・判断区分ごとの件数・人間確認が必要なページ一覧・ページごとの判断概要・主な修正例・未解決箇所・`editable/lesson_pages.json`へ未反映である注意書き・次に人間が行う操作を含む。人間はまずこのファイルを読み、`requires_human_review_pages`のページだけを重点確認すればよい。

#### 安全性・既存仕様との関係

- Claude API・外部APIの呼び出し、画像・テキストの外部送信、Claude Codeプロセスの自動起動はいずれも行わない
- 候補の`editable/lesson_pages.json`への自動反映は行わない（将来の別タスク）
- 比較元JSON（`summary.json`・`pages/page_NNN.json`）・元画像は変更しない
- Phase 10.8の差分ハイライト・Phase 10.9の確定テキスト編集機能はそのまま維持される（`review.html`は変更されない）
- `claude_review/`は`output/`配下のためGit管理対象外

### 17.10 今回対象外にしたこと

- Apple Vision結果の`editable/lesson_pages.json`への自動採用（将来のバージョンで別タスクとして検討）
- Apple Vision単体での取り込み（Tesseractの置き換え）
- 外部API・有料サービスとしてのOCR（Apple Visionはローカル処理のみで、画像・OCR結果を外部へ送信しない）
- 差分ハイライト（17.7節）は表示専用であり、`needs_review`判定・比較指標の計算方法・閾値には一切影響しない
- Claude Codeレビュー指示書（17.9節）が生成する候補JSONの`editable/lesson_pages.json`への自動反映（将来の別タスク）
- プログラムからのClaude API呼び出し・Claude Codeプロセスの自動起動（17.9節の指示書はあくまで人間が別セッションへ手動で渡すことを前提にしている）
- 確定テキスト編集・書き出しJSON（17.8節）は`review.html`内で完結し、正式データ（`editable/lesson_pages.json`）への反映は行わない（将来の別タスク）
