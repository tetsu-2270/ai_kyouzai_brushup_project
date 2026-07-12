# 04 出力仕様

> 本ドキュメントは出力仕様（`lesson_pages.json`のスキーマ、各派生出力の生成元・構成）に加えて、それらを生成するCLIコマンドの使い方（`--mode`/`--plan-output`/`review-report`等）も含む、**CLI仕様・出力仕様を含む現行仕様書**です。ファイル名は歴史的経緯で`04_output_spec.md`のままですが、内容としてはCLIコマンドの入出力仕様書を兼ねています。他ドキュメントから参照する際は本ファイル（`docs/04_output_spec.md`）を正としてください（`04_cli_spec.md`という名前のファイルは存在しません）。

## プロジェクト標準output構成（Phase 9.2時点で確定・共通設計ルール）

**Phase 9.2までに確定した、このプロジェクトの共通設計ルールです。** [`PROJECT_RULES.md`](../PROJECT_RULES.md)「4. output構成」にも同内容の要約があります。今後のPhaseでこのルールを変更する場合は、理由と影響範囲を説明して承認を得てから変更してください。それ以外の場合、以下は今後のPhase作業でも維持される前提として参照してください。

```text
output/
  editable/
    lesson_pages.json      # 正式な編集対象（再生成時にユーザーが編集するのはここのみ）
  rendered/
    page_NNN.png           # 正式な完成画像
  canva/
    canva_design.md        # 正式なCanva指示書（オプション出力。主outputではない）
  exports/
    material.md / .docx / .pdf / .pptx   # 正式な完成output
  compat/
    lesson_pages.json / canva_design.md / brushup.md / brushup.docx / brushup.pdf
                            # Phase 8以前の旧仕様との互換用output。新規利用では通常参照しない
```

- **output構成**: `editable/`=再生成時の編集対象、`rendered/`=完成画像、`canva/`=正式なCanva指示書、`exports/`=正式な完成output、`compat/`=旧仕様互換用（`--no-compat-output`で無効化可）。`output_dir`直下には通常ユーザーが使う完成outputを置かない（`scenario/`/`review_report.md`/`imported_pages.json`/`assets/`は役割重複が無いため直下のまま）。
- **editable中間ファイルの扱い**: 完成画像・PDF・DOCX・PPTXを直接編集するのではなく、`output/editable/lesson_pages.json`を編集→`regenerate`→`rendered/`/`exports/`を再生成する。
- **source情報の扱い**: 元資料由来の画像・ページ画像・source assetsを落とさない。PDF/PPTX/画像から取り込んだ元画像・ページ画像は可能な限り`source_image`/`source_assets`として保持する。`source_page_no`は内部メタデータとして保持し、通常は完成outputに表示しない（確認したい場合は`review-report`を使う）。

以降の各節は、この標準構成の詳細仕様（生成条件・スキーマ・CLIオプション等）を記載する。

## 実行ログ（`logs/`）の標準仕様（Phase 10.2で追加・共通設計ルール）

`output/`とは別に、プロジェクト直下に`logs/`ディレクトリを置き、CLI実行のたびに実行ログを出力する。`input/`/`output/`と異なり、**`logs/`ディレクトリ自体はGit管理対象**とし、中身のログファイルのみを除外する。

```text
logs/
  .gitkeep                            # Git管理対象（logs/ディレクトリ自体を追跡するため）
  YYYYMMDD_HHMMSS_<command>.log       # 実行ログ本体。Git管理対象外
```

管理方針:

| 対象 | Git | ZIP |
|---|---|---|
| `logs/.gitkeep` | 対象 | 対象 |
| `logs/*.log`（ログ本体） | **対象外** | **対象**（`scripts/make_release_zip.sh`は`logs/`を除外しない） |
| `input/` | 対象外 | 対象外 |
| `output/` | 対象外 | 対象外 |

`.gitignore`は以下のように設定する（`logs/*`で中身を除外しつつ、`!logs/.gitkeep`で`.gitkeep`だけ例外的に追跡する）。

```gitignore
logs/*
!logs/.gitkeep
```

### ログファイル名

`logs/YYYYMMDD_HHMMSS_<command>.log`。`<command>`はCLIサブコマンド名（`build-all`/`regenerate`/`check-ocr`/`import-source`/`canva`/`docx`/`pdf`/`scenario`/`canva-sync`/`wp-publish`等）。ただし`lesson-pages`は`--mode`（`proofread`/`restructure`/`generate`）が実質的な処理内容を表すため、モード名をファイル名に使う（例: `lesson-pages --mode generate` → `logs/..._generate.log`）。ファイル名に使えない文字は`_`に置換する。

### ログの内容

`src/execution_logger.py`の`ExecutionLogger`が、以下の見出し（セクション）を持つテキストログを組み立てる。

```text
===== START =====       # timestamp・command・args
===== ENVIRONMENT =====  # python・cwd
===== INPUT =====        # input_path・output_dir・mode・output_format等（コマンドにより異なる）
===== INPUT_RESULT ===== # 取り込み・読み込んだpages数、OCR成功/空ページ数等
===== OCR =====          # OCR環境診断の要約（画像inputの場合のみ）
===== OUTPUT =====       # generated_files（生成した主要成果物一覧）
===== WARNINGS =====     # 警告のうえ処理を継続した内容
===== ERRORS =====       # エラー内容（非ゼロ終了時）
===== STDERR =====       # 標準エラー出力に実際に表示した内容（そのまま）
===== RESULT =====       # exit_code・ended_at
```

ログディレクトリの作成・ログファイルの書き込みに失敗しても、本処理は止めない（標準エラー出力に警告を表示するのみ）。

### ログ出力対象コマンド

`build-all`・`regenerate`・`check-ocr`・`lesson-pages`（3モードとも）・個別CLI（`import-source`/`canva`/`docx`/`pdf`/`scenario`/`canva-sync`/`wp-publish`）。すべて`src/cli.py`の`main()`が一括して実行開始〜終了（成功・失敗いずれも）でログを書き出す。

### ログの機密情報マスク（Phase 10.2追加修正・共通設計ルール）

`logs/*.log`は配布用ZIPの対象になる（本節冒頭の管理方針の表を参照）ため、CLI引数・stderr出力・エラーメッセージ等に秘密情報が混ざっていても、ログへ生値を残さない。`src/execution_logger.py`の`mask_secrets()`が、ログファイルへ書き出す直前の最終テキストに対してマスク処理を行う（`START`のargs・各セクションの内容・`STDERR`・`WARNINGS`・`ERRORS`のいずれも対象）。

マスク対象キーワード（大文字小文字を区別しない）:

```text
password / passwd / secret / token / api_key / apikey / access_key /
access_token / authorization / bearer / client_secret / refresh_token / private_key
```

マスク例:

```text
--api-key sk-xxxx            → --api-key [REDACTED]
--token=secret-value         → --token=[REDACTED]
password=abc123              → password=[REDACTED]
Authorization: Bearer xxxxx  → Authorization: Bearer [REDACTED]
```

`.env`や認証情報ファイルの中身自体をログへ出力する処理は存在しない。マスクは「値が単一トークン（空白区切り）で表現される」ケースを対象としており、複数行にまたがる秘密情報（PEM形式の秘密鍵など）は部分的なマスクにとどまる場合がある点に留意する。

## 検証エビデンス（`logs/evidence/`。テスト・検証結果の永続保存）

`logs/`のCLI実行ログとは別に、`pytest`・`scripts/run_sample.sh`等の**検証結果そのもの**を`logs/evidence/<run_id>/`へ永続保存する仕組みがある。目的は、Claude Codeが一度実行した検証結果を、Codexがローカルファイルから直接確認できるようにし、確認のためだけの再実行（時間・計算資源・外部API利用料の重複）を避けることである。

```text
logs/
  evidence/
    .gitkeep                            # Git管理対象（logs/evidence/ディレクトリ自体を追跡するため）
    latest.json                         # 最新の完了済みrun_idを指すポインタ。Git管理対象外
    <run_id>/                           # 例: 20260711_103735_9179。Git管理対象外
      manifest.json                     # 機械可読な実行結果一式
      summary.md                        # 人間・Codexが短時間で判断できる要約
      commands/
        001_pytest.log                  # コマンドごとの標準出力・標準エラー・終了コード
        002_run_sample.log
      pytest/
        junit.xml                       # pytest --junitxml の出力
```

### 正式な実行入口

```bash
bash scripts/run_verification.sh
```

内部で`python3 -m src.verification_runner`（`src/verification_evidence.py`のライブラリを利用）を呼び出し、以下を順に実行する。

1. `python3 -m pytest -q --junitxml=logs/evidence/<run_id>/pytest/junit.xml`
2. `bash scripts/run_sample.sh`

片方が失敗しても、もう片方は続けて実行する（失敗を記録したうえで残りも実行し、最終的な終了コードは失敗を反映する）。実教材を使う`build-all`等の受け入れ確認も、同じ`EvidenceRun`の仕組み（`src/verification_evidence.py`）から呼び出せるが、実教材・OCR本文は`logs/evidence/`へコピーしない（ファイルの存在・サイズ・SHA-256のみ記録する）。

### `run_id`と過去結果の扱い

`run_id`は時刻＋衝突防止用のランダムサフィックス（例: `20260711_103735_9179`）。**過去の`run_id`ディレクトリは削除・上書きしない**。最新の完了済み結果は`logs/evidence/latest.json`が指す（`manifest.json`/`summary.md`の書き出しが完了した後にのみ更新するため、`latest.json`は常に完成済みの実行を指す）。

### `manifest.json`の主なフィールド

```json
{
  "schema_version": 1,
  "run_id": "...",
  "purpose": "...",
  "started_at": "...", "ended_at": "...", "duration_seconds": 0,
  "overall_status": "passed",
  "overall_exit_code": 0,
  "python_version": "...", "platform": "...",
  "git": { "branch": "...", "head": "...", "is_dirty": true, "status_summary": ["M path", "?? path"] },
  "commands": [
    {
      "index": 1, "name": "pytest", "command": ["python3", "-m", "pytest", "-q", "--junitxml=..."],
      "started_at": "...", "ended_at": "...", "duration_seconds": 0,
      "exit_code": 0, "status": "passed",
      "log_file": "commands/001_pytest.log", "artifacts": ["pytest/junit.xml"],
      "pytest_summary": { "total": 607, "passed": 607, "failed": 0, "errors": 0, "skipped": 0 }
    }
  ],
  "external": []
}
```

`git`はコミットハッシュ・ブランチ・`git status --porcelain`のパス一覧のみを記録し、ファイル内容や秘密情報は記録しない。`external`は、将来外部API・有料処理を検証する場合にサービス名・リクエスト数・追跡ID・概算費用等を記録するための構造で、**今回のバージョンでは実際には使用しない**（外部APIを呼び出す処理自体を追加していない）。

### 失敗・中断時の扱い

コマンドが非ゼロ終了・例外・タイムアウトになっても、`manifest.json`/`summary.md`は可能な限り確定させる（`status`は`passed`/`failed`/`timeout`/`error`/`interrupted`のいずれかで、成功していない実行を`passed`として記録しない）。`Ctrl-C`等の中断時も`interrupted`として記録してから終了する。`manifest.json`/`latest.json`はいずれも一時ファイルへ書き出してから置換する方式（`os.replace`）で、書き込み途中の状態を完成済みとして誤読しない。

### 秘密情報マスク

`src/execution_logger.py`の`mask_secrets()`をそのまま再利用する（重複実装を避ける）。コマンドの引数・標準出力・標準エラー・Gitステータス等、`manifest.json`/コマンドログへ書き出すすべての文字列値に適用する。`.env`や認証情報ファイルの中身を読み取って記録する処理は存在しない。

### Git管理・ZIP方針

| 対象 | Git | ZIP |
|---|---|---|
| `logs/evidence/.gitkeep` | 対象 | 対象 |
| `logs/evidence/<run_id>/`（実行結果本体） | **対象外** | **対象外**（`logs/*.log`とは異なり、機密性の高い実行文脈・Git差分要約を含み得るため、配布ZIPには含めない方針とした） |
| `logs/evidence/latest.json` | 対象外 | 対象外 |

`.gitignore`は以下のように設定する。

```gitignore
logs/*
!logs/.gitkeep

!logs/evidence/
logs/evidence/*
!logs/evidence/.gitkeep
```

### Codexによる確認運用

**主確認手段はClaude Codeの完了レポート（`CLAUDE_RULES.md`のテンプレート）であり、このエビデンスは補助確認手段である。** Codexは、まずユーザーから貼られた完了レポートを確認し、レポートが自己完結していれば原則としてこのエビデンスを追加確認しない。レポート内の矛盾・完了条件対応の不明・テスト結果不足・重大な懸念等がある場合だけ、`logs/evidence/latest.json`と対応する`manifest.json`/`summary.md`を確認する。対象コミット・作業ツリー状態・実行内容が現在の確認対象と一致する場合、同じテストを再実行しない。エビデンスが無い・破損している・対象コードが実行後に変更されている・必要なテストが未実行の場合のみ再実行を検討する（詳細は`AGENTS.md`・`PROJECT_RULES.md`「9. このプロジェクトの正式な検証入口とエビデンス保存先」・`~/ai-development-rules/DEVELOPMENT_RULES.md`「6. Claude Code完了レポート（主確認手段）」「7. エビデンス（補助確認手段）」参照）。

## 成功判定の方針（実質失敗を正常終了扱いにしない。Phase 10.2で追加）

Phase 10.1のOCR必須チェック（`proofread`/`restructure`でTesseract不能・全ページOCR空ならエラー終了）と同じ考え方を、他の失敗ケースにも適用する。詳細は[`CLAUDE_RULES.md`](../CLAUDE_RULES.md)「成功判定の方針」を参照。要点:

- 非ゼロ終了にすべきもの: 入力ファイル・ディレクトリが存在しない/空/対応ファイル無し、取り込み・読み込んだpagesが0件、OCR必須モードでOCR不能・全ページ空、指定したoutput-formatの成果物が実際に生成されない、JSON構文エラー。
- 警告のうえ継続してよいもの: 一部ページのみOCR空、一部source_image参照欠落（テキスト出力は可能）、`--no-compat-output`によるcompat出力の無効化、フォント未指定時の代替フォント使用。
- `check-ocr`は診断コマンドのため、OCR環境が不足していても`exit 0`でよい（診断自体が例外で壊れた場合のみ非ゼロ終了）。

## 元資料の自動取り込み（`import-source` / `build-all`）

作成者向けの主導線は、元資料（画像/PDF/PPTX）を`input/source/`に置いて`build-all`コマンドを実行することである（詳細は`docs/08_user_acceptance_test.md`、README「クイックスタート（作成者向け）」を参照）。`imported_pages.json`/`lesson_pages.json`はいずれもシステムが自動生成する中間ファイルであり、**作成者が手作業で作るものではない**。

`import-source`は、元資料から`docs/03_data_format.md`の`pages`形式互換のJSON（`imported_pages.json`）を生成する。

| 元資料 | 取り込み方法 | 保存されるアセット |
|---|---|---|
| 画像（`.png`/`.jpg`/`.jpeg`/`.webp`） | ディレクトリ配下をファイル名順に1画像=1ページ。OCR（`pytesseract`+tesseract本体）でテキスト抽出。OCR前提の事前チェックは後述 | `output/assets/page_NNN.<ext>`（元画像そのもの） |
| PDF（`.pdf`） | `pymupdf`でページ単位にテキスト抽出＋ページ画像化 | `output/assets/page_NNN.png`（ページ全体のラスタ画像） |
| PPTX（`.pptx`） | `python-pptx`でスライド単位にテキスト抽出＋スライド内埋め込み画像を抽出（スライド全体のレンダリングは非対応） | `output/assets/slide_NNN_M.<ext>`（スライド内の埋め込み画像） |
| PPT（`.ppt`旧形式） | 未対応（明確なエラーメッセージを返す） | - |

`imported_pages.json`の各ページは、`page_no`/`source_image`/`source_assets`/`title`/`summary`/`lines`/`improvement_points`/`canva.layout_type`/`canva.main_visual`/`canva.notes`を持つ（`docs/03_data_format.md`のスキーマに準拠）。`source_image`は1ページの主要な参照画像、`source_assets`はPPTXのスライド内に複数の画像がある場合などの追加アセット一覧（画像・PDF取り込みでは通常空配列）。OCRが成功した場合、抽出テキストは`lines`（1行1要素の`{"speaker": "", "text": ...}`）に格納され、`title`/`summary`の自動生成にも使われる。`lines`は`lesson-pages`実行時に`body`へ変換され、`proofread`/`restructure`の校正・再構成対象になる。

### OCR前提の事前チェック（Phase 10.1）

画像取り込みはOCR（Tesseract）に依存する。Tesseract本体・日本語言語データ・Homebrewが無い、またはPATHに通っていない環境では、OCRが実行できず全ページのテキストが空のまま`proofread`/`restructure`が実質機能しなくなる問題があった。これを防ぐため、`src/ocr_environment.py`にOCR環境診断機能を追加した。

- `check_tesseract_environment()`: `tesseract`コマンドがPATH上にあるか、無ければ`/opt/homebrew/bin/tesseract`・`/usr/local/bin/tesseract`（Homebrewでの典型的なインストール先）に存在するかを確認する。バージョン・利用可能言語（`tesseract --list-langs`）・日本語(`jpn`)の有無も取得する。
- `check_homebrew_environment()`: `brew`コマンドについて同様にPATH上・`/opt/homebrew/bin/brew`・`/usr/local/bin/brew`を確認する。
- `get_ocr_environment_status()`: 上記2つをまとめ、`ocr_ready`（tesseractがPATH上にあり日本語言語データもある状態）、`path_suggestions`（Apple Siliconなら`eval "$(/opt/homebrew/bin/brew shellenv)"`、Intel Macなら`eval "$(/usr/local/bin/brew shellenv)"`のような`brew shellenv`によるPATH設定コマンド）、`warnings`/`errors`を含む辞書を返す。

`import_images()`（`import-source`/`build-all`が画像を取り込む際に使う）は、処理前に`get_ocr_environment_status()`を1回呼び出し、`ocr_ready`でない場合は標準エラー出力に警告を表示したうえで処理を継続する。処理後、全ページで`lines`が空だった場合は追加の警告を表示する。この層の処理はモード（`proofread`/`restructure`）を意識しない共通処理であり、**単体の`import-source`コマンドは警告のみで非ゼロ終了にしない**（`import-source`はテキスト抽出専用コマンドであり、抽出結果をどう使うかは呼び出し側次第のため）。

Tesseractが既知パスには見つかるがPATHに無い場合、`_try_ocr()`はその既知パスを`pytesseract.pytesseract.tesseract_cmd`に明示設定して実行を試みる（PATHが通っていなくても、既知パスで見つかった実体があればOCR自体は実行できる）。使用する言語は`resolve_ocr_lang()`が`tesseract --list-langs`の結果に応じて`jpn+eng`/`jpn`/`eng`を選ぶ。

#### `build-all`のOCR必須モードチェック（Phase 10.1追加修正）

`build-all`がサポートする`--mode`は`proofread`・`restructure`のいずれも、画像から抽出したテキストの校正・再構成を行うことが目的である（`OCR_REQUIRED_MODES = {"proofread", "restructure"}`）。画像inputでOCRが実質使えない、または全ページ抽出結果が空のまま「成功したように見えるが中身が空」というのは、`build-all`にとって望ましくない。そこで`build_all()`は、`import-source`ステップの直後に以下を追加でチェックし、**該当する場合は非ゼロ終了（`exit 1`）する**（`import-source`単体の警告とは別に、`cli.py`の`_validate_ocr_precondition()`が実施する）。

| 条件（画像input + proofread/restructureの場合のみ） | 挙動 |
|---|---|
| Tesseract本体が使えない | `exit 1`。インストール手順・PATH設定案内を表示 |
| 日本語言語データ(`jpn`)が無い | `exit 1`。`brew install tesseract-lang`等の案内を表示 |
| 取り込みページ全件で`lines`が空 | `exit 1`。`check-ocr`での診断を促す |
| 一部ページのみ`lines`が空 | `exit 0`のまま警告のみ表示し処理を継続（「何ページ中何ページが空か」を明記） |

`--allow-empty-ocr`（既定は無効）を指定すると、上記チェックをすべてスキップして従来通り処理を継続できる（テスト・開発用途）。**通常の利用でこのフラグを指定しない限り、空のOCR結果のまま成功することは無い。**

このチェックは画像input（`_detect_input_kind()`が`"image"`と判定した場合）のみに適用される。PDF（`pymupdf`によるネイティブテキスト抽出）・PPTX（`python-pptx`によるネイティブテキスト抽出）はTesseractに依存しないため対象外であり、`generate`モード（そもそも画像を取り込まない）や、`regenerate`・個別CLI（`lesson-pages`に既存のpages形式/lesson_pages形式JSONを直接渡す経路）にも影響しない。

`build-all`は、以下の場合もエラー終了する（Phase 10.2で追加。「成功判定の方針」参照）。

- 取り込んだ`pages`が0件（入力ディレクトリが空・対応ファイルが1つも無い場合は、この時点より前に`import-source`自体がエラーにする）
- 指定した`--output-format`の成果物が実際には生成されなかった場合

#### OCR環境診断コマンド・スクリプト

```bash
python3 -m src.cli check-ocr
```

`tesseract`/`brew`のPATH・既知パス・バージョン・利用可能言語・日本語言語データの有無・対応が必要な手順を表示する（診断のみ。インストールは行わない）。

```bash
bash scripts/check_ocr_env.sh
```

同様の診断をシェルスクリプトとして実行する（`PATH`表示、`which`、既知パスの`ls`、`tesseract --version`/`--list-langs`を、いずれかが無くても最後まで実行する）。

```bash
bash scripts/setup_ocr_macos.sh
```

（任意）macOSでHomebrew経由にTesseract・日本語言語データを実際にインストールするスクリプト。**ユーザーが明示的に実行するものであり、CLI本体やClaude Codeが自動実行することはない。** Homebrew自体が無い場合はインストールを行わず、案内のみ表示する。

`build-all`は`import-source`（→`imported_pages.json`+`output/assets/`）→`lesson-pages`（→`lesson_pages.json`）→`generate`/`canva`/`docx`/`pdf`/`scenario`/`review-report`を内部で順に実行する。`--mode`は`proofread`/`restructure`のみ（`generate`は元資料を使わないモードのため`build-all`の対象外。`generate`を使う場合は`lesson-pages --mode generate`を直接使う）。

### Apple Vision OCRとの比較output（`output/ocr_comparison/`。`--ocr-engine tesseract+vision`指定時のみ・macOS専用・任意）

`--ocr-engine tesseract+vision`を指定した場合のみ、既存のTesseract結果一式の生成後（`editable/lesson_pages.json`等、通常のパイプラインは一切変更しない）に、追加ステップとしてApple Vision OCRとの比較を実行し、`output_dir`直下に以下を生成する（`--ocr-engine`を指定しない場合、または`tesseract`を指定した場合は一切生成されない）。

```text
output/ocr_comparison/
  summary.json          # 全体サマリー（機械可読。needs_reviewページ一覧・比較指標等）
  summary.md            # 全体サマリー（人間可読）
  pages/page_NNN.json   # ページごとの両エンジン結果・比較指標・不一致理由
  review.html           # 元画像・両エンジン結果（文字単位の差分ハイライト付き）・不一致理由を
                        # 1ページずつ並べた自己完結型HTML
  CLAUDE_OCR_REVIEW.md  # (Apple Vision利用可能時のみ) Claude Code向けの自己完結した画像照合
                        # レビュー指示書（Phase 10.10。詳細は後述）
  claude_review/
    README.md            # claude_review/の説明（build-allが生成）
    pages/page_NNN.json  # ページ別の画像照合結果（指示書を実行したClaude Codeが作成。
                          # build-all実行時点では生成されない）
    progress.json         # 進捗（同上）
    candidates.json       # 全ページの集約結果（同上）
    review_summary.md     # 人間確認用サマリー（同上）
```

`review.html`は各ページを「元画像 / Tesseract / Apple Vision」の3列（狭い画面では縦並び）で構成し、Tesseract/Apple Visionの全文は`difflib.SequenceMatcher`による文字単位の差分ハイライト（置換・削除・追加を左右で色分け・下線スタイルで区別）付きで表示する（Phase 10.8。詳細は`docs/13_ocr_quality_check_workflow.md`「17.7 差分ハイライト」参照）。この差分ハイライトは表示専用であり、`needs_review`判定・比較指標・`summary.json`/ページ別JSONの形式には一切影響しない。

Tesseract/Apple Visionの表示欄（読み取り専用）とは別に、編集可能な「確定テキスト」欄を各ページに持つ（Phase 10.9）。確定欄にコピー・手修正した内容、または「Tesseractを採用」／「Apple Visionを採用」の指定は、ブラウザの`localStorage`へ自動保存され、「レビュー結果をJSONで書き出す」ボタンで以下の形式のJSONをダウンロードできる。

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

採用優先順位（確定テキスト＞採用チェック＞未確認）・保存キーの一意性・安全性の詳細は[`docs/13_ocr_quality_check_workflow.md`](13_ocr_quality_check_workflow.md)「17.8 確定テキスト編集・採用判定・JSON書き出し」を参照。**このJSON書き出しは`output/editable/lesson_pages.json`・`summary.json`・ページ別JSON・Tesseract/Apple Vision結果のいずれも自動変更しない**（正式データへの反映は別タスク）。

Apple Visionが利用できた場合、`CLAUDE_OCR_REVIEW.md`（Claude Code向けの自己完結した画像照合レビュー指示書）と`claude_review/README.md`も自動生成される（Phase 10.10）。この指示書を読んだ別セッションのClaude Codeが、元画像を正本としてTesseract/Apple Vision結果を照合し、`claude_review/pages/page_NNN.json`（ページ別候補）・`progress.json`（進捗）・`candidates.json`（全体集約）・`review_summary.md`（人間確認用サマリー）を作成できる。**プログラムからのClaude API呼び出し・自動起動は行わない**（`build-all`実行時点では指示書とREADMEのみを生成し、それ以外は指示書を読んだClaude Codeが作成する）。**このレビュー結果も`output/editable/lesson_pages.json`へ自動反映されない。** 仕様の詳細は[`docs/13_ocr_quality_check_workflow.md`](13_ocr_quality_check_workflow.md)「17.9 Claude Codeレビュー指示書」を参照。

詳細な比較指標・`needs_review`判定基準・設計思想は[`docs/13_ocr_quality_check_workflow.md`](13_ocr_quality_check_workflow.md)「17. Apple Vision OCRとの比較」を参照。**`output/editable/lesson_pages.json`は`build-all`/`--ocr-engine tesseract+vision`実行時点では変更されない**（Apple Vision結果の自動反映は行わない）。`output/ocr_comparison/`は`output/`配下のためGit管理対象外（「input・output・logs・生成物のGit管理方針」参照）。

`claude_review/candidates.json`（Claude Codeによる画像照合レビュー結果）を`editable/lesson_pages.json`へ反映したい場合は、`apply-ocr-review`コマンド（`--dry-run`→`--apply`の2段階操作）を使う。このコマンドは`build-all`からは自動起動されない（人間が内容を確認したうえで明示的に実行する）。詳細は[`docs/16_apply_ocr_review_workflow.md`](16_apply_ocr_review_workflow.md)を参照。

## 完成outputの形式選択とeditable中間ファイル（Phase 9）

Phase 9で、完成outputの形式を`--output-format`で選べるようにし、また「編集して再生成するための中間ファイル」を正式なoutputとして位置づけた。

### 基本方針

- **Canva指示書は数ある完成outputの選択肢の一つであり、主outputではない。** `--output-format canva`を指定したときのオプション出力として扱う。
- **完成画像・PDF・PPTX・DOCXを直接編集するのではなく、`output/editable/lesson_pages.json`を編集して再生成する。** これが「編集対象」として想定する唯一のファイルである。
- `--output-format`の指定に関わらず、`output/editable/lesson_pages.json`は常に生成する。
- **正式な編集対象は`output/editable/lesson_pages.json`のみ、正式なCanva指示書は`output/canva/canva_design.md`のみ、正式な完成output（Markdown/DOCX/PDF/PPTX）は`output/exports/`のみ。** `output_dir`直下には、通常ユーザーが使う完成outputを置かない（後述「正式outputと後方互換output」参照）。

### `--output-format`の選択肢

| 値 | 意味 | 生成される完成output |
|---|---|---|
| `same`（既定） | 入力の性質に合わせる | 画像入力→`image`、PDF入力→`pdf`、PPTX入力→`pptx` |
| `image` | 完成画像 | `output/rendered/page_NNN.png` |
| `pdf` | PDF | `output/exports/material.pdf` |
| `pptx` | PowerPoint | `output/exports/material.pptx`（1ページ=1スライド。スライド内には`rendered/`の完成画像を配置する簡易構成） |
| `docx` | Word | `output/exports/material.docx` |
| `md` | Markdown | `output/exports/material.md`（教材ブラッシュアップ設計書と同じ内容。`render_brushup()`が生成） |
| `canva` | Canva指示書 | `output/canva/canva_design.md` |
| `json` | 中間ファイルのみ | 追加ファイル無し（`editable/lesson_pages.json`自体が対象） |
| `all` | 上記すべて | `rendered/`+`exports/`（pdf/pptx/docx/md）+`canva/` |

`build-all --output-format ...`で指定する。`--output-format`を省略した場合は`same`（入力の性質に合わせる）が既定値になる。

### 正式outputと後方互換output（`output/compat/`）

Phase 8時点では`output_dir`直下に`lesson_pages.json`/`canva_design.md`/`brushup.md`/`brushup.docx`/`brushup.pdf`を生成していたが、Phase 9で追加した`output/editable/lesson_pages.json`/`output/canva/canva_design.md`/`output/exports/material.*`と**同名または役割が重複し、どちらを編集・参照すべきか分かりにくくなる問題があった**（`brushup.pdf`と`exports/material.pdf`はどちらが正式か、等）。これを解消するため、`output_dir`直下にはこれらを生成せず、後方互換が必要な場合は`output/compat/`配下にまとめることにした。

- **正式な編集対象は`output/editable/lesson_pages.json`のみ。** `output/compat/lesson_pages.json`は同内容の後方互換コピーであり、通常は編集・参照しない。
- **正式なCanva指示書は`output/canva/canva_design.md`のみ**（`--output-format canva`/`all`指定時に生成）。`output/compat/canva_design.md`は同内容の後方互換コピーであり、通常は編集・参照しない。
- **正式な完成output（Markdown/DOCX/PDF/PPTX）は`output/exports/material.*`のみ**（`--output-format`で指定した形式のみ生成）。`output/compat/brushup.md`/`brushup.docx`/`brushup.pdf`は同内容の後方互換コピーであり、新規利用では参照しない（旧`brushup.*`にPPTX相当は無いため、`compat/`にも`brushup.pptx`は存在しない）。
- `output/compat/`は既定で生成される（`build-all`実行時、`--output-format`の指定に関わらず`lesson_pages.json`/`canva_design.md`/`brushup.md`/`brushup.docx`/`brushup.pdf`の5ファイルを常に生成）。`--no-compat-output`を指定すると`output/compat/`自体を生成しない。
- `scenario/`/`review_report.md`は正式outputとの役割重複が無いため、従来通り`output_dir`直下に生成する（`--no-compat-output`の影響を受けない）。

### 画像output（`rendered/`）

`src/image_renderer.py`の`render_document_images()`が生成する。各ページについて、

- `source_image`が設定されている場合: その元画像をそのまま`rendered/page_NNN.png`として採用する（教材に限らず、チラシ・SNS投稿画像等、元のビジュアルをそのまま活かす用途を想定）。
- `source_image`が無い場合（`generate`モード等）: ページ番号ヘッダー・タイトル・区切り線・`summary`・本文（折り返し・打ち切り表示付き）・フッターのページ番号を描画した簡易画像を、全ページ共通のレイアウトで合成する（Phase 10で読みやすさを改善）。

#### 日本語フォントの解決（`--font-path`。Phase 10）

`source_image`が無いページのテキスト合成には日本語フォントが必要である。`src/image_renderer.py`の`resolve_font_path()`が以下の優先順位でフォントを解決する。

1. `--font-path`で明示指定されたパス（存在しない/読み込めない場合は`ValueError`で即座にエラー終了する。黙って別のフォントにフォールバックしない）。
2. 環境の日本語フォント候補を順に探索（macOSの`ヒラギノ角ゴシック`各種、Linuxの`Noto Sans CJK`等、Windowsの`游ゴシック`/`メイリオ`等。実在し読み込めることを確認したものだけを採用）。
3. 候補が1つも見つからない場合は`None`を返す。

`render_document_images()`は、テキスト合成が必要なページ（`source_image`が無いページ）が存在するにもかかわらずフォントが解決できなかった場合、**黙って文字化けリスクを抱えたまま処理を続けず**、標準エラー出力に警告を1回表示したうえで処理を継続する（Pillow既定フォントにフォールバックする。既定フォントは日本語グリフを持たないため文字化けし得る）。

```bash
python3 -m src.cli build-all --input input/source --output-format image --font-path "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"
python3 -m src.cli regenerate --input output/editable/lesson_pages.json --output-format image --font-path /path/to/font.ttc
```

`--font-path`は`build-all`・`regenerate`の両方で指定できる。

### PPTX export（`exports/material.pptx`）

`src/pptx_export_renderer.py`の`write_pptx_export()`が生成する。1ページ=1スライドとし、タイトルのテキストボックスと、そのページの完成画像（`rendered/`）をスライドに配置する簡易構成。スライド内の複雑な図形・アニメーションの再現は対象外（`rendered/`の画像自体が最終的な見た目を担う）。

### 再生成（`regenerate`コマンド）

```bash
python3 -m src.cli regenerate --input output/editable/lesson_pages.json --output-format image
```

`output/editable/lesson_pages.json`（またはユーザーが編集した同形式のJSON）を読み込み、`--output-format`で指定した完成outputを再生成する。`--output-dir`を省略した場合、`--input`の2階層上（`output/editable/lesson_pages.json`なら`output/`）を出力先とする。`--output-format`の既定値は`all`（`same`が指定された場合も`all`として扱う。再生成時は元の入力形式という概念が無いため）。

`output/editable/lesson_pages.json`の編集してよい項目・編集しない方がよい項目、`regenerate`の具体例（画像/PDF/Canva指示書/全形式/日本語フォント指定）は[`docs/09_editable_regenerate_guide.md`](09_editable_regenerate_guide.md)を参照。

`regenerate`は以下の場合にエラー終了する（Phase 10.2で追加。「成功判定の方針」参照）。

- `--input`のファイルが存在しない、またはJSON構文が不正
- 読み込んだ`pages`が0件
- 指定した`--output-format`の成果物が実際には生成されなかった場合

## 教材本文ブラッシュアップ（`prepare-content-brushup` / `apply-content-brushup`。Phase 10.13）

OCR確定原文（`editable/lesson_pages.json`）は元画像の正確な転記であることを示すが、文章として
完成していることは意味しない。本機能は、OCR確定原文を変更不能な証拠として保持したまま、
AI作業エージェント（Claude Code/Codex）が教材本文の分かりやすさを改善する候補を作成し、
人間の明示操作（`--dry-run`→`--apply`）を経て`editable/lesson_pages.json`へ反映する。
詳細は[`docs/18_content_brushup_workflow.md`](18_content_brushup_workflow.md)を参照。

```text
output/<output-dir>/
  content_brushup/
    VERIFIED_OCR_SNAPSHOT.json   # OCR確定原文の証拠（SHA-256付き。prepare-content-brushupが生成）
    AI_CONTENT_BRUSHUP.md         # AIエージェント向け本文改善指示書（同上）
    README.md                     # content_brushup/の説明（同上）
    pages/page_NNN.json           # ページ別改善候補（指示書を実行したAIエージェントが作成）
    progress.json                  # 進捗（同上）
    candidates.json                # 全体集約（同上）
    review.html                    # 原文と改善案の比較確認画面（apply-content-brushupが生成）
    review_summary.md              # 人間確認用サマリー（同上）
    apply_report.json / .md        # 反映結果レポート（同上）
```

デザインJSONと同様、`original`（OCR確定原文と完全一致）と`proposed`（改善案）を分離して保持し、
`changes`に変更箇所ごとの理由・`change_type`・`risk_level`を記録する。`risk_level: high`または
`requires_human_review: true`のページが対象範囲に1件でもあれば、そのページだけでなく対象範囲
全体を反映不可として扱う（Phase 10.11・10.12と同じ「全体停止方式」の安全設計）。

`--apply`成功後、`title`/`body`/`summary`が更新され、`image_text`/`canva_prompt`/`video_scene`は
既存の`_apply_derived_fields()`で再計算される。`page_no`/`source_page_no`/`source_image`/
`layout_instruction`/`notes`/`metadata`および`VERIFIED_OCR_SNAPSHOT.json`自体は変更されない。
反映前に`editable/backups/..._before_content_brushup.json`へバックアップを作成する。

本文が更新されると、Phase 10.12のデザインJSONが前提としていた文字量・行数と食い違う可能性が
あるため、`prepare-image-brushup`は生成時点の`lesson_pages.json`のSHA-256を
`design_manifest.json`の`source_lesson_pages_sha256`として記録するようAIエージェントへ指示し、
`render-brushup`は現在のハッシュと一致しない場合（本文更新後に古いデザインJSONのまま等）は
描画を拒否する。

## 教材画像ブラッシュアップ生成（`prepare-image-brushup` / `render-brushup`。Phase 10.12）

`rendered/`（前節）は`source_image`があれば元画像をそのままコピーするだけであり、「ブラッシュアップ済み
教材画像」ではない。確定済み本文（`editable/lesson_pages.json`）と元画像の視覚情報を使って実際に
見た目を再設計した画像を生成するのが本機能で、`rendered/`とは別の出力先（`rendered_brushup/`）を使う。
3段階の導線（`prepare-image-brushup`→AI作業エージェントによるデザイン設計→`render-brushup`）の詳細は
[`docs/17_image_brushup_workflow.md`](17_image_brushup_workflow.md)を参照。

```text
output/<output-dir>/
  brushup_design/
    AI_IMAGE_BRUSHUP.md      # prepare-image-brushupが生成するAIエージェント向けデザイン指示書
    README.md                 # brushup_design/の説明（prepare-image-brushupが生成）
    pages/page_NNN.json       # ページ別デザインJSON（指示書を実行したAIエージェントが作成）
    progress.json              # 進捗（同上）
    design_manifest.json       # 全ページの集約manifest（同上）
    render_report.json/.md     # render-brushupが生成する結果レポート
    comparison.html            # 元画像とブラッシュアップ画像の比較確認用の自己完結HTML
  rendered_brushup/
    page_NNN.png               # ブラッシュアップ済み完成画像（render-brushupが生成）
```

デザインJSONは教材本文を複製しない。各ブロックは`source_field`（`title`/`body`/`summary`のいずれか）で
`lesson_pages.json`の値を参照するだけで、`render-brushup`が実際の描画時に本文をそのまま取得する
（`title`/`summary`はそのまま、`body`は既存の`clean_dialogue_lines()`で話者・台詞ペアへ分解した各行を
段落として描画）。任意コード・任意HTML・任意CSS・任意PythonをデザインJSONへ埋め込む設計にはなっておらず、
`schema_version`/`page_no`/`source_image`（パストラバーサル・絶対パス拒否）/`canvas`/`theme`/
`template`（許可値のみ）/`blocks`（許可type・許可source_fieldのみ）を検証してから描画する。

各ブロックは`line_range`（`source_field`の段落の一部だけを参照。既存行の並べ替え・複製ではない）と、
`columns: 2`時の`split_at`（列の分割位置を意味区切りで明示）・`column_ratio`（左右の幅配分。既定
0.5均等）を指定できる。元画像で強調されている部分（大きく太字の問いかけ等）と補足説明・注記とで
文字サイズ・太さ・箱の有無を変えて情報階層を再現するために使う。文字サイズを分けたいが背景は
1枚のカードにまとめたい場合は`type: "group"`（複数の子ブロックを1つの共有背景の中へ積み重ねる）
を使う（実データレビューで、この使い分けをしないと「レイアウト崩しにしかならない」「本文の一部が
本文の外に浮いて見える」という指摘を受けたための追加。詳細は
[`docs/17_image_brushup_workflow.md`](17_image_brushup_workflow.md)「5.7 実データレビューで
判明した設計ルール」参照）。

本文が指定文字サイズで収まらない場合、余白縮小→行間縮小→最小フォントサイズまでの縮小→（bodyブロックに
限り）2段組みへの変更、の順に調整し、それでも収まらない場合は本文を省略・打ち切りせずページを失敗として
扱う（`render_report.json`/`.md`に理由を記録し、コマンド全体を非ゼロ終了する）。生成画像が元画像の
単純コピーでないことをファイルハッシュ・ピクセルデータ比較で機械的に確認する。**`editable/lesson_pages.json`・
元画像・`assets/`・既存の`rendered/`はいずれも変更しない。**

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
出力ファイル: **`output/exports/material.md`（正式。`--output-format md`/`all`指定時）**、または`output/compat/brushup.md`（後方互換出力。「正式outputと後方互換output」参照）。個別CLI（`generate`コマンド）を直接使う場合は任意の出力パスを指定できる（開発者向け経路）。

`lesson_pages.json`の`page_no`/`title`/`body`/`summary`から生成する（生成関数自体は`src/renderer.py`の`render_brushup()`で、書き出し先が正式output/後方互換outputで異なるだけで内容は同じ）。

構成:
1. 表紙
2. 全体方針
3. ページ別概要（`summary`。表示時のみMarkdown記法を除去。後述）
4. ページ別本文（`body`を話者ごとに整形。`body`自体の見出し記法は保持する）

## Canva向け設計書
出力ファイル: **`output/canva/canva_design.md`（正式。`--output-format canva`/`all`指定時）**、または`output/compat/canva_design.md`（後方互換出力。「完成outputの形式選択とeditable中間ファイル（Phase 9）」の「正式outputと後方互換output」参照）

**Canva指示書は数ある完成outputの選択肢の一つであり、主outputではない。** 内容自体は`lesson_pages.json`の`page_no`/`title`/`summary`/`image_text`/`layout_instruction`/`canva_prompt`/`source_image`/`source_assets`から生成する点は変わらない。

構成:
1. 全体デザインルール
2. ページ見出し直下の元画像参照（`source_image`が空でなければ「元画像: {source_image}」、`source_assets`が空でなければ「参考画像: {source_assets}」を明記。Canva設計時にどの元画像・元スライド画像を参照すべきかが分かるようにするため）
3. ページ別概要（`summary`。表示時のみMarkdown記法を除去。後述）
4. ページ別画像内テキスト（`image_text`。表示時のみMarkdown記法を除去。後述）
5. ページ別レイアウト指示（`layout_instruction`。表示時のみMarkdown記法を除去。後述）
6. Canva AI投入用プロンプト（`canva_prompt`。原文のまま、対象外）

### Markdownとして解釈される出力でのMarkdown記法除去（表示時のみ）

教材ブラッシュアップ設計書（`exports/material.md`・`compat/brushup.md`）/`canva_design.md`は実際にMarkdownとして解釈されるファイルであり、`layout_instruction`/`summary`/`image_text`のように**行頭から値を丸ごと1行として出力する箇所**は、値が`#`/`-`等で始まっていると本来意図しない見出しや箇条書きとして誤解釈されてしまう。これを防ぐため、以下の3箇所は表示直前にのみ行頭のMarkdown見出し記法（`#`/`##`/`###`）・箇条書き記法（`-`/`*`、直後に空白があるもののみ）を取り除く。

| 出力 | 対象セクション | 対象フィールド | クリーニング関数 |
|---|---|---|---|
| `canva_design.md` | ### レイアウト指示 | `layout_instruction` | `canva_renderer._clean_canva_free_text()` |
| `canva_design.md` | ### 概要 | `summary` | `canva_renderer._clean_canva_free_text()` |
| `canva_design.md` | ### 画像内テキスト | `image_text`（`body`が空で`summary`にフォールバックする場合を含む） | `canva_renderer._clean_canva_free_text()` |
| 教材ブラッシュアップ設計書（`exports/material.md`・`compat/brushup.md`） | ### 概要 | `summary` | `renderer._clean_summary_for_display()` |

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
出力ファイル: **`output/exports/material.docx`（正式。`--output-format docx`/`all`指定時）**、または`output/compat/brushup.docx`（後方互換出力）。個別CLI（`docx`コマンド）を直接使う場合は任意の出力パスを指定できる（開発者向け経路）。

`lesson_pages.json`から教材ブラッシュアップ設計書と同じ内容（表紙・全体方針・ページ別概要/本文）をWord文書として出力する。

## PDF教材
出力ファイル: **`output/exports/material.pdf`（正式。`--output-format pdf`/`all`指定時）**、または`output/compat/brushup.pdf`（後方互換出力）。個別CLI（`pdf`コマンド）を直接使う場合は任意の出力パスを指定できる（開発者向け経路）。

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
