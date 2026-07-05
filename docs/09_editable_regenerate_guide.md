# 09 editable中間ファイルの編集・再生成ガイド

> `output/`配下のディレクトリ構成（`editable/`/`rendered/`/`canva/`/`exports/`/`compat/`）は、[`CLAUDE_RULES.md`](../CLAUDE_RULES.md)「プロジェクト設計ルール」・[`docs/04_output_spec.md`](04_output_spec.md)「プロジェクト標準output構成」で定義済みの共通設計ルールです。本書はそのうち「`output/editable/lesson_pages.json`を編集して再生成する」運用に絞って、具体的な手順を説明します。

## 1. 編集してよいのはeditable/lesson_pages.jsonだけ

**完成画像（`output/rendered/`）・PDF・DOCX・PPTX（`output/exports/`）を直接編集しないでください。** これらは`output/editable/lesson_pages.json`から自動生成される完成outputであり、直接編集しても次に再生成したときに上書きされて消えます。

修正したい内容がある場合は、必ず以下の運用に従ってください。

```text
output/editable/lesson_pages.json を編集
↓
regenerate コマンドを実行
↓
output/rendered/ や output/exports/ が作り直される
```

## 2. 編集してよい項目・編集しない方がよい項目

`output/editable/lesson_pages.json`の各ページは、以下のような構造を持ちます（詳細スキーマは[`docs/04_output_spec.md`](04_output_spec.md)参照）。

```json
{
  "page_no": 1,
  "title": "ページタイトル",
  "body": "話者: 台詞\n話者: 台詞",
  "summary": "このページの概要",
  "layout_instruction": "レイアウト指示",
  "notes": "補足",
  "source_page_no": [1],
  "source_image": "assets/page_001.png",
  "source_assets": []
}
```

### 編集してよい項目

| 項目 | 内容 |
|---|---|
| `title` | ページタイトル |
| `summary` | ページ概要 |
| `body` | 本文（「話者: 台詞」形式の複数行文字列） |
| `layout_instruction` | レイアウト・配置の指示（Canva指示書・画像outputの合成に使われる） |
| `notes` | 補足メモ |

これらを編集して`regenerate`すれば、`image_text`/`canva_prompt`/`video_scene`も自動的に再計算されます（手動で合わせる必要はありません）。

### 通常編集しない方がよい項目

| 項目 | 理由 |
|---|---|
| `source_page_no` | 元ページとの対応を追跡する内部メタデータ。書き換えると`review-report`等での追跡が壊れる |
| `source_image` | 元画像・元ページ画像への参照パス。書き換えると画像outputが元画像を見つけられなくなる |
| `source_assets` | 元画像以外の関連アセットへの参照パス。同上の理由で書き換え非推奨 |
| `role` | ページ種別の内部メタデータ（`intro`/`explanation`/`practice`/`summary`等） |
| `page_no` | ページ番号。並び替えたい場合は`--mode restructure`の再実行を検討する（手動でのpage_no変更は非推奨） |

`image_text`/`canva_prompt`/`video_scene`は`title`/`body`/`summary`/`layout_instruction`/`notes`から都度自動算出される値のため、直接編集しても`regenerate`時に上書きされます。編集するだけ無駄になるため、上記5項目（`title`/`summary`/`body`/`layout_instruction`/`notes`）を編集してください。

## 3. JSON構文を壊さないこと

`output/editable/lesson_pages.json`は通常のJSONファイルです。カンマの過不足や引用符の閉じ忘れなどで構文が壊れると、`regenerate`実行時にエラーになり再生成できません。エディタのJSON構文チェック機能（多くのテキストエディタ・IDEに搭載）を活用してください。

## 4. regenerateコマンドの使い方

```bash
python3 -m src.cli regenerate --input output/editable/lesson_pages.json --output-format <形式>
```

`--output-dir`を省略すると、`--input`の2階層上（`output/editable/lesson_pages.json`なら`output/`）に再生成されます。

### 完成画像を再生成する

```bash
python3 -m src.cli regenerate --input output/editable/lesson_pages.json --output-format image
```

### PDFを再生成する

```bash
python3 -m src.cli regenerate --input output/editable/lesson_pages.json --output-format pdf
```

### Canva指示書を再生成する

```bash
python3 -m src.cli regenerate --input output/editable/lesson_pages.json --output-format canva
```

### すべての形式を再生成する

```bash
python3 -m src.cli regenerate --input output/editable/lesson_pages.json --output-format all
```

### 日本語フォントを指定して画像を再生成する

```bash
python3 -m src.cli regenerate --input output/editable/lesson_pages.json --output-format image --font-path /path/to/font.ttc
```

## 5. 日本語フォントについて（`--font-path`）

`source_image`が無いページ（`generate`モードで作った教材等）の完成画像は、`title`/`summary`/`body`を描画して簡易合成します。この描画には日本語フォントが必要です。

- 通常は環境内の日本語フォント（macOSの`ヒラギノ角ゴシック`、Linuxの`Noto Sans CJK`、Windowsの`游ゴシック`等）を自動探索します。
- 自動探索で見つからない場合、**黙って文字化けさせるのではなく、以下の警告を表示します。**

  ```text
  WARNING: Japanese font was not found. Rendered images may contain garbled Japanese text.
  Use --font-path to specify a Japanese font.
  ```

- この警告が出た場合は、`--font-path`で日本語対応フォントのファイルパスを明示的に指定してください（`build-all`/`regenerate`どちらでも指定可能）。

```bash
python3 -m src.cli build-all --input input/source --output-format image --font-path "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"
```

`--font-path`に存在しないパスや読み込めないファイルを指定した場合は、その場でエラーになります（黙って別のフォントにフォールバックすることはしません）。

## 6. 困ったときは

- **再生成しても変わらない**: 編集したファイルが本当に`output/editable/lesson_pages.json`か確認してください（`output/compat/lesson_pages.json`は後方互換用のコピーで、編集しても無視されます）。
- **regenerateがエラーになる**: JSON構文が壊れていないか確認してください（`python3 -m json.tool output/editable/lesson_pages.json`で構文チェックできます）。
- **画像の日本語が文字化けする**: `--font-path`で日本語対応フォントを明示指定してください（上記「5. 日本語フォントについて」参照）。
- **どのファイルが正式outputか分からない**: [`docs/04_output_spec.md`](04_output_spec.md)「プロジェクト標準output構成」を参照してください。
- **画像取り込み直後から`body`が空になっている（`title`が「取り込みページN」のまま）**: OCR（Tesseract）が使えていない可能性があります。`python3 -m src.cli check-ocr`または`bash scripts/check_ocr_env.sh`で診断してください（詳細は[`docs/04_output_spec.md`](04_output_spec.md)「OCR前提の事前チェック」参照）。この場合も`source_image`は保持されているため、editable上で`title`/`summary`/`body`を手動で書き起こして`regenerate`することもできます。
- **`build-all --mode proofread`/`restructure`がエラー終了する（`ERROR: mode=... requires OCR text`等）**: 画像inputでOCRが実質使えない状態（Tesseract未導入・日本語言語データ無し・全ページOCR結果が空）です。`check-ocr`で原因を確認し、Tesseract・日本語言語データを導入してから再実行してください。テスト・開発用途でどうしても空のOCR結果のまま続けたい場合のみ`--allow-empty-ocr`を指定できます。
- **なぜエラーになったか・どこでOCRが空になったかを後から確認したい**: `regenerate`/`build-all`実行のたびに`logs/YYYYMMDD_HHMMSS_<command>.log`へ実行ログが残ります（Phase 10.2）。入力・OCR環境の要約・警告・エラー・生成した成果物一覧が記録されているので、うまくいかなかった実行のログを確認してください。詳細は[`docs/04_output_spec.md`](04_output_spec.md)「実行ログ（logs/）の標準仕様」を参照。
