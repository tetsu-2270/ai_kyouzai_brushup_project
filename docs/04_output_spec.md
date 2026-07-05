# 04 出力仕様

> 本ドキュメントは出力仕様（`lesson_pages.json`のスキーマ、各派生出力の生成元・構成）に加えて、それらを生成するCLIコマンドの使い方（`--mode`/`--plan-output`/`review-report`等）も含む、**CLI仕様・出力仕様を含む現行仕様書**です。ファイル名は歴史的経緯で`04_output_spec.md`のままですが、内容としてはCLIコマンドの入出力仕様書を兼ねています。他ドキュメントから参照する際は本ファイル（`docs/04_output_spec.md`）を正としてください（`04_cli_spec.md`という名前のファイルは存在しません）。

## 元資料の自動取り込み（`import-source` / `build-all`）

作成者向けの主導線は、元資料（画像/PDF/PPTX）を`input/source/`に置いて`build-all`コマンドを実行することである（詳細は`docs/08_user_acceptance_test.md`、README「クイックスタート（作成者向け）」を参照）。`imported_pages.json`/`lesson_pages.json`はいずれもシステムが自動生成する中間ファイルであり、**作成者が手作業で作るものではない**。

`import-source`は、元資料から`docs/03_data_format.md`の`pages`形式互換のJSON（`imported_pages.json`）を生成する。

| 元資料 | 取り込み方法 | 保存されるアセット |
|---|---|---|
| 画像（`.png`/`.jpg`/`.jpeg`/`.webp`） | ディレクトリ配下をファイル名順に1画像=1ページ。OCR（`pytesseract`。tesseract本体が無い環境ではテキスト空でフォールバック）でテキスト抽出 | `output/assets/page_NNN.<ext>`（元画像そのもの） |
| PDF（`.pdf`） | `pymupdf`でページ単位にテキスト抽出＋ページ画像化 | `output/assets/page_NNN.png`（ページ全体のラスタ画像） |
| PPTX（`.pptx`） | `python-pptx`でスライド単位にテキスト抽出＋スライド内埋め込み画像を抽出（スライド全体のレンダリングは非対応） | `output/assets/slide_NNN_M.<ext>`（スライド内の埋め込み画像） |
| PPT（`.ppt`旧形式） | 未対応（明確なエラーメッセージを返す） | - |

`imported_pages.json`の各ページは、`page_no`/`source_image`/`source_assets`/`title`/`summary`/`lines`/`improvement_points`/`canva.layout_type`/`canva.main_visual`/`canva.notes`を持つ（`docs/03_data_format.md`のスキーマに準拠）。`source_image`は1ページの主要な参照画像、`source_assets`はPPTXのスライド内に複数の画像がある場合などの追加アセット一覧（画像・PDF取り込みでは通常空配列）。

`build-all`は`import-source`（→`imported_pages.json`+`output/assets/`）→`lesson-pages`（→`lesson_pages.json`）→`generate`/`canva`/`docx`/`pdf`/`scenario`/`review-report`を内部で順に実行する。`--mode`は`proofread`/`restructure`のみ（`generate`は元資料を使わないモードのため`build-all`の対象外。`generate`を使う場合は`lesson-pages --mode generate`を直接使う）。

## 正データと派生出力の関係
`lesson_pages.json`（`docs/03_data_format.md`とは別スキーマ）が正データであり、以下の出力はすべてこのファイルから派生生成される。`brushup.md`と`canva_design.md`が同じ`lesson_pages.json`から生成されるため、ページ番号・タイトルは常に一致する。

`lesson_pages.json`のトップレベルは以下の構造を持つ（v2.0）。

```json
{
  "metadata": {
    "project_title": "教材ブラッシュアップ設計書 v1.0",
    "mode": "proofread",
    "source_policy": "preserve_original",
    "target_audience": "教材制作者・Canva作業者",
    "tone": "",
    "generated_at": "2026-07-04T22:00:00+09:00"
  },
  "pages": [
    {
      "page_no": 1,
      "source_page_no": [1],
      "role": "",
      "title": "...",
      "body": "...",
      "summary": "...",
      "image_text": "...",
      "layout_instruction": "...",
      "canva_prompt": "...",
      "video_scene": "...",
      "source_image": "...",
      "source_assets": [],
      "notes": "..."
    }
  ]
}
```

- `metadata.mode`は`lesson-pages`コマンドの`--mode`（`proofread`/`restructure`/`generate`）に対応する。
- `metadata.requirements_source`は`--requirements`を指定した場合のみ、要件定義の`theme`が入る（省略時はキー自体を出力しない）。
- 各ページの`source_page_no`は、生成元となった元ページ番号の**配列**（1ページ由来でも`[1]`のように配列。`generate`では`[]`）。
- 各ページの`source_assets`は、`source_image`以外に保持している関連画像の一覧（PPTXのスライド内に複数の埋め込み画像がある場合など）。通常は空配列。
- 各ページの`role`は`intro`/`explanation`/`practice`/`summary`等（`restructure`/`generate`で設定。`proofread`では基本空文字）。
- **`source_page_no`/`role`は内部管理情報であり、`brushup.md`/`canva_design.md`/DOCX/PDF/動画シナリオのいずれの派生出力にも表示されない**。制作者が確認したい場合は後述の`review-report`コマンドを使う。
- 後方互換のため、`document.project_title`（`metadata.project_title`）・`document.target_reader`（`metadata.target_audience`）としてもアクセスできる。旧来の`project_title`/`target_reader`をトップレベルに直接持つ`lesson_pages.json`（v1.0形式）も読み込み時にはそのまま解釈される。

`lesson-pages`の3モード（`proofread`/`restructure`/`generate`）の詳細は[`docs/00_redesign_v2.md`](00_redesign_v2.md)を参照。

## `restructure`の再構成プラン

`restructure`モードは、`--plan-output`を指定すると、ページ構成の意思決定過程を「再構成プラン」として出力できる（本文組み立て前の構造情報のみ）。

出力例（`--plan-output`で指定したパス）:

```json
{
  "mode": "restructure",
  "strategy": "元教材の主旨を維持しつつ、対象読者向けに導入・実践・まとめを追加し、内容の薄いページは統合、長すぎるページは分割して再構成する。",
  "pages": [
    {"new_page_no": 1, "role": "intro", "title": "この教材でできるようになること", "source_page_no": [1], "operation": "add_intro_from_source"},
    {"new_page_no": 2, "role": "explanation", "title": "AIとは / ChatGPTとは", "source_page_no": [1, 2], "operation": "merge"},
    {"new_page_no": 3, "role": "practice", "title": "実際にやってみましょう", "source_page_no": [1, 2], "operation": "add_practice"},
    {"new_page_no": 4, "role": "summary", "title": "まとめ", "source_page_no": [1, 2], "operation": "add_summary"}
  ]
}
```

`operation`の種類:

| operation | 意味 |
|---|---|
| `add_intro_from_source` | 元ページ情報をもとに導入ページを新規追加 |
| `merge` | 内容が薄い（目安30文字未満）連続ページを1ページへ統合 |
| `split_first_half` / `split_second_half` | 長すぎる（目安200文字超）1ページを句点位置で前半・後半に分割。両方とも同じ`source_page_no`を持つ |
| `carry_over` | 統合・分割の対象にならなかったページをそのまま1ページとして引き継ぐ |
| `add_practice` | 実践ページを新規追加（`source_page_no`は元ページ全体） |
| `add_summary` | まとめページを新規追加（`source_page_no`は元ページ全体） |

`merge`/`split_first_half`/`split_second_half`/`carry_over`は、参照する`source_page_no`に対応する元ページが実データに存在しない場合、`apply_restructure_plan`が「restructure_planが不正です」という`ValueError`を送出する（`--plan-output`で出力したプランを手動編集して再利用する場合の安全策）。`add_intro_from_source`/`add_practice`/`add_summary`は教材全体を俯瞰する集約ページのため、元ページが0件でも例外にはならない。

### `layout_instruction`/`source_image`/`source_assets`の引き継ぎ

restructureで生成される各ページの`layout_instruction`/`source_image`/`source_assets`は、`operation`ごとに以下のルールで決まる。

| operation | `layout_instruction` | `source_image` | `source_assets` |
|---|---|---|---|
| `merge` | 統合元ページの`layout_instruction`を` / `で結合（空のものは除く） | 統合元のうち最初に存在するもの | 統合元すべての`source_assets`を重複排除して結合 |
| `split_first_half` / `split_second_half` | 分割元ページの`layout_instruction`をそのまま両方に継承 | 分割元ページの`source_image`をそのまま両方に継承 | 分割元ページの`source_assets`をそのまま両方に継承 |
| `carry_over` | 元ページの`layout_instruction`をそのまま維持 | 元ページの`source_image`をそのまま維持 | 元ページの`source_assets`をそのまま維持 |
| `add_intro_from_source` / `add_practice` / `add_summary` | 元ページからの単純コピーではなく、roleに応じた汎用の指示文を設定 | 空文字（特定の元画像には紐付けない） | 空配列 |

また、`merge`された本文は、各元ページの`title`を`## タイトル`という見出し行として本文中に挿入してから結合する（例: `## AIとは\n(本文)\n\n## ChatGPTとは\n(本文)`）。この見出し行は`parse_body_lines`が「話者無しの1行」として扱うため、`brushup.md`等では箇条書きの1項目として表示される（見出しとしての装飾はされない）。**`body`自体はこの見出し記法を保持したまま`brushup.md`/DOCX/PDFの本文構造化に使う。**

一方で`image_text`/`canva_prompt`/`video_scene`は、Canva・動画向けの自然文として使うため、これらを組み立てる際は`#`/`##`/`###`等のMarkdown見出し記法を取り除いた文字列にする（例: `## サンプル記事 001`は`サンプル記事 001`として扱う）。ただし`#タグ`のような、`#`の直後に空白が無い文字列（ハッシュタグ等）は見出し記法とはみなさず、そのまま保持する。

`scenario`コマンドが生成する`scenario.json`/`scenario.md`/`scene.json`/`voicevox.txt`も、台詞部分は`LessonPage.video_scene`を優先的に使う（`dialogue_lines_for_scenario()`が`video_scene`の「台詞: ...」行を`dialogue_lines_from_video_scene()`で構造化して利用する）。`video_scene`が空の場合のみ、`clean_dialogue_lines()`で`body`からMarkdown見出し記法を除去したテキストを生成してフォールバックする。これにより、`merge`由来の`## タイトル`や後述の`add_practice`/`add_summary`由来の箇条書き行が、動画・音声読み上げ用途の出力にそのまま混入することはない。

## 制作者確認用レポート（review-report）
出力ファイル: 任意のパス（例: `output/review_report.md`）

`review-report`コマンドは、`lesson_pages.json`の各ページについて`role`と`source_page_no`（内部管理情報）を一覧化したMarkdownを出力する。配布用PDF/DOCXには含まれないため、制作者が「どのページがどの元ページ由来か」を確認する用途に使う。

## 教材ブラッシュアップ設計書
出力ファイル: `output/brushup.md`

`lesson_pages.json`の`page_no`/`title`/`body`/`summary`から生成する。

構成:
1. 表紙
2. 全体方針
3. ページ別概要（`summary`。表示時のみMarkdown記法を除去。後述）
4. ページ別本文（`body`を話者ごとに整形。`body`自体の見出し記法は保持する）

## Canva向け設計書
出力ファイル: `output/canva_design.md`

`lesson_pages.json`の`page_no`/`title`/`summary`/`image_text`/`layout_instruction`/`canva_prompt`/`source_image`/`source_assets`から生成する。

構成:
1. 全体デザインルール
2. ページ見出し直下の元画像参照（`source_image`が空でなければ「元画像: {source_image}」、`source_assets`が空でなければ「参考画像: {source_assets}」を明記。Canva設計時にどの元画像・元スライド画像を参照すべきかが分かるようにするため）
3. ページ別概要（`summary`。表示時のみMarkdown記法を除去。後述）
4. ページ別画像内テキスト（`image_text`。表示時のみMarkdown記法を除去。後述）
5. ページ別レイアウト指示（`layout_instruction`。表示時のみMarkdown記法を除去。後述）
6. Canva AI投入用プロンプト（`canva_prompt`。原文のまま、対象外）

### Markdownとして解釈される出力でのMarkdown記法除去（表示時のみ）

`brushup.md`/`canva_design.md`は実際にMarkdownとして解釈されるファイルであり、`layout_instruction`/`summary`/`image_text`のように**行頭から値を丸ごと1行として出力する箇所**は、値が`#`/`-`等で始まっていると本来意図しない見出しや箇条書きとして誤解釈されてしまう。これを防ぐため、以下の3箇所は表示直前にのみ行頭のMarkdown見出し記法（`#`/`##`/`###`）・箇条書き記法（`-`/`*`、直後に空白があるもののみ）を取り除く。

| 出力 | 対象セクション | 対象フィールド | クリーニング関数 |
|---|---|---|---|
| `canva_design.md` | ### レイアウト指示 | `layout_instruction` | `canva_renderer._clean_canva_free_text()` |
| `canva_design.md` | ### 概要 | `summary` | `canva_renderer._clean_canva_free_text()` |
| `canva_design.md` | ### 画像内テキスト | `image_text`（`body`が空で`summary`にフォールバックする場合を含む） | `canva_renderer._clean_canva_free_text()` |
| `brushup.md` | ### 概要 | `summary` | `renderer._clean_summary_for_display()` |

**`lesson_pages.json`側の`summary`/`image_text`/`layout_instruction`自体は変更しない（表示時のみの整形）。** 除去する/しないの判定は共通:

- 除去する: `# 見出し` → `見出し`、`- 箇条書き` → `箇条書き`、`* 箇条書き` → `箇条書き`
- 除去しない: `#AI初心者`のようなハッシュタグ（`#`の直後に空白が無い）、文中の`#`/`-`、URL、ファイル名等

対象外（原文のまま）: `canva_prompt`（「概要: 」「レイアウト: 」等のプレフィックスにより実際の誤解釈リスクが構造的に低いため）、`video_scene`、`scenario`出力（`scene.json`の`visual_prompt`含む）、DOCX、PDF（いずれもMarkdownとして解釈されるファイル形式ではないため実害がない）、WordPress投稿本文（`html.escape()`済みでMarkdown変換もされないため）。`notes`は現状`canva_design.md`のどのセクションにも直接表示されないため対象に含めていない。`brushup.md`の`body`（本文）自体は、restructureのmergeが挿入する`## タイトル`見出しを含めて保持する（本文構造として利用するため）。

## Markdown品質基準
- 見出し階層を崩さない。
- 1ページごとに区切る。
- 話者名を明示する。
- Canvaで作業しやすいように、配置・文字サイズ・強調箇所を具体化する。

## Word教材（DOCX）
出力ファイル: `output/brushup.docx`

`lesson_pages.json`から`brushup.md`と同じ内容（表紙・全体方針・ページ別概要/本文）をWord文書として出力する。

## PDF教材
出力ファイル: `output/brushup.pdf`

`lesson_pages.json`からDOCXと同じ内容をPDF化したもの。日本語はreportlab内蔵のCIDフォント（HeiseiKakuGo-W5）で表示する。

## 動画生成用シナリオ一式
出力先: 任意のディレクトリ（例: `output/scenario/`）に以下4ファイルをまとめて`lesson_pages.json`から生成する。

- `scenario.json`: `body`を話者・台詞に分解し、1行ごとに `page_no` / `order`（通し番号）/ `speaker` / `text` / `source_image` を持つJSON。動画編集ツールへの機械的な受け渡し用。
- `scenario.md`: ページ・話者を明示した人間が読むための台本Markdown。
- `voicevox.txt`: VOICEVOXでの読み上げ用テキスト。`[話者名]` の見出し行と台詞本文を交互に並べる（話者ごとの音声キャラクター選択は人が行う）。
- `scene.json`: Veo等の動画生成AIへの入力を想定したシーン分割JSON。ページ単位を1シーンとし、`layout_instruction`/`notes`から組み立てた`visual_prompt`、`body`から組み立てた`dialogue_text`、構造化済みの`lines`を持つ。

## Canva連携レポート
出力ファイル: 任意のパス（例: `output/canva_sync_report.json`）

`canva-sync`コマンドは、Canva Connect APIでページごとにデザインを作成し、結果を以下の形式で出力する。

```json
{
  "mock": true,
  "designs": [
    {"page_no": 1, "design_id": "mock-design-1", "edit_url": "https://www.canva.com/design/mock-1/edit"}
  ]
}
```

`.env`（`.env.example`参照）に`CANVA_API_KEY`が設定されていない場合は`mock: true`となり、実際のAPI呼び出しを行わずダミーのデザインIDを返す。

## WordPress投稿連携レポート
出力ファイル: 任意のパス（例: `output/wp_publish_report.json`）

`wp-publish`コマンドは、WordPress REST APIで「画像アップロード→記事作成→カテゴリ設定→タグ設定→アイキャッチ設定」を行い、結果を以下の形式で出力する。

```json
{
  "mock": true,
  "post_id": 9006,
  "post_url": "https://example.com/mock-post/9006",
  "featured_media_id": 9001,
  "media_ids": [9001, 9002],
  "category_ids": [9003, 9004],
  "tag_ids": [9005],
  "skipped_images": []
}
```

`.env`（`.env.example`参照）に`WP_URL`/`WP_USERNAME`/`WP_APP_PASSWORD`のいずれかが設定されていない場合は`mock: true`となり、実際のAPI呼び出しを行わない。`--image-dir`で指定したディレクトリに`source_image`のファイルが存在しないページは、実APIモードでは`skipped_images`に記録されアップロードをスキップする（モックモードでは常にアップロード成功として扱う）。
