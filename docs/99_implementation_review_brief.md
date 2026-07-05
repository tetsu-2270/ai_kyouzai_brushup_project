# 99 実装レビュー提出用ブリーフ（Phase 1〜4完了版・GPTレビュー対応版）

> **本ドキュメントはPhase 1〜4完了時点（2026-07-04）のスナップショットであり、以降更新していません。** テスト件数・CLIサブコマンド数などの数値は当時のものです。Phase 5（3モード対応）・Phase 6（restructure本格化・input/output除外）以降の現行仕様は[`docs/01_requirements.md`](01_requirements.md)・[`docs/02_architecture.md`](02_architecture.md)・[`docs/04_output_spec.md`](04_output_spec.md)・[`docs/05_implementation_tasks.md`](05_implementation_tasks.md)を正としてください。本ドキュメントはCanva/WordPress連携の既知の制約など、当時のレビュー経緯の記録として保存しています。
>
> **`99_*`ドキュメントの運用ルール:**
> - `99_*`は実装状態をある一時点でレビュー・スナップショットしたものであり、現行仕様の正ではない。
> - 記載されている数値（テスト件数・実装フェーズ・CLIサブコマンド数など）は作成時点の情報であり、常に最新とは限らない。
> - 現行仕様は`docs/01`〜`docs/04`、実装状況は`README.md`「実装状況」節・`python3 -m pytest -q`の実行結果・実コード（`src/`）を正とする。
> - 新しいレビューを作成する場合は、既存の`99_*`ファイルを上書きせず、日付またはバージョン付きの別ファイル（例: `docs/99_review_2026-08.md`）として追加する。

本ドキュメントは、Phase 1〜4の実装内容をレビュー提出用に整理したものです。記載内容は実際のファイル・コード・テスト実行結果に基づいています（2026-07-04時点）。

## 0. 改訂履歴

- **v1（コミット `2ce480e` 時点）**: Phase1〜4完了版として初版作成。
- **v2**: GPTによるレビュー結果を受けて以下を修正。
  1. `.pytest_cache/`・`__pycache__/`・`tests/__pycache__/`・`src/ai_kyouzai_brushup.egg-info/`を実ディスクからも削除し、配布ZIP・Git管理対象に含まれないことを再確認
  2. READMEのPhase4表記を「本番連携完了」と誤読されないよう「モック付き連携雛形。実API疎通は未実施」に修正
  3. Canva連携がOAuth2/PKCE未対応（簡易Bearer実装）であることをREADME・本ドキュメントに明記
  4. WordPress連携が実サイト疎通未実施であることをREADME・本ドキュメントに明記
  5. PDF出力の日本語表示を目視確認する手順をREADMEに追記
  6. 入力バリデーションを追加（`lines`の型・`speaker`/`text`の型・`improvement_points`各要素の型・`source_image`の絶対パス/親ディレクトリ参照禁止・`wp-publish`の`status`許可値チェック）
- **v3（本版）**: 方針整理として、Canva API連携・WordPress投稿連携を**任意機能**として明確に位置づけ。以下を対応。
  1. Canva/WordPressの環境変数（`CANVA_API_KEY`/`WP_URL`/`WP_USERNAME`/`WP_APP_PASSWORD`）が未設定でも、教材ブラッシュアップMarkdown・Canva向けレイアウト設計書・DOCX・PDF・動画シナリオ出力（必須機能）が正常に動作することをテストで明示的に検証
  2. `canva-sync`/`wp-publish`が未設定時にモック動作へ切り替わる際、標準エラー出力への通知メッセージと、レポートJSONへの`note`フィールドを追加し「未設定のためモック動作」であることを明示
  3. READMEに「必須機能・任意機能」の対比表を新設し、Canva/WordPress連携が任意機能であることを明記

## 1. 概要

- 対象コミット範囲: `354ce7b`（プロジェクト一式初回コミット）〜本レビュー対応コミットまで
- `docs/05_implementation_tasks.md`: Phase 1〜4 全項目チェック済み
- テスト: `pytest` 56件、全てpass（テストファイル11本）
- Python実行環境: 3.11以上が必須（実行確認は3.14.6で実施）
- **必須機能（Canva/WordPressの設定有無に関わらず常に動作）**: `generate`（教材ブラッシュアップMarkdown）/ `canva`（Canva向けレイアウト設計書Markdown）/ `docx`（Word教材）/ `pdf`（PDF教材）/ `scenario`（動画生成用シナリオ4形式）
- **任意機能（`.env`に認証情報がある場合のみ実際のAPIを呼び出す。無くても必須機能に影響しない）**: `canva-sync`（Canva API連携）/ `wp-publish`（WordPress投稿連携）

## 2. Phase別実装サマリ

### Phase 1: CLI最小実装
- `src/parser.py`: JSON読み込み。ファイル不在・UTF-8不正・JSON構文不正を検出し、原因が分かる`FileNotFoundError`/`ValueError`を送出
- `src/models.py`: `page_no`必須・整数チェック・重複検出、`pages`/`lines`/`canva`の型チェックと想定外キー検出
- `page_no`昇順ソート
- `src/renderer.py` / `src/canva_renderer.py`: `brushup.md` / `canva_design.md` 生成（既存実装を踏襲、テストで動作確認）

### Phase 2: 品質向上
- `src/cli.py`: `FileNotFoundError`/`ValueError`をmain()で捕捉し、トレースバックなしでエラーメッセージ＋終了コード1
- `examples/sample_pages_extended.json`: 3話者会話ページ・未設定項目ページを含む拡張サンプルを追加
- pytestテストを`tests/test_parser.py`・`tests/test_validation.py`・`tests/test_models.py`・`tests/test_cli.py`に整備
- README.mdを実装状態に合わせて更新

### Phase 3: AI連携
- `prompts/ocr_transcription_prompt.md`: 出力に`source_image`を追加、`unreadable_parts`は確認用フィールドでpages JSONには含めないことを明記
- `prompts/brushup_prompt.md`: 出力項目を`summary`/`improvement_points`に対応付け
- `prompts/canva_design_prompt.md`: 出力先を`canva.layout_type`/`main_visual`/`notes`に整理し、「Canva AI投入用プロンプト」の自動生成との役割重複を解消
- `docs/07_api_integration_design.md`: 将来のAPI連携（OCR/ブラッシュアップ/Canva設計の自動化）に向けた設計メモ。実装は行っていない（意図的）

### Phase 4: 将来拡張
- ① DOCX出力（`src/docx_renderer.py`）— 必須機能
- ② PDF出力（`src/pdf_renderer.py`）— 必須機能
- ③ 動画生成用シナリオ出力（`src/scenario_renderer.py`）— 必須機能
- ④ Canva API連携（`src/canva_client.py`、`src/env_config.py`）— **任意機能**（未設定でも①〜③・既存の`generate`/`canva`には影響しない）
- ⑤ WordPress投稿連携（`src/wordpress_client.py`）— **任意機能**（未設定でも①〜③・既存の`generate`/`canva`には影響しない）

詳細な実装方式は8節を参照。

## 3. 当初設計から変更した点

| # | 変更内容 | 理由・経緯 |
|---|---|---|
| 1 | Python実行要件が3.11以上であることが判明 | 既存`src/`コードが`str \| Path`等のPEP604構文を使用しており、当初のCLAUDE.mdには明記がなかった。コードは変更せず、pyenvで3.11以上（3.14.6）を用意する運用で解決 |
| 2 | CLIサブコマンドが2種類→7種類に増加 | `docs/02_architecture.md`はgenerate/canva相当の2出力のみを想定していたが、Phase4で`docx`/`pdf`/`scenario`/`canva-sync`/`wp-publish`を追加 |
| 3 | データバリデーションを独自に設計・追加 | `docs/03_data_format.md`はデータ形式の説明のみで詳細なバリデーション仕様は未定義だった。`CLAUDE_RULES.md`の要件に基づき、`page_no`必須/整数/重複、`pages`/`lines`/`canva`の型・想定外キー検出をPhase1で新規実装 |
| 4 | `prompts/`3ファイルの出力形式をJSONスキーマに合わせて修正 | 当初は`source_image`欠落、`unreadable_parts`という非対応フィールド、「Canva AI投入用プロンプト」の二重生成など、`docs/03`のスキーマや`canva_renderer.py`の自動生成と不整合があったため整合を取った |
| 5 | Canva/WordPress認証方式を独自に決定 | `docs/01_requirements.md`では「対象外（将来拡張できる構成にする）」としか記載がなく認証方式の指定はなかった。今回はユーザー指示に基づき、Canvaは`.env`の`CANVA_API_KEY`を単純なBearerトークンとして送る簡易方式、WordPressはApplication Password方式のBasic認証を採用（詳細は8節・7節参照） |
| 6 | 動画生成用シナリオの出力形式（4種）を新規設計 | `docs/03`/`docs/04`には元々定義がなかったため、`scenario.json`/`scenario.md`/`voicevox.txt`/`scene.json`のフォーマットをPhase4で新規に設計した（8節参照） |
| 7 | 生成物（バイナリ・シナリオ出力）のgit管理方針を追加 | `output/*.docx`・`output/*.pdf`はバイナリのため`.gitignore`に追加し、git管理対象外とした（`.md`/`.json`のテキスト生成物は既存方針を踏襲しリポジトリに含めている） |
| 8 | 入力バリデーションをGPTレビュー結果に基づき追加 | `lines`がリストであること、`lines[].speaker`/`text`が文字列であること、`improvement_points`の各要素が文字列であること、`source_image`に絶対パス・`../`親ディレクトリ参照が含まれないこと、`wp-publish`の`--status`が`draft`/`publish`/`future`/`pending`/`private`のいずれかであることを追加検証（`src/models.py`・`src/wordpress_client.py`） |
| 9 | Canva API連携・WordPress投稿連携を「任意機能」として明確化 | ユーザー方針として、両連携は必須機能ではなく任意機能であると整理。未設定時は例外を投げず自動的にモック動作へ切り替わり、標準エラー出力とレポートJSONの`note`で明示するよう修正。必須機能（`generate`/`canva`/`docx`/`pdf`/`scenario`）が両連携の設定状態に一切依存しないことをテストで直接検証した |

## 4. 追加ライブラリ一覧

| ライブラリ | pyproject.tomlの指定 | 実インストールバージョン | 用途 | 追加コミット |
|---|---|---|---|---|
| python-docx | `>=1.1.0` | 1.2.0 | DOCX出力（Phase4①） | `60e0916` |
| reportlab | `>=4.0.0` | 5.0.0 | PDF出力（Phase4②）。付随して`pillow`(12.3.0)も自動インストールされる | `713f559` |
| requests | `>=2.31.0` | 2.34.2 | Canva/WordPress REST API呼び出し（Phase4④⑤） | `7547e87` |
| pytest（dev） | `>=8.0.0` | 9.1.1 | テスト実行（`[project.optional-dependencies] dev`） | 初回コミットから存在 |

外部有料サービスやOCR/LLM APIへの依存は追加していない（`CLAUDE_RULES.md`の「有料サービス前提にしない」方針を維持）。

## 5. 実行方法（README.mdに反映済み）

`README.md`の「使い方」節に、以下7コマンド全てを実行例付きで記載済み。

```bash
python3 -m src.cli generate --input examples/sample_pages.json --output output/brushup.md
python3 -m src.cli canva --input examples/sample_pages.json --output output/canva_design.md
python3 -m src.cli docx --input examples/sample_pages.json --output output/brushup.docx
python3 -m src.cli pdf --input examples/sample_pages.json --output output/brushup.pdf
python3 -m src.cli scenario --input examples/sample_pages.json --output-dir output/scenario
python3 -m src.cli canva-sync --input examples/sample_pages.json --output output/canva_sync_report.json
python3 -m src.cli wp-publish --input examples/sample_pages.json --output output/wp_publish_report.json --categories "お知らせ,教材" --tags "まじょこ" --status draft
```

いずれも`python3 -m src.cli <command> --help`でオプション一覧を確認できる（本ブリーフ作成時に全コマンドの`--help`出力を実際に確認済み）。

## 6. テスト実行方法（README.mdに反映済み）

```bash
python3 -m pip install -e ".[dev]"
python3 -m pytest -q
```

実行結果: `56 passed`

| テストファイル | 件数 | 対象 |
|---|---|---|
| tests/test_parser.py | 3 | JSON読み込み・ファイル不正時のエラー |
| tests/test_validation.py | 16 | データバリデーション（`lines`/`speaker`/`text`/`improvement_points`の型、`source_image`のパストラバーサル禁止を含む） |
| tests/test_models.py | 1 | ページ番号ソート |
| tests/test_renderers.py | 3 | brushup.md / canva_design.md 生成 |
| tests/test_cli.py | 8 | 全サブコマンドのCLI経由実行・エラー処理・**Canva/WordPress環境変数が未設定でも必須機能(generate/canva/docx/pdf/scenario)が全て正常動作することの検証** |
| tests/test_docx_renderer.py | 1 | DOCX生成 |
| tests/test_pdf_renderer.py | 2 | PDF生成 |
| tests/test_scenario_renderer.py | 5 | 動画シナリオ4形式の生成 |
| tests/test_env_config.py | 3 | `.env`読み込みユーティリティ |
| tests/test_canva_client.py | 6 | Canva連携（モック/実APIモード、未設定時の通知メッセージ・レポートnoteを含む） |
| tests/test_wordpress_client.py | 8 | WordPress連携（モック/実APIモード、statusバリデーション、未設定時の通知メッセージ・レポートnoteを含む） |
| **合計** | **56** | |

上記のうち`tests/test_cli.py::test_core_commands_work_without_canva_or_wordpress_credentials`は、`CANVA_API_KEY`/`WP_URL`/`WP_USERNAME`/`WP_APP_PASSWORD`をすべて未設定にした状態で`generate`/`canva`/`docx`/`pdf`/`scenario`の5コマンドを実行し、いずれも正常に出力ファイルを生成できることを確認する（必須機能が任意機能の設定状態に依存しないことの直接的な検証）。

## 7. 未実装・保留事項

以下のCanva/WordPress関連の2項目は、**いずれも任意機能の範囲内の課題であり、必須機能（教材ブラッシュアップMarkdown・Canva向けレイアウト設計書・DOCX・PDF・動画シナリオ出力）の動作には影響しない**（1節・8節参照）。

- **Canva連携は「モック付き連携雛形」であり、OAuth2/PKCEによる本番認証には未対応**: 本実装は`.env`の`CANVA_API_KEY`を単純に`Authorization: Bearer <key>`ヘッダーとして送る簡易方式。実際のCanva Developer PortalのConnect APIはOAuth2/PKCE（認可コードフロー・アクセストークンの発行と有効期限管理・リフレッシュ）を要求するため、本実装のままでは実際のCanva環境と疎通できない可能性が高い。実APIキー・実OAuthフローでの疎通確認は未実施（ユニットテストはHTTPリクエストをモックした範囲のみ）。本番利用にはOAuth2/PKCE対応の追加実装が必要。
- **WordPress連携も「モック付き連携雛形」であり、実サイトでの疎通確認は未実施**: Application Password方式によるBasic認証の実装雛形はあるが、発行手順のドキュメント化や、実際のWordPressサイト（実URL・実認証情報）に対する動作確認は行っていない。全てモックまたはHTTPモックによるユニットテストの範囲にとどまる。
- **動画生成用シーン分割JSON（`scene.json`）は独自設計**: Veo等の実際の外部ツール入力仕様に合わせたものではない。実運用時はツール側の要求スキーマに合わせた調整が必要になる可能性がある。
- **`input/raw_images`・`input/transcripts`の運用手順は未整備**: OCR結果を人がどう`pages`JSONにまとめるかは`prompts/`を手動でAIに投入する運用のままで、自動化はしていない（`docs/07_api_integration_design.md`は設計のみ）。
- **DOCX/PDFへの実画像埋め込みは未対応**: `source_image`はファイル名のテキスト参照のみで、実際の画像ファイルを埋め込む機能はない（既存のMarkdown出力の挙動を踏襲）。
- **PDF内の日本語表示の機械的検証は未実施**: `pdftotext`等のテキスト抽出ツールが環境になかったため、生成PDFをコード側から自動検証できていない（レビュー担当者への目視確認依頼で対応）。
- **Phase3「API連携設計」は設計のみで実装なし**（意図的。`CLAUDE_RULES.md`の「外部API前提にしない」方針に基づく）。

## 8. Canva / WordPress / DOCX / PDF / 動画シナリオ出力の実装方式

### DOCX出力（`src/docx_renderer.py`）
`python-docx`を使用し、`render_brushup()`と同じ構成（表紙・全体方針・ページ別の元画像/概要/文字起こし/改善ポイント）をWord文書として生成する。`write_docx(path, project)`が`Document`を組み立てて`.save()`する。画像ファイルの埋め込みはせず、`source_image`はテキストとして記載する。

### PDF出力（`src/pdf_renderer.py`）
`reportlab`（`platypus`のFlowable API）を使用し、DOCXと同じ構成をPDF化する。日本語表示には、reportlab内蔵のCIDフォント`HeiseiKakuGo-W5`（Adobe-Japan1のCMapを参照する組み込みフォント）を使用しており、外部フォントファイルのインストールは不要。`render_pdf()`がFlowableのリストを返し、`write_pdf()`が`SimpleDocTemplate`でPDF化する。

### 動画生成用シナリオ出力（`src/scenario_renderer.py`）
入力の追加ライブラリなし（標準ライブラリ`json`のみ）。`scenario`サブコマンド1回の実行で以下4ファイルをディレクトリにまとめて生成する。
- `scenario.json`: 台詞1行ごとに`page_no`/`order`（通し番号）/`speaker`/`text`/`source_image`
- `scenario.md`: ページ・話者を明示した人間向け台本
- `voicevox.txt`: `[話者名]`見出し行＋台詞本文を交互配置（音声キャラクターの選択自体は人が行う想定。VOICEVOXの標準APIやファイル形式仕様に準拠したものではなく、コピー&ペースト運用を想定した独自テキスト形式）
- `scene.json`: ページ単位を1シーンとし、`canva.main_visual`/`notes`から組み立てた`visual_prompt`、結合済み`dialogue_text`、構造化済み`lines`を持つ（Veo等への入力を想定した独自スキーマ）

### 【任意機能】Canva連携（`src/canva_client.py`）※モック付き連携雛形、OAuth2/PKCE未対応
`CanvaClient`クラスがCanva Connect APIの`POST /v1/designs`をページ単位で呼び出し、デザインを作成する。認証は`.env`の`CANVA_API_KEY`を`Authorization: Bearer <key>`ヘッダーとして送る**簡易方式**。`CANVA_API_KEY`が未設定（`.env`にもOS環境変数にも無い）の場合は`is_mock=True`となり、**`requests`を一切呼び出さず**`mock-design-{page_no}`という仮のデザインIDとURLを返す（`create_designs_for_project()`でページごとに実行し、`canva-sync`サブコマンドが結果をJSONレポートとして出力）。未設定時は標準エラー出力に通知メッセージを表示し、レポートJSONにも`note`フィールドで「モック動作である」ことを明記する。他の必須機能（`generate`/`canva`/`docx`/`pdf`/`scenario`）は`canva_client.py`の状態に一切依存しない。

**注意**: 実際のCanva Connect APIはOAuth2/PKCE（認可コードフロー）による認証を要求するため、本実装の「静的なAPIキーをBearerトークンとして送る」方式のままでは実際のCanva環境と疎通できない可能性が高い。あくまで「APIキー未設定時にエラーにならず処理を継続できる任意の連携雛形」であり、本番相当のAPI疎通確認・OAuth2/PKCE対応は今後の課題（7節参照）。

### 【任意機能】WordPress投稿連携（`src/wordpress_client.py`）※モック付き連携雛形、実サイト疎通未実施
`WordPressClient`クラスがWordPress REST API（`wp-json/wp/v2`）を用いて以下を順に実行する。
1. 画像アップロード（`POST /wp/v2/media`、ページの`source_image`が`--image-dir`配下に実在する場合のみ）
2. カテゴリ・タグの検索、未存在なら作成（`GET`/`POST /wp/v2/categories`・`/tags`）
3. 記事作成（`POST /wp/v2/posts`。本文はページ情報から独自に組み立てたHTML、`categories`/`tags`/`featured_media`を含む。`status`は`draft`/`publish`/`future`/`pending`/`private`のいずれかのみ許可し、それ以外は`ValueError`で拒否）
4. 最初にアップロードした画像を`featured_media`としてアイキャッチ設定

認証は`WP_URL`/`WP_USERNAME`/`WP_APP_PASSWORD`（WordPressのApplication Password機能を想定したBasic認証）。いずれか未設定の場合は`is_mock=True`となり、`requests`を呼び出さずに仮のID・URLを返す。未設定時は標準エラー出力に通知メッセージを表示し、レポートJSONにも`note`フィールドで「モック動作である」ことを明記する。実APIモードで画像ファイルが`--image-dir`に見つからない場合はアップロードをスキップし、`skipped_images`にファイル名を記録する（モックモードでは常に成功扱い）。他の必須機能は`wordpress_client.py`の状態に一切依存しない。

**注意**: Application Password方式の実装雛形はあるが、実際のWordPressサイト（実URL・実認証情報）に対する疎通確認は行っていない。あくまで「認証情報未設定時にエラーにならず処理を継続できる任意の連携雛形」であり、実サイトでの動作確認は今後の課題（7節参照）。

## 9. 秘密情報の混入チェック結果

以下を実際に確認した（対象: `ai_kyouzai_brushup_project`ディレクトリ配下、Gitで管理されている/されていない両方のファイル）。

- `.env`ファイル自体は**存在しない**（`ls .env` → No such file or directory）。コミットされているのは値が空の`.env.example`のみ。
- `.gitignore`に`.env`を追加済み（誤ってコミットされる事故を防止）。
- プロジェクト全体を`api_key|secret|password|token|bearer|BEGIN...KEY|client_secret|access_token|refresh_token`等のパターンでgrepした結果、該当箇所はすべて「変数名」「テスト用のダミー値（`dummy-key`・`secret`という文字列リテラル・`admin`)」であり、実際の鍵・トークンの値は含まれていない。
- 認証情報ファイルにありがちな名前（`*credential*`, `*.pem`, `*.key`, `token*.json`, `*.p12`, `*.pfx`, `wp_config*`, `*.env`）で検索したが該当ファイルなし。
- `input/`ディレクトリは空（実データ・実画像は含まれていない）。
- `.claude/settings.local.json`というファイルが存在する（Gitには未追跡・未コミット）。これはClaude Codeのローカル権限設定（許可したBashコマンドパターンの一覧）であり、APIキーや個人情報は含まれていないが、プロジェクトのコードではなくツールのローカル設定なので**レビュー提出物には含めない**方針とし、`.gitignore`にも追加済み（10節参照）。
- （v2追記）`.pytest_cache/`・`src/__pycache__/`・`tests/__pycache__/`・`src/ai_kyouzai_brushup.egg-info/`を実ディスクから削除し、再度`find`で存在しないことを確認した。これらは元々`.gitignore`（`__pycache__/`・`.pytest_cache/`・`*.egg-info/`）でGit管理対象外だったが、`pip install -e .`や`pytest`実行のたびに自動再生成される類のビルド/テストキャッシュであり、`git archive`ベースの配布ZIPには元々含まれない。

**結論: 秘密情報の混入は確認されなかった。**

## 10. ZIP化可否の判定

**判定: レビュー提出用にZIP化して問題ない状態。**

ただし、単純にディレクトリを丸ごとZIP化すると、Git管理外の一時ファイル・ローカルツール設定が混入するため、以下のいずれかの方法を推奨する。

### 推奨方法A: git管理対象のみをZIP化（最も安全）
```bash
cd /Users/teppei/work
git archive --format=zip -o ai_kyouzai_brushup_project_review.zip HEAD -- scripts/ai_kyouzai_brushup_project
```
この方法なら`.gitignore`対象（`__pycache__/`/`.pytest_cache/`/`*.egg-info/`/`output/*.docx`/`output/*.pdf`/`.env`/`.claude/settings.local.json`）や、未追跡ファイルは自動的に含まれない。（v2で`unzip -l`により再検証し、該当ファイルが含まれないことを確認済み）

### 推奨方法B: ディレクトリを直接ZIP化する場合の除外指定
```bash
cd /Users/teppei/work/scripts
zip -r ai_kyouzai_brushup_project_review.zip ai_kyouzai_brushup_project \
  -x "*/__pycache__/*" "*/.pytest_cache/*" "*/*.egg-info/*" \
  -x "*/.env" -x "*/.claude/*" -x "*/output/*.docx" -x "*/output/*.pdf"
```

いずれの方法でも、ZIP化前に`.env`ファイルが存在しないこと、`.pytest_cache/`・`__pycache__/`・`*.egg-info/`が実ディスクからも削除済みであること（v2対応で実施済み）、`.claude/`ディレクトリが含まれないことを再確認することを推奨する。
