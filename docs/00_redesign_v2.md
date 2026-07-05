# AI教材ブラッシュアップシステム 再設計書 v2.0

> **この文書はv2再設計時点の一次設計資料であり、現行仕様の正は[`docs/01_requirements.md`](01_requirements.md)・[`docs/02_architecture.md`](02_architecture.md)・[`docs/03_data_format.md`](03_data_format.md)・[`docs/04_output_spec.md`](04_output_spec.md)を参照してください。**
> Phase6以降で追加された`role`・`--plan-output`・`review-report`などは、現行仕様書側（上記4ファイル）を正とします。本文書はrestructure/generateの3モード構想・再設計の背景を理解するための歴史的資料として保持します。

## 1. この設計書の目的

本設計書は、これまで作成してきた「AI教材ブラッシュアップシステム」を、以下の前提で再設計するためのものです。

- 設計者はGPT
- Claude Codeは実装者
- 既存実装を極力壊さない
- `lesson_pages.json` を正データとする
- `brushup.md` / `canva_design.md` / DOCX / PDF / 動画シナリオは派生出力とする
- 実行時に処理モードを選べるようにする

現状のシステムは、元ファイルを尊重する「編集者視点」の作りになっています。  
これは必要な機能ですが、それだけでは用途が限定されます。

今後は次の3モードを持つシステムへ変更します。

1. `proofread`：元ファイルを神とする校正・整形モード
2. `restructure`：元ファイルの主旨は変えずに抜本的に教材として再構成するモード
3. `generate`：与えられた要件から教材を新規生成するモード

---

## 2. 現在の設計上の整理

### 2.1 現在できていること

現時点の実装では、以下が確認済みです。

- `lesson_pages.json` を生成できる
- `lesson_pages.json` から `brushup.md` を生成できる
- `lesson_pages.json` から `canva_design.md` を生成できる
- `lesson_pages.json` から DOCX / PDF を生成できる
- `lesson_pages.json` から動画生成用シナリオを生成できる
- Canva API連携は任意機能
- WordPress投稿連携は任意機能
- Canva / WordPress の環境変数未設定でも本体機能は動作する
- テストは64件通過済み

### 2.2 現在の主な課題

現在の大きな課題は、実行モードが明確に分かれていないことです。

現状の思想は、主に以下です。

```text
元ファイル
↓
内容を尊重して整える
↓
lesson_pages.json
↓
各種出力
```

これは「校正・整形」には向いています。

しかし、実際に必要な用途は次の3種類あります。

```text
A. 元ファイルをできるだけ変えずに整える
B. 元ファイルの主旨は維持しつつ、教材として抜本的に作り直す
C. 元ファイルなしで、要件から教材を作る
```

この3つは、入力・判断基準・出力内容が異なるため、モードとして分離します。

---

## 3. 新しい全体方針

### 3.1 正データは `lesson_pages.json`

今後も、正データは `lesson_pages.json` とします。

```text
lesson_pages.json
├─ brushup.md
├─ canva_design.md
├─ out.docx
├─ out.pdf
└─ scenario/
```

`brushup.md` や `canva_design.md` を直接の正データにはしません。

理由は、原稿と画像設計の乖離を防ぐためです。

### 3.2 モードごとに `lesson_pages.json` の作り方を変える

モードによって変わるのは、主に `lesson_pages.json` の生成方法です。

```text
proofread
  既存教材をなるべく維持して lesson_pages.json を作る

restructure
  既存教材の主旨を維持しつつ再構成して lesson_pages.json を作る

generate
  requirements.json から新規に lesson_pages.json を作る
```

生成後の派生出力は共通です。

```text
lesson_pages.json
↓
brushup.md / canva_design.md / DOCX / PDF / scenario
```

---

## 4. 3つの実行モード

## 4.1 `proofread` モード

### 目的

元ファイルを神とし、内容・主旨・構成・ページ順をできるだけ維持したまま、表現を整えるモードです。

### 利用場面

- 既存教材をきれいにしたい
- 誤字脱字を直したい
- 表現を自然にしたい
- 読みにくい文章を少し分かりやすくしたい
- 元の構成やページ順は変えたくない

### 許可される変更

- 誤字脱字修正
- 表記ゆれ修正
- 冗長表現の整理
- 初心者向けの言い換え
- 見出しの軽微な調整
- 画像内テキストの読みやすさ改善

### 原則禁止する変更

- 主張の変更
- 結論の変更
- ページ順の大幅変更
- 内容の大幅追加
- 内容の大幅削除
- 別教材のような再構成

### 入力

```text
--input examples/sample_pages.json
```

### 出力

```text
output/lesson_pages.json
output/brushup.md
output/canva_design.md
output/out.docx
output/out.pdf
output/scenario/
```

### CLI例

```bash
python -m src.cli lesson-pages \
  --mode proofread \
  --input examples/sample_pages.json \
  --output output/lesson_pages.json
```

---

## 4.2 `restructure` モード

### 目的

元ファイルの主旨・ゴール・約束している価値は維持しつつ、教材として抜本的に作り直すモードです。

### 利用場面

- 元教材が分かりにくい
- ページ構成が悪い
- 説明順が悪い
- 説明が長すぎる
- 読者に刺さりにくい
- 販売教材として弱い
- Instagram投稿や講座資料として再設計したい
- 元ファイルの素材は使うが、完成物として作り直したい

### 許可される変更

- ページ順の変更
- ページ統合
- ページ分割
- 見出しの作り直し
- 説明の追加
- 不要部分の削除
- 導入文の追加
- まとめページの追加
- 読者目線での再構成
- 画像内テキストの作り直し
- Canva設計の作り直し

### 守るべきこと

- 元ファイルの主旨を変えない
- 元ファイルの結論を変えない
- 元ファイルが読者に約束している価値を変えない
- どの元ページを参考にしたか追跡できるようにする

### `source_page_no` の保持

`restructure` モードでは、各ページに `source_page_no` を持たせます。

例：

```json
{
  "page_no": 1,
  "source_page_no": [1, 2],
  "title": "AI投稿は毎日やらなくても大丈夫",
  "body": "50〜60代の方がAI投稿を続けるには、毎日投稿よりも無理なく続けることが大切です。",
  "summary": "毎日より、続けやすさが大切です。"
}
```

### 入力

```text
--input examples/sample_pages.json
--requirements examples/requirements_ai_instagram.json
```

`requirements` は任意ですが、指定を推奨します。  
対象者・トーン・ページ数・用途を明確にすることで、再構成の品質が上がるためです。

### CLI例

```bash
python -m src.cli lesson-pages \
  --mode restructure \
  --input examples/sample_pages.json \
  --requirements examples/requirements_ai_instagram.json \
  --output output/lesson_pages.json
```

---

## 4.3 `generate` モード

### 目的

元ファイルなしで、要件から教材を新規生成するモードです。

### 利用場面

- まだ教材本文がない
- テーマだけ決まっている
- 対象者だけ決まっている
- 講座構成を作りたい
- Instagram投稿教材を作りたい
- 販売用PDFをゼロから作りたい
- AI編集プラットフォームとして新規コンテンツを作りたい

### 入力

```text
--requirements examples/requirements_ai_instagram.json
```

`generate` モードでは `--requirements` は必須です。  
`--input` は不要です。

### CLI例

```bash
python -m src.cli lesson-pages \
  --mode generate \
  --requirements examples/requirements_ai_instagram.json \
  --output output/lesson_pages.json
```

### 注意

現時点では、外部LLM APIを勝手に追加しません。

そのため、最初の実装では以下のどちらかにします。

- requirements からルールベースで教材ページのたたき台を作る
- 将来のLLM連携を前提に、プロンプト生成まで行う

本格的なAI本文生成を行う場合は、別フェーズで LLM連携レイヤーを設計します。

---

## 5. 入力ファイル設計

## 5.1 source_pages.json

既存教材を入力する形式です。

主に `proofread` / `restructure` で使います。

```json
{
  "project_title": "AIインスタ投稿入門",
  "target_audience": "50〜60代のAI初心者",
  "pages": [
    {
      "page_no": 1,
      "source_image": "images/page_001.png",
      "lines": [
        {
          "speaker": "講師",
          "text": "AIを使えば、投稿文を作るのが楽になります。"
        }
      ],
      "notes": "導入ページ"
    }
  ]
}
```

## 5.2 requirements.json

`restructure` / `generate` で使う要件定義ファイルです。

```json
{
  "theme": "50〜60代向けAIインスタ投稿入門",
  "target_audience": "AI初心者の50〜60代",
  "goal": "Instagram投稿を自分で作れるようにする",
  "reader_problem": "AIに興味はあるが、何から始めればよいか分からない",
  "promised_value": "AIを使って無理なく投稿を作れるようになる",
  "tone": "やさしく、安心感があり、専門用語を避ける",
  "page_count": 10,
  "output_style": "教材PDFとInstagram投稿画像",
  "must_include": [
    "AIは難しくないこと",
    "投稿文の作り方",
    "画像作成の考え方",
    "継続のコツ"
  ],
  "must_not_include": [
    "必ず毎日投稿するという表現",
    "高額ツールが必須という表現"
  ]
}
```

## 5.3 run_config.json

将来的には、CLI引数だけでなく設定ファイルでも実行条件を指定できるようにします。

```json
{
  "mode": "restructure",
  "input": "examples/sample_pages.json",
  "requirements": "examples/requirements_ai_instagram.json",
  "output": "output/lesson_pages.json",
  "output_formats": [
    "markdown",
    "canva",
    "docx",
    "pdf",
    "scenario"
  ]
}
```

初期実装では必須ではありません。  
ただし、将来的には `--config` で読み込めるようにする設計にします。

---

## 6. 正データ `lesson_pages.json` の設計

## 6.1 全体構造

```json
{
  "metadata": {
    "project_title": "AIインスタ投稿入門",
    "mode": "restructure",
    "source_policy": "preserve_intent",
    "target_audience": "50〜60代のAI初心者",
    "tone": "やさしく、安心感がある",
    "generated_at": "2026-07-04T00:00:00+09:00"
  },
  "pages": [
    {
      "page_no": 1,
      "source_page_no": [1, 2],
      "title": "AI投稿は毎日やらなくて大丈夫",
      "body": "50〜60代の方がAI投稿を続けるには、毎日投稿よりも無理なく続けることが大切です。",
      "summary": "毎日より、続けやすさが大切です。",
      "image_text": "毎日投稿しなくてOK\n週2回でも十分\n大切なのは続けること",
      "layout_instruction": "中央に大きな見出し。下部に3つの安心ポイントを配置。",
      "canva_prompt": "50〜60代の初心者向け。やさしい色合い。スマホで読みやすいInstagram正方形画像。",
      "video_scene": "講師が、毎日投稿しなくてもよい理由をやさしく説明する。",
      "source_image": "images/page_001.png",
      "notes": "元ページ1と2を統合して再構成"
    }
  ]
}
```

## 6.2 必須項目

各ページは以下を持ちます。

- `page_no`
- `title`
- `body`
- `summary`
- `image_text`
- `layout_instruction`
- `canva_prompt`
- `video_scene`
- `source_image`
- `notes`

## 6.3 モード別の追加項目

### proofread

- `source_page_no` は元ページと同一の番号を保持してよい
- ページ数は原則入力と一致

### restructure

- `source_page_no` は必須
- 複数ページを統合した場合は配列で保持
- ページ数は入力と一致しなくてよい

### generate

- `source_page_no` は空配列または省略可
- `source_image` は空文字または生成予定を示す文字列でよい
- `requirements` 由来であることを metadata に残す

---

## 7. 出力設計

## 7.1 brushup.md

教材本文として使う出力です。

生成元：

```text
lesson_pages.json の title / body / summary
```

役割：

- 教材本文
- 講座原稿
- DOCX/PDFの確認用
- ChatGPT/Claudeで再レビューするための読み物

## 7.2 canva_design.md

Canvaで画像やスライドを作るための設計書です。

生成元：

```text
lesson_pages.json の title / summary / image_text / layout_instruction / canva_prompt
```

役割：

- Canvaで1ページずつデザイン化する
- デザイナーに渡す
- Instagram投稿画像の制作指示にする
- Canva AIへ1ページ単位で貼る

## 7.3 DOCX

Word教材として使う出力です。

生成元：

```text
lesson_pages.json
```

役割：

- Wordでの編集
- 配布教材
- 印刷前確認
- 校正作業

## 7.4 PDF

配布・販売用の固定レイアウト出力です。

生成元：

```text
lesson_pages.json
```

役割：

- 配布用PDF
- 販売教材
- 受講者向け資料

注意：

- 日本語表示は目視確認する
- PDFの自動テストは「生成できること」まで
- 最終確認はMac Preview等で行う

## 7.5 動画シナリオ

動画生成やVOICEVOX用の出力です。

生成元：

```text
lesson_pages.json の summary / video_scene / body
```

出力形式：

- `scenario.json`
- `scenario.md`
- `scene.json`
- `voicevox.txt`

---

## 8. CLI設計

## 8.1 lesson-pages コマンド

### 目的

入力データまたは要件から `lesson_pages.json` を生成します。

### 仕様

```bash
python -m src.cli lesson-pages \
  --mode proofread|restructure|generate \
  --input <source_pages.json> \
  --requirements <requirements.json> \
  --output <lesson_pages.json>
```

### デフォルト

```text
--mode proofread
```

### モード別の必須条件

| mode | --input | --requirements |
|---|---|---|
| proofread | 必須 | 任意 |
| restructure | 必須 | 任意。ただし推奨 |
| generate | 不要 | 必須 |

### エラー条件

- 未知の mode が指定された場合はエラー
- generate で requirements 未指定ならエラー
- proofread で input 未指定ならエラー
- restructure で input 未指定ならエラー
- input JSON が不正ならエラー
- requirements JSON が不正ならエラー

## 8.2 派生出力コマンド

既存コマンドは維持します。

```bash
python -m src.cli generate \
  --input output/lesson_pages.json \
  --output output/brushup.md

python -m src.cli canva \
  --input output/lesson_pages.json \
  --output output/canva_design.md

python -m src.cli docx \
  --input output/lesson_pages.json \
  --output output/out.docx

python -m src.cli pdf \
  --input output/lesson_pages.json \
  --output output/out.pdf

python -m src.cli scenario \
  --input output/lesson_pages.json \
  --output-dir output/scenario
```

## 8.3 任意機能コマンド

Canva API連携とWordPress投稿連携は任意機能です。

```bash
python -m src.cli canva-sync ...
python -m src.cli wp-publish ...
```

要件：

- 環境変数未設定でも本体機能に影響しない
- 未設定時はモックまたはスキップ
- 本番API疎通は別フェーズ扱い

---

## 9. 処理フロー

## 9.1 proofread フロー

```text
source_pages.json
↓
入力バリデーション
↓
元ページ構成を維持
↓
文章を校正・整形
↓
summary / image_text / canva_prompt / video_scene を生成
↓
lesson_pages.json
↓
各種出力
```

## 9.2 restructure フロー

```text
source_pages.json + requirements.json
↓
入力バリデーション
↓
元ファイルの主旨を抽出
↓
対象者・目的・トーンに合わせて再構成
↓
ページ統合・分割・並べ替え
↓
source_page_no を保持
↓
lesson_pages.json
↓
各種出力
```

## 9.3 generate フロー

```text
requirements.json
↓
要件バリデーション
↓
教材構成を生成
↓
各ページの title / body / summary を生成
↓
image_text / canva_prompt / video_scene を生成
↓
lesson_pages.json
↓
各種出力
```

---

## 10. 実装方針

## 10.1 追加・修正する主なモジュール

### `src/lesson_pages.py`

役割：

- `lesson_pages.json` の生成
- モード別生成ロジックの制御
- `proofread` / `restructure` / `generate` の分岐

追加候補関数：

```python
build_lesson_pages(
    mode: str,
    source_path: str | None,
    requirements_path: str | None,
) -> LessonDocument
```

```python
build_lesson_pages_from_source_proofread(...)
```

```python
build_lesson_pages_from_source_restructure(...)
```

```python
build_lesson_pages_from_requirements(...)
```

### `src/models.py`

追加・修正：

- `LessonMetadata`
- `LessonPage`
- `LessonDocument`
- `Requirements`
- `GenerationMode`

### `src/cli.py`

追加・修正：

- `lesson-pages` コマンドに `--mode` を追加
- `--requirements` を追加
- モードごとの必須条件チェック
- エラーメッセージ整備

### `src/validation.py` または既存バリデーション

追加・修正：

- requirements のバリデーション
- mode のバリデーション
- lesson_pages のバリデーション強化

---

## 11. テスト設計

## 11.1 モード別テスト

追加すべきテスト：

1. `proofread` で既存入力から `lesson_pages.json` が生成される
2. `proofread` ではページ数が元入力と一致する
3. `proofread` では metadata.mode が `proofread` になる
4. `restructure` で `source_page_no` 付きの `lesson_pages.json` が生成される
5. `restructure` では metadata.mode が `restructure` になる
6. `generate` で requirements だけから `lesson_pages.json` が生成される
7. `generate` では metadata.mode が `generate` になる
8. `generate` で requirements 未指定ならエラー
9. `proofread` で input 未指定ならエラー
10. `restructure` で input 未指定ならエラー
11. 未知の mode 指定時はエラー

## 11.2 派生出力テスト

1. `lesson_pages.json` から `brushup.md` が生成される
2. `lesson_pages.json` から `canva_design.md` が生成される
3. `brushup.md` と `canva_design.md` の page_no が一致する
4. `brushup.md` の title が `canva_design.md` 側にも反映される
5. DOCX が生成される
6. PDF が生成される
7. scenario 出力が生成される

## 11.3 任意機能テスト

1. Canva APIキー未設定でも本体機能が動く
2. WordPress認証情報未設定でも本体機能が動く
3. Canva連携コマンドは未設定時にモックまたはスキップする
4. WordPress投稿コマンドは未設定時にモックまたはスキップする

---

## 12. READMEに明記すべきこと

READMEには以下を必ず書きます。

### 12.1 基本思想

```text
このシステムでは lesson_pages.json を正データとします。
brushup.md / canva_design.md / DOCX / PDF / scenario は lesson_pages.json から生成される派生出力です。
```

### 12.2 3モードの違い

| mode | 日本語名 | 用途 |
|---|---|---|
| proofread | 校正・整形 | 元ファイルを神として整える |
| restructure | 再構成 | 主旨は維持して教材として作り直す |
| generate | 新規生成 | 要件から教材を作る |

### 12.3 推奨フロー

```bash
python -m src.cli lesson-pages \
  --mode restructure \
  --input examples/sample_pages.json \
  --requirements examples/requirements_ai_instagram.json \
  --output output/lesson_pages.json

python -m src.cli generate \
  --input output/lesson_pages.json \
  --output output/brushup.md

python -m src.cli canva \
  --input output/lesson_pages.json \
  --output output/canva_design.md
```

### 12.4 Canva / WordPress の位置づけ

```text
Canva API連携とWordPress投稿連携は任意機能です。
未設定でも本体機能は動作します。
現時点ではモック付きの連携雛形であり、本番API疎通は別途確認が必要です。
```

---

## 13. Claude Codeへの実装指示書

以下を Claude Code に渡してください。

```text
設計者GPTが作成した「AI教材ブラッシュアップシステム 再設計書 v2.0」に従って実装してください。

重要方針：
- 設計変更は勝手に行わない
- 不明点がある場合は質問する
- 既存CLI互換性をできるだけ維持する
- 正データは lesson_pages.json とする
- brushup.md / canva_design.md / DOCX / PDF / scenario は派生出力とする
- 実行時に proofread / restructure / generate の3モードを選択できるようにする
- Canva API連携とWordPress連携は任意機能のままにする

実装範囲：
1. lesson-pages コマンドに --mode を追加
2. --requirements を追加
3. proofread / restructure / generate の3モードを実装
4. requirements.json のモデルとバリデーションを追加
5. lesson_pages.json の metadata.mode を追加
6. restructure では source_page_no を保持
7. generate では requirements のみから lesson_pages.json を生成
8. READMEを更新
9. examples/requirements_ai_instagram.json を追加
10. テストを追加

テスト要件：
- pytest 全件pass
- 3モードそれぞれのCLI実行例が動く
- 既存の派生出力コマンドが動く
- Canva/WordPress未設定でも本体機能が動く

完了後、以下を報告してください。
- 修正ファイル
- 追加ファイル
- 追加テスト
- pytest結果
- 3モードの実行例
- 既存CLI互換性
- 残課題
```

---

## 14. 今後の拡張候補

今回の再設計では、外部LLM API連携は必須にしません。  
ただし、将来的には以下を追加できます。

### 14.1 LLM連携レイヤー

- OpenAI API
- Claude API
- Gemini API
- ローカルLLM

### 14.2 生成品質チェック

- 主旨が変わっていないか
- 対象者に合っているか
- 誇大表現がないか
- 教材として分かりやすいか
- 画像テキストと本文が乖離していないか

### 14.3 プラグイン化

- DOCX出力プラグイン
- PDF出力プラグイン
- Canva設計プラグイン
- WordPress投稿プラグイン
- 動画シナリオプラグイン
- 小説校閲プラグイン
- ブログ記事編集プラグイン

---

## 15. 最終判断

今回の設計変更により、システムの位置づけは次のように変わります。

```text
旧：
既存教材を整えるツール

新：
教材を校正・再構成・新規生成できる制作基盤
```

特に重要なのは、以下です。

```text
モードによって「元ファイルをどこまで尊重するか」を明示的に選べる
```

これにより、次のような使い分けができます。

```text
proofread：
元教材を壊さず整える

restructure：
元教材を素材にして教材として作り直す

generate：
要件から新規教材を作る
```

この設計で進めることで、AI教材ブラッシュアップシステムは単なる校正ツールではなく、将来的に「AI編集者」「AI教材制作者」「AIコンテンツ制作基盤」へ拡張しやすくなります。
