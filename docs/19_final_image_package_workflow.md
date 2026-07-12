# 統一スライドマスター・Codex向け最終画像生成パッケージワークフロー（Phase 10.14）

## 1. このワークフローの位置づけ

```text
OCR確定原文 → 本文ブラッシュアップ → 構成・デザイン設計
→ Codexによる最終ビジュアル生成 → 確定済み日本語本文の決定論的合成 → 完成画像
```

- Phase 10.7〜10.11: OCR取得〜確定原文の保存まで完了（[`16_apply_ocr_review_workflow.md`](16_apply_ocr_review_workflow.md)等）
- Phase 10.12: Pillowによるレイアウトの器（デザインJSON・レンダラー）を実装（[`17_image_brushup_workflow.md`](17_image_brushup_workflow.md)）
- Phase 10.13: 教材本文のブラッシュアップ（[`18_content_brushup_workflow.md`](18_content_brushup_workflow.md)）
- **Phase 10.14（本ワークフロー）: 全ページ共通のスライドマスターと、Codex向け最終画像生成パッケージの作成**
- Phase 10.15（次工程・未実装）: Codexが文字なし背景を生成し、確定済み本文を決定論的に合成して完成画像を確定する

**本Phaseでは完成画像（`rendered_final/`）を生成しません。** `prepare-final-image-package`が生成するのは、
次工程（Codex）が実行するための自己完結した入力一式と、レイアウト確認用のプレビューです。

## 2. Phase 10.12との違い（なぜ本Phaseが必要か）

Phase 10.12のプレビュー（`rendered_brushup/`）は、ページごとに本文量に応じて白いカードの
高さ・幅・位置が変わる設計でした。そのため、ページ間で見た目の統一感が無く、
「本当にこれが1つの教材の完成品か」という一貫性の問題がありました。

本Phaseでは、**全ページで完全に同一のキャンバスサイズ・カード位置・カードサイズ・
角丸・罫線・影・注記位置・ページ番号位置**（`MASTER_LAYOUT.json`）を先に固定し、
ページごとに変えてよいのは「カードの内側の構成（1段組み/2段組み・強調箇所）」だけに
限定します。

## 3. CLIコマンド

```bash
python3 -m src.cli prepare-final-image-package --output-dir output/ocr_engine_eval [--font-path <path>]
```

### 入力

- `editable/lesson_pages.json`（Phase 10.13までの確定済み本文。最新のものを使う）
- `brushup_design/design_manifest.json`・`brushup_design/pages/page_NNN.json`（Phase 10.12の画像デザイン。
  現在の`lesson_pages.json`と整合していることが前提。**古い・欠落している場合は`render-brushup`と同じ
  検証ロジック（`brushup_renderer.load_design_pages`）を再利用してエラー終了します**。先に
  `prepare-image-brushup`→AI作業エージェントによるデザイン設計→`render-brushup`を完了させてください）
- `assets/`（元画像。マスターキャンバスのアスペクト比正規化に使う）

### 出力

```text
output/<output-dir>/
├── rendered_brushup_preview/        # 新規: 統一マスターによるプレビュー（page_NNN.png）
└── final_image_package/             # 新規: Codex向け最終画像生成パッケージ
    ├── CODEX_FINAL_IMAGE_GENERATION.md
    ├── MASTER_LAYOUT.json
    ├── package_manifest.json
    ├── asset_manifest.json
    ├── README.md
    ├── pages/page_NNN.json          # ページ別の内部レイアウト仕様（マスター座標は含まない）
    ├── text/page_NNN.json           # 確定済み本文のCodex向けスナップショット
    ├── prompts/master_background.md # 共通の文字なし背景生成プロンプト
    ├── prompts/page_NNN.md          # ページ別背景差分プロンプト（マスター背景の派生）
    └── preview/
        ├── master_guides.png        # 全ページ共通マスターを可視化したガイド画像
        ├── page_NNN.png             # レイアウト確認用プレビュー（完成画像ではない）
        └── comparison.html          # 元画像とプレビューの比較確認画面
```

`rendered_final/`（Phase 10.15の完成画像置き場）はこのコマンドでは**作成されません**。

## 4. 既存出力ディレクトリの名称整理（重要）

このプロジェクトの`output/<output-dir>/`には、似た名前の複数のディレクトリが並びます。混同を避けるため、
それぞれの位置づけを明記します。

| ディレクトリ | 位置づけ | 完成画像か |
|---|---|---|
| `rendered/` | Phase 10.12より前からの後方互換output（元画像のコピー） | いいえ |
| `rendered_brushup/` | Phase 10.12のプレビュー（ページごとにカード寸法が変わる） | いいえ |
| `rendered_brushup_preview/` | **Phase 10.14（本Phase）のプレビュー。全ページ共通マスター使用** | **いいえ** |
| `rendered_final/` | Phase 10.15でCodexが生成する完成画像（本Phaseでは未作成） | **はい（Phase 10.15完了後のみ）** |
| `brushup_design/` | Phase 10.12のページ別デザイン仕様（本Phaseの前提入力） | - |
| `final_image_package/` | 本Phaseが生成する、Codex向け最終画像生成パッケージ一式 | - |

**`rendered_brushup_preview/`・`final_image_package/preview/`の中身を「完成画像」「最終画像」
「ブラッシュアップ完了」と呼ばないでください。** ユーザーへの最終確認は、Phase 10.15が
`rendered_final/`を生成した後に初めて行います。

## 5. 全ページ共通のスライドマスター（`MASTER_LAYOUT.json`）

### 5.1 キャンバスサイズの決め方

1. デッキ内の全ページの元画像のアスペクト比を集計する
2. 標準比率（16:9 / 4:3 / 1:1 / 3:4 / 9:16）のうち最も近いものを選ぶ
3. その標準比率に対応する固定サイズ（例: 16:9なら1600x900）をデッキ全体で1つだけ使う

実データ（`output/ocr_engine_eval`）は元画像が全11ページとも1706x960（16:9）で統一されているため、
キャンバスは`1600x900`に正規化されます。

### 5.2 固定領域（`regions`）

`title_region`・`content_card`・`notice_region`・`page_number_region`の4領域を、1600x900基準の
テンプレート値から実際のキャンバスサイズへ比例スケーリングして決定します。**この値は生成時に一度
確定し、以後全ページで完全に同じ値を再利用します**（ページごとに再計算しません）。

```json
{
  "outer_margin": 56,
  "title_region": {"x": 72, "y": 52, "width": 1456, "height": 130},
  "content_card": {
    "x": 56, "y": 200, "width": 1488, "height": 590, "corner_radius": 28,
    "padding": {"top": 38, "right": 42, "bottom": 38, "left": 42}
  },
  "notice_region": {"x": 72, "y": 802, "width": 900, "height": 40},
  "page_number_region": {"x": 700, "y": 842, "width": 200, "height": 36}
}
```

**本文カード（`content_card`）の外形（x/y/width/height/corner_radius/border/shadow）は、
内容量によって一切変わりません。** 内容が少ないページはカード内部で上寄せ/中央寄せ/分散配置
（`content_layout.vertical_alignment`）にし、多いページはカード内部の余白・行間・フォントサイズを
段階的に縮小し、最終手段として2段組みへ切り替えます（それでも収まらない場合はページ生成自体を
失敗させます。本文の切り詰め・要約は行いません）。

### 5.3 デッキ共通テーマ（`theme`/`typography`/`card`）

背景色・カード色・本文色・アクセント色・罫線色・影色・フォントの太さ方針を、デッキ全体で1つに
統一します。ページごとに配色を変えることはありません。

### 5.4 鮮度検証（Phase 10.12/10.13と同じ仕組みの再利用）

`MASTER_LAYOUT.json`には`source_lesson_pages_sha256`が記録されます。これは
[`17_image_brushup_workflow.md`](17_image_brushup_workflow.md)で導入された`lesson_pages_sha256()`/
`check_manifest_freshness()`と同じ仕組みで、後から本文が更新された場合に、古いマスターでの
利用を防ぐためのものです。

さらに`prepare-final-image-package`自体が、実行の都度`brushup_design/design_manifest.json`の
鮮度（Phase 10.13で追加された`source_lesson_pages_sha256`との突き合わせ）を、
**既存の`brushup_renderer.load_design_pages()`をそのまま再利用して**検証します。
Phase 10.12の画像デザインが古い・未生成の場合は、`prepare-image-brushup`→`render-brushup`を
先に実行するよう促すエラーで終了します。

## 6. ページ別内部レイアウト仕様（`pages/page_NNN.json`）の自動決定ロジック

本Phaseでは、Phase 10.12のように別セッションのAIエージェントがページごとにデザインを設計するのではなく、
**`prepare-final-image-package`自身が、確定済み本文の構造を機械的に分析して内部レイアウトを決定します**
（外部AI呼び出しは行いません）。判定ルールは以下のとおりです。

- 本文の1行目は、既存の取り込み慣例によりタイトル重複行のため、カード内部の描画対象から除外する
  （`line_range`で参照範囲を絞るだけで、行の並べ替え・複製は一切行わない）
- 本文の最終行が`※`で始まる場合は、独立した注記として`notice_region`に描画し、カード内部の描画対象
  から除外する
- 本文中に`◎`を含む行があれば、その行だけを大きめの太字・アクセント色の独立ブロックとして分離する
  （元の行を並べ替えたり複製したりしない。同じ`source_field`の異なる部分を複数ブロックへ分けて
  文字サイズ・強調を変える手法は、Phase 10.12の`line_range`と同じ考え方）
- 本文中に「例1）」「例2）」のような番号付き例示が2箇所見つかった場合、その区間を2段組み
  （`columns: 2`、`split_at`で「例2）」の直前を明示分割）にする。左右の幅比率（`column_ratio`）は、
  両列の最長行を実測して自動提案する（Phase 10.12の実データレビューで判明した調整と同じ考え方）
- カード内部の合計段落数が少ないページは`vertical_alignment: "center"`、中程度は`"distributed"`
  （ブロック間に均等な余白を挿入）、多いページは`"top"`にする

生成された各ブロックは`source_field`（`body`/`summary`）と`line_range`で本文の一部を参照するだけで、
デザインJSON側に本文そのものを複製しません（Phase 10.12以来一貫した安全設計）。

## 7. 強調ルール（`emphasis`）

`emphasis`は、Codexが装飾を考える際の参考情報として、本文中の実在する一節への参照
（`{"source": "body", "match": "...", "style": "strong"}`）を持ちます。**本文そのものはここに
複製されません。** `match`が現在の`lesson_pages.json`の該当フィールドに実在しない場合、
ページ仕様の検証は失敗します（`validate_page_spec()`）。

## 8. Codex向け最終画像生成パッケージ

### 8.1 `CODEX_FINAL_IMAGE_GENERATION.md`

自己完結した指示書です。`prepare-final-image-package`実行後、以下の1文をコピーしてCodexへ渡してください
（コマンド実行時の標準出力にもそのまま表示されます）。

```text
output/ocr_engine_eval/final_image_package/CODEX_FINAL_IMAGE_GENERATION.mdを読み、記載された手順を最後まで実行してください。
```

指示書には、Codexが**文字を一切含まない背景・装飾画像のみ**を生成すること、`content_card`等の
固定領域の内側に装飾を置かないこと、確定済み本文（`text/page_NNN.json`）は画像へ描画するための
データではなく参考情報であることが明記されています。

### 8.2 `prompts/master_background.md` / `prompts/page_NNN.md`

共通の背景生成プロンプトと、その派生であるページ別の差分プロンプトです。いずれも「日本語・英語を
問わず一切の文字を生成しない」「本文カード等の固定領域に装飾を置かない」ことを明記しています。

### 8.3 `text/page_NNN.json`

Phase 10.13で人間承認済みの確定本文（`title`/`body`/`summary`/`notice`）のスナップショットです。
`notice`は本文の最終行（`※`で始まる注記行）を分離したものです。

## 9. プレビュー（完成画像ではない）

`final_image_package/preview/page_NNN.png`・`rendered_brushup_preview/page_NNN.png`は、
固定マスターへ実際に収まるか（オーバーフローしないか）・全ページで本当にカード寸法が揃っているかを
確認するためのものです。Codexの背景生成前のプレビューであり、**最終的な視覚品質の評価対象では
ありません**。

`preview/master_guides.png`は、キャンバス・4つの固定領域・カード内側パディングを座標付きで可視化した
ガイド画像です。全ページが同じマスターを使っていることを視覚的に確認できます。

`preview/comparison.html`は、外部CDN・外部CSS・外部JSに依存しない自己完結HTMLで、元画像とプレビュー・
カード座標・内部レイアウト種別・強調ルールをページごとに並べます。

## 10. 検証項目（`validate_page_spec`/`validate_master_layout`/`validate_text_snapshot`）

- 全ページでキャンバスサイズ・`content_card`のx/y/width/height・`notice_region`・
  `page_number_region`が完全に同一であること（`MASTER_LAYOUT.json`から供給されるため構造的に保証される）
- ページ別仕様がマスター座標（`canvas`/`content_card`/`regions`等）を上書きしようとしていないこと
- ページ別仕様の`source_lesson_pages_sha256`が`MASTER_LAYOUT.json`と一致すること
- 本文を複製するフィールド（`text`/`content`/`value`等）が使われていないこと
- `emphasis[].match`が現在の`lesson_pages.json`に実在すること
- `text/page_NNN.json`が現在の`lesson_pages.json`（`title`/`body`（注記除く）/`summary`/`notice`）と
  一致すること

## 11. 既存機能との関係

- Phase 10.12（`prepare-image-brushup`/`render-brushup`）の完了を前提とする（未完了・古い場合は拒否）
- `editable/lesson_pages.json`・元画像・既存の`rendered/`・`rendered_brushup/`は変更しない
- `apply-content-brushup`で本文が更新された場合、`brushup_design`と同様に本コマンドの再実行が必要
  （`MASTER_LAYOUT.json`の`source_lesson_pages_sha256`で検出可能）

## 12. 制限事項

- ページ別内部レイアウト（1段組み/2段組み・強調箇所）の判定は、本文中の記号パターン
  （`◎`・「例N）」）に基づく機械的なルールベースであり、AIエージェントによるページごとの
  デザイン判断（Phase 10.12の`prepare-image-brushup`のような）は行っていない
- 強調は段落（行）単位の一括スタイル変更であり、1行内の一部の文字だけをハイライトする表現は未対応
- 2段組みの列幅比率（`column_ratio`）は両列の最長行の実測に基づく自動提案であり、Phase 10.12の
  実データレビューで行ったような人間の目視調整は行っていない
- Codexによる実際の最終画像生成・完成画像の確定はPhase 10.15（未実装）の役割であり、本Phaseの
  範囲外
