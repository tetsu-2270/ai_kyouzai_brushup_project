# 完成教材画像 決定論的レンダリングワークフロー（Phase 10.15）

## 1. このワークフローの位置づけ

```text
OCR確定原文 → 本文ブラッシュアップ → 構成・デザイン設計
→ Codexによる最終ビジュアル生成 → 確定済み日本語本文の決定論的合成 → 完成画像
```

- Phase 10.14: 全ページ共通のスライドマスター（`MASTER_LAYOUT.json`）とCodex向け最終画像生成
  パッケージ（`final_image_package/`）を作成（[`19_final_image_package_workflow.md`](19_final_image_package_workflow.md)）
- Codex: `final_image_package/CODEX_FINAL_IMAGE_GENERATION.md`の指示に従い、文字を一切含まない
  共通背景画像（`rendered_final/background_master.png`）を生成
- **Phase 10.15（本ワークフロー）: Codex生成済み背景 + 固定マスター + 確定済み本文スナップショット
  から、完成画像（`rendered_final/page_NNN.png`）を決定論的に合成する**

## 2. CLIコマンド

```bash
python3 -m src.cli render-final-images --output-dir output/ocr_engine_eval
```

背景・フォントは任意で上書きできる。

```bash
python3 -m src.cli render-final-images \
  --output-dir output/ocr_engine_eval \
  --background output/ocr_engine_eval/rendered_final/background_master.png \
  --font-path "/System/Library/Fonts/ヒラギノ角ゴシック W4.ttc"
```

### 既定の入力パス

| 入力 | 既定パス |
|---|---|
| 背景画像 | `<output-dir>/rendered_final/background_master.png` |
| マスターレイアウト | `<output-dir>/final_image_package/MASTER_LAYOUT.json` |
| パッケージmanifest | `<output-dir>/final_image_package/package_manifest.json` |
| ページ別内部レイアウト仕様 | `<output-dir>/final_image_package/pages/page_NNN.json` |
| 確定済み本文スナップショット | `<output-dir>/final_image_package/text/page_NNN.json` |

### 出力

```text
output/<output-dir>/
├── rendered_final/
│   ├── background_master.png    # Codexが生成した共通背景（変更しない）
│   └── page_NNN.png             # 本Phaseが生成する完成画像
└── final_image_package/
    ├── final_render_report.json
    ├── final_render_report.md
    └── final_comparison.html
```

## 3. 入力検証（1件でも不正なら完成画像を生成せず非ゼロ終了）

- 背景画像の存在・`MASTER_LAYOUT.json`の`canvas`と一致するサイズ・破損無し・非不透明であること
- `MASTER_LAYOUT.json`/`package_manifest.json`の存在
- 全ページの`pages/page_NNN.json`/`text/page_NNN.json`の存在（欠落・余剰の両方を検出）
- 全ページが同じ`master_layout`（`MASTER_LAYOUT.json`の`master_id`）を参照していること
- `MASTER_LAYOUT.json`/`package_manifest.json`/各ページ仕様/各本文スナップショットの
  `source_lesson_pages_sha256`が、現在の`editable/lesson_pages.json`と一致すること
  （Phase 10.14と同じ`lesson_pages_sha256`/`check_master_layout_freshness`の仕組みを再利用）
- `emphasis[].match`が現在の本文に実在すること（Phase 10.14の`validate_page_spec`を再利用）
- ページ仕様の`content_layout.blocks[].line_range`が、本文スナップショットの段落数に収まって
  いること（範囲外だと文字を静かに描画しない＝禁止されている「途中打ち切り」になるため）
- ページ仕様の`notice`有無と、本文スナップショットから読み取れる注記有無が一致すること
- 日本語を描画できるフォントが解決できること（見つからない場合は`--font-path`を明示指定するよう
  エラーにする。Phase 10.14以前の`prepare-*`系コマンドは警告のみで継続するが、本コマンドは
  「完成画像」を扱うため文字化けを許容せず拒否する）
- `source_image`等のパス参照に絶対パス・パストラバーサルが無いこと（Phase 10.12以来の
  `_normalize_relative_path`を再利用）

## 4. 決定論的合成

各ページについて、共通背景（`background_master.png`）を複製したキャンバスへ、`MASTER_LAYOUT.json`の
固定領域（`title_region`/`content_card`/`notice_region`/`page_number_region`）を使って
タイトル・本文カード・注記・ページ番号を描画する。**背景原本は複製元としてのみ使い、変更しない。**

本文カードの内部レイアウト（`single_column`/`two_column`・`vertical_alignment`・強調）は、
Phase 10.14が既に確定した`pages/page_NNN.json`をそのまま解釈する（本Phaseはページ別レイアウトの
再判定は行わない）。カード外形（x/y/width/height/corner_radius等）は全ページで完全に同一。

### 強調表示

`content_layout.blocks[].style.color`がテーマの`accent`色と一致するブロック（Phase 10.14が
`◎`検出行等に割り当てた「強調」ブロック）には、本文カードの内側パディング領域に収まる
左アクセントバーを追加で描画する（太字・アクセント色に加えた視覚的階層表現）。`note`ブロック種別
（淡い背景の箱）は既存のまま利用できる。

## 5. 文字は本文スナップショット（`text/page_NNN.json`）のみから取得する

`lesson_pages.json`は**検証**（本文スナップショットが最新かどうかの鮮度確認）にのみ使い、実際に
画像へ描画する文字列は`text/page_NNN.json`の`title`/`body`/`notice`フィールドから取得する。

### notice抽出（Phase 10.14追加修正で正式修正済み）

`final_image_package.split_body_and_notice()`はかつて、生の本文行（`"speaker: text"`形式）の
先頭が`※`かどうかで注記を判定していたため、話者が空文字列の行（`": ※無断転載禁止（おとスタ）"`
のように保存される）を検出できず、`notice`フィールドが空文字列のまま`body`側に注記が残る不具合が
実データで確認された。`lesson_pages.parse_body_lines`と同じ話者・本文の分解ロジックを最終行にも
適用するよう修正済みで、現在は`notice`フィールドが正しく埋まる。

`src/final_slide_compositor.py`の`_derive_notice_text()`は、この修正後も防御的フォールバックとして
残している（`notice`が正しく埋まっている場合はそちらを優先し、通常は`body`解析へフォールバック
しない）。

## 6. オーバーフロー時の扱い

Phase 10.14と同じ縮小手順（指定サイズ→行間→ブロック間隔→内側余白→最小フォントサイズ→
2段組み切替え）を試し、それでも収まらない場合は本文を切り詰めず、そのページの生成を失敗させる
（`overflow: true`、`truncated`は常に`false`。省略記号による短縮も行わない）。

さらに、本文量が少ない`single_column`ページでカード内の垂直方向利用率が既定より低い場合は、
文字サイズを段階的に拡大しながら再測定する（`_measure_card_blocks_with_growth`。本文カードの
外寸・2段組みページ・既に十分埋まっているページは変更しない）。

## 7. 視覚描画検証（`*_visually_rendered`）とレポート・比較確認画面

「描画処理へ渡した文字列がtext snapshotと一致するか」（`source_text_match`）と、「実際に完成画像へ
正しく描画されたか」は別の検証軸として分離している。後者は、合成後の完成画像そのものを実測して
検証する。

- `title_bbox`/`title_region`/`title_font_size`/`title_line_count`/`title_mask_nonempty`/
  `title_bbox_within_region`/`title_pixels_present`/`title_dark_artifact_detected`/
  `title_visually_rendered`: タイトル領域の実測結果
- `body_bbox`/`content_inner_region`/`horizontal_utilization`/`vertical_utilization`/
  `body_dark_artifact_detected`/`body_visually_rendered`/`body_low_utilization_warning`:
  本文カード内の実測結果（利用率が低い場合は警告として記録するのみで、失敗にはしない）
- `notice_bbox`/`notice_dark_artifact_detected`/`notice_visually_rendered`、
  `page_number_bbox`/`page_number_dark_artifact_detected`/`page_number_visually_rendered`
- `all_regions_visually_rendered`: 上記4領域すべてが`true`の場合のみ`true`
- `ocr_available`/`ocr_text`/`ocr_title_match_ratio`/`ocr_warning`: 既存OCR機能によるタイトルの
  補助確認（主判定はbbox/pixel検証。OCR結果は参考情報であり、一致率が低くても失敗にはしない）

ページの成功条件は次のすべてを満たす場合のみ。

```text
source_text_match == true
overflow == false
truncated == false
all_regions_visually_rendered == true
（元画像・背景原本との単純コピーでないこと）
```

- `final_image_package/final_render_report.json`（`schema_version: 2`）/`final_render_report.md`:
  ページ別の`source_text_sha256`・`rendered_fields`・`source_text_match`・`overflow`・`truncated`・
  上記`*_visually_rendered`一式・警告を記録する
- `final_image_package/final_comparison.html`: 外部CDN・外部CSS・外部JSに依存しない自己完結HTML。
  元画像・Phase 10.14プレビュー（`rendered_brushup_preview/`）・Phase 10.15完成画像
  （`rendered_final/`）をページごとに横並び表示し、title bbox/region・利用率・暗色矩形検査結果・
  補助OCR結果・notice sourceも表示する

### 画像参照パスの算出（`relative_asset_path`）

`final_comparison.html`（`final_image_package/`直下に保存）から各画像への相対パスは、固定文字列の
`../`/`../../`を手作業で選ぶのではなく、`relative_asset_path(html_path, target_path,
allowed_root=output_dir)`がHTMLの実際の保存先から画像の実際の保存先までを`os.path.relpath()`で
機械的に算出する（POSIX区切りへ変換・`output_dir`外参照拒否・不存在ファイル拒否）。

HTML書き出し前に、各ページの必須参照（元画像・Phase 10.14プレビューは常に必須、Phase 10.15完成
画像はそのページが成功した場合のみ必須）が実在するかを検証し、1件でも欠ければHTML生成そのものを
拒否する（`_validate_comparison_assets_exist`）。書き出し後は、実際のHTMLを解析して全`<img src>`
がoutput-dir内に解決され、Pillowで読み込めることを検証し（`validate_comparison_html_references`）、
結果を`final_render_report.json`の`comparison_html_validation`へ記録する。

## 8. 既存機能との関係

- `prepare-image-brushup`/`render-brushup`/`prepare-final-image-package`/`apply-content-brushup`/
  `apply-ocr-review`等の既存コマンドの挙動は変更しない
- `editable/lesson_pages.json`・元画像（`assets/`）・`rendered/`・`rendered_brushup/`・
  `rendered_brushup_preview/`・`final_image_package/`配下の既存ファイル（`MASTER_LAYOUT.json`・
  `pages/`・`text/`等）は変更しない（本コマンドが書き込むのは`rendered_final/page_NNN.png`と
  レポート・比較HTMLのみ）
- 本文が更新された場合、Phase 10.14と同様に`source_lesson_pages_sha256`の不一致で検出され、
  `prepare-final-image-package`の再実行を促すエラーで終了する

## 9. 制限事項

- カード内部レイアウト・強調箇所の判定自体はPhase 10.14が確定したものをそのまま使う（本Phaseは
  レイアウトの再判定は行わない）
- 強調表示は左アクセントバー＋太字・アクセント色という固定的な表現であり、1行内の一部の文字だけを
  ハイライトする表現は未対応（Phase 10.14からの継続的な制限）
- 背景はデッキ全体で1枚の共通背景（`background_master.png`）のみに対応する。ページ別背景
  （`prompts/page_NNN.md`が想定する差分背景）を使う運用は未対応（`--background`で1枚だけ
  明示的に差し替えることは可能）
