# 02 アーキテクチャ設計

> 本ドキュメントは現状実装（Phase 1〜9）に合わせて更新済みです。
> `output/`配下のディレクトリ構成（`editable/`/`rendered/`/`canva/`/`exports/`/`compat/`）・editable中間ファイルの扱い・source情報の扱いは、Phase 9.2までに確定したプロジェクト共通設計ルールです。詳細は[`docs/04_output_spec.md`](04_output_spec.md)「プロジェクト標準output構成」、要約は[`CLAUDE_RULES.md`](../CLAUDE_RULES.md)「プロジェクト設計ルール」を参照してください。今後のPhaseでこれらを変更しない前提で作業する場合は、その旨をPhase指示文で明示してください。

## 全体構成

```text
input/                       # (Git管理対象外) 利用者が投入する元ファイル置き場
  source/                     # import-source/build-allの--input。元資料（画像/PDF/PPTX）を置く
  raw_images/                 # wp-publishの--image-dirデフォルト参照先（画像アップロード用）
examples/
  sample_pages.json                 # 基本サンプル入力（pages形式。開発者・自動テスト向け）
  sample_pages_extended.json        # 拡張サンプル入力（3話者会話・未設定項目）
  requirements_ai_instagram.json    # 要件定義サンプル（restructure/generateの--requirements用）
src/
  cli.py                     # CLI入口。check-ocr / import-source / build-all / regenerate / lesson-pages / review-report /
                              # generate / canva / llm-handoff / docx / pdf / scenario / canva-sync / wp-publish の14サブコマンド
  llm_handoff.py               # editable/lesson_pages.jsonから、ChatGPT/Claude等へ手作業で貼り付けるための
                              # Markdownを生成（LLM出力の自動取り込みは行わない。詳細はdocs/11参照）
  import_source.py           # 元資料(画像/PDF/PPTX)からのテキスト・画像自動取り込み（imported_pages.json+画像アセット生成）。
                              # 画像取り込み時、ocr_environment.pyでOCR環境を事前診断（Phase 10.1）
  ocr_environment.py          # OCR実行に必要なtesseract/日本語言語データ/Homebrewの診断（PATHに無いだけか、
                              # そもそも無いかを切り分け）・診断レポート/警告メッセージ生成（Phase 10.1）
  execution_logger.py         # CLI実行ログ(logs/YYYYMMDD_HHMMSS_<command>.log)の生成。開始/終了時刻・
                              # 入出力・OCR要約・警告/エラー・stderr内容・exit_codeを記録（Phase 10.2）
  models.py                  # 入力(pages形式)のデータ構造・バリデーション、requirements.jsonのデータ構造・バリデーション
  lesson_pages.py             # 正データlesson_pages.jsonのデータ構造、3モード(proofread/restructure/generate)の分岐、restructureの再構成プラン生成・適用、派生フィールド算出
  parser.py                  # 入力JSON読み込み（pages形式/lesson_pages形式を自動判定）、requirements.json読み込み
  renderer.py                # lesson_pages.jsonからbrushup.md生成
  canva_renderer.py          # lesson_pages.jsonからcanva_design.md生成（元画像/参考画像の参照表示を含む。オプション出力）
  docx_renderer.py           # lesson_pages.jsonからDOCX生成
  pdf_renderer.py            # lesson_pages.jsonからPDF生成
  image_renderer.py           # lesson_pages.jsonから完成画像(rendered/page_NNN.png)を生成（Phase 9・source_imageがあればそれを採用、無ければ簡易合成）。
                              # 日本語フォント探索(resolve_font_path)・--font-path対応・フォント未検出時の警告を実装（Phase 10）
  pptx_export_renderer.py     # lesson_pages.json+完成画像からPPTX(exports/*.pptx)を生成（Phase 9・1ページ=1スライドの簡易構成）
  scenario_renderer.py       # lesson_pages.jsonから動画生成用シナリオ4形式を生成
  env_config.py               # .env読み込み共通ユーティリティ
  canva_client.py             # 【任意機能・モック雛形】Canva Connect API連携
  wordpress_client.py         # 【任意機能・モック雛形】WordPress REST API連携
scripts/
  run_sample.sh               # サンプル入力から一連の出力を生成するデモスクリプト
  make_release_zip.sh         # レビュー・配布用ZIPを作成（input//output/等を自動除外）
tests/                       # pytestテスト一式
output/                       # (Git管理対象外) 実行結果の生成物置き場。すべて再生成可能な派生物・中間ファイル
  imported_pages.json          # import-sourceが生成する中間ファイル（pages形式互換。手作業で作らない）
  assets/                      # 元画像・元ページ画像・スライド埋め込み画像
  editable/
    lesson_pages.json           # ★正式な編集対象（再生成時にユーザーが編集するのはこのファイルのみ。Phase 9）
  rendered/                     # 完成画像 page_NNN.png（Phase 9）
  canva/
    canva_design.md             # ★正式なCanva指示書（オプション出力。Phase 9）
  exports/
    material.md / material.docx / material.pdf / material.pptx
                                 # ★正式な完成output（Phase 9〜9.2）
  compat/                       # Phase 8互換output。正式output（editable//canva//exports/）との重複を避けるため分離（Phase 9.1〜9.2）
    lesson_pages.json            # editable/lesson_pages.jsonの後方互換コピー
    canva_design.md              # canva/canva_design.mdの後方互換コピー
    brushup.md / brushup.docx / brushup.pdf
                                 # exports/material.*の後方互換コピー（`--no-compat-output`で無効化可）
prompts/                     # OCR・ブラッシュアップ・Canva用プロンプト集（import-sourceのOCRを使わず人手でAIに投入する運用向け）
```

## データ処理フロー

```text
元資料（画像/PDF/PPTX） in input/source/
        │
        ▼ import-source（build-allが内部で自動実行）
output/imported_pages.json (pages形式互換) + output/assets/
        │
        ├─────────────────────────────────────────────┐
source_pages.json (pages形式・開発者向け直接指定も可)  ┤
requirements.json (任意/必須)                          ┘
                                ├─→ lesson-pages --mode proofread|restructure ─┐
requirements.json (必須)  ──→ lesson-pages --mode generate ───────────────────┤
                                                                               ▼
                                                          output/editable/lesson_pages.json (正データ・再生成用の編集対象)
                                                                               │
                              ┌────────────────┬────────────────┬─────────────┼─────────────┬───────────────┐
                              ▼                ▼                ▼             ▼             ▼               ▼
                     rendered/page_NNN.png  exports/*.pdf  exports/*.pptx  exports/*.docx  exports/*.md  canva/canva_design.md
                        (--output-format image)              (pptx)          (docx)          (md)        (canva。オプション出力)
```

1. （元資料がある場合）`import-source`が画像/PDF/PPTXからテキスト・画像を自動取り込み、`imported_pages.json`（pages形式互換）+`output/assets/`を生成する（`src/import_source.py`）。`build-all`はこのステップを内部で自動実行する。
2. `pages`形式JSON（`imported_pages.json`または`docs/03_data_format.md`のJSON）またはlesson_pages形式JSONを読み込む（`parser.py`）。
3. `--mode`に応じて`lesson_pages.py`が正データを構築する。
   - `proofread`: 元ページを1:1で引き継ぎ、`metadata.mode=proofread`を付与。`source_image`/`source_assets`も引き継ぐ。
   - `restructure`: 元ページから中間表現（`SourcePageSummary`）を抽出し、再構成プラン（`build_restructure_plan`）→ 本文組み立て（`apply_restructure_plan`）の2段階でページを再構成。`source_image`/`source_assets`もoperationごとのルールで引き継ぐ（`docs/04_output_spec.md`参照）。
   - `generate`: `requirements.json`のみからルールベースで教材のたたき台を生成（元資料が無いため`source_image`/`source_assets`は空のまま）。
4. `lesson_pages.json`として書き出す（正データ）。`build-all`はこれを`output/editable/lesson_pages.json`として書き出す（**再生成時にユーザーが編集する対象**）。`--no-compat-output`が指定されていなければ、同内容を`output/compat/lesson_pages.json`にも書き出す（Phase 8互換。`output_dir`直下には重複させない）。
5. `--output-format`（既定`same`＝入力の性質に合わせる）に応じて、`image_renderer.py`/`pdf_renderer.py`/`pptx_export_renderer.py`/`docx_renderer.py`/`renderer.py`/`canva_renderer.py`のいずれかが完成outputを生成する。`build-all`はこのステップも内部で自動実行する。
6. ユーザーが`output/editable/lesson_pages.json`を編集した後、`regenerate`コマンドで手順5をやり直せる（完成画像・PDF等を直接編集するのではなく、この中間ファイルを編集して再生成する）。

## データモデル

### `src/models.py`（入力=pages形式、requirements.json）
- `DialogueLine`: `speaker` / `text`
- `CanvaInfo`: `layout_type` / `main_visual` / `notes`
- `Page`: `page_no` / `source_image` / `title` / `summary` / `lines: list[DialogueLine]` / `improvement_points: list[str]` / `canva: CanvaInfo` / `source_assets: list[str]`（`source_image`以外の関連画像。通常は空配列）
- `Project`: `project_title` / `target_reader` / `pages: list[Page]`
- `Requirements`: `theme` / `target_audience` / `goal` / `reader_problem` / `promised_value` / `tone` / `output_style` / `page_count: int | None`（**現状未使用。将来拡張用**） / `must_include: list[str]` / `must_not_include: list[str]`

### `src/import_source.py`（元資料からのpages形式互換JSON生成）
- 関数群のみでデータクラスは持たない。`import_images`/`import_pdf`/`import_pptx`/`import_source`が、いずれも`models.py`の`Page`と同じスキーマの辞書（`pages`形式互換）を返す。
- `import_images`は、OCR前に`ocr_environment.get_ocr_environment_status()`を1回呼び出し、環境が整っていない場合は標準エラー出力に警告を表示したうえで処理を継続する。全ページのOCR結果が空だった場合も追加の警告を表示する（Phase 10.1）。

### `src/ocr_environment.py`（OCR環境診断）
- 関数群のみ。`check_tesseract_environment`/`check_homebrew_environment`/`get_ocr_environment_status`がtesseract/brewのPATH・既知パス・バージョン・利用可能言語を確認する。`resolve_ocr_lang`がOCRに使う`--lang`値（`jpn+eng`/`jpn`/`eng`）を決める。`format_precondition_warning`/`format_all_pages_empty_warning`/`format_environment_report`が、`import_source.py`・`cli.py`（`check-ocr`コマンド）向けのメッセージを組み立てる。

### `src/lesson_pages.py`（正データ=lesson_pages形式）
- `LessonMetadata`: `project_title` / `mode` / `source_policy` / `target_audience` / `tone` / `generated_at` / `requirements_source`
- `LessonPage`: `page_no` / `title` / `body` / `summary` / `image_text` / `layout_instruction` / `canva_prompt` / `video_scene` / `source_image` / `notes` / `source_page_no: list[int]` / `role: str` / `source_assets: list[str]`
- `LessonDocument`: `metadata: LessonMetadata` / `pages: list[LessonPage]`（`project_title`/`target_reader`は`metadata`への後方互換プロパティとして提供）
- `SourcePageSummary`: `restructure`が元ページから抽出する中間表現。`source_page_no` / `title` / `summary` / `key_points: list[str]` / `raw_text` / `layout_instruction` / `source_image` / `source_assets: list[str]`

> 過去のドキュメントに記載されていた`CanvaLayout`というクラスは実装に存在しない。Canva関連の構造体は`CanvaInfo`（models.py、入力側）であり、`lesson_pages.json`側では`layout_instruction`/`canva_prompt`という文字列フィールドとして保持する。

## 出力形式
Markdown（教材ブラッシュアップ設計書・`canva_design.md`・`review_report.md`）、DOCX、PDF（reportlab、日本語はCIDフォント`HeiseiKakuGo-W5`）、PPTX（python-pptx）、画像（PNG。Pillow）、JSON（`lesson_pages.json`/`restructure_plan.json`/`scenario.json`/`scene.json`/`canva_sync_report.json`/`wp_publish_report.json`）、プレーンテキスト（`voicevox.txt`）に対応済み。詳細は[`docs/04_output_spec.md`](04_output_spec.md)を参照。

## 任意機能（Canva/WordPress連携）

`canva_client.py`（Canva Connect API）・`wordpress_client.py`（WordPress REST API）は、いずれも**任意機能・モック付き連携雛形**である。

- `.env`（`env_config.py`が読み込み）に認証情報が無ければ、`requests`を一切呼び出さずモックのID・URLを返す（`is_mock=True`）。
- 必須機能（`import-source`/`build-all`/`regenerate`/`lesson-pages`/`review-report`/`generate`/`canva`/`docx`/`pdf`/`scenario`）は、Canva/WordPressの設定状態に一切依存しない。
- Canva側は`CANVA_API_KEY`を単純な`Authorization: Bearer`ヘッダーとして送る簡易実装であり、実際のCanva Connect APIが要求するOAuth2/PKCEには未対応。WordPress側もApplication Password方式の実装はあるが、実サイトでの疎通確認は未実施。
- 本番相当のAPI疎通確認・OAuth2/PKCE対応は今後の課題（[`docs/99_implementation_review_brief.md`](99_implementation_review_brief.md)参照）。
