# 08 実利用テスト・品質評価フェーズ（Phase 8〜9）

## 目的

Phase 8は「元資料自動取り込み・一括生成の実利用評価フェーズ」、Phase 9は「完成output形式選択・editable中間ファイル・画像output・再生成導線の追加」です。

作成者は元資料（画像・PDF・PPTX）を`input/source/`に置いて`build-all`コマンドを実行するだけで、システムが自動的に内部JSONと画像アセットを生成し、完成output（画像/PDF/PPTX/DOCX/Markdown/Canva指示書、いずれか選択）一式を作れます。**作成者がJSON・Markdown・TXTを手作業で作る必要はありません。**

**重要な考え方（Phase 9）: 完成画像やPDFを直接編集するのではなく、`output/editable/lesson_pages.json`（中間ファイル）を編集して再生成します。** Canva指示書は数ある完成output形式の一つであり、主outputではありません。

Phase 8〜9で対象外のもの: introの`source_page_no`拡大、3ページ以上の連鎖merge、`--plan-input`、`Requirements.page_count`の実装、ローカルLLM/外部API連携、OCR精度の高度化、PPTX exportの高度なレイアウト再現。

**本書は元資料（画像/PDF/PPTX）がある場合の手順です。元資料が無く要件定義だけから新規に教材を作りたい場合（新規構築）は、`build-all`ではなく`lesson-pages --mode generate`を使ってください（README「`lesson-pages`の3モード（v2.0）」参照）。**

---

## 1. 主導線: 元資料を置いて`build-all`を実行する

```
元資料（画像 / PDF / PPTX）
  ↓
output/imported_pages.json + output/assets/（システム自動生成）
  ↓
output/editable/lesson_pages.json（システム自動生成、proofreadまたはrestructure。再生成用の編集対象）
  ↓
output/rendered/（完成画像）/ output/exports/（PDF・PPTX・DOCX・Markdown）/ output/canva/（Canva指示書・オプション）
```

### 1.1 元資料を置く

`input/source/`ディレクトリに、元資料の画像を**ファイル名順**に並べて置きます（`input/`はGit管理対象外です）。

```bash
mkdir -p input/source
cp ~/Desktop/教材素材/*.png input/source/
```

対応形式:

| 形式 | 対応状況 |
|---|---|
| 画像（`.png`/`.jpg`/`.jpeg`/`.webp`） | 対応済み。1画像=1ページとして取り込む |
| PDF（`.pdf`） | 対応済み。1ページ=1ページとして取り込む（テキスト抽出＋ページ画像化） |
| PPTX（`.pptx`） | 対応済み（一部制限あり）。1スライド=1ページとして取り込む（テキスト抽出＋スライド内埋め込み画像の保持。スライド全体の見た目をそのまま画像化する機能は未対応） |
| PPT（`.ppt`旧形式） | 未対応。PowerPoint等で`.pptx`に変換してから使ってください |

### 1.2 `build-all`を実行する

```bash
python3 -m src.cli build-all \
  --input input/source \
  --mode proofread \
  --output-dir output \
  --output-format image
```

これだけで、取り込みから完成outputの生成までが自動的に実行されます。内部では以下の順で処理します。

1. `import-source`: 元資料からテキスト・画像を自動取り込み → `output/imported_pages.json` + `output/assets/`
2. `lesson-pages`: `output/editable/lesson_pages.json`（正データ・再生成用の編集対象）を生成
3. `--output-format`で指定した完成outputを生成（`output/rendered/`・`output/exports/`・`output/canva/`）

`--mode`は`proofread`（元資料の趣旨を維持して整形。最初はこちらを推奨）または`restructure`（教材として再構築）を指定します。`restructure`では対象読者・トーンを反映する`--requirements`を任意で指定できます。

```bash
python3 -m src.cli build-all \
  --input input/source \
  --mode restructure \
  --requirements input/requirements.json \
  --output-dir output \
  --output-format all
```

`requirements.json`の書き方は[`examples/requirements_ai_instagram.json`](../examples/requirements_ai_instagram.json)を参照してください（こちらはrequirements特有の項目のため、従来通り作成者が用意します）。

### 1.3 完成outputの形式を選ぶ（`--output-format`）

| 値 | 生成される完成output | 用途の例 |
|---|---|---|
| `same`（既定） | 入力の性質に合わせる（画像入力→`image`、PDF入力→`pdf`、PPTX入力→`pptx`） | 迷ったらこれでよい |
| `image` | `output/rendered/page_NNN.png` | チラシ・SNS投稿画像・案内資料など、完成物として画像が欲しい場合 |
| `pdf` | `output/exports/material.pdf` | PDFとして配布したい場合 |
| `pptx` | `output/exports/material.pptx` | PowerPointで手直ししたい場合 |
| `docx` | `output/exports/material.docx` | Wordで手直ししたい場合 |
| `md` | `output/exports/material.md` | Markdownで確認したい場合 |
| `canva` | `output/canva/canva_design.md` | Canvaでの再現指示が欲しい場合（オプション出力） |
| `json` | なし（`editable/lesson_pages.json`のみ） | 中間ファイルだけ欲しい・後で`regenerate`する場合 |
| `all` | 上記すべて | どの形式が使えそうか一通り見比べたい場合 |

### 1.4 元資料を差し替えて最初から作り直す（`--clean-output`）

`input/source`の元資料を差し替えて`build-all`を再実行すると、既定では前回の生成物に**上書き**されます。前回より少ないページ数（例: 52ページ→13ページ）に差し替えた場合、上書きだけでは`output/rendered/page_014.png`以降のような古いページの成果物が消えずに残り、今回の教材に存在しないページの画像・ファイルが混在してしまいます。

元資料を差し替えて最初から作り直す場合は、`--clean-output`を付けてください。

```bash
python3 -m src.cli build-all \
  --input input/source \
  --mode proofread \
  --output-dir output \
  --output-format all \
  --clean-output
```

`--clean-output`は、取り込み・生成の**前**に`output_dir`配下の既知の生成物（`assets/`・`editable/`・`compat/`・`scenario/`・`rendered/`・`exports/`・`canva/`・`imported_pages.json`・`review_report.md`・`ocr_check_report.md`・`ocr_correction_candidates.json`・`llm_handoff.md`、および`output_dir`直下に残り得るPhase 8時点の旧仕様output`lesson_pages.json`・`canva_design.md`・`brushup.md`・`brushup.docx`・`brushup.pdf`）だけを削除してから再生成します。`output_dir`配下に手作業で置いたファイル・メモ等には触れません。既定では無効（従来どおり上書きのみ）です。詳細は[`README.md`](../README.md)「元資料から成果物一式を一括生成（`build-all`）」を参照してください。

`--output-format`の指定に関わらず、`output/editable/lesson_pages.json`は常に生成されます。**正式な編集対象は`output/editable/lesson_pages.json`のみ、正式なCanva指示書は`output/canva/canva_design.md`のみ、正式な完成output（Markdown/DOCX/PDF/PPTX）は`output/exports/material.*`のみです。** `output/`直下には、通常ユーザーが使う完成outputを置きません。Phase 8時点の`lesson_pages.json`/`canva_design.md`/`brushup.md`/`brushup.docx`/`brushup.pdf`は、後方互換が必要な場合に`output/compat/`配下へまとめて生成します（`--no-compat-output`で無効化できます）。`output/scenario/`・`output/review_report.md`は正式outputとの役割重複が無いため、引き続き`output/`直下に生成されます。

### 1.4 editable中間ファイルを編集して再生成する（`regenerate`）

生成された完成outputに手直ししたい点があった場合、**完成画像やPDFを直接編集するのではなく**、`output/editable/lesson_pages.json`を編集してから再生成します。

```bash
# output/editable/lesson_pages.json をテキストエディタで編集した後
python3 -m src.cli regenerate --input output/editable/lesson_pages.json --output-format image
```

編集できる主な項目は`title`/`summary`/`body`/`layout_instruction`/`notes`です（`image_text`/`canva_prompt`/`video_scene`はこれらから自動算出されるため直接編集する必要はありません）。`--output-dir`を省略すると、`--input`の2階層上（`output/editable/lesson_pages.json`なら`output/`）に再生成されます。編集してよい項目・編集しない方がよい項目の一覧、`regenerate`の具体例（PDF/Canva指示書/全形式/日本語フォント指定）は[`docs/09_editable_regenerate_guide.md`](09_editable_regenerate_guide.md)を参照してください。

`source_image`が無いページの画像output（`generate`モード等）で日本語が文字化けする場合は、`--font-path`で日本語対応フォントを明示指定してください。

```bash
python3 -m src.cli regenerate --input output/editable/lesson_pages.json --output-format image --font-path /path/to/font.ttc
```

環境に日本語フォントが見つからない場合、`build-all`/`regenerate`実行時に以下の警告が表示されます（黙って文字化けさせることはありません）。

```text
WARNING: Japanese font was not found. Rendered images may contain garbled Japanese text.
Use --font-path to specify a Japanese font.
```

## 2. モードごとの設計思想

### proofread（編集モード）: 「元資料の趣旨が神」

元資料の全体構成・言っていることの趣旨・主題・ページ順・重要な内容は変えません。ただし、機械的に写すだけでもありません。購入者・受講者にとって読みやすい教材にするため、以下の範囲の編集は許可します。

**許可する編集**: 誤字脱字の修正／表記ゆれの統一／冗長な言い回しの整理／文字が多くて分かりにくい部分の短文化／読みにくい文章の自然な言い換え／主題から少しズレた補足や脱線の整理／同じ意味の重複表現の整理／見出し・箇条書き・段落の整理／教材として分かりやすくするための軽い補足／Canva・DOCX・PDFにしやすい形への整形

**禁止する編集**: 元資料の主張や結論を変える／元資料にない重要な主張を勝手に追加する／元資料の内容を大きく削る／ページ順や全体構成を大きく組み替える／読者に伝えるべき重要情報を落とす／意味が変わる言い換えをする／元資料と違う教材テーマに変える

システムは`source_page_no`で元ページとの対応を保持し、元資料にある画像・図版・ページビジュアルを`source_image`/`source_assets`として保持します。

### restructure（再構築モード）: 「教材として再構築可」

元資料を材料として教材として作り直してよいモードです。導入・実践・まとめページの追加、ページ統合・分割、順番の再構成、説明の補足が可能です。ただし`source_page_no`で元資料との対応を追跡し、画像・図版・ページビジュアルは可能な限り継承・参照できるようにします。

## 3. 生成される出力ファイル一覧

| ファイル | 内容 | 位置づけ |
|---|---|---|
| `output/imported_pages.json` | 元資料から自動取り込みしたテキスト・画像参照 | システム生成物（中間ファイル）。手で作らない |
| `output/assets/` | 元画像・元ページ画像・スライド埋め込み画像 | システム生成物。完成output生成時に参照する元画像 |
| `output/editable/lesson_pages.json` | 正データ（再生成用の編集対象） | **システム生成物だが、ユーザーが編集してよい唯一のファイル**。編集後は`regenerate`で再生成する |
| `output/rendered/page_NNN.png` | 完成画像（`--output-format image`または`same`で画像入力時） | ★正式output。配布・確認用 |
| `output/exports/material.pdf` | PDF（`--output-format pdf`時） | ★正式output |
| `output/exports/material.pptx` | PowerPoint（`--output-format pptx`時） | ★正式output |
| `output/exports/material.docx` | Word（`--output-format docx`時） | ★正式output |
| `output/exports/material.md` | Markdown（`--output-format md`時） | ★正式output |
| `output/canva/canva_design.md` | Canva向けレイアウト設計書・AI投入用プロンプト（`--output-format canva`時） | ★正式output（オプション出力。主outputではない） |
| `output/scenario/*` | 動画・音声化用4ファイル | システム生成物 |
| `output/review_report.md` | `role`/`source_page_no`の制作者確認用レポート | システム生成物 |
| `output/compat/lesson_pages.json`・`canva_design.md`・`brushup.md`・`brushup.docx`・`brushup.pdf` | Phase 8時点の成果物一式（`lesson_pages.json`/`canva_design.md`/教材ブラッシュアップ設計書のMarkdown・DOCX・PDF） | **後方互換専用**。正式output（`editable/`/`canva/`/`exports/`）と役割が重複するため`output/`直下には置かず`compat/`にまとめる。新規利用では参照しない。`--no-compat-output`で生成自体を無効化できる |

## 4. 確認する順序（推奨）

1. **`output/imported_pages.json`** — 元資料のテキスト・画像参照が正しく取り込まれているか
2. **`output/editable/lesson_pages.json`** — 元教材の内容が欠落・改変されていないか（すべての完成outputの元になるため、ここがおかしいと他も連鎖的におかしくなる）
3. **完成output（`--output-format`で選んだもの）** — `output/rendered/`の画像を確認する、または`output/exports/`のPDF・PPTX・DOCX・Markdownを開いて配布可能な見た目か確認する
4. **`output/canva/canva_design.md`（`canva`/`all`指定時のみ）** — 「元画像: assets/...」の参照が各ページに出ているか、Canva向け指示として使えそうか
5. **`output/scenario/`** — `voicevox.txt`と`scene.json`を中心に、動画・音声化に使えそうか確認する

気になる点があれば`output/editable/lesson_pages.json`の`title`/`summary`/`body`/`layout_instruction`/`notes`を編集し、`regenerate`コマンドで作り直してから再確認してください。restructureも試した場合は、`output/review_report.md`で「どのページがどの元ページ由来か」を確認すると、再構成の妥当性を判断しやすくなります。

## 5. フィードバック時に見るべき観点

チェックリスト形式のフィードバックシートを[`docs/feedback_template.md`](feedback_template.md)に用意しています。コピーして記入してください。主な観点は以下の通りです。

- 元教材の内容が欠落していないか
- 文章が読みやすくなっているか
- ページ構成が自然か
- 導入・実践・まとめが有効か（restructureのみ）
- 完成画像として使えそうか（`rendered/`）
- PDF/PPTX/DOCXとして配布できそうか（`exports/`）
- Canva向け指示が使えそうか（元画像への参照が出ているか含む。`canva/`）
- scenario出力が動画化に使えそうか
- 不自然な記号やMarkdown記法が残っていないか
- `source_page_no`など内部情報が配布物に出ていないか
- `output/editable/lesson_pages.json`を編集して`regenerate`した際、意図通り再生成されるか

## 6. OCRについての注意

画像からのテキスト抽出には`pytesseract`（Python側は導入済み）に加えて、**OS側にtesseract本体・日本語言語データのインストールが必要**です。

### 6.1 事前診断（推奨）

`input/source`に画像を置いて`build-all`を実行する前に、OCR環境を診断してください。

```bash
python3 -m src.cli check-ocr
# または
bash scripts/check_ocr_env.sh
```

`tesseract`/日本語言語データ(`jpn`)/Homebrewが、PATH上にあるか・既知のインストール先（macOSなら`/opt/homebrew/bin/`または`/usr/local/bin/`）にあるだけか・そもそも無いかを切り分けて表示します。

### OCR品質について

大見出し・本文・グラフ・注記が混在する教材画像でも、`src/ocr_engine.py`が複数の前処理・複数PSM・品質スコアによる最良候補選択と、低品質時のみの再試行を行い、単純な`pytesseract.image_to_string()`呼び出しより明らかな誤認識・ノイズ（英字ノイズ・不自然なタイトル等）を減らします。ただし、Tesseract自体が誤認識する文字は完全には無くならないため、`ocr-check`で残った崩れを確認する運用は引き続き推奨します（詳細は[`docs/13_ocr_quality_check_workflow.md`](13_ocr_quality_check_workflow.md)参照）。

Tesseract自身の信頼度スコアだけでは検出できない誤認識（実データでは、Tesseractが問題なしと判定したページに複数の重大な漢字誤読が残っていたケースを確認済み）については、macOS環境限定・完全に任意の機能として、`--ocr-engine tesseract+vision`でApple Vision OCRとの比較を利用できます（`bash scripts/build_apple_vision_ocr.sh`で事前にヘルパーをビルドする必要があります。未ビルド・macOS以外では自動的にTesseractのみへフォールバックし、通常の`build-all`は失敗しません）。比較結果は`output/ocr_comparison/review.html`等で確認でき、**`output/editable/lesson_pages.json`へ自動反映されることはありません**。詳細は[`docs/13_ocr_quality_check_workflow.md`](13_ocr_quality_check_workflow.md)「17. Apple Vision OCRとの比較」参照。

### 6.2 よくある状態と対処

| 状態 | 対処 |
|---|---|
| tesseractが無い | macOS/Homebrew: `brew install tesseract tesseract-lang` |
| tesseractは既知パスにあるがPATHに無い | `eval "$(/opt/homebrew/bin/brew shellenv)"`（Intel Macは`/usr/local/bin/brew`）を実行。永続化するなら`~/.zprofile`に追記 |
| jpn言語データが無い | `brew install tesseract-lang`。`tesseract --list-langs`で確認 |
| Homebrewが既知パスにあるがPATHに無い | 上記と同じ`brew shellenv`コマンドを実行 |
| Homebrewが無い | https://brew.sh の手順でインストール、または手動でtesseractをインストール |

（任意）macOSでHomebrew経由に実際にインストールする場合は`bash scripts/setup_ocr_macos.sh`を使えます。**ユーザーが明示的に実行するスクリプトであり、CLI本体が自動実行することはありません。**

### 6.3 単体の`import-source`コマンドの挙動

tesseract本体・日本語言語データが無い、またはPATHに無い環境で単体の`import-source`（画像input）を実行すると、**標準エラー出力に分かりやすい警告（英語+日本語）を表示したうえで処理を継続**します。黙って全ページ空のまま成功扱いにはしません。各ページの`canva.notes`にも「OCRでテキストを抽出できませんでした。元画像を直接参照してください。」という注記が入ります。画像・元ページ画像自体は`output/assets/`に必ず保存されるため、OCRが使えない場合でも取り込み自体は失敗しません（`import-source`はテキスト抽出専用コマンドであり、抽出結果を校正・再構成に使うかどうかは呼び出し側次第のため、警告のみで処理を継続します）。

### 6.4 `build-all`（proofread/restructure）の挙動：OCR不能なら失敗する（Phase 10.1追加修正）

**`build-all`は`proofread`・`restructure`のいずれのモードでも、画像inputかつOCRが実質使えない状態では成功しません。** 以下のいずれかに該当する場合、分かりやすいエラーメッセージを表示して**エラー終了（`exit 1`）**します。

- Tesseract本体が使えない（未導入、またはPATH・既知のインストール先のいずれにも見つからない）
- 日本語言語データ(`jpn`)が無い
- 取り込んだ全ページで`lines`（OCR結果）が空

一部のページだけOCR結果が空の場合は、エラーにはせず「何ページ中何ページが空だったか」を警告したうえで処理を継続します。

```text
$ python3 -m src.cli build-all --input input/source --mode proofread --output-dir output
ERROR: mode=proofread requires OCR text, but Tesseract is not available.
Install Tesseract and Japanese language data, then run again.

If Homebrew is installed but not on PATH:
  eval "$(/opt/homebrew/bin/brew shellenv)"

Then:
  brew install tesseract
  brew install tesseract-lang

If you want to proceed anyway with empty OCR text (e.g. for testing), pass --allow-empty-ocr.
$ echo $?
1
```

どうしても空のOCR結果のまま処理を続けたい場合（テスト・開発用途）は、`--allow-empty-ocr`を指定してください。**通常の利用でこのフラグを付けない限り、空のOCR結果のまま「成功」することはありません。**

```bash
python3 -m src.cli build-all --input input/source --mode proofread --output-dir output --allow-empty-ocr
```

このチェックは画像inputにのみ適用されます。PDF・PPTXはOCRではなくネイティブなテキスト抽出（`pymupdf`/`python-pptx`）を使うため対象外です。`generate`モード（画像を取り込まない）・`regenerate`・個別CLI（`lesson-pages`に既存のJSONを直接渡す経路）にも影響しません。OCR精度そのものの向上はPhase 8時点・Phase 10.1時点ともに対象外です。

## 7. 開発者向け: 内部形式を直接使いたい場合

`lesson-pages`コマンドは、`build-all`を経由しなくても、`pages`形式JSON（[`examples/sample_pages.json`](../examples/sample_pages.json)参照）や`lesson_pages`形式JSONを直接`--input`に渡せます。これは開発・デバッグ・自動テスト向けの経路であり、**作成者向けの主導線ではありません**。作成者は`build-all`を使ってください。

## 8. 注意事項

- 実際の教材素材・生成物は`input/`・`output/`配下に置き、**Gitにコミットしない**でください（`.gitignore`で除外済み）。
- 個人情報・未公開の教材内容が含まれる場合は特に取り扱いに注意してください。
- 気になった点は`docs/feedback_template.md`に記録し、次フェーズの着手判断の材料にしてください。
- 複数の教材・複数のモードで試す場合は、`output/`を上書きする前に別ディレクトリ（`--output-dir output_v2`等）にすると比較しやすくなります。

## 9. 実行ログ（`logs/`）と成功判定の考え方（Phase 10.2で追加）

コマンド実行のたびに、プロジェクト直下の`logs/`に実行ログ（`logs/YYYYMMDD_HHMMSS_<command>.log`）が残ります。「なぜエラーになったか」「どのページでOCRが空だったか」等を後から確認したい場合は、このログを見てください。`logs/`ディレクトリ自体はGit管理対象ですが、ログファイル本体（`logs/*.log`）はGit管理対象外です（`input/`/`output/`と同様にコミットされません）。配布用ZIP（`scripts/make_release_zip.sh`）には、`input/`/`output/`とは異なり**ログファイルも含まれます**。

ログファイルはZIPで配布され得るため、**CLI引数・stderr出力・エラー内容に`password`/`token`/`api_key`/`secret`/`authorization`等の秘密情報らしき値が含まれていても、ログ書き出し時に`[REDACTED]`へ自動的にマスクされます**（Phase 10.2追加修正）。`.env`や認証情報ファイルの中身自体をログへ出す処理はありません。

**「exit code 0だが実質失敗している」状態を避ける方針**を取っています。以下は非ゼロ終了（コマンドが失敗扱い）になります。

- 入力ファイル・入力ディレクトリが存在しない、または対応ファイルが1つも無い
- 取り込み・読み込んだページ数が0件（`import-source`/`lesson-pages`/`build-all`/`regenerate`いずれも）
- `proofread`/`restructure`でOCRが実質使えない、または全ページOCR結果が空（詳細は「6. OCRについての注意」参照）
- 指定した`--output-format`の成果物、または個別CLI（`canva`/`docx`/`pdf`等）の出力ファイルが実際には生成されなかった・空だった場合
- JSON構文エラー

一方、以下は警告のうえ処理を継続します（ただし必ずログには残ります）。

- 一部ページのみOCR結果が空
- `--no-compat-output`によるcompat出力の無効化
- フォント未指定時に環境の代替フォントを使用する場合

`check-ocr`は環境診断コマンドのため、OCR環境が不足していても通常は`exit 0`です（診断自体が壊れた場合のみ非ゼロ終了）。
