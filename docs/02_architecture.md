# 02 アーキテクチャ設計

> 本ドキュメントは現状実装（Phase 1〜9）に合わせて更新済みです。
> `output/`配下のディレクトリ構成（`editable/`/`rendered/`/`canva/`/`exports/`/`compat/`）・editable中間ファイルの扱い・source情報の扱いは、Phase 9.2までに確定したプロジェクト共通設計ルールです。詳細は[`docs/04_output_spec.md`](04_output_spec.md)「プロジェクト標準output構成」、要約は[`PROJECT_RULES.md`](../PROJECT_RULES.md)「4. output構成」を参照してください。今後のPhaseでこれらを変更しない前提で作業する場合は、その旨をPhase指示文で明示してください。

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
                              # generate / canva / ocr-check / apply-ocr-corrections / approve-ocr-candidates /
                              # llm-handoff / apply-llm-suggestions / edit-plan-template / docx / pdf / scenario /
                              # canva-sync / wp-publish の19サブコマンド
  ocr_check.py                 # lesson_pages.jsonのOCR品質（誤認識・文字化け・不自然な表記）を検出し、
                              # レポート(ocr_check_report.md)と補正候補JSON(ocr_correction_candidates.json)を
                              # 生成。自動修正・自動反映は行わない（詳細はdocs/13参照）
  ocr_patterns.py               # OCR崩れ検出・修正候補生成に使う辞書（誤認識辞書・削除候補・推定修正候補・
                              # 元画像確認必須候補・許可語）を管理。組み込みデフォルト＋config/ocr_patterns.json
                              # （外部辞書、無くても動く）を安全にマージする（詳細はdocs/13参照）
  ocr_apply.py                  # ocr_correction_candidates.jsonのうちstatus: approvedの候補だけを
                              # lesson_pages.jsonへ反映。元ファイルは上書きしない・自動承認はしない
                              # （詳細はdocs/14参照）
  ocr_approval.py               # ocr_correction_candidates.jsonのうち条件に一致する明確な候補
                              # （既定: 高重要度・高確信度のreplace候補）だけをstatus: approvedに一括変更。
                              # editable/lesson_pages.jsonへの反映は行わない（詳細はdocs/14参照）
  llm_handoff.py               # editable/lesson_pages.jsonから、ChatGPT/Claude等へ手作業で貼り付けるための
                              # Markdownを生成（LLM出力の自動取り込みは行わない。詳細はdocs/11参照）
  llm_suggestions.py            # ChatGPT/Claude等の改善案Markdownを読み込み、ページ別の改善候補
                              # （llm_suggestion_candidates.json/llm_suggestion_report.md）に構造化。
                              # lesson_pages.jsonへの自動反映は行わない（詳細はdocs/15参照）
  edit_plan.py                 # LLM改善案の採用判断シート（edit_plan_template.md）を生成。LLM回答を
                              # そのまま反映せず、採用判断を整理してから手編集する運用を支援（詳細はdocs/12参照）
  import_source.py           # 元資料(画像/PDF/PPTX)からのテキスト・画像自動取り込み（imported_pages.json+画像アセット生成）。
                              # 画像取り込み時、ocr_environment.pyでOCR環境を事前診断（Phase 10.1）。
                              # ファイル名は数字部分を数値として比較する自然順ソートで並べる（例: "- 2" が "- 10" より前）。
                              # 画像1枚のOCR自体はocr_engine.py（複数前処理・複数PSM・品質スコア）に委譲する
  ocr_engine.py                # 教材画像向けOCR品質改善エンジン。画像前処理（拡大・グレースケール・
                              # コントラスト補正・二値化）の複数候補生成、複数PSM(6/11)でのOCR実行
                              # （信頼度・座標付き）、品質スコアによる最良候補選択、低品質時のみの
                              # 追加前処理・領域分割（タイトル帯/本文帯・左右カラム）再試行、ノイズ除去・
                              # config/ocr_patterns.jsonの高確信度置換・波ダッシュ誤認識補正等の後処理を行う。
                              # 画像から確定できない文章の推測生成はしない（詳細はdocs/13参照）
  apple_vision_ocr.py          # (macOS専用・任意) tools/apple_vision_ocr/のSwift製ヘルパーを安全に呼び出す
                              # アダプター。shell=True不使用。失敗時は例外を投げず available=False で
                              # 安全にフォールバックする
  ocr_compare.py                # Tesseract/Apple Vision結果の比較（正規化・類似度・行数差・読み順差・
                              # ノイズ差・重要語句差・needs_review判定）。純粋関数群
  ocr_comparison.py             # ページごとの比較オーケストレーション + output/ocr_comparison/への保存 +
                              # レビュー用review.html生成（--ocr-engine tesseract+vision指定時のみ）
  output_clean.py             # build-all --clean-output用。output-dir配下の既知の生成物（assets/・editable/・
                              # compat/・scenario/・rendered/・exports/・canva/・imported_pages.json・
                              # review_report.md・ocr_check_report.md・ocr_correction_candidates.json・
                              # llm_handoff.md、およびPhase 8時点の旧仕様output lesson_pages.json・
                              # canva_design.md・brushup.md・brushup.docx・brushup.pdf）だけを安全に削除して
                              # から再生成する。output-dirがプロジェクトディレクトリ配下または/tmp配下である
                              # こと等を検証し、条件を満たさない場合は削除しない
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
  build_apple_vision_ocr.sh   # (macOS専用・任意) tools/apple_vision_ocr/をビルドする
tools/
  apple_vision_ocr/            # (Git管理対象。.build/のみ対象外) Apple Vision OCRヘルパー（SwiftPM）
    Package.swift
    Sources/AppleVisionOCRCore/   # Vision呼び出し・引数解析・JSON組み立てのロジック本体
    Sources/apple-vision-ocr/     # 薄い実行ファイル本体
    Sources/AppleVisionOCRSelfTests/  # Xcode本体が無い環境向けの自作テストハーネス
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
- `_try_ocr(image_path, ocr_status) -> str`は、画像1枚のOCRを`ocr_engine.run_multi_ocr()`へ委譲する薄いラッパー（シグネチャ・「OCR不能なら空文字を返す」という既存動作は維持）。実行後の診断情報（選択PSM・前処理・品質スコア・再試行有無等）は、モジュールレベルの`_last_ocr_diagnostics`（副チャンネル）から取得できる。`import_images(..., diagnostics_sink=[])`を指定すると、ページ番号付きでその診断情報を収集でき、`cli.py`の`run_import_source(..., logger=...)`がこれを実行ログの`OCR_QUALITY`セクションへ記録する（`imported_pages.json`のスキーマ自体には影響しない）。

### `src/ocr_environment.py`（OCR環境診断）
- 関数群のみ。`check_tesseract_environment`/`check_homebrew_environment`/`get_ocr_environment_status`がtesseract/brewのPATH・既知パス・バージョン・利用可能言語を確認する。`resolve_ocr_lang`がOCRに使う`--lang`値（`jpn+eng`/`jpn`/`eng`）を決める。`format_precondition_warning`/`format_all_pages_empty_warning`/`format_environment_report`が、`import_source.py`・`cli.py`（`check-ocr`コマンド）向けのメッセージを組み立てる。

### `src/ocr_engine.py`（教材画像向けOCR品質改善エンジン。今回追加）
- `generate_preprocess_variants(image)`: 元画像を変更せず、"original"（無加工）・"enhanced"（拡大+グレースケール+コントラスト補正+軽いシャープ化）・"binarized"（"enhanced"にしきい値二値化）の3候補を生成する。
- `run_ocr_pass(image, lang, psm, tesseract_cmd, ...)`: `pytesseract.image_to_data()`で認識文字列・信頼度・座標・ブロック/段落/行番号を取得する（`image_to_string`は使わない）。
- `words_to_text(words)`: block/par/lineでまとめた行を左から右の順に結合してテキストへ復元する。日本語文字同士の間には半角スペースを入れない（tesseractが1文字ずつ別トークンで返すため）。段組み分割後の結合にも使う。
- `score_candidate(candidate, allowed_words, high_confidence_dict)`: 平均信頼度・日本語文字率・低信頼度トークン比率・有効文字数・英字ノイズ数（`garbled_latin_token_count`）・OCR誤認識辞書一致数（`dictionary_hit_count`）を組み合わせた品質スコア。単純な文字数最大化ではノイズの多い結果が勝つため、ノイズ・辞書一致は減点要素にしている。
- `run_multi_ocr(image_path, ocr_status, lang, tesseract_cmd, patterns=None)`: 最上位のオーケストレーション。"original"/"enhanced" × PSM(6/11)の4候補を実行し、品質スコアが`_LOW_QUALITY_SCORE_THRESHOLD`未満の場合のみ、二値化・タイトル帯/本文帯分割・左右カラム分割による追加候補（計5回）を試して再スコアリングする。最良候補を`postprocess_candidate()`（低信頼度ノイズ除去・不自然な先頭/末尾行の除去・`config/ocr_patterns.json`の高確信度置換・波ダッシュ誤認識`(\d)て(\d)`→`(\d)〜(\d)`補正・空白整理）にかけたテキストと、`OcrDiagnostics`（選択PSM・前処理・品質スコア・再試行有無・所要時間等）を返す。
- 特定画像の座標・文字列はハードコードしない（前処理・領域分割は画像サイズに対する比率、ノイズ判定は長さ・文字種・信頼度のパターンのみで判定）。辞書による自動補正は`config/ocr_patterns.json`の`high_confidence_replacements`に限定し、それ以外のOCR崩れは引き続き`ocr-check`以降の人間承認フロー（`docs/13`〜`docs/14`）で扱う。

### `src/apple_vision_ocr.py` / `src/ocr_compare.py` / `src/ocr_comparison.py`（Apple Vision OCR比較。macOS専用・任意・今回追加）
- `src/apple_vision_ocr.py`: `tools/apple_vision_ocr/`のSwift製ローカルヘルパー（`apple-vision-ocr`。`scripts/build_apple_vision_ocr.sh`でビルド）を`subprocess`で安全に呼び出す薄いアダプター。`shell=True`は使わず、画像パスは常に引数配列として渡す。`is_macos()`/`find_apple_vision_helper_path()`/`check_apple_vision_availability()`でビルド済みかを事前確認できる。`run_apple_vision_ocr(image_path, ...)`は例外を投げず、macOS以外・ヘルパー未ビルド・タイムアウト・不正なJSON出力等のあらゆる失敗時に`AppleVisionResult(available=False, ...)`を返す（呼び出し側は`try/except`無しで安全にフォールバックできる）。
- `src/ocr_compare.py`: Tesseract/Apple Vision2つのOCR結果を比較する純粋関数群。`normalize_for_comparison()`は改行差・連続空白（半角/全角）・連続空行のみを正規化し、漢字・句読点・長音・引用符・数字は変更しない。`compute_comparison_metrics()`が全文類似度・タイトル類似度・行数差・有効文字数差・一方にしか存在しない行・読み順差・ノイズトークン差・重要語句差（漢字を含む置換/削除/追加箇所）をまとめ、`evaluate_needs_review()`がテスト可能なモジュール定数の閾値に基づき`needs_review`可否と理由を返す。
- `src/ocr_comparison.py`: ページごとの比較を実行するオーケストレーション（`run_ocr_comparison_for_pages()`。Tesseractは`imported_pages`の既存結果を再利用し再実行しない）と、`output/ocr_comparison/`（`summary.json`/`summary.md`/`pages/page_NNN.json`/`review.html`）への保存（`write_comparison_outputs()`）を担当する。Apple Visionが利用できない場合はエンジン不一致を理由に全ページを`needs_review`にしない（既存のTesseract自身の`quality`判定のみを使う）。`editable/lesson_pages.json`は一切変更しない。
- `tools/apple_vision_ocr/`: SwiftPMパッケージ。`AppleVisionOCRCore`（`VNRecognizeTextRequest`呼び出し・引数解析・JSON組み立てのロジック本体）と、薄い実行ファイル`apple-vision-ocr`で構成する。この開発環境はXcode本体（XCTest/Swift Testing）が無くCommand Line Toolsのみのため、テストはFoundationのみに依存する自作ハーネス（`AppleVisionOCRSelfTests`。`swift run AppleVisionOCRSelfTests`で実行）を使う。詳細は[`docs/13_ocr_quality_check_workflow.md`](13_ocr_quality_check_workflow.md)「17. Apple Vision OCRとの比較」参照。

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
