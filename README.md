# AI教材ブラッシュアップシステム 実装プロジェクト一式

> 詳細な設計・仕様ドキュメントは`docs/`配下にあります。まず[`docs/README.md`](docs/README.md)を見てください（後述「ドキュメント構成」節も参照）。

## 目的
既存教材の画像・テキストを読み取り、学習者に伝わりやすい教材へブラッシュアップする。あわせてCanva等で再現しやすい画像設計書・ページ別レイアウト指示を生成する。

## プロジェクト方針：外部API非依存・ローカルLLM移行前提

本プロジェクトでは、当面はOpenAI API、Gamma API、Canva APIなどの外部API連携を前提にしない。

まずはChatGPT、Claude Code、Canva、Gammaなどの既存サブスク製品と、ローカルツール（このリポジトリのCLI）を組み合わせ、手作業を含めて実用可能な教材ブラッシュアップ運用を作ることを優先する。

ここでいう将来的なLLM活用は、ChatGPTやClaudeの画面操作・コピペ運用を増やすことではなく、**ローカルLLMを学習・検証し、教材ブラッシュアップ処理の一部をプロジェクト内に組み込んでいくこと**を指す。ChatGPT・Claude Code・Canva・Gammaはいずれも製品名として扱い、「LLM」という言葉の総称的な言い換えとしては使わない。

将来的には、ChatGPTに任せようとしていた教材の要約・章立て整理・本文ブラッシュアップ・スライド構成案作成・Canva/Gamma向けレイアウト指示作成等の処理を、段階的にローカルLLMへ置き換える。一方で、教材内容の最終判断・元資料との正確性確認・画像の意味解釈・販売/納品品質の判断・Canva/Gammaへの最終反映やデザイン調整・完成物のレビューは、当面は人が行う前提とする。

外部API化は目的ではなく、ローカルLLMでは対応が難しい場合に検討する将来の選択肢とする。収益化の状況を理由に外部API化を判断することはしない。

詳細な設計方針は[`docs/07_api_integration_design.md`](docs/07_api_integration_design.md)を参照。

## 想定成果物
- 完成画像（配布・確認用。教材ページに限らず、チラシ・SNS投稿画像・案内資料等にも対応）
- PDF/PowerPoint(PPTX)/Word(DOCX)/Markdown形式の完成教材
- Canva画像生成用プロンプト（数ある完成output形式の一つ。主outputではない）
- 再生成用の編集可能な中間ファイル（`output/editable/lesson_pages.json`）
- 台詞・状況説明者・登場人物別の文字起こし
- 教材全体の構成改善案
- Claude Codeで拡張可能なCLI雛形

## クイックスタート（作成者向け）: 元資料を置いて一括生成する

**教材の作成者は、JSON・Markdown・TXTを手作業で作る必要はありません。** 元資料（画像・PDF・PPTX）を`input/source/`に置いて`build-all`コマンドを実行するだけで、完成outputと再生成用の中間ファイルが自動生成されます。

```bash
mkdir -p input/source
cp ~/教材素材/*.png input/source/   # 画像・PDF・PPTXをファイル名順に置く

python3 -m src.cli build-all --input input/source --mode proofread --output-dir output
```

**重要な考え方: 完成画像やPDFを直接編集するのではなく、`output/editable/lesson_pages.json`（中間ファイル）を編集して再生成します。** 内部では「元資料からのテキスト・画像自動取り込み（`import-source`）→正データ生成（`lesson-pages`）→完成output生成」が自動的に実行され、`output/editable/lesson_pages.json`（編集対象）と、`output/rendered/`（完成画像）を中心とした成果物一式が生成されます。

完成outputの形式は`--output-format`で選べます（既定は`same`＝入力の性質に合わせる）。

```bash
# 完成画像として出力する（既定。画像入力の場合はこれと同じ）
python3 -m src.cli build-all --input input/source --output-dir output --output-format image

# PDF/PPTX/DOCX/Markdown/Canva指示書/中間ファイルのみ/すべて、から選べる
python3 -m src.cli build-all --input input/source --output-dir output --output-format pdf
python3 -m src.cli build-all --input input/source --output-dir output --output-format all
```

`output/editable/lesson_pages.json`を編集した後は、`regenerate`コマンドで完成outputを作り直せます。

```bash
python3 -m src.cli regenerate --input output/editable/lesson_pages.json --output-format image
```

詳しい手順・出力形式一覧・確認観点は[`docs/08_user_acceptance_test.md`](docs/08_user_acceptance_test.md)を参照してください。

**元資料が無い場合（新規構築）は`build-all`ではなく`generate`モードを使ってください。** `input/source/`に置く画像・PDF・PPTXが無い状態から、要件定義（`requirements.json`）だけで教材のたたき台を新規生成したい場合は、後述「`lesson-pages`の3モード（v2.0）」の`generate`モードを参照してください（`build-all`は`proofread`/`restructure`専用で、元資料を前提とするため`generate`には対応していません）。

| やりたいこと | 使うもの |
|---|---|
| 元資料（画像/PDF/PPTX）がある。趣旨を変えずに整えたい／教材として再構成したい | `build-all --mode proofread` または `build-all --mode restructure` |
| 元資料が無い。要件定義だけから新規に教材のたたき台を作りたい | `lesson-pages --mode generate --requirements ...` → `generate`/`canva`等の個別コマンド |

以下の「データの正・派生関係」以降は、`lesson_pages.json`のスキーマや個別コマンドの詳細（主に開発者・拡張作業向け）です。

## データの正・派生関係（重要）

**`lesson_pages.json` がこのシステムの正データ（Single Source of Truth）です。**
`brushup.md` / `canva_design.md` / DOCX / PDF / 動画生成用シナリオは、いずれも`lesson_pages.json`から派生生成される出力物であり、それ自体を直接編集して正データとして扱ってはいけません。

以前のバージョンでは`brushup.md`（原稿）と`canva_design.md`（画像設計）がそれぞれ入力JSONから個別に生成されており、片方だけ修正すると原稿と画像設計の間に内容の乖離が生まれる問題がありました。この問題を解消するため、両方を同じ`lesson_pages.json`のページデータから生成する構成に変更しています。

`lesson_pages.json`の各ページは以下の項目を持ちます。

| 項目 | 内容 | 使用される出力 |
|---|---|---|
| `page_no` | ページ番号 | 全出力 |
| `title` | ページタイトル | brushup.md / canva_design.md |
| `body` | 原稿本文（「話者: 台詞」形式の複数行文字列。ここが編集対象） | brushup.md / DOCX / PDF / 動画シナリオ |
| `summary` | ページ概要 | brushup.md / canva_design.md |
| `image_text` | 画像内に配置するテキスト（`body`から自動算出） | canva_design.md |
| `layout_instruction` | レイアウト配置指示 | canva_design.md / 動画シナリオ |
| `canva_prompt` | Canva AI投入用プロンプト（`title`/`summary`/`body`/`layout_instruction`から自動算出） | canva_design.md |
| `video_scene` | 動画シーン説明（`body`/`layout_instruction`/`notes`から自動算出） | （参考情報として保持） |
| `source_image` | 元画像ファイル名 | 動画シナリオ / WordPress連携（任意機能） |
| `notes` | 補足指示 | 動画シナリオ |

`image_text` / `canva_prompt` / `video_scene` は`title`/`body`/`summary`/`layout_instruction`/`notes`から**都度自動算出**される値です。`body`（原稿）を書き換えて再生成すれば、`image_text`や`canva_prompt`も自動的に同期されるため、原稿と画像設計が食い違うことはありません。

`lesson_pages.json`のトップレベルは`metadata`（`project_title`/`mode`/`source_policy`/`target_audience`/`tone`/`generated_at`/`requirements_source`）と`pages`から構成されます。各ページは`source_page_no`（生成元の元ページ番号の**配列**。1ページ由来でも`[1]`のように配列にする。`generate`モードでは`[]`）と`role`（`intro`/`explanation`/`practice`/`summary`など。`proofread`では基本空文字）を持ち、どの元ページから作られたかを追跡できます。

**`source_page_no`/`role`は内部管理情報であり、配布用のPDF/DOCXには表示されません。**（`brushup.md`/`canva_design.md`/DOCX/PDF/動画シナリオのいずれのレンダラーも参照しない。制作者が確認したい場合は後述の`review-report`コマンドを使う。）

## `lesson-pages`の3モード（v2.0）

`lesson-pages`コマンドは、元ファイルをどこまで尊重するかによって3つのモードを持ちます。`--mode`省略時は`proofread`になります。

| mode | 日本語名 | 用途 | `--input` | `--requirements` |
|---|---|---|---|---|
| `proofread` | 校正・整形 | 元ファイルを神として、内容・構成・ページ順を維持したまま表現を整える | 必須 | 任意 |
| `restructure` | 再構成 | 元ファイルの主旨・約束する価値は維持しつつ、教材として作り直す | 必須 | 任意（対象者・トーンを反映するため推奨） |
| `generate` | 新規生成 | 元ファイルなしで、要件定義から教材のたたき台を新規生成する | 不要 | 必須 |

```bash
# proofread: 既存教材をできるだけ変えずに整える
python3 -m src.cli lesson-pages --mode proofread \
  --input examples/sample_pages.json \
  --output output/lesson_pages.json

# restructure: 主旨は維持しつつ、要件定義に合わせて再構成する
python3 -m src.cli lesson-pages --mode restructure \
  --input examples/sample_pages.json \
  --requirements examples/requirements_ai_instagram.json \
  --output output/lesson_pages.json

# generate: 要件定義だけから教材のたたき台を新規生成する（--inputは不要）
python3 -m src.cli lesson-pages --mode generate \
  --requirements examples/requirements_ai_instagram.json \
  --output output/lesson_pages.json
```

`generate`は外部LLM APIを使わないルールベースの骨子生成（`requirements.json`の`must_include`から1ページずつ、導入ページ・まとめページを加えたたたき台）であり、本文は人が仕上げる前提です。実際の高度な本文生成は、生成された`lesson_pages.json`を人が編集するか、将来的にはローカルLLMの組み込みで行う想定です（プロジェクト方針は「プロジェクト方針：外部API非依存・ローカルLLM移行前提」節、設計は[`docs/07_api_integration_design.md`](docs/07_api_integration_design.md)参照）。

`requirements.json`の形式は[`examples/requirements_ai_instagram.json`](examples/requirements_ai_instagram.json)を参照してください（`theme`/`target_audience`/`goal`/`reader_problem`/`promised_value`/`tone`/`page_count`/`output_style`/`must_include`/`must_not_include`）。

**`page_count`は現状バリデーションのみ行い、`restructure`/`generate`のページ数制御には使用しません（将来拡張用のフィールドです）。** 指定しても`restructure`/`generate`の出力ページ数には反映されないので注意してください。

### `restructure`の再構成ロジック

`restructure`は、元ページを**素材として**扱い（＝「元ファイルを神とする」`proofread`とは異なる）、以下のルールベース処理で元ページ数と異なるページ構成を組み立てます（外部LLM APIは使わない）。

1. 各元ページから中間表現（`title`/`summary`/`key_points`/`raw_text`）を抽出する。
2. 本文が短いページ（目安30文字未満）は「内容が薄いページ」とみなし、直後のページへ統合する（`operation: merge`）。
3. 本文が長すぎるページ（目安200文字超）は、句点位置で前半・後半に分割する（`operation: split_first_half` / `split_second_half`。両ページとも同じ`source_page_no`を持つ）。
4. 上記のいずれにも該当しないページはそのまま1ページとして引き継ぐ（`operation: carry_over`）。
5. 先頭に導入ページ（`role: intro`、`operation: add_intro_from_source`）、末尾に実践ページ（`role: practice`）とまとめページ（`role: summary`）を必ず追加する。

処理は「再構成プラン」（構造のみ）→「本文の組み立て」の2段階で行われ、プランは`--plan-output`で確認できます。

```bash
python3 -m src.cli lesson-pages --mode restructure \
  --input examples/sample_pages.json \
  --requirements examples/requirements_ai_instagram.json \
  --output output/lesson_pages.json \
  --plan-output output/restructure_plan.json
```

`restructure_plan.json`の形式:

```json
{
  "mode": "restructure",
  "strategy": "元教材の主旨を維持しつつ、初心者向けに導入・実践・まとめを追加する",
  "pages": [
    {"new_page_no": 1, "role": "intro", "title": "この教材でできるようになること", "source_page_no": [1], "operation": "add_intro_from_source"},
    {"new_page_no": 2, "role": "explanation", "title": "AIとは / ChatGPTとは", "source_page_no": [1, 2], "operation": "merge"}
  ]
}
```

なお、現段階の再構成は本文の言い回しまでは作り直さず、統合・分割・導入/実践/まとめの追加という**構造レベルの再構成**にとどまります。本文表現の作り込みは人による編集、または将来的にはローカルLLMの組み込みを想定しています。

### 制作者確認用レポート（`review-report`）

`source_page_no`/`role`はPDF/DOCXなどの配布物には表示されませんが、「どのページがどの元ページ由来か」を制作者が確認したい場合は`review-report`コマンドでMarkdownレポートを出力できます。

```bash
python3 -m src.cli review-report --input output/lesson_pages.json --output output/review_report.md
```

### 基本的な使い方（推奨フロー・必ずこの順序で使うこと）

**このセクションは開発者・拡張作業向けです。教材の作成者は前述「クイックスタート（作成者向け）」の`build-all`を使ってください。** ここで示す個別コマンドの直接実行は、`build-all`が内部で何を行っているかを理解する場合や、途中結果（`lesson_pages.json`）を手直ししてから再生成する場合に使います。

**`generate`/`canva`/`docx`/`pdf`/`scenario`の`--input`には、必ず`lesson_pages.json`（`lesson-pages`コマンドの出力）を指定してください。** `examples/sample_pages.json`のような従来の`pages`形式JSONを直接指定することも技術的には可能です（自動判定により動作します）が、それは動作確認・簡易テスト用の後方互換であり、**通常の利用では推奨しません**。`pages`形式を直接使うと、`lesson_pages.json`を経由しないため「原稿を直したのに画像設計に反映されていない」といった、この設計変更が解消しようとした乖離が再発する可能性があります。

```bash
# 1. 元データ(pages形式JSON)から正データ lesson_pages.json を生成する
python3 -m src.cli lesson-pages --input examples/sample_pages.json --output output/lesson_pages.json

# 2. 必要であれば output/lesson_pages.json の body/summary/layout_instruction/notes を直接編集する
#    （編集後に3を実行すれば、image_text/canva_prompt/video_sceneは自動的に再同期される）

# 3. 以降の成果物は必ず lesson_pages.json から生成する
#    （brushup.mdとcanva_design.mdが同じページデータに由来するため、ページ番号・タイトルが常に一致する）
python3 -m src.cli generate --input output/lesson_pages.json --output output/brushup.md
python3 -m src.cli canva --input output/lesson_pages.json --output output/canva_design.md
python3 -m src.cli docx --input output/lesson_pages.json --output output/brushup.docx
python3 -m src.cli pdf --input output/lesson_pages.json --output output/brushup.pdf
python3 -m src.cli scenario --input output/lesson_pages.json --output-dir output/scenario
```

このフローは`scripts/run_sample.sh`としてそのまま実行できる（後述）。

## `input/` と `output/` の扱い（Git・ZIP対象外）

`input/`（利用者が投入する元ファイル置き場）と`output/`（実行結果の生成物置き場）は、**通常Git管理せず、レビュー・配布ZIPにも含めません**。理由は、利用者固有のデータ（実在の教材原稿・画像等）が誤ってリポジトリや配布物に混入するのを防ぐためです。

- サンプル入力が必要な場合は `examples/`（本リポジトリ）に置く。
- 動作確認は、上記「基本的な使い方」のコマンドで `output/` をその場で再生成して行う（`output/`配下は`.gitignore`対象。再生成すればいつでも復元できる）。
- 配布ZIPを作る場合は `bash scripts/make_release_zip.sh` を使う（`input/`/`output/`/`.git/`/`__pycache__/`/`.pytest_cache/`/`.DS_Store`等を自動的に除外する）。

### 既に `input/` / `output/` がGit管理対象に入っている場合

本リポジトリでは`output/brushup.md`・`output/canva_design.md`が過去にGit管理対象へ入っていました。以下の手順でGit管理から外してください（ローカルのファイル自体は削除されません）。

```bash
git rm -r --cached input output
git add .gitignore
git commit -m "chore: input/outputディレクトリをGit管理対象から除外"
```

実行後、`git status`で`input/`・`output/`が追跡対象から外れたことを確認してください。

## 必須機能・任意機能

**Canva API連携（`canva-sync`）・WordPress投稿連携（`wp-publish`）は任意機能です。** `.env`に認証情報を設定していなくても、以下の本体機能（必須機能）はすべて正常に動作します。

| 区分 | コマンド | `.env`未設定時の挙動 |
|---|---|---|
| **必須機能** | `lesson-pages`（正データ`lesson_pages.json`の生成） | 常に動作 |
| **必須機能** | `generate`（教材ブラッシュアップMarkdown） | 常に動作（Canva/WordPressの設定に一切依存しない） |
| **必須機能** | `canva`（Canva向けレイアウト設計書Markdown） | 常に動作（Canva APIは呼び出さない。テキストのみのローカル生成） |
| **必須機能** | `docx`（Word教材） | 常に動作 |
| **必須機能** | `pdf`（PDF教材） | 常に動作 |
| **必須機能** | `scenario`（動画生成用シナリオ4形式） | 常に動作 |
| **任意機能** | `canva-sync`（Canva APIでのデザイン作成） | `CANVA_API_KEY`未設定なら自動的にモック動作（エラー終了せず、モックである旨をレポートJSONと標準エラー出力の両方に明示） |
| **任意機能** | `wp-publish`（WordPressへの記事投稿） | `WP_URL`/`WP_USERNAME`/`WP_APP_PASSWORD`のいずれか未設定なら自動的にモック動作（同上） |

任意機能は、認証情報が`.env`に設定されている場合のみ実際のAPIを呼び出します。未設定の場合は例外を送出せず、モック動作（仮のID・URLを返す）に自動的に切り替わります。

`canva-sync`/`wp-publish`は他の必須機能と同じく、`--input`に`lesson_pages.json`形式・従来の`pages`形式のどちらを渡しても自動判定して動作する。ただし`lesson_pages.json`には`improvement_points`に相当する項目が無いため、その内容は連携結果（Canvaデザイン・WordPress記事本文）には反映されない点に注意すること。

## 動作要件

**Python: 推奨バージョンと動作確認バージョンを分けて記載します。**

- **推奨: Python 3.11以上**（`pyproject.toml`の`requires-python`もこれに合わせている。開発・レビューはこのバージョン以降を前提とする）
- **動作確認: Python 3.9.6でもpytest全件(377件)が通ることを確認済み**（`src/`内の`str | Path`等のPEP604構文は、全ファイルに`from __future__ import annotations`を付与済みのため、型注釈の評価が遅延され3.9でも動作する）
- 上記の通り3.9でも動作はするが、`pyproject.toml`の`requires-python`は3.11以上のままにしている（`pip install -e .`は3.11未満の環境では拒否される）。3.11未満の環境で試す場合は、`pip install -e .`を使わず`python3 -m pip install python-docx reportlab requests pillow pytesseract pymupdf python-pptx pytest`のように依存関係を直接インストールすることで動作させられる（未サポート・自己責任の扱い）。

その他の要件:
- `python-docx`（DOCX出力）・`reportlab`（PDF出力）・`requests`（Canva/WordPress連携）・`Pillow`/`pytesseract`（画像取り込み・OCR）・`pymupdf`（PDF取り込み）・`python-pptx`（PPTX取り込み）（`pip install -e .`で自動インストールされる）
- **OCR（画像からのテキスト抽出）にはOS側にtesseract本体・日本語言語データのインストールが必要です**（例: macOSなら`brew install tesseract tesseract-lang`）。`pytesseract`はtesseract本体を呼び出すPythonラッパーであり、`pip install`だけでは実際のOCRは動作しません。**`build-all --mode proofread`/`restructure`は、画像inputでOCRが実質使えない場合（Tesseract未導入・日本語言語データ無し・全ページOCR結果が空のいずれか）、警告のうえ空データのまま成功させるのではなく、分かりやすいエラーを表示してエラー終了（`exit 1`）します**（一部ページのみ空の場合は警告のみで継続）。環境を診断するには以下を実行してください。

  ```bash
  python3 -m src.cli check-ocr
  # または
  bash scripts/check_ocr_env.sh
  ```

  Apple SiliconでHomebrewは入っているがPATHに無い場合は`eval "$(/opt/homebrew/bin/brew shellenv)"`、Intel Macでは`eval "$(/usr/local/bin/brew shellenv)"`を実行してから`brew install tesseract tesseract-lang`を行ってください（永続化する場合は`~/.zprofile`に追記。詳細は`docs/04_output_spec.md`「OCR前提の事前チェック（Phase 10.1）」参照）。テスト・開発用途でどうしても空のOCR結果のまま処理を続けたい場合は`--allow-empty-ocr`を指定できます（既定では無効＝エラー終了）。単体の`import-source`コマンド（`build-all`を経由しない）は、テキスト抽出専用コマンドのため、OCRが使えない場合も従来通り警告のみで処理を継続します。
- PDF内の日本語はreportlab内蔵のCIDフォント（HeiseiKakuGo-W5）を使用しており、外部フォントファイルは不要
- Canva連携・WordPress連携は**任意機能**（「モック付き連携雛形」。`.env`に認証情報が未設定なら自動でモック動作し、本体機能には一切影響しない。実APIキー・実サイトでの疎通確認は未実施）
- テスト実行には `pytest` が必要（下記セットアップ参照）

推奨バージョン（3.11以上）を用意したい場合は、[pyenv](https://github.com/pyenv/pyenv) 等でインストールしてください。

## セットアップ

```bash
cd ai_kyouzai_brushup_project
python3 --version   # 3.11以上であることを確認
python3 -m pip install -e ".[dev]"   # pytestを含む開発用依存関係をインストール
```

## 使い方

作成者は以下ではなく、前述「クイックスタート（作成者向け）」の`build-all`を使ってください。以下は開発者・拡張作業向けに、個別コマンドの使い方を示します（いずれも`--input`に`output/lesson_pages.json`を指定する前提で記載する）。個別コマンドは`--output`に任意のパスを指定できるため、以下の例では分かりやすさのため`output/brushup.md`等のシンプルなパスを使うが、これは`build-all`が正式outputとして生成する`output/exports/material.md`等とは別物である（`build-all`の正式output/後方互換outputの構成は「ディレクトリ構成」節、[`docs/04_output_spec.md`](docs/04_output_spec.md)を参照）。

### 元資料（画像/PDF/PPTX）からimported_pages.jsonを生成

```bash
python3 -m src.cli import-source --input input/source --output output/imported_pages.json
```

`input`にディレクトリを指定すると配下の画像（`.png`/`.jpg`/`.jpeg`/`.webp`）をファイル名順に取り込みます。単一の画像ファイル・`.pdf`・`.pptx`を直接指定することもできます。画像アセットは`--output`と同階層の`assets/`（例: `output/assets/`）に保存されます。出力される`imported_pages.json`は、そのまま`lesson-pages`の`--input`に渡せる`pages`形式互換のJSONです。

### 元資料から成果物一式を一括生成（`build-all`）

```bash
python3 -m src.cli build-all --input input/source --mode proofread --output-dir output --output-format image
```

`import-source` → `lesson-pages` → 完成output生成を内部で順に実行します。`--mode`は`proofread`/`restructure`、`--requirements`は`restructure`時のみ任意で指定できます。

`--output-format`は`same`（既定。入力の性質に合わせる）/`image`/`pdf`/`pptx`/`docx`/`md`/`canva`/`json`/`all`から選べます。指定に関わらず、再生成用の中間ファイル`output/editable/lesson_pages.json`は常に生成されます。**正式な編集対象は`output/editable/lesson_pages.json`のみ、正式なCanva指示書は`output/canva/canva_design.md`のみです**（Phase 8互換の同名ファイルは`output/compat/`配下にまとめられ、`output_dir`直下には重複生成しません。互換出力自体が不要な場合は`--no-compat-output`を指定してください）。詳細は[`docs/04_output_spec.md`](docs/04_output_spec.md)「完成outputの形式選択とeditable中間ファイル（Phase 9）」を参照してください。

### editable中間ファイルから再生成（`regenerate`）

```bash
python3 -m src.cli regenerate --input output/editable/lesson_pages.json --output-format image
```

`output/editable/lesson_pages.json`を編集した後、完成outputを作り直すためのコマンドです。完成画像・PDF・PPTX・DOCXを直接編集するのではなく、この中間ファイルを編集して再生成してください。`--output-dir`を省略すると、`--input`の2階層上（例: `output/editable/lesson_pages.json`→`output/`）が出力先になります。

`source_image`が無いページの画像output（`generate`モード等）で日本語が文字化けする場合は、`--font-path`で日本語対応フォントを指定してください（`build-all`・`regenerate`どちらでも指定可能。未検出時は黙って文字化けさせず警告を表示します）。

```bash
python3 -m src.cli regenerate --input output/editable/lesson_pages.json --output-format image --font-path /path/to/font.ttc
```

`output/editable/lesson_pages.json`の編集してよい項目・編集しない方がよい項目、`regenerate`の具体例一覧は[`docs/09_editable_regenerate_guide.md`](docs/09_editable_regenerate_guide.md)を参照してください。

### LLM手作業投入用ファイルを生成（`llm-handoff`）

```bash
python3 -m src.cli llm-handoff --input output/editable/lesson_pages.json --output output/llm_handoff.md
```

`editable/lesson_pages.json`の内容とプロンプト指示を1つのMarkdownにまとめ、人間がChatGPT/Claude等へ手作業で貼り付けて構成チェック・文章改善案を得るためのコマンドです（**LLM出力の自動取り込みは行いません**。改善案を見ながら`editable/lesson_pages.json`を手編集し、`regenerate`で再出力してください）。使い方・貼り付け手順の詳細は[`docs/11_llm_handoff_workflow.md`](docs/11_llm_handoff_workflow.md)を参照してください。

### 正データ lesson_pages.json を生成

```bash
python3 -m src.cli lesson-pages --mode proofread --input examples/sample_pages.json --output output/lesson_pages.json
```

`--mode`は`proofread`（デフォルト）/ `restructure` / `generate`から選べます。詳細は上記「`lesson-pages`の3モード（v2.0）」を参照してください。

### ブラッシュアップ設計書を生成

```bash
python3 -m src.cli generate --input output/lesson_pages.json --output output/brushup.md
```

### Canva向け設計書を生成

```bash
python3 -m src.cli canva --input output/lesson_pages.json --output output/canva_design.md
```

### Word教材(docx)を生成

```bash
python3 -m src.cli docx --input output/lesson_pages.json --output output/brushup.docx
```

### PDF教材を生成

```bash
python3 -m src.cli pdf --input output/lesson_pages.json --output output/brushup.pdf
```

生成後は、以下の手順で**日本語表示が文字化けしていないことを目視確認**することを推奨する（`pdftotext`等のテキスト抽出ツールでの自動検証は環境依存のため未実施）。

```bash
open output/brushup.pdf   # macOS: Preview.appで開く
```

確認ポイント:
- タイトル・見出し（Page N: ...、概要、本文）が日本語として正しく表示されているか
- 台詞テキストや話者名（状況説明者・まじょこ・その他等）が文字化け・トーフ（□）表示になっていないか
- ページ全体のレイアウトが崩れていないか

### 動画生成用シナリオ一式を生成（JSON/Markdown/VOICEVOX/シーン分割JSON）

```bash
python3 -m src.cli scenario --input output/lesson_pages.json --output-dir output/scenario
```

`output-dir`配下に `scenario.json` / `scenario.md` / `voicevox.txt` / `scene.json` の4ファイルを生成する。詳細は [`docs/04_output_spec.md`](docs/04_output_spec.md) を参照。

### 【任意機能】Canva連携（デザイン作成）※モック付き連携雛形

`canva-sync`は`lesson_pages.json`と従来の`pages`形式の**両方を自動判定して受け付ける**（`generate`等と同じ判定ロジック。内部で`lesson_pages.json`をProjectへ変換して処理する）。ただし`lesson_pages.json`には`improvement_points`に相当する項目が無いため、その内容は連携結果に反映されない。

```bash
cp .env.example .env   # CANVA_API_KEYを設定する場合（設定しなくても他の機能には影響しません）
python3 -m src.cli canva-sync --input output/lesson_pages.json --output output/canva_sync_report.json
```

`.env`に`CANVA_API_KEY`を設定していない場合は自動的にモック動作となり、エラーにはならず`mock-design-N`という仮のデザインIDを含むレポートを出力する（標準エラー出力にも「未設定のためモック動作」である旨を表示し、レポートJSONにも`note`として明記する）。

**重要（未対応事項）**: 本実装は`.env`の`CANVA_API_KEY`を単純に`Authorization: Bearer <key>`ヘッダーとして送る簡易方式であり、Canva Connect APIが実際に要求するOAuth2/PKCE（認可コードフロー・アクセストークンの発行と有効期限管理）には対応していない。実際のCanva環境でそのまま動作することは確認しておらず、本番利用にはOAuth2/PKCE対応の追加実装が必要（詳細は[`docs/99_implementation_review_brief.md`](docs/99_implementation_review_brief.md)を参照）。

### 【任意機能】WordPress投稿連携（画像アップロード〜アイキャッチ設定）※モック付き連携雛形

`wp-publish`も`canva-sync`と同様に、`lesson_pages.json`と従来の`pages`形式の**両方を自動判定して受け付ける**。`lesson_pages.json`使用時は`body`を話者・台詞に分解した内容が記事本文に、`layout_instruction`/`notes`がCanva情報相当として扱われる（`improvement_points`相当は無いため反映されない）。

```bash
cp .env.example .env   # WP_URL/WP_USERNAME/WP_APP_PASSWORDを設定する場合（設定しなくても他の機能には影響しません）
python3 -m src.cli wp-publish --input output/lesson_pages.json --output output/wp_publish_report.json \
  --categories "お知らせ,教材" --tags "まじょこ" --status draft
```

画像アップロード→記事作成→カテゴリ設定→タグ設定→アイキャッチ設定までを行う。`.env`に認証情報（`WP_URL`/`WP_USERNAME`/`WP_APP_PASSWORD`）を設定していない場合は自動的にモック動作となり、エラーにはならず仮のID・URLを含むレポートを出力する（標準エラー出力にも「未設定のためモック動作」である旨を表示し、レポートJSONにも`note`として明記する）。

**重要（未対応事項）**: WordPressのApplication Password方式によるBasic認証の実装雛形はあるが、実際のWordPressサイトに対する疎通確認（実URL・実認証情報での動作確認）は行っていない。テストはすべてHTTPリクエストをモックしたユニットテストの範囲にとどまる（詳細は[`docs/99_implementation_review_brief.md`](docs/99_implementation_review_brief.md)を参照）。

### まとめて実行（サンプル）

```bash
bash scripts/run_sample.sh
```

`examples/sample_pages.json`から`output/lesson_pages.json`を生成し、そこから`brushup.md`/`canva_design.md`/`brushup.docx`/`brushup.pdf`/`scenario/`一式までを一括生成する（上記「基本的な使い方（推奨フロー）」と同じ内容）。`examples/sample_pages_extended.json`（3話者の会話ページ・項目未設定ページを含む拡張サンプル）も用意しています。

### 入力エラー時の挙動
入力ファイルが存在しない、JSONが不正、必須項目（`page_no`など）が欠落・不正な場合は、原因が分かるメッセージを表示して終了コード1で終了します（Pythonのトレースバックは表示しません）。

```bash
$ python3 -m src.cli generate --input no_such.json --output out.md
エラー: 入力ファイルが見つかりません: no_such.json
```

## テスト

```bash
python3 -m pytest -q
```

## 実際の教材素材で試す（実利用テスト）

サンプルデータではなく、実際の教材素材（画像・PDF・PPTX）を使って生成物の品質を確認したい場合は [`docs/08_user_acceptance_test.md`](docs/08_user_acceptance_test.md) を参照してください。`input/source/`への置き方、`build-all`の実行コマンド、確認すべき順序と観点をまとめています。結果は [`docs/feedback_template.md`](docs/feedback_template.md) をコピーして記録できます。**実際の教材素材・生成物は`input/`/`output/`配下に置き、Gitにコミットしないでください**（`.gitignore`で除外済み）。

## ドキュメント構成

より詳しい設計・仕様は`docs/`配下にまとまっています。**まず[`docs/README.md`](docs/README.md)（docs配下の全文書の役割一覧）を見て、次に`docs/01_requirements.md`→`docs/02_architecture.md`→（必要に応じて`docs/03`/`docs/04`）の順に読むと分かりやすいです。**

- 入力JSONの形式・話者分類ルールは [`docs/03_data_format.md`](docs/03_data_format.md) を参照。
- `lesson_pages.json`のスキーマ・各派生出力の生成元・CLIコマンド仕様（`--plan-output`/`review-report`等）は [`docs/04_output_spec.md`](docs/04_output_spec.md) を参照。
- Claude Codeでこのプロジェクトに取り組む場合の運用手順は [`docs/06_claude_code_workflow.md`](docs/06_claude_code_workflow.md) を参照（後述「Claude Codeで実装する場合」も参照）。
- 実装進捗（`docs/05_implementation_tasks.md`）とレビュー時点スナップショット（`docs/99_*`、既存ファイルは上書きせず追加方式）の運用ルールは [`docs/README.md`](docs/README.md) と `CLAUDE_RULES.md` を参照。

## ディレクトリ構成

`output/`配下のディレクトリ構成（`editable/`/`rendered/`/`canva/`/`exports/`/`compat/`）は、Phase 9.2までに確定したプロジェクト共通設計ルールです。詳細は[`docs/04_output_spec.md`](docs/04_output_spec.md)「プロジェクト標準output構成」、要約は[`CLAUDE_RULES.md`](CLAUDE_RULES.md)「プロジェクト設計ルール」を参照してください。

コマンド実行のたびに、プロジェクト直下の`logs/`に実行ログ（`logs/YYYYMMDD_HHMMSS_<command>.log`）が出力されます（Phase 10.2）。`logs/`ディレクトリ自体はGit管理対象ですが、ログファイル本体は`input/`/`output/`と同様にGit管理対象外です（配布用ZIPには含まれます）。**ログファイルはZIPで配布され得るため、CLI引数・stderr出力・エラー内容に含まれる`password`/`token`/`api_key`/`secret`/`authorization`等の秘密情報らしき値は、書き出し前に自動で`[REDACTED]`へマスクされます**（Phase 10.2追加修正）。詳細は[`docs/04_output_spec.md`](docs/04_output_spec.md)「実行ログ（logs/）の標準仕様」を参照してください。

```text
examples/
  sample_pages.json                    # 基本サンプル入力（proofread/restructureの--input用）
  sample_pages_extended.json           # 拡張サンプル入力（3話者会話・未設定項目）
  requirements_ai_instagram.json       # 要件定義サンプル（restructure任意/generate必須の--requirements用）
src/
  cli.py                     # CLI入口（import-source / build-all / regenerate / lesson-pages / review-report /
                              # generate / canva / docx / pdf / scenario / canva-sync / wp-publish サブコマンド）
  import_source.py           # 元資料(画像/PDF/PPTX)からのテキスト・画像自動取り込み（imported_pages.json生成）
  ocr_environment.py          # OCR環境診断（tesseract/日本語言語データ/Homebrewの有無・PATH確認）
  execution_logger.py         # CLI実行ログ(logs/YYYYMMDD_HHMMSS_<command>.log)の生成
  llm_handoff.py               # editable/lesson_pages.jsonから、ChatGPT/Claude等へ手作業で貼り付けるための
                              # Markdownを生成（LLM出力の自動取り込みは行わない。詳細はdocs/11参照）
  models.py                  # 入力(pages形式)・requirements.jsonのデータ構造・バリデーション
  lesson_pages.py             # 正データ lesson_pages.json のデータ構造・3モード(proofread/restructure/generate)の分岐・restructureの再構成プラン生成・派生フィールド算出
  parser.py                  # 入力JSON読み込み（pages形式/lesson_pages形式を自動判定）
  renderer.py                # lesson_pages.jsonからbrushup.md生成
  canva_renderer.py          # lesson_pages.jsonからcanva_design.md生成（オプション出力）
  docx_renderer.py           # lesson_pages.jsonからDOCX生成
  pdf_renderer.py            # lesson_pages.jsonからPDF生成
  image_renderer.py           # lesson_pages.jsonから完成画像(rendered/page_NNN.png)を生成（Phase 9）。
                              # 日本語フォント自動探索・--font-path対応・未検出時の警告を実装（Phase 10）
  pptx_export_renderer.py     # lesson_pages.json+完成画像からPPTX(exports/*.pptx)を生成（Phase 9）
  scenario_renderer.py       # lesson_pages.jsonから動画生成用シナリオ一式(JSON/Markdown/VOICEVOX/シーン分割JSON) 生成
  env_config.py               # .env読み込み共通ユーティリティ
  canva_client.py             # 【任意機能】Canva Connect API連携（APIキー未設定時はモック、他機能に影響なし）
  wordpress_client.py         # 【任意機能】WordPress REST API連携（認証情報未設定時はモック、他機能に影響なし）
scripts/
  run_sample.sh               # サンプル入力から一連の出力を生成するデモスクリプト
  make_release_zip.sh         # レビュー・配布用ZIPを作成（input//output/等を自動除外）
tests/                       # pytestテスト一式
input/                        # (Git管理対象外) 利用者が投入する元ファイル置き場
  source/                     # build-all/import-sourceの--input。元資料（画像/PDF/PPTX）を置く
output/                       # (Git管理対象外) 実行結果の生成物置き場。すべてシステムが生成する派生物・中間ファイル
  imported_pages.json         # import-sourceが元資料から自動生成する中間ファイル（手作業で作らない）
  assets/                     # 元画像・元ページ画像・スライド埋め込み画像
  editable/
    lesson_pages.json          # ★正式な編集対象（再生成時にユーザーが編集するのはこのファイルのみ。Phase 9）
  rendered/                    # 完成画像 page_NNN.png（--output-format image/all時、または既定[same]で画像入力時）
  canva/
    canva_design.md            # ★正式なCanva指示書（--output-format canva/all時。オプション出力）
  exports/
    material.md / material.docx / material.pdf / material.pptx
                              # ★正式な完成output（--output-format md|docx|pdf|pptx|all時。Phase 9〜9.2）
  compat/                      # Phase 8互換output。正式output（editable//canva//exports/）との重複を避けるため分離
    lesson_pages.json           # editable/lesson_pages.jsonと同内容の後方互換コピー（通常は編集・参照しない）
    canva_design.md             # canva/canva_design.mdと同内容の後方互換コピー
    brushup.md / brushup.docx / brushup.pdf
                              # exports/material.*と同内容の後方互換コピー（`--no-compat-output`で無効化可。Phase 9.2）
  scenario/ / restructure_plan.json / review_report.md
                              # 正式outputとの役割重複が無いため引き続きoutput_dir直下に生成される
prompts/                     # OCR・ブラッシュアップ・Canva用プロンプト集
archive/                      # 過去にClaude Codeへ渡した一回限りの実装指示書（実行済み・削除せず保管）
.env.example                 # Canva/WordPress連携用の環境変数サンプル
```

## 実装状況
- **Phase 1（CLI最小実装）: 完了**
- **Phase 2（品質向上）: 完了**
- **Phase 3（AI連携プロンプト整備・API連携設計）: 完了**
- **Phase 4（将来拡張）: 完了** — DOCX出力・PDF出力・動画生成用シナリオ出力（いずれも必須機能）は動作確認済み。
  **Canva連携・WordPress連携は任意機能・「モック付き連携雛形」であり、本番相当のAPI疎通確認は未実施**（未設定でも必須機能には一切影響しない。詳細は上記「必須機能・任意機能」表、下記「Canva連携」「WordPress投稿連携」の各節、[`docs/99_implementation_review_brief.md`](docs/99_implementation_review_brief.md)を参照）
- **v2.0（3モード対応）: 完了** — `lesson-pages`に`--mode proofread|restructure|generate`と`--requirements`を追加。`proofread`/`restructure`は既存の`--input`のみの呼び出しと後方互換。`restructure`/`generate`は外部LLM APIを使わないルールベースの実装であり、実際の高度な再構成・本文生成は今後の拡張課題（詳細は[`docs/00_redesign_v2.md`](docs/00_redesign_v2.md)を参照）。

詳細な進捗は [`docs/05_implementation_tasks.md`](docs/05_implementation_tasks.md) を参照してください。

## 推奨実行環境
- Python 3.11以上（動作確認バージョンは上記「動作要件」を参照。3.9.6でもpytest全件通過を確認済み）
- pip
- Git / GitHub
- Claude Code

## Claude Codeで実装する場合

最初に `CLAUDE_START_HERE.md` をClaude Codeへ読み込ませてください。

```text
CLAUDE_START_HERE.md を読んで、その指示に従ってください。
```

詳細手順は [`docs/06_claude_code_workflow.md`](docs/06_claude_code_workflow.md)、開発ルールは `CLAUDE_RULES.md` を参照してください。ドキュメント全体の見取り図は [`docs/README.md`](docs/README.md) を参照してください。
