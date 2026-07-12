# 17 確定済みOCR本文による教材画像ブラッシュアップ生成（`prepare-image-brushup` / `render-brushup`）

> 確定済みの正確な本文（`output/editable/lesson_pages.json`）と元画像の視覚情報を使い、正確な日本語文字を保持したブラッシュアップ済み教材画像を生成する機能です。

## 1. 最終目的とこの機能の位置づけ

このプロジェクトの最終目的は、OCRで文字を読み取ることではありません。

```text
元教材画像 → 正確な本文を取得 → 内容・構成・視認性を改善 → ブラッシュアップ済み教材画像を生成
```

Phase 10.7〜10.11で、Tesseract/Apple VisionによるOCR・両エンジンの比較・Claude Codeによる元画像照合・
`apply-ocr-review`による`editable/lesson_pages.json`への安全な反映までが完成し、画像ブラッシュアップに
使う正確な文字列が準備できました。この機能（Phase 10.12）は、その正確な文字列を実際に使って、
見た目を再設計したブラッシュアップ済み教材画像を生成する、最終目的そのものを担う段階です。

**既存の`rendered/page_NNN.png`（`build-all`/`regenerate`が生成）は、`source_image`があれば元画像を
そのままコピーします。これは後方互換動作として維持されますが、「ブラッシュアップ済み教材画像」と
呼べる成果物ではありません。** 実際に見た目を再設計した画像は、本機能が生成する
`rendered_brushup/`に出力されます（`rendered/`とは別ディレクトリ）。

## 2. 全体の流れ（3段階）

```text
Step 1: prepare-image-brushup
  editable/lesson_pages.json + assets/ から、AIエージェント向けのデザイン指示書
  （brushup_design/AI_IMAGE_BRUSHUP.md）を生成する
↓
Step 2: AI作業エージェント（Claude Code または Codex）によるデザイン設計
  指示書を読んだAIエージェントが、元画像を視覚確認しながらページごとのデザインJSON
  （brushup_design/pages/page_NNN.json）を作成する
↓
Step 3: render-brushup
  デザインJSON + editable/lesson_pages.jsonの確定済み本文から、決定論的なレンダラーが
  ブラッシュアップ済み画像（rendered_brushup/page_NNN.png）を生成する
```

## 3. 役割分担（文字とデザインの分離）

**画像生成AIへ教材本文を画像として描かせません。** 日本語の長文を画像生成AIへ描かせると、
OCRで確定した正しい文字列が再び誤字・欠落・架空文字になるためです。

| 担当 | 役割 |
|---|---|
| Claude Code / Codex（AI作業エージェント） | 元画像の視覚確認、情報階層の分析、ページ目的の判断、レイアウト・配色・強調・装飾方針の決定、構造化されたデザインJSONの作成 |
| 決定論的レンダラー（`render-brushup`、Pillow使用） | `lesson_pages.json`の確定済み文字列を使った正確な描画、はみ出し・欠落・文字化けの検出 |
| 画像生成AI | 今回のバージョンでは使用しません（将来、文字を含まない背景・挿絵素材専用として拡張の余地があります） |

## 4. `prepare-image-brushup`（Step 1）

```bash
python3 -m src.cli prepare-image-brushup --output-dir output/ocr_engine_eval
```

既定入力: `<output-dir>/editable/lesson_pages.json`・`<output-dir>/assets/`

生成物:

```text
<output-dir>/brushup_design/
  AI_IMAGE_BRUSHUP.md   # AIエージェント向けデザイン指示書（Claude Code/Codec両対応の製品非依存文書）
  README.md             # brushup_design/ディレクトリの説明
```

`build-all`実行時点では生成しません。人間が正確な本文の確定後（`apply-ocr-review`実行後等）に
明示的に実行します。指示書には、実データから対象ページ総数・ページ番号一覧・相対パスを埋め込みますが、
**本文（title/body/summary）は一切埋め込みません**（`CLAUDE_OCR_REVIEW.md`と同じ設計方針）。

実行後、標準出力に固定の案内が表示されます。

```text
IMAGE_BRUSHUP_PREPARE: passed
指示書: output/ocr_engine_eval/brushup_design/AI_IMAGE_BRUSHUP.md

Claude CodeまたはCodexへ次の1文を渡してください:
output/ocr_engine_eval/brushup_design/AI_IMAGE_BRUSHUP.mdを読み、記載された手順を最後まで実行してください。
```

## 5. AI作業エージェントによるデザイン設計（Step 2）

利用者は上記の1文をClaude CodeまたはCodexへそのまま渡します。エージェントは指示書に従い、
ページごとに元画像を視覚確認しながら、以下を作成します（**プログラムからの自動起動・Claude API呼び出しは行いません**）。

```text
brushup_design/pages/page_NNN.json   # ページ別デザインJSON
brushup_design/progress.json          # 進捗（完了/未処理ページ）
brushup_design/design_manifest.json   # 全ページの集約manifest
```

### 5.1 デザインJSONの仕様

```json
{
  "schema_version": 1,
  "page_no": 1,
  "source_image": "assets/page_001.jpeg",
  "canvas": {"width": 900, "height": 1200, "background_color": "#F8F7F2"},
  "design_intent": {
    "page_purpose": "導入・実践案内",
    "preserve": ["縦長構成", "タイトルの強調"],
    "improve": ["余白を増やす", "本文の行間を広げる"]
  },
  "theme": {
    "primary_color": "#2F6655", "secondary_color": "#E8F1EC",
    "accent_color": "#D9973D", "text_color": "#202522", "muted_text_color": "#6B746F"
  },
  "template": "title_body",
  "blocks": [
    {"id": "title", "type": "title", "source_field": "title",
     "style": {"font_size": 44, "font_weight": "bold", "alignment": "center",
               "color": "#202522", "background_color": null, "padding": 20}},
    {"id": "body", "type": "body", "source_field": "body",
     "style": {"font_size": 28, "font_weight": "regular", "alignment": "left",
               "color": "#202522", "background_color": "#FFFFFF", "padding": 32}}
  ],
  "footer": {"show_page_number": true, "show_source_notice": true},
  "review_notes": "", "designed_by": "ai_work_agent", "designed_at": "ISO 8601"
}
```

### 5.2 最重要制約: 本文の複製禁止

**デザインJSONは教材本文を複製しません。** 各ブロックは`source_field`（`title`/`body`/`summary`の
いずれか）で`lesson_pages.json`の値を参照するだけです。`text`/`content`/`value`等のフィールドで
本文を直接埋め込むことは`render-brushup`実行時に拒否されます。これにより、デザインを考える
AIエージェントが本文を誤記・改変するリスクを構造的に防いでいます。

### 5.3 許可されるブロック種別（`blocks[].type`）

| type | 用途 |
|---|---|
| `title` / `summary` / `body` | 通常のテキストブロック |
| `note` | 枠で囲んだ注意書き・補足ボックス |
| `checklist` | 1行ずつチェック項目として列挙 |
| `steps` | 1行ずつ番号付き手順として列挙 |
| `quote` | 左アクセントバー付きの引用表示 |
| `divider` | 区切り線（`source_field`不要） |
| `spacer` | 余白（`source_field`不要） |
| `group` | 複数の子ブロック（`title`/`summary`/`body`のみ）を1つの共有背景の中へ積み重ねて表示する（`source_field`の代わりに`blocks`を持つ） |

`"columns": 2`は`body`/`note`いずれのブロックでも指定でき、2段組みで描画します（`checklist`/`steps`/`quote`/`title`/`summary`/`group`の子ブロックは非対応）。

### 5.4 `blocks[].line_range` / `blocks[].split_at` / `blocks[].column_ratio`（最重要・情報階層の再現に必須）

`line_range: [start, end]`（0始まり、`end`は`null`で末尾まで）を指定すると、`source_field`の
段落（bodyの場合は改行区切りの1行=1段落）のうち、その範囲だけをそのブロックで描画します。
既存の行を並べ替えたり複製したりするものではなく、同じ本文の異なる部分を複数のブロックへ分けて
**文字サイズ・太さ・箱の有無を変えるため**の機構です。

問いかけと補足説明が元画像で同じ1枚のカードに収まっている場合、`note`を2つに分けて別々の背景を
描画すると「本文の外に浮いた独立要素」に分裂して見えてしまいます。その場合は`type: "group"`
（5.3節）を使い、子ブロックごとに`line_range`・文字サイズを変えつつ、背景は1つだけにしてください。

`split_at`（`columns: 2`と併用。`line_range`適用後の段落インデックス）を指定すると、2段組みの
分割位置を意味区切りで明示できます。`column_ratio`（既定0.5）は左右の幅配分で、左右で段落の
長さが明らかに異なる場合、不自然な位置での改行を避けるために調整します（5.7節「レビューで
判明した設計ルール」参照）。

### 5.5 許可テンプレート（`template`。分類・集計用）

`title_body` / `title_summary_body` / `checklist` / `question` / `two_column` / `quote` / `summary` / `steps`

### 5.6 中断・再開

ページ数が多い場合でも1回のコンテキストへ全ページを読み込む必要はありません。`progress.json`の
`completed_pages`/`remaining_pages`で進捗を管理し、既に正常なデザインJSONがあるページはスキップして
再開できます（`CLAUDE_OCR_REVIEW.md`と同じ設計）。

### 5.7 実データレビューで判明した設計ルール（必読）

Phase 10.12実装直後、実データ（`output/ocr_engine_eval/`）11ページに対して人間が最初のデザインJSON
（`title`/`body`丸ごと2ブロックだけの構成）で`render-brushup`した結果、以下の指摘を受けた。
**これらは実装の欠陥・設計判断の誤りであり、AI作業エージェントが以降ページを設計する際は必ず
守ること。**

1. **タイトルの二重表示禁止**: `title`ブロックで見出しを別枠表示しているのに、`body`ブロックが
   `line_range`無しで1行目（タイトル重複行）ごと描画すると、同じ文言が2回表示される。
   → `body`を参照するブロックの`line_range`は`[1, null]`（1行目を除く）から始めることを徹底する
2. **情報階層（メリハリ）の欠如禁止**: 元画像は問いかけ部分を大きく太字にし、補足説明・注記は
   小さくしている。この強弱を無視して全行を同じ文字サイズ・同じ枠に詰め込むと、「単なる
   レイアウト崩し」になり、ブラッシュアップとして機能しない
   → `line_range`で問いかけ（大・太字・枠なし）／補足説明（中・枠あり）／注記（小・muted・枠なし）
   のようにブロックを分け、元画像の強弱を再現する（5.4節・4.4節参照）
3. **2段組みの自動分割は意味区切りを無視する**: `split_at`省略時の自動分割は行数の均等さだけを
   見るため、「例1」の途中で列が切り替わり「例2」の内容と混在するなど、内容が意味不明になる
   ことがある
   → 元画像に「例1/例2」等の明確な区切りがある場合は`split_at`で厳密に指定する
4. **余白（`padding`）の過大設定禁止**: 余白を大きくしすぎると、収めるためにレンダラー側の
   自動縮小が働き、かえって文字が小さく読みにくくなる
   → `style.padding`は8〜20px程度を目安にし、文字の大きさを優先する
5. **枠と本文の情報が重複しないようにする**: レンダラーは元々`footer.show_source_notice`で
   固定文言「※無断転載禁止」を自動描画していたが、本文（body）に実在する注記行と重複表示される
   問題があったため、この自動描画は廃止した（`show_source_notice`は現在、元画像ファイル名を
   小さく表示するトレーサビリティ用途に変更されている）。実在する注記文言は、他の本文と同様に
   `line_range`で切り出した独立ブロックとして表示すること

**第2回レビュー（`group`/`column_ratio`導入のきっかけ）で追加判明したルール:**

6. **問いかけを本文の外へ浮かせて分裂させない**: 「①〜」のような問いかけ自体も`body`の一部
   （本文）である。元画像で問いかけと補足説明が同じ1枚のカードに収まっているにもかかわらず、
   問いかけだけを枠なしで浮かせ、補足説明だけを別の枠で囲むと、「本文の一部が本文の外に
   独立して浮いている」ように見えてしまう
   → 文字サイズを変えたいだけであれば、別々の`note`に分けず`type: "group"`（5.3節・5.4節）を
   使い、1つの共有背景の中で子ブロックごとの文字サイズだけを変える
7. **2段組みで注記が箇条書きに混入しないようにする**: 2段組みの`line_range`の終端に、注記
   （※無断転載禁止等）まで含めてしまうと、右列の最後の箇条書き項目のように見えてしまう
   → 注記は2段組みブロックの`line_range`から除外し、他ページと同様に独立した小さいブロックで
   表示する
8. **2段組みの左右幅は内容量に応じて調整する**: 左右で段落の1行あたりの文字数が明らかに
   異なる場合、既定の均等割り（50/50）だと、内容が長い側で読点・閉じ括弧の直前など不自然な
   位置で改行されることがある
   → `column_ratio`（4.5節）で内容が長い側の列を広げる（目安: 明確に長ければ0.55〜0.6程度）

**本文の文言そのものについて**: 上記のルールはすべて見た目（レイアウト・文字サイズ・配置）の
調整であり、`lesson_pages.json`の`title`/`body`/`summary`の文言自体を一切変更しない
（`source_field`参照のみ）という制約は変わらない。文言の質（言い回し・分かりやすさ）の
改善は、このPhase 10.12（画像デザイン）のスコープ外であり、必要であれば別工程として
明示的に追加する。

## 6. `render-brushup`（Step 3）

```bash
python3 -m src.cli render-brushup --output-dir output/ocr_engine_eval
# 任意でフォント指定
python3 -m src.cli render-brushup --output-dir output/ocr_engine_eval --font-path "/System/Library/Fonts/ヒラギノ角ゴシック W4.ttc"
```

入力: `editable/lesson_pages.json` + `brushup_design/design_manifest.json` + `brushup_design/pages/page_NNN.json` + `assets/`

生成物:

```text
rendered_brushup/page_NNN.png          # ブラッシュアップ済み画像
brushup_design/render_report.json      # 機械可読なページ別結果
brushup_design/render_report.md        # 人間可読なレポート
brushup_design/comparison.html         # 元画像とブラッシュアップ画像の比較確認画面（自己完結HTML）
```

### 6.1 本文の取得元（最重要）

**描画する文字は常に`editable/lesson_pages.json`（`LessonPage`）から取得します。** デザインJSON内の
`source_field`はキー名の参照であり、本文そのものはデザインJSON内に存在しません。`title`/`summary`は
そのままの文字列、`body`は`clean_dialogue_lines()`（既存の`lesson_pages.py`の関数を再利用）で
話者・台詞ペアへ分解した各行を段落として描画します。丸数字・括弧・句読点・長音・記号はそのまま保持し、
HTMLエンティティ等へは変換しません。

### 6.2 オーバーフロー対策（本文の打ち切りを禁止）

本文が指定文字サイズで収まらない場合、以下の順序で調整します。**本文を省略・要約したり、
「…」で打ち切ったりすることはありません。**

1. 指定文字サイズで描画可能か測定
2. ブロック内の余白を許容範囲で縮小
3. 行間を許容範囲で縮小
4. 本文文字サイズを設定された最小サイズ（指定サイズの60%、絶対下限8px）まで縮小
5. `type: "body"`のブロックに限り、収まらない場合は2段組みへ自動的に変更する（`body`/`note`
   いずれのブロックも、デザインJSON側が明示的に`columns: 2`を指定した場合は、オーバーフローの
   有無に関わらず常に2段組みで描画する。`split_at`で分割位置を明示できる）
6. それでも収まらない場合はそのページを失敗として扱う（`render_report`に理由を記録し、
   コマンド全体を非ゼロ終了する）

### 6.3 元画像コピー検出

生成した`rendered_brushup/page_NNN.png`が元画像の単純コピーでないことを、ファイルハッシュと
ピクセルデータの比較で機械的に確認します（`verify_not_source_copy()`）。万一同一だった場合は
そのページを失敗として扱います。ただし「異なっていれば改善」とは限らないため、`comparison.html`で
人間による目視確認も行います。

### 6.4 テキスト完全性の記録

各ページの結果に、実際に描画へ渡した文字列（`rendered_fields`）と`lesson_pages.json`の値
（`source_fields`）を記録し、両者が一致すること（`text_match`）を確認します。デザインJSONが
本文を複製できない設計のため、この一致は構造的に保証されます。

### 6.5 CLI終了時の案内

```text
IMAGE_BRUSHUP_RENDER: passed
生成ページ数: 11 / 11
ブラッシュアップ画像: output/ocr_engine_eval/rendered_brushup/
比較画面: output/ocr_engine_eval/brushup_design/comparison.html
レポート: output/ocr_engine_eval/brushup_design/render_report.md
```

失敗ページがある場合は`IMAGE_BRUSHUP_RENDER: failed`となり、終了コードは非ゼロになります。

## 7. 既存機能との関係

- `output/editable/lesson_pages.json`・元画像・`assets/`はこの機能によって変更されません。
- 既存の`rendered/`（`build-all`/`regenerate`が生成）は変更されません。本機能は完全に別の
  出力先（`rendered_brushup/`）を使います。
- Tesseract/Apple Vision OCR・OCR比較・Phase 10.8の差分ハイライト・Phase 10.9のレビューUI・
  Phase 10.10のClaude OCRレビュー指示書・Phase 10.11の`apply-ocr-review`は、いずれも本機能の
  前提となる正確な本文を確定させる工程であり、本機能によって変更されません。

## 8. 今回の制限事項

- デザインJSONの`source_field`はページ単位のフィールド全体（`title`/`body`/`summary`）を参照する
  粗粒度の設計です。フィールドの一部だけを異なるブロックへ割り当てる（例: 本文の特定の1行だけを
  `checklist`ブロックにする）ことは今回のバージョンでは未対応です。
- 元画像の配色は、キャンバス背景色・テーマ色としてAIエージェントが手動で近似する設計です。
  グラデーション背景等、元画像の複雑な配色パターンを自動抽出する機能は未実装です。
- 画像生成AI（背景・挿絵素材の生成）との連携は今回未実装です。
- 元画像内の文字をそのまま画像素材として再利用する機能はありません（誤字が残るため意図的に
  未実装。文字を含まない写真・イラスト等の再利用も今回のバージョンでは未対応です）。
