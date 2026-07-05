# 08 実利用テスト・品質評価フェーズ（Phase 8）

## 目的

Phase 8は「元資料自動取り込み・一括生成の実利用評価フェーズ」です。

作成者は元資料（画像・PDF・PPTX）を`input/source/`に置いて`build-all`コマンドを実行するだけで、システムが自動的に内部JSONと画像アセットを生成し、教材ブラッシュアップ成果物一式（`brushup.md`/`canva_design.md`/DOCX/PDF/動画シナリオ）を作れます。**作成者がJSON・Markdown・TXTを手作業で作る必要はありません。**

Phase 8で対象外のもの: introの`source_page_no`拡大、3ページ以上の連鎖merge、`--plan-input`、`Requirements.page_count`の実装、LLM/API連携、OCR精度の高度化。

**本書は元資料（画像/PDF/PPTX）がある場合の手順です。元資料が無く要件定義だけから新規に教材を作りたい場合（新規構築）は、`build-all`ではなく`lesson-pages --mode generate`を使ってください（README「`lesson-pages`の3モード（v2.0）」参照）。**

---

## 1. 主導線: 元資料を置いて`build-all`を実行する

```
元資料（画像 / PDF / PPTX）
  ↓
output/imported_pages.json + output/assets/（システム自動生成）
  ↓
output/lesson_pages.json（システム自動生成、proofreadまたはrestructure）
  ↓
output/brushup.md / canva_design.md / brushup.docx / brushup.pdf / scenario/
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
  --output-dir output
```

これだけで、取り込みから成果物一式の生成までが自動的に実行されます。内部では以下の順で処理します。

1. `import-source`: 元資料からテキスト・画像を自動取り込み → `output/imported_pages.json` + `output/assets/`
2. `lesson-pages`: `output/lesson_pages.json`（正データ）を生成
3. `generate` / `canva` / `docx` / `pdf` / `scenario` / `review-report`: 各種成果物を生成

`--mode`は`proofread`（元資料の趣旨を維持して整形。最初はこちらを推奨）または`restructure`（教材として再構築）を指定します。`restructure`では対象読者・トーンを反映する`--requirements`を任意で指定できます。

```bash
python3 -m src.cli build-all \
  --input input/source \
  --mode restructure \
  --requirements input/requirements.json \
  --output-dir output
```

`requirements.json`の書き方は[`examples/requirements_ai_instagram.json`](../examples/requirements_ai_instagram.json)を参照してください（こちらはrequirements特有の項目のため、従来通り作成者が用意します）。

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
| `output/assets/` | 元画像・元ページ画像・スライド埋め込み画像 | システム生成物。Canva設計時に参照する元画像 |
| `output/lesson_pages.json` | 正データ | システム生成物。以降のすべての出力はここから生成される |
| `output/brushup.md` | 教材ブラッシュアップ設計書（配布・確認用の本文） | システム生成物 |
| `output/canva_design.md` | Canva向けレイアウト設計書・AI投入用プロンプト（元画像への参照込み） | システム生成物 |
| `output/brushup.docx` | Word教材（配布用） | システム生成物 |
| `output/brushup.pdf` | PDF教材（配布用） | システム生成物 |
| `output/scenario/*` | 動画・音声化用4ファイル | システム生成物 |
| `output/review_report.md` | `role`/`source_page_no`の制作者確認用レポート | システム生成物 |

## 4. 確認する順序（推奨）

1. **`output/imported_pages.json`** — 元資料のテキスト・画像参照が正しく取り込まれているか
2. **`output/lesson_pages.json`** — 元教材の内容が欠落・改変されていないか（すべての派生出力の元になるため、ここがおかしいと他も連鎖的におかしくなる）
3. **`output/brushup.md`** — 教材本文として読みやすいか
4. **`output/canva_design.md`** — 「元画像: assets/...」の参照が各ページに出ているか、Canva向け指示として使えそうか
5. **`output/brushup.docx`** — Wordで開き、配布可能な見た目か確認する
6. **`output/brushup.pdf`** — Preview.app等で開き、日本語表示が文字化けしていないか目視確認する（`open output/brushup.pdf`）
7. **`output/scenario/`** — `voicevox.txt`と`scene.json`を中心に、動画・音声化に使えそうか確認する

restructureも試した場合は、`output/review_report.md`で「どのページがどの元ページ由来か」を確認しながら`brushup.md`と見比べると、再構成の妥当性を判断しやすくなります。

## 5. フィードバック時に見るべき観点

チェックリスト形式のフィードバックシートを[`docs/feedback_template.md`](feedback_template.md)に用意しています。コピーして記入してください。主な観点は以下の通りです。

- 元教材の内容が欠落していないか
- 文章が読みやすくなっているか
- ページ構成が自然か
- 導入・実践・まとめが有効か（restructureのみ）
- Canva向け指示が使えそうか（元画像への参照が出ているか含む）
- DOCX/PDFとして配布できそうか
- scenario出力が動画化に使えそうか
- 不自然な記号やMarkdown記法が残っていないか
- `source_page_no`など内部情報が配布物に出ていないか

## 6. OCRについての注意

画像・PDFからのテキスト抽出には`pytesseract`（Python側は導入済み）に加えて、**OS側にtesseract本体のインストールが必要**です（例: macOSなら`brew install tesseract tesseract-lang`）。tesseract本体が無い環境では、テキストは空のまま取り込まれ、各ページの`canva.notes`に「OCRでテキストを抽出できませんでした。元画像を直接参照してください。」という注記が入ります。画像・元ページ画像自体は`output/assets/`に必ず保存されるため、OCRが使えない場合でも取り込みや成果物生成自体は失敗しません。OCR精度そのものの向上はPhase 8の対象外です。

## 7. 開発者向け: 内部形式を直接使いたい場合

`lesson-pages`コマンドは、`build-all`を経由しなくても、`pages`形式JSON（[`examples/sample_pages.json`](../examples/sample_pages.json)参照）や`lesson_pages`形式JSONを直接`--input`に渡せます。これは開発・デバッグ・自動テスト向けの経路であり、**作成者向けの主導線ではありません**。作成者は`build-all`を使ってください。

## 8. 注意事項

- 実際の教材素材・生成物は`input/`・`output/`配下に置き、**Gitにコミットしない**でください（`.gitignore`で除外済み）。
- 個人情報・未公開の教材内容が含まれる場合は特に取り扱いに注意してください。
- 気になった点は`docs/feedback_template.md`に記録し、次フェーズの着手判断の材料にしてください。
- 複数の教材・複数のモードで試す場合は、`output/`を上書きする前に別ディレクトリ（`--output-dir output_v2`等）にすると比較しやすくなります。
