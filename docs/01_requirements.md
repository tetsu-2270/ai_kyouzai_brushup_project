# 01 要件定義

> 本ドキュメントは現状実装（Phase 1〜8）に合わせて更新済みです。設計の一次情報は
> [`docs/00_redesign_v2.md`](00_redesign_v2.md) を参照してください。本ドキュメントはその要約・要件整理です。
> Phase 8で追加した元資料自動取り込み（`import-source`/`build-all`）の詳細は[`docs/04_output_spec.md`](04_output_spec.md)・[`docs/08_user_acceptance_test.md`](08_user_acceptance_test.md)を参照してください。

## システム名
AI教材ブラッシュアップシステム

## 背景
既存教材は画像・会話・状況説明・補足情報が混在しており、そのままでは教材化やCanva再現が難しい。ページ単位で情報を整理し、教材として読みやすく、視覚的に再構成できる形にする。

さらに、用途は「既存教材を整える」だけでなく、「既存教材を素材に作り直す」「要件だけから新規に作る」の3種類に広がっているため、`proofread` / `restructure` / `generate` の3モードに対応する。

## 目的
- 画像教材の内容をページ単位で整理する。
- 状況説明者、主人公、その他登場人物ごとに台詞を分ける。
- 教材として分かりやすい表現にブラッシュアップする（`proofread`）。
- 元教材を素材に、ページ統合・分割・導入/実践/まとめ追加などで教材として再構成する（`restructure`）。
- 元教材なしで、要件定義から教材のたたき台を新規生成する（`generate`）。
- Canvaで再現できるレイアウト設計書を出力する。
- Word/PDF/動画生成用シナリオなど、複数の派生形式で出力する。
- Claude Codeで実装・改修しやすい構成にする。

## 正データと3モード（重要）

**`lesson_pages.json` がこのシステムの正データ（Single Source of Truth）です。** `brushup.md` / `canva_design.md` / DOCX / PDF / 動画生成用シナリオは、すべて`lesson_pages.json`から派生生成される出力物であり、これらを直接編集して正データとして扱ってはいけません。

`lesson_pages.json`は`lesson-pages`コマンドの`--mode`で以下の3通りの作り方を選べる。

| mode | 方針 | `--input` | `--requirements` |
|---|---|---|---|
| `proofread` | 元ファイルを神として、内容・構成・ページ順を維持したまま表現を整える | 必須 | 任意 |
| `restructure` | 元ファイルを素材として、主旨は維持しつつルールベースで統合・分割・導入/実践/まとめ追加を行う | 必須 | 任意（対象者・トーンの反映に推奨） |
| `generate` | 元ファイルなしで、要件定義からルールベースで教材のたたき台を新規生成する | 不要 | 必須 |

3モードの詳細（再構成アルゴリズム・`restructure_plan`の形式等）は[`docs/00_redesign_v2.md`](00_redesign_v2.md)・[`docs/04_output_spec.md`](04_output_spec.md)を参照。

### `source_page_no`は内部メタデータ

各ページが持つ`source_page_no`（元ページ番号の配列）・`role`（`intro`/`explanation`/`practice`/`summary`等）は、**再構成の過程を追跡するための内部管理情報**であり、`brushup.md` / `canva_design.md` / DOCX / PDF / 動画生成用シナリオといった利用者向け・配布用の出力には一切表示しない。制作者がどのページがどの元ページ由来かを確認したい場合は、`review-report`コマンドが出力する`review_report.md`（制作者向けの内部確認用ファイル）を使う。

## 実装済みCLIコマンド

すべて `python3 -m src.cli <サブコマンド>` で実行する。**作成者向けの主導線は`build-all`（元資料がある場合）または`lesson-pages --mode generate`（元資料が無い新規構築の場合）。** `import-source`/`lesson-pages`/`generate`等の個別サブコマンドは、`build-all`が内部で使う部品であり、開発者・拡張作業や途中結果の手直し用途に使う。

| サブコマンド | 役割 | 区分 |
|---|---|---|
| `import-source` | 元資料（画像/PDF/PPTX）からテキスト・画像を自動取り込み、`imported_pages.json`（pages形式互換）+画像アセットを生成 | 必須機能 |
| `build-all` | `import-source`→`lesson-pages`→`generate`/`canva`/`docx`/`pdf`/`scenario`/`review-report`を一括実行（`--mode proofread\|restructure`、`--requirements`）。作成者向けの主導線 | 必須機能 |
| `lesson-pages` | 正データ`lesson_pages.json`を生成（`--mode proofread\|restructure\|generate`、`--requirements`、`--plan-output`） | 必須機能 |
| `review-report` | `lesson_pages.json`の`role`/`source_page_no`を制作者確認用Markdownに整理 | 必須機能（制作者向け補助） |
| `generate` | `lesson_pages.json`から教材ブラッシュアップ設計書(`brushup.md`)を生成 | 必須機能 |
| `canva` | `lesson_pages.json`からCanva向けレイアウト設計書(`canva_design.md`)を生成 | 必須機能 |
| `docx` | `lesson_pages.json`からWord教材(DOCX)を生成 | 必須機能 |
| `pdf` | `lesson_pages.json`からPDF教材を生成 | 必須機能 |
| `scenario` | `lesson_pages.json`から動画生成用シナリオ4形式(JSON/Markdown/VOICEVOX/シーン分割JSON)を生成 | 必須機能 |
| `canva-sync` | Canva Connect APIでページごとのデザインを作成 | 任意機能（`CANVA_API_KEY`未設定時はモック動作） |
| `wp-publish` | WordPressへ記事を作成（画像アップロード〜アイキャッチ設定） | 任意機能（認証情報未設定時はモック動作） |

「必須機能」はCanva/WordPressの設定状態に一切依存せず常に動作する。「任意機能」は`.env`未設定でもエラーにならずモック動作に切り替わる（詳細はREADME「必須機能・任意機能」節）。

## 入力

作成者向け主導線（`build-all`）の場合:
- 元資料そのもの: 画像（`.png`/`.jpg`/`.jpeg`/`.webp`）・PDF（`.pdf`）・PPTX（`.pptx`）。`import-source`が実際にファイルを読み込み、テキスト抽出（OCR/PDFテキスト抽出/PPTXテキスト抽出）と画像アセットの保存（`output/assets/`へのコピー・ページ画像化・埋め込み画像抽出）を行う
- （`restructure`で使う、任意）要件定義`requirements.json`（下記）

開発者向け経路（`pages`形式JSONを直接`--input`に渡す場合）:
- 画像から文字起こししたテキスト（`pages`形式JSONの`lines`）
- 元教材のページ画像への参照（`source_image`。ファイル名を参照するのみで、画像自体の読み込み・埋め込みはこの経路では行わない。画像自体の読み込みが必要な場合は`import-source`/`build-all`を使う）
- ページ番号
- 登場人物情報（`speaker`）
- 教材の目的・対象読者（`project_title`/`target_reader`、または`requirements.json`の`target_audience`等）
- （`restructure`/`generate`で使う）要件定義`requirements.json`（`theme`/`target_audience`/`goal`/`reader_problem`/`promised_value`/`tone`/`page_count`/`output_style`/`must_include`/`must_not_include`）

## 出力
- 元資料からの自動取り込み中間ファイル（`build-all`/`import-source`使用時のみ）: `imported_pages.json`、画像アセット一式（`output/assets/`）
- 正データ: `lesson_pages.json`
- 教材ブラッシュアップ設計書: `brushup.md`
- Canva向けレイアウト設計書: `canva_design.md`（元資料由来のページは元画像・参考画像への参照を含む）
- Word教材: `.docx`
- PDF教材: `.pdf`
- 動画生成用シナリオ一式: `scenario.json` / `scenario.md` / `voicevox.txt` / `scene.json`
- （`restructure`のみ、任意）再構成プラン: `restructure_plan.json`
- 制作者確認用レポート: `review_report.md`（`role`/`source_page_no`の一覧。配布物には含めない）
- （任意機能）Canva連携レポート・WordPress投稿連携レポート

出力形式の詳細は[`docs/04_output_spec.md`](04_output_spec.md)を参照。

## `input/` / `output/` の扱い

`input/`（利用者が投入する元ファイル置き場）と`output/`（実行結果の生成物置き場）は、利用者固有データの混入防止のため**Git管理・配布ZIPの対象外**とする（`.gitignore`で除外、`scripts/make_release_zip.sh`でも除外）。動作確認用のサンプルは`examples/`に置く。詳細はREADME「`input/`と`output/`の扱い」節を参照。

## 対象外（現時点で未実装・意図的に対象外のもの）
- OCR精度の高度化（`import-source`が`pytesseract`による基本的なOCRを実装済みだが、これは「画像を入力として扱える」ことの実現が目的であり、精度向上そのものは対象外。OCR自体を使わず`prompts/ocr_transcription_prompt.md`を人手でAIに投入する運用も引き続き可能）
- DOCX形式の元資料取り込み（画像/PDF/PPTXのみ対応。`.doc`/`.docx`からの取り込みは未実装）
- PPTXのスライド全体を1枚の画像としてレンダリングする機能（外部レンダラーが必要なため対象外。スライド内の埋め込み画像の保持のみ対応）
- `.ppt`（PowerPoint旧形式）の取り込み（`.pptx`への変換が必要）
- Canva API・WordPress投稿の本番疎通（OAuth2/PKCE対応やApplication Passwordでの実サイト確認は未実施。モック付き連携雛形の段階）
- `restructure`/`generate`における外部LLM連携（現状はルールベースのみ。将来拡張候補として[`docs/00_redesign_v2.md`](00_redesign_v2.md)14節に記載）
- `requirements.json`の`page_count`の実反映（現状はバリデーションのみ行い、`restructure`/`generate`のページ数制御には使用しない。将来拡張用のフィールド）
- introの`source_page_no`拡大・3ページ以上の連鎖merge・`--plan-input`（Phase 7調査で候補に挙がったが未着手。詳細は`docs/05_implementation_tasks.md`Phase 7参照）
