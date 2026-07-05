# 05 実装タスク

## Phase 1: CLI最小実装
- [x] JSON読み込み
- [x] データバリデーション
- [x] ページ番号順ソート
- [x] `brushup.md` 生成
- [x] `canva_design.md` 生成

## Phase 2: 品質向上
- [x] 入力エラー時のメッセージ改善
- [x] サンプルデータ追加
- [x] pytest追加
- [x] README更新

## Phase 3: AI連携
- [x] 文字起こしプロンプト整備
- [x] ブラッシュアッププロンプト整備
- [x] Canvaプロンプト整備
- [x] API連携設計

## Phase 4: 将来拡張
- [x] DOCX出力
- [x] PDF出力
- [x] Canva API連携
- [x] WordPress投稿連携
- [x] 動画生成用シナリオ出力

## Phase 5: v2.0 3モード対応（`docs/00_redesign_v2.md`）
- [x] `lesson-pages`コマンドに`--mode`（proofread/restructure/generate）を追加
- [x] `--requirements`を追加
- [x] `Requirements`モデル・バリデーションを追加（`src/models.py`）
- [x] `lesson_pages.json`に`metadata`（`mode`等）を追加
- [x] 各ページに`source_page_no`を追加（proofread/restructureは元ページ番号、generateは空配列）
- [x] `examples/requirements_ai_instagram.json`を追加
- [x] モード別テスト・requirementsバリデーションテストを追加
- [x] README / docs/04_output_spec.mdを更新

## Phase 6: input/output除外 & restructure本格化
- [x] `.gitignore`に`input/`/`output/`/`*.zip`/`.DS_Store`/仮想環境ディレクトリを追加
- [x] `scripts/make_release_zip.sh`を追加（`input/`/`output/`/`.git/`等を除外した配布ZIPを作成）
- [x] READMEに`input/`/`output/`除外方針・`git rm --cached`手順を明記
- [x] `restructure`にルールベースの再構成ロジックを実装（元ページの中間表現抽出→再構成プラン→本文組み立ての2段階）
  - [x] 内容が薄いページの統合（`merge`）
  - [x] 長すぎるページの分割（`split_first_half`/`split_second_half`）
  - [x] 導入ページ・実践ページ・まとめページの追加（`add_intro_from_source`/`add_practice`/`add_summary`）
  - [x] 変更のないページの引き継ぎ（`carry_over`）
- [x] 各ページに`role`（`intro`/`explanation`/`practice`/`summary`）を追加
- [x] `lesson-pages --plan-output`で再構成プラン（`restructure_plan.json`相当）を出力可能に
- [x] `review-report`コマンドを追加（`role`/`source_page_no`を制作者確認用にMarkdown化。配布用PDF/DOCXには非表示のまま）
- [x] restructureの再構成テスト・DOCX/PDFが`source_page_no`/`role`を露出しないことのテストを追加

## Phase 7: restructureの信頼性・品質改善（現状調査に基づく改善B/A/C）

現状調査（restructure機能の弱点整理）に基づき、設計者判断でB→A→Cの順に対応。D（introのsource_page_noを全ページに拡大）/E（3ページ以上の連鎖merge）/G（`--plan-input`追加）は保留、`Requirements.page_count`・LLM/API/OCR連携も今回は対象外。

- [x] B: `apply_restructure_plan`で`merge`/`split_first_half`/`split_second_half`/`carry_over`が参照する元ページが存在しない場合、`IndexError`ではなく原因の分かる`ValueError`を送出するよう修正
- [x] A: restructure後の`layout_instruction`/`source_image`の欠落を解消
  - `merge`ページ: 統合元ページの`layout_instruction`を` / `で結合、`source_image`は統合元のうち最初に存在するものを採用
  - `split_first_half`/`split_second_half`ページ: 分割元ページの`layout_instruction`/`source_image`を両方に継承
  - `carry_over`ページ: 元ページの`layout_instruction`/`source_image`を維持
  - `intro`/`practice`/`summary`ページ: 元ページからの単純コピーではなく、roleに応じた汎用`layout_instruction`を設定（`source_image`は空のまま）
- [x] C: `merge`本文に、統合元ページの`title`を`## タイトル`見出しとして挿入
- [x] 上記に対応するテストを追加（`tests/test_lesson_pages_modes.py`に9件追加）
- [x] Cの副作用修正: `image_text`/`canva_prompt`/`video_scene`にMarkdown見出し記法（`#`/`##`/`###`等）が混入していたのを除去。`body`自体の見出し行は維持（`brushup.md`/DOCX/PDFの本文構造化に使うため）。`#タグ`のようなハッシュタグ形式は誤って除去しないよう区別
- [ ] D: introの`source_page_no`を全ページに拡大（保留）
- [ ] E: 3ページ以上の連鎖merge対応（保留）
- [ ] G: `--plan-input`（プラン読み込み→適用）コマンドの追加（保留）

### 出力の目視確認・派生フィールド棚卸しで判明した残課題
- [x] `_build_practice_body`/`_build_summary_body`が`- 項目`というMarkdown箇条書き記号を`body`に直接埋め込んでいた問題を修正。`body`側は自然文の行のみとし、箇条書き記号は各レンダラー（brushup.md/DOCX/PDF/scenario.md）側の描画のみが付与するようにした（`brushup.md`/DOCX/PDFでの「• - 項目」という二重表示を解消）。
- [x] `scenario`コマンド（`scenario.json`/`scenario.md`/`scene.json`/`voicevox.txt`）が`LessonPage.video_scene`を使わず`body`を独自に再解析していたため`## タイトル`/`- 項目`が混入していた問題を修正。`dialogue_lines_for_scenario()`を新設し、`video_scene`が存在する場合はそれを（`dialogue_lines_from_video_scene()`で構造化して）優先利用、空の場合のみ`clean_dialogue_lines()`で`body`からクリーン済みテキストを生成するフォールバックに変更。
- [x] `layout_instruction`/`notes`のMarkdown混入リスク: 調査の結果、設計者判断で**案C（`canva_design.md`出力時のみ除去）**を採用し実装。`src/canva_renderer.py`に`_clean_canva_free_text()`を追加し、「### レイアウト指示」セクションの表示直前にのみ行頭の見出し記法（`#`/`##`/`###`）・箇条書き記法（`-`/`*`、直後に空白があるもののみ）を除去する。`lesson_pages.json`側の`layout_instruction`自体・`canva_prompt`/`video_scene`/`scenario`出力（`scene.json`の`visual_prompt`含む）は変更していない。`notes`は現状`canva_design.md`のどのセクションにも直接表示されないため対象外（表示箇所がないため）。案D（入力時点で正規化）は不採用。詳細は`docs/04_output_spec.md`「レイアウト指示のMarkdown記法除去」を参照。
- [x] `page.summary`のMarkdown混入リスク: 調査の結果、設計者判断で**案C（Markdownとして解釈される表示系出力に限定して除去）**を採用し実装。`src/canva_renderer.py`の`_clean_canva_free_text()`を`summary`（### 概要）・`image_text`（### 画像内テキスト。`body`が空で`summary`にフォールバックする場合を含む）にも適用し、`src/renderer.py`に同種の`_clean_summary_for_display()`を追加して`brushup.md`の「### 概要」にも適用した。`lesson_pages.json`側の`summary`/`image_text`自体、`canva_prompt`/`video_scene`/`scenario`出力/DOCX/PDF/WordPress投稿本文は変更していない。案D（生成時点で正規化）は不採用。詳細は`docs/04_output_spec.md`「Markdownとして解釈される出力でのMarkdown記法除去」を参照。

### 最終棚卸し（2026-07-05実施）— Phase 7完了扱い

`title`/`summary`/`body`/`image_text`/`canva_prompt`/`video_scene`/`layout_instruction`/`notes`/`review-report`/`scenario`系出力・README/docs/04/05自体について、`# 見出し`・`## 見出し`・`### 見出し`・`- 箇条書き`・`* 箇条書き`・`#ハッシュタグ`・文中の`#`/`-`・URL・ファイル名を含むテストデータで、proofread/restructure両モードの実出力を確認した。

- `title`はすべての出力で「Page N: {title}」のようにプレフィックス付きで埋め込まれるため、行頭にならず安全（DOCX/PDF/scenario.md/review-report含む）。
- `review-report`は`role`/`source_page_no`/`title`のみを出力し`summary`/`body`/`image_text`等を一切使わないため、そもそも対象外（安全）。
- `scenario.json`/`scene.json`はJSON文字列としてのみ扱われ、Markdownとして解釈されるファイル形式ではないため、内容に関わらず構造的に安全。
- README.md/docs/04/05自体の例示（`` `# 見出し` `` 等）はすべてインラインコードで囲われており、ドキュメント自身のMarkdown構造を壊していないことを確認した。
- **新規判明（Phase 7スコープ外の既知の制約として記録。今回は未修正）**: `body`の話者が空文字かつ台詞テキストが`"- "`で始まる場合（例: `{"speaker": "", "text": "- 大事なポイント"}`）、`brushup.md`・`scenario.md`・DOCX・PDFの箇条書きレンダリングが二重の記号（Markdownでは`"- - 大事なポイント"`、DOCX/PDFでは箇条書き記号＋文字通りの"-"）になる。`canva_design.md`の「### 画像内テキスト」は`_clean_canva_free_text()`が`-`も除去するため対象外（影響なし）。DOCX/PDFはMarkdownとして解釈されないため実害は文字面のみ。この事象はPhase 7で修正した「システムが生成するMarkdown記法の混入」（merge見出し・practice/summaryの箇条書き・layout_instruction/summary/image_textの表示時除去）とは別種の、**ユーザーが入力した本文の話者無し行が偶然ハイフンで始まる場合の表示上の癖**であり、`body`自体を書き換えない方針や`parse_body_lines`の解析ロジックに関わる、より大きな設計判断を要するため、Phase 7の範囲には含めない。

以上より、**Phase 7（restructureの信頼性・品質改善、および出力品質改善の一連の対応）は完了扱いとする。** 新規判明した残課題（body話者無し行のハイフン二重記号）は次フェーズ以降の候補として別途記録する。

## Phase 8: 実利用テスト・品質評価フェーズ

新機能追加（D/E/G、`--plan-input`、連鎖merge、`Requirements.page_count`等）には進まず、実際の教材素材を入力したときの生成物の品質を評価するフェーズ。

### 初期設計（運用手順のみ整備。以下は設計見直しにより不採用）

- [x] ~~実材料のテンプレートを追加（`examples/real_material_template.json`）~~ → 作成者にJSONを手作業で作らせる運用は不採用となり、以下「設計見直し」により削除。`examples/sample_pages.json`が開発者向けのpages形式サンプルとして残る。

### 設計見直し: 元資料自動取り込み・一括生成へ（実装済み）

Phase 8を「元資料自動取り込み・一括生成の実利用評価フェーズ」として再定義。作成者に`real_material_template.json`/`imported_pages.json`/`lesson_pages.json`/Markdown/TXTを手作業で作らせる運用は採用しないこととし、以下を実装した。

- [x] `src/import_source.py`を新設: 元資料（画像/PDF/PPTX）から`pages`形式互換のJSONを自動生成する取り込み処理
  - 画像（`.png`/`.jpg`/`.jpeg`/`.webp`）: ディレクトリ配下をファイル名順に1画像=1ページとして取り込み、OCR（`pytesseract`。tesseract本体が無い環境ではテキスト空でフォールバックし、取り込み自体は失敗させない）でテキスト抽出、元画像を`output/assets/`にコピー
  - PDF（`.pdf`）: `pymupdf`（PyMuPDF）でページ単位にテキスト抽出＋ページ画像化し、`output/assets/`に保存
  - PPTX（`.pptx`）: `python-pptx`でスライド単位にテキスト抽出＋スライド内埋め込み画像を`output/assets/`に保存（スライド全体を1枚の画像としてレンダリングする機能は外部レンダラーが必要なため対象外。埋め込み画像の保持のみ対応し、その旨を`canva.notes`に明記）
  - `.ppt`（旧形式）は未対応であることを明示するエラーメッセージのみ実装
- [x] `Page`/`LessonPage`/`SourcePageSummary`に`source_assets`（1ページに複数の関連画像がある場合の追加アセット一覧）を追加。`source_image`と同じ経路（proofreadは1:1継承、restructureのmerge/split/carry_overは`_merge_source_assets`/直接継承）で伝播する
- [x] CLIサブコマンド`import-source`を追加: 元資料から`imported_pages.json`（`pages`形式互換）と`output/assets/`を生成
- [x] CLIサブコマンド`build-all`を追加: `import-source`→`lesson-pages`→`generate`/`canva`/`docx`/`pdf`/`scenario`/`review-report`を一括実行。`--mode`は`proofread`/`restructure`、`--requirements`は`restructure`時のみ任意
- [x] `canva_design.md`の各ページに「元画像: {source_image}」「参考画像: {source_assets}」を明記（`src/canva_renderer.py`）
- [x] `docs/08_user_acceptance_test.md`/README.md/`docs/README.md`/`docs/04_output_spec.md`を、作成者向けの主導線が「元資料を置いて`build-all`実行」になるよう書き換え。`examples/real_material_template.json`は削除（`sample_pages.json`が開発者向けサンプルとして残る）
- [x] テスト追加（`tests/test_import_source.py`/`tests/test_build_all_cli.py`/`tests/test_lesson_pages_modes.py`/`tests/test_renderers.py`）: ファイル名順page_no付与、assets保存、`project_from_dict`との互換性、`build-all`によるoutput一式生成、proofreadでのページ順・source_page_no維持、restructureでのsource_page_no保持、canva_design.mdでのsource_image表示、`source_assets`のmerge時の重複排除
- [ ] 実際の教材素材（画像/PDF/PPTX）でのテスト実施・フィードバック収集（利用者による実施待ち）
- [ ] フィードバックに基づく次フェーズ（D/E/G等）の着手判断

### 今回実装しなかったもの（意図的に対象外）

ユーザーにJSON/Markdown/TXT作成を要求する運用、DOCX取り込み、OCR精度改善の高度化、LLM/API連携、`--plan-input`、3ページ以上の連鎖merge、introの`source_page_no`拡大、`Requirements.page_count`。

### 全体整合性チェック（2026-07-05実施）

Phase 8の設計変更（`input/source/`+`build-all`導線追加）により、既存の新規構築フロー（`generate`モード）・開発者向けサンプル・個別CLI・各rendererが壊れていないかを確認した。

- [x] `docs/01_requirements.md`/`docs/02_architecture.md`が更新されておらず、CLIコマンド表に`import-source`/`build-all`が無い、OCRが「対象外」のまま、`source_assets`が未記載など、実装と乖離していた点を修正
- [x] README「クイックスタート（作成者向け）」が`build-all`一辺倒で、元資料が無い新規構築（`generate`モード）への導線が無かったため、分岐の説明・対応表を追加（`docs/README.md`「迷ったときは」・`docs/08_user_acceptance_test.md`冒頭にも追記）
- [x] `generate`モード（元資料無し）のフルパイプライン（`lesson-pages`→`generate`/`canva`/`docx`/`pdf`/`scenario`/`review-report`）が、`source_image`/`source_assets`空のまま全出力を生成できることを実地確認・テスト追加
- [x] `examples/sample_pages.json`が個別CLI経由で引き続き単体動作すること、`build-all`導線と個別CLI導線が同一セッション内で干渉しないことをテストで確認
- [x] `real_material_template.json`への参照がリポジトリ全体（docs/05の履歴記録を除く）に残っていないことをテストで保証
- [x] pytest 197件・`run_sample.sh`とも成功を確認

## Phase 9: output形式選択・editable中間ファイル・画像output・再生成導線

Canva指示書を主outputとする設計を改め、「配布・確認用の完成output」と「再生成用の編集可能な中間output」の2系統に整理した。既存の`generate`モード・`build-all`導線・個別CLI導線・既存rendererは壊さない前提で、既存構造への追加として実装した。

- [x] `output/editable/lesson_pages.json`を正式な中間output（再生成時にユーザーが編集する対象）として追加。`--output-format`の指定に関わらず`build-all`が常に生成する
- [x] `src/image_renderer.py`を新設: 完成画像（`output/rendered/page_NNN.png`）を生成。`source_image`があればそれを採用（教材に限らずチラシ・SNS投稿画像等、元のビジュアルを尊重）、無ければ`title`/`summary`/本文を描画した簡易画像を合成（日本語フォントはmacOSの`ヒラギノ角ゴシック`等を優先探索し、見つからない環境ではPillow既定フォントにフォールバック）
- [x] `src/pptx_export_renderer.py`を新設: PPTX export（`output/exports/material.pptx`）を生成。1ページ=1スライドに、タイトルのテキストボックスと完成画像を配置する簡易構成（`python-pptx`の書き込みAPIを利用。複雑な図形・アニメーションの再現は対象外）
- [x] `build-all`に`--output-format`（`same`/`image`/`pdf`/`pptx`/`docx`/`md`/`canva`/`json`/`all`。既定`same`）を追加。`same`は入力の性質（画像/PDF/PPTX）に応じて具体的な形式に解決する
- [x] `canva`は`output/canva/canva_design.md`（オプション出力の一つ）として生成するよう位置づけを変更。ただし後方互換のため、`output_dir`直下の`canva_design.md`（Phase 8時点の生成先）も`--output-format`に関わらず引き続き生成する
- [x] CLIサブコマンド`regenerate`を追加: `output/editable/lesson_pages.json`（またはユーザーが編集した同形式JSON）から完成outputを再生成。`--output-dir`省略時は`--input`の2階層上を出力先とする
- [x] 後方互換の確認: `build-all`が生成するPhase 8時点の成果物一式（`output_dir`直下の`lesson_pages.json`/`brushup.md`/`canva_design.md`/`brushup.docx`/`brushup.pdf`/`scenario/`/`review_report.md`）は変更せず、Phase 9の新規出力（`editable/`/`rendered/`/`canva/`/`exports/`）は追加として生成する（既存197件のテストを変更せずに全件通過することで裏付け）
- [x] ドキュメント更新（README.md/`docs/01_requirements.md`/`docs/02_architecture.md`/`docs/04_output_spec.md`/`docs/08_user_acceptance_test.md`/`docs/README.md`/`docs/feedback_template.md`）: output形式選択・editable中間ファイル・画像output・Canva指示書のオプション化・再生成コマンドの使い方を反映
- [x] テスト追加（`tests/test_output_formats.py`ほか）: editable常時出力、`--output-format`各値（same/image/canva/json/all/pdf/pptx/docx/md）、`regenerate`（editable編集後の再生成・明示的`--output-dir`・generateモード互換）
- [ ] 実際の教材素材でのPPTX export・画像output品質のフィードバック収集（利用者による実施待ち）

### 今回実装しなかったもの（意図的に対象外）

PPTX exportの高度なレイアウト再現（図形・アニメーション等）、画像合成のデザイン性向上（フォント選択の高度化含む）、`--output-format`の設定ファイル化、LLM/API連携によるレイアウト自動デザイン。

### 追加修正: 同名ファイルの重複解消と後方互換outputの整理（Phase 9.1）

Phase 9実装直後、`output/editable/lesson_pages.json`/`output/canva/canva_design.md`（正式output）と、Phase 8互換のため`output_dir`直下に生成していた`lesson_pages.json`/`canva_design.md`が同名で重複し、どちらを編集・参照すべきか分かりにくい問題が判明した。以下の通り整理した。

- [x] `build-all`が生成する後方互換用の`lesson_pages.json`/`canva_design.md`を`output_dir`直下から`output/compat/`配下に移動。`output_dir`直下には同名ファイルを重複させない
- [x] `build-all`に`--no-compat-output`フラグを追加（既定は`compat_output=True`＝互換output生成。指定すると`output/compat/`自体を生成しない）。デフォルトで後方互換outputを生成しない案（opt-in）も検討したが、Phase 8時点のドキュメント・利用手順への影響が大きいため見送り、既定は「生成するが場所を移す」を採用（設計判断の詳細は完了報告を参照）
- [x] `brushup.md`/`brushup.docx`/`brushup.pdf`/`scenario/`/`review_report.md`は同名重複が無いため、従来通り`output_dir`直下に生成する変更は加えていない
- [x] ドキュメント更新（README.md/`docs/01_requirements.md`/`docs/02_architecture.md`/`docs/04_output_spec.md`/`docs/08_user_acceptance_test.md`）: 正式output（`editable/`・`canva/`）と後方互換output（`compat/`）の違いを明記
- [x] テスト更新: `output_dir`直下の`lesson_pages.json`/`canva_design.md`を参照していた既存テスト（`tests/test_build_all_cli.py`の5件、`tests/test_output_formats.py`の1件）を、正式output（`editable/`/`canva/`。`--output-format canva`指定時）または`compat/`配下の参照に更新。新規に「直下への重複が無いこと」「`--no-compat-output`でcompat/自体が生成されないこと」を確認するテストを追加

### 追加修正: brushup系outputとexports系outputの役割重複整理（Phase 9.2）

Phase 9.1では`lesson_pages.json`/`canva_design.md`の同名重複のみ解消したが、`brushup.md`/`brushup.docx`/`brushup.pdf`（`output_dir`直下）と`exports/material.md`/`material.docx`/`material.pdf`（Phase 9の正式output）が同名ではないものの役割が重複し、「どちらが正式か」分かりにくい問題が判明した。以下の通り整理した。

- [x] `build-all`が生成する後方互換用の`brushup.md`/`brushup.docx`/`brushup.pdf`を`output_dir`直下から`output/compat/`配下に移動し、`--no-compat-output`（Phase 9.1で追加済み）の対象に含めた。`output_dir`直下には正式な完成outputを置かない方針とした
- [x] `scenario/`/`review_report.md`は正式outputとの役割重複が無いため、従来通り`output_dir`直下に生成する変更は加えていない
- [x] ドキュメント更新（README.md/`docs/01_requirements.md`/`docs/02_architecture.md`/`docs/04_output_spec.md`/`docs/08_user_acceptance_test.md`/`docs/README.md`）: 正式な完成outputは`output/exports/`のみであること、`brushup.*`は後方互換専用で新規利用では参照しないことを明記
- [x] テスト更新: `output_dir`直下の`brushup.md`/`brushup.docx`を参照していた既存テスト（`tests/test_build_all_cli.py`の2件、`tests/test_output_formats.py`の2件）を、`compat/brushup.*`参照に更新。新規に「`brushup.*`が直下に生成されないこと」「`exports/material.*`が正式outputとして生成されること」「`--no-compat-output`で`compat/brushup.*`も生成されないこと」を確認するテストを追加

### 共通設計ルールの明文化（Phase 9.2完了後）

今後のPhase指示文で毎回同じ設計方針を書き下さなくて済むよう、Phase 9.2までに確定したoutput構成・editable中間ファイル・source情報の扱いを、プロジェクト共通設計ルールとして固定化した。実装ロジックの変更は無し（ドキュメント整理のみ）。

- [x] `CLAUDE_RULES.md`に「プロジェクト設計ルール（output構成・editable中間ファイル・source情報の扱い）」節を新設。output構成（`editable/`/`rendered/`/`canva/`/`exports/`/`compat/`）・editable中間ファイルの運用（編集→`regenerate`→再生成）・source情報の扱い（`source_image`/`source_assets`を落とさない、`source_page_no`は内部メタデータ）を要約
- [x] `docs/04_output_spec.md`冒頭に「プロジェクト標準output構成（Phase 9.2時点で確定・共通設計ルール）」節を新設。詳細仕様の正となる参照先として位置づけた
- [x] `docs/02_architecture.md`/`docs/README.md`/README.mdに、上記2ファイルへの参照ポインタを追加
- [x] 今後のPhase指示文で使える短い参照文言をCLAUDE_RULES.mdに明記（「CLAUDE_RULES.mdおよびdocs/04_output_spec.mdに定義済みの...を維持してください」）
- [x] docs consistencyテストを追加: 共通設計ルールがCLAUDE_RULES.md/docs/04_output_spec.mdに明記されていることを確認

## Phase 10: 画像output品質・日本語フォント・再生成編集ガイドの改善

Phase 9.2で確定したoutput構成（`editable/`/`rendered/`/`canva/`/`exports/`/`compat/`）は変更せず、画像outputの実用性・日本語フォント問題の検知・editable編集運用の説明を強化した。

- [x] `src/image_renderer.py`のフォント探索候補をmacOS/Linux/Windowsそれぞれ複数パスに拡充（`_JAPANESE_FONT_CANDIDATES`）
- [x] `resolve_font_path()`を新設: `--font-path`明示指定時はその場で検証（存在しない/読み込めない場合は`ValueError`で明確にエラーにする。黙ってフォールバックしない）。未指定時は環境の候補を自動探索
- [x] `warn_missing_japanese_font()`を新設: テキスト合成が必要なページがあるのにフォントが1つも見つからない場合、標準エラー出力に警告を1回表示したうえで処理は継続する（黙って文字化けリスクを抱えない）
- [x] `build-all`/`regenerate`に`--font-path`オプションを追加。画像output（`rendered/`・PPTX内画像）の日本語テキスト合成に使うフォントを明示指定できる
- [x] `_synthesize_page_image()`を改善: ページ番号ヘッダー・タイトル・区切り線・概要・本文（折り返し・打ち切り時の案内表示付き）・フッターのページ番号を、全ページ共通のレイアウトで描画するように整理し、読みやすさ・一貫性を向上
- [x] `docs/09_editable_regenerate_guide.md`を新設: `output/editable/lesson_pages.json`の編集してよい項目・編集しない方がよい項目、JSON構文の注意、`regenerate`の具体例（画像/PDF/Canva指示書/全形式/日本語フォント指定）、フォント未検出時のトラブルシューティングをまとめた。`docs/README.md`から参照できるようにした
- [x] ドキュメント更新（README.md/`docs/01_requirements.md`/`docs/02_architecture.md`/`docs/04_output_spec.md`/`docs/08_user_acceptance_test.md`/`docs/feedback_template.md`）: `--font-path`・フォント未検出警告・editable編集ガイドへの参照を追加
- [x] テスト追加（`tests/test_image_renderer.py`10件、`tests/test_output_formats.py`+5件）: フォント解決（明示パス有効/無効/読み込み不可/自動探索なし）、フォント未検出時の警告と処理継続、複数ページの画像生成、`--font-path`が`build-all`/`regenerate`で受け付けられ実際にimage_rendererへ渡ること、無効な`--font-path`で明確なエラーになること
- [ ] 実際の教材素材での画像output品質・日本語フォント表示のフィードバック収集（利用者による実施待ち）

### 今回実装しなかったもの（意図的に対象外）

画像合成の高度なデザインエンジン化（装飾性の高いレイアウト自体）、`--font-path`の設定ファイル化、PPTX exportの高度なレイアウト再現。
