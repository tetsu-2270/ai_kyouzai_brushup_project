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

現状調査（restructure機能の弱点整理）に基づき、設計者判断でB→A→Cの順に対応。D（introのsource_page_noを全ページに拡大）/E（3ページ以上の連鎖merge）/G（`--plan-input`追加）は保留、`Requirements.page_count`・ローカルLLM/外部API/OCR連携も今回は対象外。

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

ユーザーにJSON/Markdown/TXT作成を要求する運用、DOCX取り込み、OCR精度改善の高度化、ローカルLLM/外部API連携、`--plan-input`、3ページ以上の連鎖merge、introの`source_page_no`拡大、`Requirements.page_count`。

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

PPTX exportの高度なレイアウト再現（図形・アニメーション等）、画像合成のデザイン性向上（フォント選択の高度化含む）、`--output-format`の設定ファイル化、ローカルLLM/外部API連携によるレイアウト自動デザイン。

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

## Phase 10.1: OCR前提ソフトウェアの事前チェック・PATH診断・セットアップ導線・OCR空振り防止

`input/source`の実データ（画像27枚）で`build-all --mode proofread`を実行したところ、全ページOCR結果が空になる問題が発生した。原因調査の結果、tesseract本体が環境に無く（Homebrewは`/opt/homebrew/bin/brew`に存在するがPATHに無い状態）、OCRが実質的に失敗していたことが分かった。これを「黙って空データのまま成功扱いにする」のではなく、分かりやすく検知・案内するようにした。

- [x] `src/ocr_environment.py`を新設: `check_tesseract_environment()`/`check_homebrew_environment()`（PATH上・既知パス（`/opt/homebrew/bin/`・`/usr/local/bin/`）・バージョン・利用可能言語を確認）、`get_ocr_environment_status()`（両者を統合し`ocr_ready`/`path_suggestions`/`warnings`/`errors`を算出）、`resolve_ocr_lang()`（`jpn+eng`/`jpn`/`eng`の選択）を実装
- [x] `src/import_source.py`の`_try_ocr()`を改善: 環境診断で見つかったtesseractパス（PATHに無くても既知パスで見つかっていれば使う）と対応言語をpytesseractに明示的に渡すようにした
- [x] `import_images()`にOCR前提の事前チェックを追加: OCR環境が整っていない場合、標準エラー出力に警告（英語+日本語）を表示したうえで処理を継続。全ページのOCR結果が空だった場合も追加の警告を表示する。**既存の`generate`/`build-all`/`regenerate`/個別CLI導線や、Tesseract未導入のCI・開発環境でも動作し続けられるよう、非ゼロ終了にはしていない**（後方互換上のトレードオフ。詳細は完了報告参照）
- [x] `python3 -m src.cli check-ocr`サブコマンドを追加: tesseract/Homebrewの状態と対応手順を表示するOCR環境診断コマンド
- [x] `scripts/check_ocr_env.sh`を追加: シェルベースの同等診断（インストールは行わず、確認・案内のみ。個々のコマンドが無くても最後まで実行する）
- [x] `scripts/setup_ocr_macos.sh`を追加（任意）: Homebrew経由でTesseract・日本語言語データを実際にインストールするスクリプト。ユーザーが明示的に実行するものであり、CLI本体・Claude Codeが自動実行することはない
- [x] ドキュメント更新（README.md/`docs/01_requirements.md`/`docs/02_architecture.md`/`docs/04_output_spec.md`/`docs/08_user_acceptance_test.md`）: OCR前提の事前チェック・`check-ocr`の使い方・PATH診断・よくある状態と対処を追加
- [x] テスト追加（`tests/test_ocr_environment.py`21件、`tests/test_import_source.py`+6件、`tests/test_output_formats.py`+4件）: tesseract/Homebrewの検出パターン（PATH上/既知パスのみ/無し）、jpn言語データ有無、PATH案内文言、OCR結果が`imported_pages.json`/`editable/lesson_pages.json`に反映されること、全ページ空の警告、`check-ocr`コマンドの実行確認

### 今回実装しなかったもの・意図的なトレードオフ（**Phase 10.1追加修正で解消。下記参照**）

~~OCR環境が整っていない場合の非ゼロ終了（exit 1）は実装していない。理由: 既存テストスイート・本開発環境自体がtesseract未導入であり、非ゼロ終了にすると`generate`/`build-all`の既存テスト（ダミー画像を使うもの多数）が軒並み失敗し、「pytestがすべて通る」「既存導線が壊れていない」という受け入れ条件と直接衝突するため。~~ → 既存テストがTesseract未導入環境でも通り続けられるよう、`tests/conftest.py`にOCR環境を「利用可能」とみなす既定fixtureを追加することで両立させ、`build-all`の`proofread`/`restructure`は非ゼロ終了するように変更した（詳細は次項）。

## Phase 10.1 追加修正: OCR必須モードでOCR不能時は正常終了しない

Phase 10.1で追加した警告は表示されるものの、`build-all --mode proofread`はTesseract未導入・全ページOCR空でも`exit 0`のまま「成功」してしまい、校正対象のテキストが無いまま処理が完了する問題が残っていた。`proofread`/`restructure`にとってOCRテキストは処理の前提であるため、これを非ゼロ終了に変更した。

- [x] `src/ocr_environment.py`に`OCR_REQUIRED_MODES = {"proofread", "restructure"}`と、非ゼロ終了用エラーメッセージ生成関数（`format_ocr_required_tesseract_missing_error`/`format_ocr_required_japanese_missing_error`/`format_ocr_required_all_pages_empty_error`/`format_partial_pages_empty_warning`）を追加
- [x] `src/cli.py`に`_validate_ocr_precondition()`を追加し、`build_all()`の`import-source`ステップ直後（`lesson_pages`生成前）で呼び出す。画像input（`_detect_input_kind()`が`"image"`）かつ`--allow-empty-ocr`未指定の場合のみ動作し、Tesseract未導入・`jpn`無し・全ページOCR結果が空のいずれかで`SystemExit(1)`にする。一部ページのみ空の場合は警告のみで継続する
- [x] `build-all`に`--allow-empty-ocr`オプションを追加（既定は無効）。指定した場合のみ上記チェックをスキップし、従来通り（Phase 10.1時点の警告のみ）の挙動になる
- [x] `run_import_source()`が取り込んだpages辞書を返すように変更（`_validate_ocr_precondition()`が取り込み結果の`lines`を見て判定するため）
- [x] PDF/PPTX inputはネイティブテキスト抽出を使うため、このチェックの対象外（`_detect_input_kind()`で判定）
- [x] `tests/conftest.py`を新設: OCR環境を既定で「利用可能」とみなし、`_try_ocr()`もダミーの非空テキストを返すautouse fixtureを追加。OCRの有無を直接検証しないテスト（画像output・`--output-format`・`--no-compat-output`・`--font-path`等、Tesseract未導入のこの開発環境でも動作する必要がある既存テスト）が、新しい非ゼロ終了チェックの巻き添えにならないようにした。OCR環境診断自体を検証する`tests/test_ocr_environment.py`と、`_try_ocr()`の実装そのものを検証する2テストは、`@pytest.mark.real_ocr`でこのfixtureを無効化し、実装を直接検証する
- [x] `pyproject.toml`に`real_ocr`マーカーを登録
- [x] テスト更新: `test_build_all_prints_warning_when_tesseract_missing_for_image_input`（警告のみで継続、を期待する古いテスト）を`test_build_all_fails_when_tesseract_missing_for_image_input_proofread`（`SystemExit(1)`を期待する新しいテスト）に置き換え
- [x] テスト追加（`tests/test_output_formats.py`に6件）: Tesseract無し/jpn無し/全ページ空はエラー終了、一部ページ空は警告して継続、`--allow-empty-ocr`でチェックをスキップ、PDF inputはこのチェックの対象外
- [x] ドキュメント更新（README.md/`docs/01_requirements.md`/`docs/04_output_spec.md`/`docs/08_user_acceptance_test.md`）: `build-all`のOCR必須モードチェック・`--allow-empty-ocr`・エラー終了時の挙動を明記

### 今回実装しなかったもの（意図的に対象外）

`lesson-pages`単体コマンド（`build-all`を経由せず、既存のpages形式JSONを直接渡す経路）にはこのOCR必須チェックを追加していない。理由: `lesson-pages`は「元資料を画像から取り込む」処理そのものを行わず、渡されたJSONがOCR由来かどうかを区別する情報を持たないため（個別CLI導線を壊さない方針を優先）。同様の理由で、単体の`import-source`コマンドも警告のみで非ゼロ終了にはしていない。

## Phase 10.2: 成功判定の再点検・実行ログ出力追加・ログ仕様の共通設計化

Phase 10.1のOCR必須チェックと同じ観点で、他の処理にも「exit code 0だが実質失敗している」状態が残っていないか点検した。あわせて、実行内容・警告・失敗理由を後から追えるよう`logs/`ディレクトリへの実行ログ出力を追加し、ログ仕様をプロジェクト共通設計ルールとして明文化した。

### 成功判定の点検結果

- [x] **「pagesが0件でも成功扱い」だった箇所を発見**: `regenerate`が読み込んだ`document.pages`が空でも、そのまま（空の）成果物を生成して`exit 0`で終了していた。`build_all()`も、理論上0ページが取り込まれた場合（画像ディレクトリは既にチェック済みだが、PDF/PPTXで0ページの場合など）に同様の問題が起こり得た → 非ゼロ終了に変更
- [x] **「指定output-formatの成果物が生成されなくても成功扱い」だった箇所を発見**: レンダラーが何らかの理由で成果物を書き出せなかった場合でも、`build-all`/`regenerate`はそのまま`exit 0`で終了していた（従来、レンダラー自体が例外を投げない限り検知できなかった）→ `_verify_expected_outputs()`を追加し、生成後に実際にファイルが存在するか検証、無ければ非ゼロ終了に変更
- [x] 確認の結果、**既に正しく非ゼロ終了していた箇所**（変更不要）: 入力パス不存在（`FileNotFoundError`）、画像ディレクトリが空・対応ファイルが1つも無い場合（`import_source()`の既存の`ValueError`）、`regenerate`の入力ファイル不存在・JSON構文エラー（`parser.py`の既存の`FileNotFoundError`/`ValueError`）、OCR必須モードでOCR不能・全ページOCR空（Phase 10.1で対応済み）
- [x] `check-ocr`は診断コマンドとして意図的に`exit 0`のまま維持（環境不足を診断すること自体が目的であり、診断結果が悪いこと自体を失敗として扱わない）

### 実行ログ出力の実装

- [x] `src/execution_logger.py`を新設: `ExecutionLogger`（ログファイル作成・セクション記録・warning/error収集・generated_files記録・finalize時にファイル書き出し）、`TeeStderr`（標準エラー出力を元のストリームへ書きつつログ用にも蓄積。既存の`print(..., file=sys.stderr)`呼び出し箇所を個別に変更せずに済む）
- [x] `src/cli.py`の`main()`を、コマンドの成否に関わらず必ずログを書き出すよう変更（`try/except/finally`で`SystemExit`/`FileNotFoundError`/`ValueError`いずれの終了経路でも`logger.finalize()`を呼ぶ）
- [x] ログ出力対象: `build-all`・`regenerate`・`check-ocr`・`lesson-pages`（`--mode`に応じて`generate`/`proofread`/`restructure`をログファイル名にする）・個別CLI（`import-source`/`canva`/`docx`/`pdf`/`scenario`/`canva-sync`/`wp-publish`も基本的なINPUT/OUTPUT記録つきでログを出す）
- [x] `build_all()`/`regenerate()`/`_validate_ocr_precondition()`/`_generate_formatted_outputs()`に`logger`引数（省略可）を追加し、INPUT/INPUT_RESULT/OCR/OUTPUT/WARNINGS/ERRORSの各セクションを記録するようにした
- [x] ログ出力先は環境変数`AI_KYOUZAI_LOGS_DIR`で上書き可能にした（既定は`logs/`）。自動テストが実際のプロジェクトの`logs/`を汚さないよう、`tests/conftest.py`のautouse fixtureがテストごとに一時ディレクトリへ差し替える
- [x] ログディレクトリ作成・書き込みに失敗しても本処理は止めない（標準エラー出力に警告を表示するのみ）

### logs/のGit・ZIP管理

- [x] `logs/.gitkeep`を追加し、`.gitignore`に`logs/*`＋`!logs/.gitkeep`を追加（`logs/`ディレクトリ自体はGit管理対象、ログファイル本体は対象外）
- [x] `scripts/make_release_zip.sh`を確認: 元々`logs/`を除外する設定が無かったため、追加の変更なしでログファイルもZIPに含まれることを確認済み（コメントを追記し意図を明記）
- [x] `input/`・`output/`は引き続きGit・ZIP対象外のまま変更なし

### 共通設計ルールへの反映

- [x] `CLAUDE_RULES.md`に「4. ログ出力の共通設計ルール」「5. 成功判定の方針（実質失敗を正常終了扱いにしない）」を新設。「6. 今後のPhase指示文での参照方法」の参照文言にログ仕様・成功判定の方針を追加
- [x] `docs/04_output_spec.md`に「実行ログ（logs/）の標準仕様」「成功判定の方針」の2節を新設（`build-all`/`regenerate`各節にも失敗条件を追記）
- [x] `docs/02_architecture.md`に`execution_logger.py`を追加
- [x] `docs/08_user_acceptance_test.md`に「9. 実行ログ（logs/）と成功判定の考え方」を新設
- [x] ドキュメント更新（README.md/`docs/01_requirements.md`/`docs/README.md`/`docs/09_editable_regenerate_guide.md`）: logs/仕様・成功判定方針への言及を追加

### テスト追加・更新

- [x] `tests/test_execution_logger.py`（新規5件）: ログファイル生成・必須セクションの内容・ファイル名のサニタイズ・ログディレクトリ作成失敗時の非致命的な警告・`TeeStderr`の動作
- [x] `tests/test_output_formats.py`（+11件）: `build-all`/`generate`(lesson-pages)/`regenerate`/`check-ocr`のログファイル生成（成功時・失敗時）、pages 0件時のエラー終了（`regenerate`）、input空・対応ファイル無し時のエラー終了（`build-all`）、指定output-format成果物未生成時のエラー終了（`regenerate`）
- [x] `tests/conftest.py`に`isolate_execution_logs` fixtureを追加（テストが実プロジェクトの`logs/`を汚さないようにする）

### 今回実装しなかったもの・制限事項

- 個別CLI（`import-source`/`canva`/`docx`/`pdf`/`scenario`/`canva-sync`/`wp-publish`）のログは、INPUT/OUTPUTの基本記録のみで、`build-all`/`regenerate`ほど詳細なセクション（OCR要約等）は持たない（各コマンドの性質上、詳細記録の必要性が低いため最小限にとどめた）
- JSON構造化ログ（機械可読形式）は未実装。今回はテキストログ＋構造化された見出しのみ（要件通り）

## Phase 10.2 追加修正: 個別CLIの成果物未生成チェックとログの機密情報対策

Phase 10.2完了報告で「個別CLIの成果物未生成検証は追加していない（リスク低のため）」としていたが、今回の目的（実質失敗を正常終了扱いにしない）に照らすと不十分だったため追加対応した。あわせて、`logs/*.log`がZIP対象になる以上、ログに秘密情報が残らないようにする対策を追加した。

### 個別CLIの成果物未生成チェック

- [x] `src/cli.py`に`validate_generated_file(path, label)`（成果物が存在し、サイズが0でないことを検証）・`validate_generated_json_pages(path, pages_count, label)`（上記に加え、pagesが0件でないことを検証）を追加
- [x] `_verify_expected_outputs()`（`build-all`/`regenerate`が使う既存の成果物検証）にサイズ0チェックを追加（従来は存在確認のみだった）
- [x] 個別CLIの`main()`ディスパッチに検証を追加: `import-source`（`imported_pages.json`存在+pages非0件）、`lesson-pages`（`lesson_pages.json`存在+pages非0件）、`review-report`/`generate`/`canva`/`docx`/`pdf`/`canva-sync`/`wp-publish`（各出力ファイルの存在+サイズ非0）、`scenario`（`scenario.json`/`scenario.md`/`voicevox.txt`/`scene.json`の4ファイルすべて存在+サイズ非0）
- [x] 対象外にした個別CLIは無し。`main()`が扱う全個別CLIサブコマンドに検証を追加した

### ログの機密情報マスク

- [x] `src/execution_logger.py`に`mask_secrets(text)`を追加。`password`/`passwd`/`secret`/`token`/`api_key`/`apikey`/`access_key`/`access_token`/`authorization`/`bearer`/`client_secret`/`refresh_token`/`private_key`（大文字小文字を区別しない）を含むキーの値を`[REDACTED]`に置換する
- [x] CLIオプション形式（`--api-key sk-xxxx`/`--api-key=sk-xxxx`）、key=value/key: value形式（`password=abc123`）、HTTPヘッダ形式（`Authorization: Bearer xxxxx`）のいずれにも対応
- [x] `ExecutionLogger.finalize()`で、ログ本文を組み立てた最終テキストに対して`mask_secrets()`を適用してから書き出すようにした（args・各セクション・stderr・warnings・errorsのすべてを一括でカバーする、最も取りこぼしの少ない実装方針）
- [x] `Authorization: Bearer xxxxx`のような「ヘッダ名+スキーム名+トークン」の3要素構成で、ヘッダ名用のkey=valueパターンとBearer用パターンが二重にマッチして不自然な二重マスクになる問題を、negative lookaheadで回避

### テスト追加・更新

- [x] `tests/test_output_formats.py`（+7件）: `lesson-pages`のpages0件時エラー終了、`import-source`のpages0件時エラー終了、`canva`/`docx`/`pdf`の成果物未生成時エラー終了、正常系が壊れていないことの確認
- [x] `tests/test_execution_logger.py`（+15件）: `mask_secrets()`の各パターン（CLIオプション/key=value/Bearer/大文字小文字/無関係な単語への誤爆防止）、`ExecutionLogger`がargs・stderr・エラーメッセージ内の秘密情報を実際にマスクして書き出すことの確認

### 今回実装しなかったもの・制限事項

- 個別CLIについて「明らかに入力が無い」「JSONが壊れている」場合は既存の`parser.py`の例外処理で非ゼロ終了になる（変更なし）
- ログマスクは「値が空白区切りの単一トークンで表現される」ケースを対象としており、PEM形式の秘密鍵など複数行にまたがる値は部分的なマスクにとどまる（今回の受け入れ条件が明示する形式はすべて単一トークンのため対象外とした）

## Phase 10.3: 検証エビデンスの永続保存（`logs/evidence/`）

`pytest`/`run_sample.sh`の実行結果がCLI実行ログ（`logs/`）とは別に永続化されず、Codexが結果を確認するために同じ検証を再実行する可能性があるという運用上の課題に対応した。ChatGPT（Codex）が設計し、Claude Codeが実装した。

### 検証エビデンス保存の実装

- [x] `src/verification_evidence.py`: `EvidenceRun`（1回の検証実行を表すコンテキスト）・`run_command()`（コマンド実行＋ログ保存）・`collect_git_info()`（ブランチ・HEAD・dirty状態）・`parse_junit_summary()`（JUnit XML集計）・`check_acceptance_files()`（受け入れ確認ファイルの存在・サイズ・SHA-256）を実装
- [x] `src/verification_runner.py`: `scripts/run_verification.sh`から呼ばれるCLI本体。`pytest -q --junitxml=...` → `bash scripts/run_sample.sh`の順に実行し、片方が失敗してももう片方は続けて実行する（最終的な終了コードは失敗を反映）
- [x] `scripts/run_verification.sh`: 正式な実行入口（`set -e`を使わず、`python3 -m src.verification_runner`の終了コードをそのまま返す）
- [x] `run_id`（時刻＋衝突防止用ランダムサフィックス）ごとに新しいディレクトリを作成し、過去の実行結果を削除・上書きしない
- [x] `manifest.json`/`summary.md`は失敗・例外・タイムアウト・中断（`KeyboardInterrupt`）時にも可能な限り確定させる。書き込みは一時ファイル経由の置換（`os.replace`）でアトミックに行い、途中状態のJSONを完成扱いにしない
- [x] `logs/evidence/latest.json`は、`manifest.json`/`summary.md`の書き出し完了後にのみ更新し、常に完成済みの実行を指す
- [x] 秘密情報マスクは既存の`src/execution_logger.py`の`mask_secrets()`をそのまま再利用（重複実装しない）。コマンド引数・標準出力・標準エラー・Gitステータス等、記録するすべての文字列値に適用
- [x] `.gitignore`に`!logs/evidence/`＋`logs/evidence/*`＋`!logs/evidence/.gitkeep`を追加（`logs/evidence/`ディレクトリ自体はGit管理対象、実行結果本体は対象外）
- [x] 外部API・有料処理を将来記録するための`manifest.json`の`external`フィールド（構造のみ。今回は空配列固定・実際の外部API呼び出しは追加していない）

### 今回実装しなかったもの・制限事項

- 任意のコマンドを証跡付きで実行する補助入口（「安全な引数処理を行い`eval`を使わない」という指示付きの任意機能）は実装していない。標準の2コマンド（`pytest`/`run_sample.sh`）のみを対象にした（スコープを絞ることで安全性の検証範囲を明確にするため）
- `manifest.json`の`external`フィールドは構造のみ整備し、実際に外部API・有料処理を検証する機能は今回追加していない
- 配布ZIP（`scripts/make_release_zip.sh`）へのエビデンス同梱は行わない（`logs/*.log`とは異なりGit管理対象外のまま。理由は`docs/04_output_spec.md`「検証エビデンス」のGit管理・ZIP方針表を参照）

### テスト追加・更新

- [x] `tests/test_verification_evidence.py`（新規20件）: run_idの一意性、過去結果を上書きしないこと、成功/失敗時のmanifest内容、終了コードの記録、stdout/stderrの保存、JUnit XML解析、latest.jsonの完成済み実行への参照、Git HEAD/dirty状態の記録、秘密情報マスク、`.env`内容の非記録、アトミック書き込み、既存`mask_secrets()`の再利用確認
- [x] `tests/test_verification_runner.py`（新規2件）: `pytest`→`run_sample`の実行順序、`pytest`失敗時も`run_sample`が続けて実行され全体終了コードが失敗を反映すること（ダミーの小規模テストファイルを使い、プロジェクト全体のpytestを再帰的に起動しない）

## Phase 10.4: 教材画像向けOCR品質の根本改善（`src/ocr_engine.py`）

`_try_ocr()`が画像全体をほぼ無加工のまま`pytesseract.image_to_string()`へ渡していたため、大見出し・本文・グラフ・注記が混在する教材画像で、本文欠落・タイトル誤認識（「だ」「YOU」等）・グラフ由来の英字ノイズ（`ane`/`SCRA`/`PPP`等）・辞書未登録の誤認識（`一買`/`アウトブット`/`70て80%`等）が発生していた問題に対応した。個別データの手修正ではなく、同種の教材画像全般に有効な処理を目指した。

### OCRエンジンの実装

- [x] `src/ocr_engine.py`（新規）: OCR品質改善ロジックを`import_source.py`から分離。`generate_preprocess_variants()`（原画像/拡大+グレースケール+コントラスト補正+シャープ化/二値化の3候補）・`split_region_variants()`（タイトル帯/本文帯・左右カラムの比率ベース領域分割）・`run_ocr_pass()`（`pytesseract.image_to_data()`による信頼度・座標付きOCR）・`words_to_text()`（日本語文字間へ余計な空白を入れない読み順再構成）・`score_candidate()`（信頼度/日本語文字率/低信頼度比率/英字ノイズ数/辞書一致数を組み合わせた品質スコア）・`postprocess_candidate()`（低信頼度ノイズ除去・不自然な先頭/末尾行除去・辞書補正・波ダッシュ誤認識補正・空白整理）・`run_multi_ocr()`（最上位オーケストレーション）を実装
- [x] `src/import_source.py`: `_try_ocr(image_path, ocr_status) -> str`の外部シグネチャ・「OCR不能なら空文字を返す」動作を維持したまま、内部を`ocr_engine.run_multi_ocr()`へ委譲。診断情報はモジュールレベルの`_last_ocr_diagnostics`副チャンネル経由で取得可能にし、`_page_from_image()`/`import_images()`/`import_source()`に`diagnostics_sink`（既定None）を追加（`imported_pages.json`のスキーマには影響しない）
- [x] `src/cli.py`: `run_import_source(..., logger=...)`が`diagnostics_sink`を収集し、実行ログへ`OCR_QUALITY`セクション（診断ページ数・要確認ページ・再試行ページ・平均スコア・ページごとの詳細）として記録
- [x] 複数前処理（原画像/enhanced）× 複数PSM（6/11）= 4候補を基本実行し、品質スコアが閾値未満の場合のみ、二値化・タイトル帯/本文帯分割・左右カラム分割の追加候補（5回）で再試行（合計最大9回。特定画像の座標はハードコードしない）
- [x] 辞書による自動補正は`config/ocr_patterns.json`の`high_confidence_replacements`に限定し、それ以外のOCR崩れは引き続き`ocr-check`以降の人間承認フローで扱う（役割分担を維持）

### 実データ5枚（`input/source/`）での検証結果

`ocr-check`による診断候補数: 16件（高重要度4件）→ 5件（高重要度0件）。英字ノイズトークン数（`garbled_latin_token_count`による機械集計）: 9→2。タイトル誤認識（「だ」「YOU」等の完全に無関係な文字列）: 2/5ページ→0/5ページ。処理時間: 1ページあたり約0.36秒→約2.0秒（前処理・複数PSM・品質評価のオーバーヘッドによる増加だが、5ページで約10秒と実用範囲）。

### 今回実装しなかったもの・制限事項

- Tesseract自体が誤認識する一部の文字・記号は、前処理・複数PSM・再試行を行っても完全には解消しない（例: 実データPage1の「考えてみましょう！」相当の行は、改善後もOCRが正しく認識できないケースが残った）。これはOCRエンジン自体の限界であり、`ocr-check`以降の人間確認フローに委ねる
- 任意のコマンドを証跡付きで実行する等の外部API・有料サービス連携は使用していない（Tesseractのみ）
- タイトル領域・本文領域の分割は比率ベースの一般的なルールに留め、レイアウト解析（段組み検出等）の高度化は対象外

### テスト追加・更新

- [x] `tests/test_ocr_engine.py`（新規34件）: 前処理が元画像を変更しないこと、複数PSM候補比較、日本語本文優先の品質スコア、大量の低信頼度英字ノイズを含む結果を選ばないこと、正当な英字・URL・許可語を一律削除しないこと、一文字/不自然な短い英字タイトルの低品質判定、低品質時のみの再試行（9回）・正常品質時は再試行しないこと（4回）、領域分割後の読み順再構成、品質スコア計算の決定性、辞書補正・波ダッシュ誤認識補正、等（pytesseract呼び出し自体はモックし、プロジェクト全体のOCRを再帰的に実行しない）
- [x] `tests/test_import_source.py`（+6件）: `_try_ocr`のOCRエンジン委譲・例外時の空文字フォールバック・診断情報副チャンネル・`diagnostics_sink`の収集有無、既存`real_ocr`テストを`image_to_data`ベースのフェイクモジュールへ更新
- [x] `tests/test_output_formats.py`（+1件）: `build-all`実行ログに`OCR_QUALITY`セクション（選択前処理・PSM・品質スコア・要確認ページ）が記録されることを確認
- [x] `tests/test_docs_consistency.py`: 開発ルール3階層整理（前タスク）で生じていた2件の既存テスト不整合（`CLAUDE_RULES.md`から移設した内容の参照先更新）もあわせて修正

## Phase 10.5: Claude Code完了報告のHTML Artifact化（`src/completion_report.py`）

Codexが実装結果を確認する主確認手段を「保存済みエビデンスの直接読み取り」から「Claude Codeの自己完結した完了レポート」へ変更する開発ルール改定にあわせ、その完了レポートをコピー用ボタン付きの自己完結型HTML Artifactとして生成する仕組みを追加した。

### 実装

- [x] `src/completion_report.py`（新規）: `CompletionReport`データクラス、`render_completion_report_html()`（Markdown本文を安全にHTMLへ埋め込み、表示用は簡易Markdown→HTML変換・コピー用はJSON文字列化＋`</script`エスケープでスクリプト注入を防止）、`write_completion_report()`（タイムスタンプ付きファイル＋`latest_claude_completion_report.html`の両方を`output/reports/`へ書き出し、過去分は上書きしない）、CLIエントリ（`python3 -m src.completion_report`）を実装
- [x] 外部CDN・外部JS・外部CSS・外部フォントは使用しない（1ファイル完結）
- [x] JavaScript無効環境でも本文を読める構造（表示用ペインは常にHTML内に静的に存在）。コピー失敗時はテキストエリアへフォールバック
- [x] 開発ルール3階層（`~/ai-development-rules/DEVELOPMENT_RULES.md`・`claude/CLAUDE.md`・`codex/AGENTS.md`・プロジェクトの`AGENTS.md`/`PROJECT_RULES.md`/`CLAUDE_RULES.md`）へ、この出力形式とCodex側の確認方針（Artifactのコピー内容を最初に確認する）を反映

### テスト追加・更新

- [x] `tests/test_completion_report.py`（新規14件）: HTML生成、タイムスタンプ付きファイルの非上書き、latestファイルの更新、Markdown原文の完全な保持（コピー用）、HTML特殊文字によるレイアウト崩れが無いこと、`</script>`を含む本文でのスクリプト注入対策、外部依存が無いこと、不正な判定値のエラー、表示用ペインがJS無し構造で存在すること、テーブル/チェックボックスの変換、保存先ディレクトリの自動作成

### 今回実装しなかったもの・制限事項

- 簡易Markdown→HTML変換は、このモジュールが生成する固定フォーマットの完了レポート専用であり、汎用的なCommonMarkパーサーではない
- 秘密情報のマスクは`completion_report.py`自体では行わない（呼び出し側の責務として設計上明確に分離）

## Phase 10.6: OCRタイトル末尾欠落と領域分割結合処理の修正（`src/ocr_engine.py`）

Phase 10.4のOCR品質改善後も、実データ2ページ（Page3/4）でタイトル行の末尾（閉じ括弧）が欠落する不具合と、`combine_region_candidates()`（領域分割結果の安全な結合用関数）が実際の`run_multi_ocr()`の再試行処理では使われず、単純な`list`結合になっていた不整合が残っていた。この2点に限定して修正した。

### 原因

- タイトル末尾欠落: ページ全体のスコアで最良の候補が、たまたまタイトル行だけ途中欠落していた一方、同じ画像から得た他の候補（同一ベースライン4候補内）にはより完全なタイトルが存在していた。候補選択がページ全体のスコアだけで行われ、タイトル行単体の完全性を考慮していなかったことが原因
- 領域結合の不整合: `combine_region_candidates()`は結合順序を保つよう設計されていたが、`run_multi_ocr()`の再試行処理は`list(a.words) + list(b.words)`という単純結合を使っており、各領域が個別にOCRされて`block_num`/`line_num`が1から再スタートするため、異なる領域の行が同一行として混ざる危険があった

### 実装

- [x] `has_unclosed_bracket()`/`is_incomplete_title_line()`（新規）: 括弧の対応関係だけを見た構造的なタイトル末尾欠落検出（文字の正誤は判定しない）
- [x] `title_line_min_confidence()`/`title_is_uncertain()`（新規）: タイトル行内の最低信頼度を見て、構造的には完全でも極端に疑わしい文字が残っている状態を検出する追加シグナル
- [x] `title_similarity()`/`find_more_complete_title()`/`complete_title_in_text()`（新規）: 同一画像内の他候補（postprocess後の文字列）から、安全条件（現在のタイトルが構造的欠落または低信頼度の場合のみ・長さが短くならない・類似度/共通接頭辞・英字ノイズを増やさない等）を満たす場合に限りタイトルを補完する。特定の教材タイトル文字列はハードコードしていない
- [x] `is_noise_symbol_token()`（新規）+ `filter_noise_words()`拡張: 低信頼度の記号だけの短いトークン（タイトル行末尾に残る「:」等）を汎用的に除去
- [x] `_offset_block_numbers()`/`combine_region_words()`（新規）+ `combine_region_candidates()`（`str`ではなく`OcrCandidate`を返すよう変更）: 領域ごとに`block_num`へ大きなオフセットを与えてから結合することで、異なる領域の行が衝突しないようにし、結合結果を通常候補と同じように品質スコア・後処理へ渡せるようにした
- [x] `run_multi_ocr()`: 実際の再試行処理を`combine_region_candidates()`経由に統一。タイトル補完は再試行前後の両方で試みる。再試行トリガーに「タイトル構造欠落」「タイトル低信頼度（かつ補完で解消できなかった）」を追加（スコアが十分でも、この2条件のいずれかに該当する場合だけ再試行する。全ページ一律の再試行にはしていない）。品質判定（`quality`）は再試行後の最終状態でのみ行う

### 実データ確認（`input/source/`5ページ、`import-source`経由）

| ページ | 修正前タイトル（末尾欠落） | 修正後タイトル | quality | retried |
|---|---|---|---|---|
| Page1 | 【「共通認識」を作ろう】 | 【「共通認識」を作ろう】（変化なし） | ok | False |
| Page2 | 【「共通認識」を作ろう】 | 【「共通認識」を作ろう】（変化なし、本文側の残存ノイズは`ocr-check`の人間確認フローで継続対応） | ok | False |
| Page3 | 【一買したキャラ | **【一貫したキャラ設定】**（完全一致） | ok | False |
| Page4 | 【一買したキャラ設定 | **【一貫したキャラ設定】**（完全一致） | ok | False |
| Page5 | アウトプットタイム | アウトプットタイム（変化なし） | ok | False |

`ocr-check`集計: 5ページ中、要確認ページ1件（Page2、中重要度2件・低重要度3件、いずれも本文の日付・数値表記まわりでタイトルとは無関係）、高重要度0件。5ページとも`retried: False`（今回の修正条件では実データに対して追加再試行は発生しなかった＝スコア・タイトルとも初回候補で十分だった）。

### テスト追加・更新

- [x] `tests/test_ocr_engine.py`（+29件、既存34件中1件を新しい戻り値型に合わせて更新）: 括弧欠落検出、タイトル類似度、安全な補完条件（短くならない・現在が正常な場合は置換しない・ノイズを増やさない候補の除外等）、低信頼度シグナル、記号ノイズトークン除去、領域結合時の`block_num`オフセットによる衝突回避・順序保持、`combine_region_candidates()`が`OcrCandidate`を返し品質スコアに使えること、`run_multi_ocr()`がタイトル構造欠落／低信頼度だけを理由に的を絞って再試行すること、正常ページでは再試行しないこと

### 今回修正しなかったもの・制限事項

- タイトル行以外（本文）の文字レベルの誤認識検出・補正は対象外（`ocr-check`以降の人間確認フローに委ねる、従来方針を維持）

## Phase 10.7: Apple Vision OCRの導入とTesseract比較判定（macOS専用・任意）

Tesseract自身の信頼度スコア・品質判定だけでは検出できない誤認識（Phase 10.6のPage7調査で確認: `quality: ok`と判定されたページに複数の重大な漢字誤読が残存）に対応するため、macOS標準のApple Vision OCR（`VNRecognizeTextRequest`）を第二の独立したOCRエンジンとして導入し、Tesseractとの不一致を検出する仕組みを追加した。既存のTesseract結果は維持し、Apple Vision結果は自動採用しない（比較・人間確認用の追加情報として扱う）。

### 実装

- [x] `tools/apple_vision_ocr/`（新規・Swift Package Manager）: `AppleVisionOCRCore`（`VNRecognizeTextRequest`呼び出し・引数解析・JSON組み立てロジック）+ 薄い実行ファイル`apple-vision-ocr`。標準出力へ`engine`/`available`/`language`/`duration_seconds`/`observations`[`text`/`confidence`/`bounding_box`/`candidates`]/`text`/`warnings`のJSONを出力する。存在しない画像（終了コード2）・未対応言語（終了コード3）・Vision実行時エラー（終了コード4）・引数エラー（終了コード64）を区別する
- [x] `scripts/build_apple_vision_ocr.sh`（新規）: `swift build -c release`でビルドする。macOS以外・Swiftツールチェーン未導入の環境では、エラーにせず案内を表示してスキップする（既存の`build-all`導線を壊さないため）
- [x] `.gitignore`に`tools/apple_vision_ocr/.build/`を追加（Swiftソース・`Package.swift`・ビルドスクリプトはGit管理対象、ビルド済みバイナリは対象外）
- [x] `src/apple_vision_ocr.py`（新規）: ヘルパーを`subprocess`で安全に呼び出すPythonアダプター。`shell=True`不使用、画像パスは常に引数配列として渡す。macOS以外・ヘルパー未ビルド・タイムアウト・不正なJSON出力・ヘルパー異常終了等、あらゆる失敗時に例外を投げず`available=False`を返す
- [x] `src/ocr_compare.py`（新規）: 正規化（改行差・連続空白・連続空行のみ。漢字・句読点・長音・引用符・数字は保持）・全文/タイトル類似度・行数差・有効文字数差・一方にしか存在しない行・読み順差・ノイズトークン差・重要語句差の比較指標と、テスト可能な閾値定数による`needs_review`判定
- [x] `src/ocr_comparison.py`（新規）: ページごとの比較オーケストレーション（Tesseractは`imported_pages`の既存結果を再利用し再実行しない）+ `output/ocr_comparison/`（`summary.json`/`summary.md`/`pages/page_NNN.json`/`review.html`）への保存。Apple Vision利用不可時はエンジン不一致を理由に全ページを`needs_review`にしない
- [x] `src/cli.py`: `build-all`に`--ocr-engine`（`tesseract`[既定]/`tesseract+vision`）を追加。`tesseract`指定時（＝省略時）は比較処理を一切呼び出さず、既存動作から変化しない。`tesseract+vision`指定時のみ、画像inputに限り既存パイプライン完了後に比較ステップを追加実行し、`OCR_COMPARISON`セクションを実行ログへ記録する。`run_import_source()`に`diagnostics_sink`引数を追加し、Tesseractのページ別スコア・品質判定・処理時間を比較へ引き渡せるようにした（省略時は従来どおりの挙動）
- [x] Apple Vision結果は`output/editable/lesson_pages.json`へ一切書き込まない（自動採用しない。正式な編集対象は引き続きTesseractベースの`editable/lesson_pages.json`のみ）

### テスト構成についての注記（この開発環境固有）

この開発環境にはXcode本体（XCTest/Swift Testing）が無くCommand Line Toolsのみのため、`swift test`（XCTest・Swift Testingいずれも）が実行時にフレームワーク解決に失敗し動作しなかった。そのため、Foundationのみに依存する自作テストハーネス実行ファイル（`AppleVisionOCRSelfTests`。`swift run AppleVisionOCRSelfTests`で実行、失敗時は非ゼロ終了）をSwift側テストとして採用した。Xcodeが利用できる環境では、通常の`.testTarget`（XCTest/Swift Testing）へ戻すことも可能（`Package.swift`内にコメントで注記済み）。

### テスト追加・更新

- [x] `tools/apple_vision_ocr/Sources/AppleVisionOCRSelfTests/`（新規12件）: 引数解析（欠落・不正値・全オプション）、JSON出力の必須フィールド・往復デコード、存在しない画像・未対応言語の検出（実OCR結果の文字列完全一致は固定テストにしない）
- [x] `tests/test_apple_vision_ocr.py`（新規13件）: macOS判定・ヘルパー未ビルド時のフォールバック、タイムアウト・不正JSON・異常終了時のフォールバック、正常JSON解析、`subprocess.run`が引数配列・`shell=False`で呼ばれること（コマンドインジェクション対策の直接検証）
- [x] `tests/test_ocr_compare.py`（新規22件）: 正規化（漢字・句読点・長音・引用符・数字を変更しないこと含む）、各比較指標、`needs_review`判定（タイトル不一致・行欠落・読み順差・軽微な空白差では反応しないこと）
- [x] `tests/test_ocr_comparison.py`（新規9件）: Apple Vision利用不可時に全ページを誤ってneeds_reviewにしないこと、比較結果がlesson_pages構造を変更しないこと、`output/ocr_comparison/`の保存構造、`review.html`が外部CDN不使用・HTML特殊文字を正しくエスケープすること
- [x] `tests/test_cli_ocr_engine_flag.py`（新規4件）: `--ocr-engine`省略時（既定`tesseract`）はApple Visionを一切呼び出さず`output/ocr_comparison/`も生成されないこと、`tesseract+vision`指定時の比較出力生成、Apple Vision結果が`editable/lesson_pages.json`へ反映されないこと、Apple Vision利用不可時のフォールバック

### 実データ評価（`input/source/`11ページ、`--ocr-engine tesseract+vision`）

- Tesseractのみ要確認ページ: なし（`tesseract_only_review_pages: []`）
- Apple Visionとの不一致のみで要確認ページ: 1, 2, 3, 5, 6, 7, 8, 9, 10, 11
- 両エンジン不一致による要確認ページ（Tesseract自身もneeds_review）: 4
- 要確認ページ数: 11/11（詳細な不一致理由はページごとに異なり、閾値は保守的寄りに設定している。「9. 完了条件との対応」参照）
- **Page7の検出**: 検出できた。Tesseractは「苦労」→「店労」、「些細」→「性細」、「もし」→「も」、末尾「※無断転載禁止（おとスタ）」が意味不明な文字列へ置換される等、複数の重大な誤読が残っていたが、Apple Visionはこれらをすべて正しく認識した。比較器は「Apple Visionのみに存在する行がある」「重要語句に差がある（例: 店、苦、信）」等の理由でPage7を`needs_review`として正しく検出した
- 処理時間（11ページ合計）: Tesseract 27.35秒、Apple Vision 3.48秒（Apple Visionの方が約8倍高速）
- Apple Visionの方が正しかった箇所（代表例）: Page1「まず」（Tesseractは「ますず」）、Page2「叱咤激励」（Tesseractは「叱距激励」）、Page3の2段組み読み順（Tesseractは左右列が1行に混在）・「負けず嫌い」（Tesseractは「負けすず嫌い」）、Page6の引用符ペア（Tesseractは1組欠落）、Page7の「苦労」「些細」「もし」「無断転載禁止」行、Page8の重複タイトル行・スプリアス「O」・読み順、Page9の「自分」（Tesseractは「目分」）・「語れる」（Tesseractは「告れる」）、Page10の末尾「無断転載禁止」行（Tesseractは完全欠落）。「◎」記号はTesseractが一貫して「〇」に誤読するのに対しApple Visionは正しく認識した（Page2/3/6/7/9で確認）
- Tesseractの方が正しかった箇所: Page4「信頼されるタイプ」の「信」の字がApple Vision側では脱落していた（Tesseractは正しく保持）。Page11の丸数字「⑩」をApple Visionは算用数字「10」へ変換してしまうのに対し、Tesseractは（末尾に余分な「.」は付くものの）丸数字の字形に近い形で保持していた
- 両方とも誤った箇所: Page1「全11問」のうち、Tesseract/Apple Visionの表記ゆれ（半角スペース有無等）はいずれも軽微だが完全一致ではない。Page4のように、細部では両エンジンとも一長一短があり、どちらか一方が常に優れているわけではないことを確認した

### 今回実装しなかったもの・制限事項

- Apple Vision結果の`editable/lesson_pages.json`への自動採用（将来のバージョンで別タスクとして検討）
- Apple Vision単体でのTesseract置き換え
- 外部API・有料サービスとしてのOCR利用（Apple Visionはローカル処理のみで、画像・OCR結果を外部へ送信しない）
- `needs_review`判定の閾値は保守的寄りに設定しており、実データ11ページでは、Apple Vision不一致だけを理由に要確認となったページが10/11、Tesseract自身の判定とApple Vision不一致の両方を理由に要確認となったページが1/11（Page4）で、最終的な要確認ページ数は合計11/11だった（内訳は上記「実データ評価」参照）。ノイズトークン差（Tesseractの単語単位JSON構造に由来する孤立した記号トークン）が主要因の1つであり、閾値の調整余地はあるが、今回は「少しでも差があれば人間確認へ回す」という指示に従い保守的な設定を維持した
- 辞書に無い未知の誤認識文字は、構造的に完全で信頼度も一定以上ある場合は補完対象にならない（元画像に無い文字を推測で追加しない方針を優先）

## Phase 10.8: OCR比較review.htmlへの文字単位差分ハイライト追加

Phase 10.7の`review.html`はTesseract全文とApple Vision全文を並べて表示するだけで、どの文字が違うのか目視で探す必要があり確認作業がしにくかった。`difflib.SequenceMatcher`による文字単位の差分ハイライトを追加し、置換・削除・追加を左右で色分け・下線スタイルで識別できるようにした。**既存の比較判定（`src/ocr_compare.py`）・自動採用禁止方針・JSON形式（`summary.json`/ページ別JSON）は変更していない**（表示専用の改善）。

### 実装

- [x] `src/ocr_comparison.py`: `_normalize_diff_line_endings(text)`（改行コードのみ`\n`へ統一。漢字・かな・句読点・長音・引用符・数字・空白は変更しない）、`_render_text_diff(left, right) -> tuple[str, str]`（`difflib.SequenceMatcher.get_opcodes()`を元に、`equal`はそのまま、`delete`は左側だけ`diff-tess-del`、`insert`は右側だけ`diff-vision-ins`、`replace`は左`diff-tess-rep`/右`diff-vision-rep`の`<mark>`要素へ変換）、`_wrap_diff_span()`（安全なタグ組み立て）を追加
- [x] HTML安全性: 元の文字列を先に`SequenceMatcher`で分割してから、分割済みの断片だけを個別に`html.escape(quote=True)`する順序を徹底（エスケープ後の全文に文字位置を適用しない）。差分用タグは`<mark>`のみを実装側で生成する
- [x] `_render_page_section()`を改修し、各ページを「元画像 / Tesseract / Apple Vision」の3列（`.compare-grid`。狭い画面では縦並びへ切り替え）へ再構成。旧レイアウトはTesseract/Apple Visionのテキストを同じ列内に上下連続表示していたが、横並びで対応箇所を比較しやすくした。統計情報・不一致理由・人間確認欄は`.meta-grid`として3列の下に配置
- [x] 各ページ冒頭に凡例（`.diff-legend`）を追加。色だけに依存せず、`title`属性・下線スタイル（実線=削除/追加相当、破線=置換）でも意味を判別できるようにした
- [x] 比較不能時（Apple Vision利用不可・片側/両側が空・非常に長い文字列・絵文字等）でもHTML生成が失敗しないことを確認。片側が空の場合は`SequenceMatcher`の性質上、もう一方の全文が自動的にその側だけの差分（`delete`または`insert`）として強調される。両方空の場合は「(OCRテキストなし)」の明確な表示にした
- [x] 外部CDN・外部JS・外部CSS・外部フォントは追加していない（既存方針を維持）

### テスト追加・更新

- [x] `tests/test_ocr_comparison.py`（+18件）: 完全一致（差分タグなし）、文字置換（左右で異なるCSSクラス）、Tesseract側だけの文字（delete）、Apple Vision側だけの文字（insert）、行の欠落・追加、空文字（左のみ・右のみ・両方）、HTML特殊文字（`<script>`/`</span>`/`&`/引用符）のエスケープとタグ構造の非破壊、Unicode（丸数字・絵文字）の非破壊、長い文字列でのエラー無し、改行コード正規化が漢字・数字等を変更しないこと、`review.html`統合（凡例・差分グリッドの存在、自己完結性の維持、JSON出力構造への非影響、`editable/lesson_pages.json`への非影響）

### 実データ確認（保存済み比較JSONからの再生成。OCR再実行なし）

`output/ocr_engine_eval/ocr_comparison/summary.json`（Phase 10.7で取得済みの実データ11ページ分。Git管理対象外）を読み込み、`ComparisonSummary`/`PageComparison`を再構築して`review.html`のみを再生成した（既存導線が無かったため、今回のためだけの新規CLIは追加せず、`render_comparison_review_html()`を直接呼び出すその場限りのスクリプトで確認した）。

- Page7: 「店」（Tesseract）/「苦」（Apple Vision）、「性」（Tesseractの「性細」側）がそれぞれ異なる差分クラスでハイライトされることを確認
- Page10: Apple Vision側だけに存在する「※無断転載禁止（おとスタ）」行が`diff-vision-ins`として強調されることを確認
- Page4: Apple Vision側で脱落した「信」（「…努力家で信頼されるタイプ」）がTesseract側で`diff-tess-del`として強調されることを確認
- Page11: Tesseract側「⑩. 」とApple Vision側「10」が、それぞれ`diff-tess-rep`/`diff-vision-rep`で強調されることを確認
- 生成された`review.html`（44,484バイト、11ページ分）で`<mark>`の開始・終了タグ数が一致（270/270）し、`<section>`も11/11で一致、外部`http(s)`参照が0件であることを確認（レイアウト崩れ・タグ不整合が無いことの機械的確認）

### 今回実装しなかったもの・制限事項

- 差分ハイライトは表示専用であり、`needs_review`判定・比較指標の計算方法・閾値には一切影響しない（Phase 10.7の設計をそのまま維持）
- Apple Vision結果の自動採用（`editable/lesson_pages.json`への反映）は今回も対象外
- 単語・文単位の差分（今回は文字単位のみ。日本語は単語分割が難しいため、文字単位が最も安全で誤解の少ない表示と判断した）

## Phase 10.9: OCR比較review.htmlへの確定テキスト編集・採用判定・JSON書き出し機能追加

Phase 10.8の差分ハイライトで「どこが違うか」は見つけやすくなったが、レビュー結果を記録する手段が無かった。Tesseract/Apple Visionの表示欄は読み取り専用のまま維持しつつ、編集可能な「確定テキスト」欄・採用判定（排他制御）・`localStorage`への自動保存・JSON書き出し機能を`review.html`に追加した。**この操作はすべて`review.html`内のブラウザローカルの状態であり、`output/editable/lesson_pages.json`・比較元JSON・Tesseract/Apple Vision結果本体のいずれも自動変更しない**（正式データへの反映は別タスク）。

### 実装

- [x] `src/ocr_comparison.py`: `_safe_json_for_script()`（`src/completion_report.py`と同じ考え方で`</script`/`<!--`を無害化するJSON埋め込みヘルパー）、`_REVIEW_JS_PURE`（DOM・`localStorage`に依存しない純粋関数群: `resolvePageAdoption()`/`simpleHash()`/`buildMaterialId()`/`buildStorageKey()`）、`_REVIEW_JS_APP`（DOM配線: コピーボタン・確定欄・採用ラジオ・チェックボックス・保存/復元・JSON書き出し・全リセット）を追加
- [x] `_render_page_section()`を改修し、Tesseract/Apple Visionパネルへ「確定欄へコピー」ボタンを追加、新たに「確定テキスト」欄（`<textarea>`）・「採用判定」（Tesseractを採用／Apple Visionを採用の排他ラジオ、ページごとに異なる`name`属性で他ページへ影響しない）・「元画像を要再確認」／「確認完了」（採用元とは独立したチェックボックス）・保存状態表示を追加
- [x] `render_comparison_review_html()`に、各ページのTesseract/Apple Vision全文（プレーンテキスト）を`<script type="application/json" id="ocr-review-page-data">`として安全に埋め込み（差分ハイライトの`<mark>`タグは含まない）、「レビュー結果をJSONで書き出す」「全レビュー状態をリセット」ボタンを追加
- [x] 採用優先順位を固定: (1) 確定テキストに内容があれば`edited`を最優先 (2) 確定欄が空でTesseract採用なら`tesseract` (3) 確定欄が空でApple Vision採用なら`apple_vision` (4) どちらも未選択なら`unresolved`。Tesseract/Apple Vision同時選択は通常のブラウザ操作では発生しない（同一`name`のラジオで排他）が、読み込みデータ等で発生した場合は確定欄が空なら書き出し時にエラー、確定欄に内容があれば`edited`優先＋警告とする。「確認完了」が選択されているのに`unresolved`の場合も警告する
- [x] 保存キーは`ocr_review_state:<materialId>:page-<ページ番号>`。`materialId`は各ページの`source_image`一覧から算出する簡易ハッシュ（`simpleHash`/`buildMaterialId`）で、教材（`review.html`）ごとに異なる値になり、別教材のレビュー状態と混ざらない
- [x] HTML・JavaScript安全性: `eval`・`new Function`は使用しない。OCR文字列・編集文字列は`textContent`/`.value`のみで扱い、HTMLとして挿入しない。外部CDN・外部JS・外部CSSは追加していない

### テスト構成についての注記（この開発環境固有）

採用判定ロジック（`resolvePageAdoption`等）は、DOM・`localStorage`に依存しない純粋関数として`_REVIEW_JS_PURE`に分離した。この開発環境にはNode.js・Xcode本体が無いため、macOS標準搭載のJavaScriptCore（`osascript -l JavaScript`。標準入力からスクリプトを読み込み実行できる）で実際にこのJSコードを実行してテストした（`tests/test_ocr_review_js.py`。macOS以外・`osascript`が無い環境ではスキップする）。DOM操作を伴う部分（コピー時の上書き確認ダイアログ、`localStorage`への実際の保存・復元、リセット確認）は、ブラウザ自動操作ツール（Node/npm、Playwright等）がこの環境に存在しないため実行テストできず、HTML構造・埋め込みJSソースの静的検証（`tests/test_ocr_comparison.py`）にとどめた（10節「残課題」参照）。

### テスト追加・更新

- [x] `tests/test_ocr_review_js.py`（新規16件）: `osascript -l JavaScript`で実際にJSを実行し検証。`resolvePageAdoption()`の4段階の優先順位（edited最優先・tesseractフォールバック・apple_visionフォールバック・unresolved）、空白のみの確定テキストが空扱いになること、Tesseract/Apple Vision同時選択時の挙動（確定欄空でerror・確定欄ありでedited+warning）、確認完了なのに未確定の場合の警告、`simpleHash`の決定性・入力依存性、`buildMaterialId`のページ構成依存性、`buildStorageKey`のページ番号・教材ごとの一意性
- [x] `tests/test_ocr_comparison.py`（新規14件）: Tesseract/Apple Vision表示が読み取り専用のまま（`<textarea>`はページ数分＝確定欄のみ）、両エンジンのコピーボタンの存在とページデータJSONの厳密一致、採用ラジオのページごとの排他制御（`name`属性がページ番号ごとに異なる）、要再確認/確認完了チェックボックスの独立性、書き出し/リセットボタンの存在、`localStorage`使用・`window.confirm`使用のJSソース検証、`eval`/`new Function`不使用、書き出しJSONのフィールド名一致、ページデータに絶対パス・秘密情報が含まれないこと、`<script>`/`</textarea>`/`&`/引用符を含むOCR文字列でも`</script>`実閉じタグ数が変わらないこと、自己完結性の維持、差分ハイライトの共存確認、既存書き出しファイル一覧が変わらないこと

### 実データ確認（保存済み比較JSONからの再生成。OCR再実行なし）

`output/ocr_engine_eval/ocr_comparison/summary.json`（Phase 10.7で取得済み）から`review.html`を再生成し、ページデータJSONブロックの内容をPythonから直接検証した（実ブラウザでのクリック操作の自動化はこの環境で行えないため、構造・埋め込みデータの正しさの検証にとどめた。10節参照）。

- Page7: Apple Vision全文がページデータへ正確に格納されており、「確定欄へコピー」ボタンでこの全文（`苦労したこと`等、正しい認識結果）を確定欄へ入れられることを確認（手修正自体は標準`<textarea>`の機能であり、追加の検証は不要と判断）
- Page4: Tesseract全文に「信頼」が正しく含まれる（Apple Vision側は「信」が脱落）ことを確認し、Tesseract側をコピーすれば該当箇所を維持できることを確認
- Page11: Apple Vision全文に「10」、Tesseract全文に「⑩」が含まれることを確認（コピー後に「10」を「⑩」へ手修正できることを、標準`<textarea>`の編集機能として確認）
- Page10: Apple Vision全文にのみ「無断転載禁止」行が含まれることを確認
- 生成された`review.html`（72,733バイト、11ページ分）で`</script>`の実閉じタグ数が2件（ページデータ用・アプリロジック用）で一致し、`<textarea>`が11件（ページ数と一致）、採用ラジオの`name`属性がページごとに異なる（例: `adopt-source-7`/`adopt-source-11`）ことを確認

### 今回実装しなかったもの・制限事項

- 確定テキスト・採用判定の`editable/lesson_pages.json`への自動反映（今回も対象外。将来の別タスク）
- ブラウザでの実際のクリック操作・`localStorage`保存/復元・確認ダイアログの自動テスト（この環境にNode/npm・ブラウザ自動操作ツールが無いため未実施。静的検証と、macOS標準のJavaScriptCoreによる純粋関数の実行テストで代替した）
- JSON書き出し後の「差分検出済みJSONを`editable/lesson_pages.json`へ再反映する」importコマンド等は今回スコープ外

## Phase 10.10: Claude Code向けOCR画像照合レビュー指示書の自動生成

Phase 10.7〜10.9でTesseract/Apple Visionの比較・差分ハイライト・確定テキスト編集機能を整えたが、利用者が毎回「Claude Codeへどう指示するか」を考える必要があった。`build-all --ocr-engine tesseract+vision`実行時に、任意ページ数（数ページ〜100ページ以上）で同じ導線を使える、Claude Code向けの自己完結した作業指示書（`CLAUDE_OCR_REVIEW.md`）を自動生成し、利用者が渡す文章を固定の1文だけにした。**プログラムからのClaude API呼び出し・Claude Codeプロセスの自動起動は行わない**（指示書は人間が別セッションへ手動で渡すことを前提にした静的な文書生成のみ）。

### 実装

- [x] `src/ocr_claude_review.py`（新規）: `render_claude_ocr_review_instructions(summary, output_dir)`（指示書本体の生成。ページ総数・ページ番号一覧・各種相対パス・Apple Vision利用可否・`needs_review`ページ・生成日時を実データから埋め込むが、OCR全文・画像バイナリ・絶対パスは埋め込まない）、`render_claude_review_readme()`（`claude_review/README.md`の生成）、`write_claude_review_entry_points(output_dir, summary)`（Apple Vision利用可能時のみ両ファイルを書き出す。利用不可時は何も書き出さず`None`を返す）、`format_page_number_ranges()`（ページ番号一覧を`1-8, 10, 12-15`のように圧縮表記し、100ページ以上でも冗長にならないようにする）を実装
- [x] `src/ocr_comparison.py`: `write_comparison_outputs()`から`ocr_claude_review.write_claude_review_entry_points()`を呼び出すよう統合（責務を分離した別モジュールから生成する設計。既存の`summary.json`/`summary.md`/`pages/`/`review.html`の生成ロジックには一切手を加えていない）
- [x] `src/cli.py`: `_run_ocr_engine_comparison()`に`_print_claude_ocr_review_notice()`を追加。Apple Vision利用可能時は標準出力へ`CLAUDE_OCR_REVIEW`バナー（コピー可能な固定の1文を含む）を表示し、利用不可時は「生成されませんでした」という理由・再実行方法を表示する（誤って「照合できる」と見せかけない）。実行ログにも`CLAUDE_OCR_REVIEW`セクションを追加した
- [x] 指示書には、判断区分`decision`（`tesseract`/`apple_vision`/`merged`/`corrected`/`unresolved`）・ページ別候補JSON/進捗JSON/全体集約JSON/人間確認用サマリーの仕様・採用判断基準・ページごとの確認手順（元画像を必ず視覚確認する）・中断/再開の手順・完了条件・禁止事項（Claude API不使用、`editable/lesson_pages.json`不変更等）を明記した
- [x] `build-all`実行時点では`CLAUDE_OCR_REVIEW.md`と`claude_review/README.md`のみを生成し、`claude_review/pages/`・`progress.json`・`candidates.json`・`review_summary.md`は生成しない（指示書を読んだClaude Codeが作成する）

### テスト追加・更新

- [x] `tests/test_ocr_claude_review.py`（新規21件）: ページ番号一覧の圧縮表記（連続区間のまとめ、100件超でも冗長にならないこと）、指示書への実際のページ総数・相対パスの埋め込み、絶対パスが含まれないこと、OCR全文が重複埋め込みされないこと、秘密情報・APIキーが含まれないこと、ソースコード自体にClaude API・外部送信コードが無いことの静的確認、候補JSONの必須スキーマ・許可された`decision`値・`unresolved`時の推測禁止・中断/再開手順・`progress.json`/`candidates.json`/`review_summary.md`仕様が指示書に明記されること、固定ページ数へ依存しないこと（3ページ・137ページで同じ関数が正しく動くこと）、特殊文字を含む`source_image`でも構造が壊れないこと、Apple Vision利用不可時に何も生成されないこと、`build-all`時点では`README.md`以外生成されないこと
- [x] `tests/test_cli_ocr_engine_flag.py`（+6件）: `tesseract+vision`指定時に指示書・READMEが生成され既存の比較出力一覧が維持されること、`tesseract`（既定）では生成されないこと、標準出力へコピー可能な固定の1文が表示されること（絶対パスは表示されない）、Apple Vision利用不可時に誤った次ステップ案内を表示しないこと、Phase 10.9のreview.html UI（差分ハイライト・確定テキスト欄・書き出し/リセットボタン）が壊れていないこと、`editable/lesson_pages.json`に指示書由来の文字列が混入しないこと

### 実データ確認（`input/source/`11ページ、`build-all --ocr-engine tesseract+vision`）

- `build-all`実行後、標準出力に`CLAUDE_OCR_REVIEW`バナーとコピー可能な1文が表示され、`output/ocr_engine_eval/ocr_comparison/CLAUDE_OCR_REVIEW.md`が実際のページ総数（11）・ページ番号一覧（`1-11`）・正しい相対パスで生成されることを確認した
- 生成された指示書の指示に**実際に従い**、11ページすべてで元画像を視覚確認したうえでTesseract/Apple Vision結果を照合し、`claude_review/pages/page_NNN.json`をページごとに保存した。判断区分の内訳は`apple_vision`4件・`merged`5件・`corrected`2件・`tesseract`0件・`unresolved`0件（全ページ元画像から明確に判読できたため`unresolved`は0件）
- **中断・再開の実演**: ページ1〜6を保存した時点で`progress.json`を更新し（`completed_pages: [1,2,3,4,5,6]`、`remaining_pages: [7,8,9,10,11]`）、その後の再開時に既存の正常な候補JSON（対象の比較JSONより新しいもの）が処理済みとして正しく検出され、未処理の7〜11ページだけを処理できることを確認した
- 全11ページ完了後、`candidates.json`（集約時の検証: ページ欠落・重複無し、順序正しい、`decision`許可値のみ、`decision_counts`合計=11で一致）と`review_summary.md`（判断区分別件数・人間確認ページ一覧「なし」・主な修正例・次に人間が行う操作を含む）を生成した
- 代表ページの照合結果:
  - **Page7**: Tesseractの「店労」「性細」「もし→も」の誤読、末尾行の意味不明化（「生計隊入上上」）をApple Visionの読みで修正。一方「発信」はApple Visionが「発言」と誤読しており、この箇所はTesseract側の読みを採用した（`merged`）
  - **Page4**: Apple Visionをベースに、Apple Visionが脱落させた「信」（「信頼されるタイプ」）だけTesseract側から補った（`merged`）
  - **Page9**: Page7と同じ「発信/発言」誤読パターンを確認し、Tesseract側を採用。「目分」「告れる」「砦細」「キャラクタ（長音欠落）」はApple Visionの読みを採用した（`merged`）
  - **Page11**: Tesseract「⑩.」・Apple Vision「10」のいずれも単独では丸数字「⑩」を正しく再現できておらず、元画像の字形に基づき「⑩」（末尾の余分な記号・Tesseractが幻覚的に追加した末尾の「ーー」を除去）へ修正した（`corrected`）
  - **Page3**: 2段組みレイアウトのため、Apple Visionの文字内容を土台にしつつ、元画像のレイアウト（左列=キャラクターT、右列=キャラクターB）に合わせて行の並びを組み直した（`corrected`）
- 作業完了後、`output/editable/lesson_pages.json`・`output/ocr_engine_eval/ocr_comparison/summary.json`・`pages/page_NNN.json`（比較元）・元画像のいずれも変更されていないことをファイル更新時刻の比較で確認した

### 今回実装しなかったもの・制限事項

- 候補（`claude_review/candidates.json`等）の`editable/lesson_pages.json`への自動反映（将来の別タスク）
- プログラムからのClaude API呼び出し・Claude Codeプロセスの自動起動（指示書は人間が別セッションへ手動で渡す運用を前提にしている）
- 今回の実データ確認は11ページだったが、指示書生成ロジック自体は固定ページ数に依存しない設計・テスト（3ページ・137ページでの検証）で確認している。100ページ規模での実際のClaude Codeによる照合作業そのものは今回実施していない

## Phase 10.11: Claude Code画像照合レビュー候補の`editable/lesson_pages.json`への安全な反映（`apply-ocr-review`）

Phase 10.10でClaude Codeが画像照合レビューを行い`claude_review/candidates.json`を作成できるようになったが、その内容を`output/editable/lesson_pages.json`へ反映する手段が無く、人間が手作業で書き写す必要があった。`apply-ocr-review`は、`--dry-run`での分析→`--apply`での実反映という明示的な2段階操作を経て、`candidates.json`のページ全文（`proposed_text`）を`lesson_pages.json`へ安全に反映するコマンドである。`ocr-check`/`apply-ocr-corrections`/`approve-ocr-candidates`（substring単位のOCR補正候補ワークフロー。[`docs/14_apply_ocr_corrections_workflow.md`](14_apply_ocr_corrections_workflow.md)）とは完全に別のワークフローであり、候補スキーマ・安全条件は混在させていない。詳細な仕様・実行例は[`docs/16_apply_ocr_review_workflow.md`](16_apply_ocr_review_workflow.md)を参照。

### 実装

- [x] `src/ocr_review_apply.py`（新規）: `resolve_paths()`（`--output-dir`から既定パス一式を解決。`--lesson-pages`/`--candidates`/`--report-dir`で個別上書き可）、`parse_page_selection()`（`--pages`の`"1,4,7-11"`形式の解析。重複・逆順区間・存在しないページ番号はエラー）、`reconstruct_fields_from_proposed_text()`（**新しい独自の分割ルールは実装せず**、`import_source.py`の`_derive_title_and_summary()`/`_text_to_lines()`をそのまま呼び出して`title`/`body`/`summary`を再構築。既存のOCR取り込み仕様（先頭行=title・titleはbodyから除外しない＝重複させる）をそのまま踏襲する）、`apply_proposed_text_to_page()`（再構築したtitle/body/summaryを設定した後、`lesson_pages._apply_derived_fields()`をそのまま呼び出してimage_text/canva_prompt/video_sceneを再計算。`layout_instruction`/`notes`/`source_image`/`source_assets`/`source_page_no`/`role`/`page_no`は変更しない）、`validate_and_plan()`（検証とページ別反映計画の作成。実書き込みは行わない）、`apply_document()`（検証済みの計画から実際にバックアップ＋原子的書き込みを行う）、`render_apply_report_json/markdown()`・`write_apply_reports()`を実装
- [x] `src/cli.py`: `apply-ocr-review`サブコマンドを追加（`--output-dir`必須、`--lesson-pages`/`--candidates`/`--report-dir`/`--pages`は任意上書き、`--dry-run`/`--apply`は相互排他かつ必須）。実行後は固定書式のバナー（`OCR_REVIEW_APPLY_DRY_RUN:`/`OCR_REVIEW_APPLY:`＋`passed`/`failed`、変更予定・変更なし・反映不可ページ一覧、バックアップ先、レポートパス、次の操作のコピー可能なコマンド）を標準出力へ表示する`_print_ocr_review_apply_notice()`を追加
- [x] **設計判断（重要・Codexの確認事項）**: ページ単位の反映可否判定（`decision: unresolved`・`requires_human_review: true`・`unresolved_spans`が残っている・`proposed_text`が空・`decision`が未知の値・`progress.json`の`remaining_pages`に含まれる＝未完了）で対象ページが1件でも条件を満たさない場合、**そのページだけを除外するのではなく、対象範囲（`--pages`指定時はその範囲、既定では全ページ）全体を反映不可として扱う**設計にした。`--allow-unresolved`のようなバイパスは提供していない。理由: 一部ページだけを黙って除外すると「見えない未反映」が生まれ、利用者がdry-run/applyの結果を見ても何が反映され何が反映されなかったかを見落としやすくなるため、全体を止めて明示的にレポートへ理由を出す方を安全側とした。この設計の妥当性（部分反映を許容すべきか）はCodexの判断を仰ぎたい
- [x] 入力検証: ファイル存在・UTF-8 JSON妥当性、`candidates.json`の`schema_version`（対応: 1のみ）・`source`（`claude_code_image_review`固定）、`pages`配列、集約⇄ページ別candidate JSON⇄比較元JSON⇄`lesson_pages.json`の`page_no`/`source_image`相互一致（`source_image`は絶対パス・パストラバーサルを拒否したうえで正規化して比較）、件数整合（`--pages`省略時のみ`total_pages`/`completed_pages`/`decision_counts`合計/`lesson_pages.json`ページ数/`progress.json`の整合を厳密チェック）、`progress.json`の`failed_pages`非空は即エラー
- [x] バックアップ・原子的書き込み: `--apply`時、書き込み前に`editable/backups/<timestamp>_lesson_pages.before_ocr_review.json`へバックアップを作成（既存バックアップは上書きしない）。書き込みは一時ファイルへ書いてから`os.replace()`で置換する方式（`src/verification_evidence.py`の`_atomic_write_text()`と同じ方式）を採用し、書き込んだ内容をJSONとして再読込・検証してから置換する
- [x] 冪等性: 対象ページすべてが既に反映済み（`has_changes=False`）の場合、`--apply`はバックアップも書き込みも行わず「変更なし」として正常終了する（2回目以降の`--apply`で無駄なバックアップが増え続けない設計）

### テスト追加（Phase 10.11）

- [x] `tests/test_ocr_review_apply.py`（新規33件）: `reconstruct_fields_from_proposed_text()`の先頭行title抽出・60文字切り詰め・titleのbody重複、`apply_proposed_text_to_page()`のimage_text/canva_prompt/video_scene再計算とlayout_instruction/notes不変・呼び出し元page非破壊、`parse_page_selection()`の単一/範囲/重複/逆順/存在しないページ番号、`validate_and_plan()`の正常系（変更あり/なしページの判定・`--pages`絞り込み）と拒否系（unresolved/requires_human_review/unresolved_spans/proposed_text空/decision未知/未完了ページ/failed_pages非空/schema_version未対応/source不一致/source_image不一致・絶対パス・パストラバーサル拒否/ファイル欠落・不正JSON時の例外）、`apply_document()`のバックアップ作成・反映内容・metadata保持・page_no等の保持・冪等性（2回目はバックアップを増やさない）・未passedでの例外・反映結果が既存ローダーで読み戻せること、レポート生成関数群
- [x] `tests/test_cli_apply_ocr_review.py`（新規9件）: サブコマンド認識、`--dry-run`/`--apply`の相互排他・両方省略時のエラー、dry-runのバナー表示と非破壊性、既定パス解決、apply実行時のバックアップ作成と`regenerate`コマンド案内、2回目applyの冪等性（バックアップが増えないこと）、unresolvedページによる拒否時の非ゼロ終了コードと`lesson_pages.json`不変、`--pages`絞り込み、`--lesson-pages`/`--candidates`個別上書き
- [x] 既存856件（Phase 10.10時点814件+今回42件）すべて成功（`pytest -q`で確認）

### 実データ確認（`output/ocr_engine_eval/`の専用コピー、11ページ）

既存の評価用成果物（`output/ocr_engine_eval/`）を不用意に破壊しないよう、`/tmp`配下の専用コピーに対して実行した。

- **dry-run**: 11ページすべてが`変更予定ページ`として表示され、`OCR_REVIEW_APPLY_DRY_RUN: passed`。元の`lesson_pages.json`は無変更、バックアップも未作成
- **不正候補での拒否確認**: Page3の`decision`を`unresolved`に書き換え、`unresolved_spans`を追加した専用コピーで実行したところ、`OCR_REVIEW_APPLY_DRY_RUN: failed`・`反映不可ページ: 3`となり終了コードは非ゼロ。元の`lesson_pages.json`はバイト単位で無変更（MD5一致を確認）
- **apply**: 11ページすべてが反映され、`OCR_REVIEW_APPLY: passed`。Page1の受け入れ基準（Tesseractの「ますず」→「まず」）が`body`だけでなく`summary`/`image_text`/`canva_prompt`/`video_scene`すべてに伝播していることを実際のJSON出力で確認した。バックアップが`editable/backups/`配下に1件作成された
- **冪等性**: 直後に再度dry-runを実行すると`変更予定ページ: なし`・`変更なしページ: 1, 2, ..., 11`。再度applyを実行しても`反映ページ: なし`・バックアップは増えず1件のまま
- **regenerate**: 反映済み`lesson_pages.json`に対して`regenerate --output-format all`を実行し正常終了。生成された`canva/canva_design.md`・`exports/material.md`に「まず」（修正後の文言）が反映され、「ますず」（修正前の誤読）が残っていないことを確認した

### 今回実装しなかったもの・制限事項

- 部分反映（一部ページだけを反映不可として除外し、残りだけ反映する方式）は採用していない。前述の設計判断のとおり全体停止方式にした（Codexの確認事項）
- `--apply`成功後の`regenerate`自動実行は行っていない（推奨方針どおり、次に実行するコマンドを案内するだけに留めた。非破壊性の観点からは自動実行しても問題ない可能性があるが、今回は明示操作を維持した）
- 候補の"古さ"検出は、ページ番号・`source_image`・比較元JSONとの突き合わせ・`progress.json`の整合性チェックまでに留まる。ハッシュ値等によるフィンガープリント方式の厳密な鮮度検証は、Phase 10.10の既存candidatesスキーマの後方互換性を壊さない範囲で将来追加できる余地がある（今回は未実装）
- Phase 10.9のブラウザ側JSON書き出し（`adopted_source`/`final_text`等のスキーマ）は今回の反映対象外（`claude_review/candidates.json`のみを対象とした）。将来対応する場合も、別の入力アダプタとして追加し、本モジュールのスキーマ・安全条件と混在させないことを推奨する

## Phase 10.7〜10.13のロードマップ（最終目的との関係）

Phase 10.7以降の一連のPhaseは、それぞれ独立した技術課題ではなく、次のロードマップの各段階を
担っている。**途中技術（OCR精度そのもの）を最終成果物と取り違えないよう、ここに明記する。**

```text
OCR取得（Phase 10.4/10.6: Tesseract単体の精度改善）
→ OCR画像照合（Phase 10.7/10.8/10.9/10.10: Apple Visionとの比較・差分ハイライト・
  確定テキスト編集UI・Claude Codeによる元画像照合レビュー）
→ OCR確定原文保存（Phase 10.11: apply-ocr-reviewによるeditable/lesson_pages.jsonへの安全な反映）
→ 本文ブラッシュアップ（Phase 10.13: OCR確定原文を証拠として保持したまま、教材本文を
  分かりやすく改善する）
→ 人間承認・正式本文反映（Phase 10.13: apply-content-brushupによる明示的な反映）
→ 画像構成・デザイン（Phase 10.12: prepare-image-brushupによるAIエージェント向けデザイン設計）
→ 決定論的画像描画（Phase 10.12: render-brushupによるブラッシュアップ済み教材画像の生成）
```

このプロジェクトの最終目的は「元教材画像から正確な原文を取得し、教材本文を分かりやすく改善し、
内容に合ったページ構成・画像デザインを作り、ブラッシュアップ済み教材を出力すること」であり、
OCRで文字を正しく読み取ること自体は最終目的ではなく、その前提条件（上記ロードマップの前半）に
過ぎない。**Phase 10.12だけでは「確定済み文字列を一字一句変更しない」という制約により、実際に
改善されたのは画像レイアウトだけで、文章表現自体は評価・改善されていなかった。** Phase 10.13で
本文ブラッシュアップ工程が加わったことで、初めてロードマップ全体が完成し、最終目的に到達する。

## Phase 10.12: 確定済みOCR本文による教材画像ブラッシュアップ生成（`prepare-image-brushup` / `render-brushup`）

Phase 10.11までで正確な本文（`editable/lesson_pages.json`）の確定・反映が完成したが、それを実際の
教材画像として再設計・生成する導線が無かった。既存の`rendered/`は`source_image`があれば元画像を
そのままコピーするだけで、「ブラッシュアップ済み教材画像」と呼べる成果物ではない。本Phaseで、
AI作業エージェント（Claude Code/Codex）がデザインを設計し、決定論的なレンダラー（Pillow）が
確定済み本文を正確に描画する、3段階の導線（`prepare-image-brushup`→AIエージェントによる設計→
`render-brushup`）を実装した。詳細仕様は[`docs/17_image_brushup_workflow.md`](17_image_brushup_workflow.md)を参照。

### 実装

- [x] `src/image_brushup_design.py`（新規）: `render_ai_image_brushup_instructions(document, output_dir)`
  （`AI_IMAGE_BRUSHUP.md`本体の生成。Claude Code・Codexどちらでも使える製品非依存の指示書。実データから
  埋め込むのはページ総数・ページ番号一覧・相対パス等の構造情報のみで、本文は埋め込まない）、
  `render_design_readme()`、`write_design_entry_points()`、デザインJSON検証（`validate_design_page()`:
  `schema_version`/`page_no`/`source_image`一致（パストラバーサル・絶対パス拒否）/`canvas`（サイズ範囲・
  色コード）/`theme`（色コード）/`template`（許可値）/`blocks`（許可type・`source_field`は`title`/`body`/
  `summary`のみ・`text`等での本文複製を明示的に拒否・style（font_size/font_weight/alignment/color/
  padding）検証）、`validate_manifest()`（ページ欠落・重複検出）を実装
- [x] `src/brushup_renderer.py`（新規）: `render_design_page()`（1ページ分の決定論的描画。`title`/
  `summary`/`body`/`note`/`checklist`/`steps`/`quote`/`divider`/`spacer`の全ブロック種別に対応。
  1パス目でブロック高さを測定し2パス目で縦方向に中央寄せして描画する2パス方式）、`_fit_text_block()`
  （spec仕様どおりの縮小手順: 指定サイズ→余白縮小→行間縮小→最小フォントまで縮小→[bodyブロックのみ]
  2段組みへ変更、の優先順で最初に収まる組み合わせを採用。デザインJSON側が明示的に`columns: 2`を
  指定した場合はオーバーフローの有無に関わらず常に2段組みで描画する）、`verify_not_source_copy()`
  （ファイルハッシュ・ピクセルデータ比較による元画像コピー検出）、`load_design_pages()`（manifest+
  ページ別デザインJSONの読み込み・検証）、`render_all_pages()`、`render_report_json/markdown()`、
  `render_comparison_html()`（外部CDN・外部CSS・外部JS非依存の自己完結HTML）を実装。本文の取得元は
  常に`LessonPage`（`title`/`summary`はそのまま、`body`は既存の`clean_dialogue_lines()`を再利用して
  話者・台詞ペアへ分解）で、デザインJSON内に本文は一切存在しない
- [x] `src/image_renderer.py`の`resolve_font_path()`/`warn_missing_japanese_font()`を再利用（重複実装
  せず）。フォント読み込み自体は太字対応のため`brushup_renderer.py`内に独自の`_load_font()`（W3/W4→W6
  等のファイル名置換によるボールド代替探索）を実装
- [x] `src/cli.py`: `prepare-image-brushup`（`--output-dir`必須）・`render-brushup`（`--output-dir`
  必須、`--font-path`任意）の2サブコマンドを追加。`_print_image_brushup_prepare_notice()`/
  `_print_image_brushup_render_notice()`で固定書式のバナーを表示

### テスト追加（Phase 10.12、新規47件）

- [x] `tests/test_image_brushup_design.py`（24件）: 指示書へのページ総数/相対パス埋め込み・本文非埋め込み・
  絶対パス非埋め込み・固定ページ数非依存（3/137ページ）、`README.md`生成、全ブロックtype受け入れ、
  未知テンプレート拒否、page_no不一致拒否、ページ欠落/重複検出、source_image不一致・絶対パス・
  パストラバーサル拒否、本文複製（`text`等のフィールド）拒否、不正色コード拒否、負のfont_size拒否、
  canvas範囲外拒否、未許可source_field拒否、未対応schema_version拒否、空blocks拒否
- [x] `tests/test_brushup_renderer.py`（16件）: PNG生成、`lesson_pages.json`由来の文字列がそのまま
  描画される（text_match）こと、丸数字・長音・括弧等の特殊文字保持、全ブロックtype描画、2段組み
  （明示指定時）、オーバーフロー前の段階的縮小、収まらない場合の失敗（省略記号"…"を使わないこと）、
  元画像コピー検出（同一ファイル/異なるファイル）、`render_all_pages`が元画像をコピーしないこと、
  `load_design_pages`のmanifest検証（正常系/欠落検出/manifest不在/source_image不一致）、
  レポート・comparison.html生成（外部URL不使用）のend-to-end確認
- [x] `tests/test_cli_image_brushup.py`（7件）: `prepare-image-brushup`のREADME/指示書生成・コピー
  可能な1文表示・絶対パス非表示・`--output-dir`必須、`render-brushup`のデザイン未作成時のクリーンな
  失敗、実際の画像生成・レポート生成・`text_match`確認・既存`rendered/`非変更・元画像非変更、
  オーバーフロー時の非ゼロ終了、`lesson_pages.json`非変更
- [x] 既存903件（Phase 10.11時点856件+今回47件）すべて成功（`pytest -q`で確認）

### 実データ確認（`output/ocr_engine_eval/`の専用コピー、11ページ）

既存の評価用成果物を変更しないよう、`/tmp`配下の専用コピーに対して実行した。

- `prepare-image-brushup`実行後、`brushup_design/AI_IMAGE_BRUSHUP.md`・`README.md`が生成され、
  標準出力にコピー可能な1文が表示されることを確認した
- 実際に元画像11ページすべてを視覚確認したうえで（`assets/page_NNN.jpeg`、1706x960の横長画像。
  暖色グラデーション枠・クリーム色カード・濃いワインレッドの文字という共通デザインを確認）、
  ページごとにデザインJSONを作成した。Page1（導入・ルール提示）は`title_body`、Page3（キャラクター例
  2件を左右比較で提示する構成を元画像で確認）は`two_column`（`columns: 2`）、Page2/4〜11
  （①〜⑩の単一の質問＋説明という共通構造を元画像で確認）は`question`（本文を`note`ブロックで
  枠囲みにして質問の重要性を強調）を採用した
- `render-brushup`実行後、11ページすべてが成功（`IMAGE_BRUSHUP_RENDER: passed`、失敗0件）。
  `template_counts`は`title_body: 1 / question: 9 / two_column: 1`
- Page1の受け入れ基準（「まず」。Phase 10.11で確定済み）、Page3の2段組み（キャラクターT/Bの左右
  比較を維持）、Page7の「苦労」「些細」「もし」「発信」、Page11の「⑩」（丸数字保持）が、いずれも
  生成画像へ正しく反映されていることを目視で確認した
- 全11ページで`text_match: true`・`overflow: false`（打ち切りなし）を確認した
- 生成画像11件のファイルハッシュ・ピクセルデータが対応する元画像と異なることを確認した
  （`verify_not_source_copy()`によるコード上の検証、および目視確認の両方）
- `comparison.html`を生成し、元画像とブラッシュアップ画像を横並びで確認できることを確認した
- 既存の`output/ocr_engine_eval/`（実際の評価用ディレクトリ）・`rendered/`・`editable/lesson_pages.json`・
  `assets/`のいずれも変更されていないことを確認した（作業はすべて`/tmp`配下の専用コピーで実施）

### 今回実装しなかったもの・制限事項

- デザインJSONの`source_field`はページ単位のフィールド全体（`title`/`body`/`summary`）を参照する
  粗粒度の設計。フィールドの一部（本文の特定の1行だけ等）を異なるブロックへ個別に割り当てることは
  未対応（将来、bodyの行単位分割参照に対応する場合も、既存の粗粒度スキーマとの後方互換性を保つ設計が
  望ましい）
- 元画像の複雑な配色（グラデーション背景等）を自動抽出してテーマ色へ反映する機能は無く、
  AIエージェントが元画像を見て手動で近似色を選ぶ設計
- 画像生成AI（背景・挿絵素材専用）との連携は未実装（指示書内でも「今回は使用しない」旨を明記）
- 元画像内の文字を画像素材としてそのまま再利用する機能は無い（意図的に未実装。誤字混入を防ぐため）
- 実データ確認は11ページだったが、指示書生成・検証ロジック自体は固定ページ数に依存しない設計・
  テスト（3ページ・137ページでの検証）で確認している。100ページ規模での実際のAIエージェントによる
  デザイン設計作業そのものは今回実施していない

## Phase 10.12 追加修正: 実データレビュー指摘によるデザイン品質の是正

Phase 10.12実装直後、`AI_IMAGE_BRUSHUP.md`の指示に従って実データ11ページのデザインJSONを作成し
`render-brushup`した生成画像を人間がレビューした結果、次の指摘を受けた。**指摘1〜3は実装（レンダラー・
スキーマ）の欠陥であり、指摘4はデザインJSONの作り方（AI作業エージェントの設計判断）の問題だった。**

1. 「枠外に題名を入れるのであれば、枠内には不要」（タイトルが`title`ブロックと`body`ブロックの
   両方に重複表示されていた）
2. 「単純に元ファイルと記載されている内容が一緒、全くブラッシュアップされていない」「何だったら
   劣化してる。元ファイルは大事なとこは大きくなっていたりするが、作成した画像は均一で
   メッセージ性が何も感じられない」（`body`全体を1つのブロックへ均一な文字サイズで詰め込んで
   おり、元画像にある「問いかけを大きく・補足説明は小さく」という情報階層が失われていた）
3. 「ページ３とか構成が変わっていて、何の事か分からない。元画像をみて構成が伝わるように再構成」
   （Page3の2段組みが単純な行数の半分割で、「例1）キャラクターT」の途中で列が切り替わり
   「例2）キャラクターB」の内容と混在していた）
4. 「枠の余白が大きすぎて邪魔。それで中の文字が小さくなって読みにくくなるとか論外」（`padding`を
   30px超に設定していたため、shrink-to-fitが余白確保のために文字サイズを不必要に縮小していた）

### 実装（是正内容）

- [x] `src/brushup_renderer.py`: `_paragraph_lines_for_field()`に`line_range`（`[start, end]`。
  0始まり、`end`は`null`で末尾まで）引数を追加。`source_field`の段落の一部だけをブロックが参照
  できるようにし、**既存の行を並べ替えたり複製したりせず**、同じ本文の異なる部分を複数のブロックへ
  分けて文字サイズ・太さ・箱の有無を変えられるようにした（指摘1・2の是正）
- [x] `_measure_columns()`を全面書き換え: 従来は折り返し済みの行を単純に半分の行数で機械的に
  分割していたが、**段落の境界を保ったまま**（1つの段落の折り返し行が左右に分裂しないように）
  段落単位で列を割り当てる方式に変更。さらに`split_at`（段落インデックス）を指定すると、
  その位置で厳密に列を分けられるようにした（指摘3の是正）
- [x] `note`ブロックが`columns`/`split_at`を無視していた欠陥を修正（従来`columns`は`body`
  ブロックでしか効かなかった。`note`ブロックでの2段組み利用は実データレビューで初めて発覚した
  実装漏れ）
- [x] `footer.show_source_notice`が固定文言「※無断転載禁止」をレンダラー内にハードコードして
  自動描画していた実装を廃止（本文に実在する同内容の注記行と二重表示されていたため）。
  同フラグは元画像ファイル名を小さく表示するトレーサビリティ用途に変更した
- [x] `src/image_brushup_design.py`: デザインJSONスキーマに`blocks[].line_range`・
  `blocks[].split_at`を追加し検証ロジックを実装。`AI_IMAGE_BRUSHUP.md`の指示書本文へ、
  情報階層の再現・タイトル重複の回避・`split_at`の使い所・余白の目安を「5.7 実データレビューで
  判明した設計ルール」として明記し、以降にこの指示書を使うAIエージェントが同じ問題を
  繰り返さないようにした（詳細は[`docs/17_image_brushup_workflow.md`](17_image_brushup_workflow.md)
  「5.7」参照）

### テスト追加（9件）

- [x] `tests/test_brushup_renderer.py`（+9件）: `line_range`によるタイトル重複行の除外、
  `line_range`の`start`/`end`指定、`line_range`を使ったbodyブロックでのタイトル非重複描画、
  `_measure_columns`が段落を分裂させないこと、`split_at`で意味区切りどおりに列振り分けされること、
  `note`ブロックの`columns: 2`+`split_at`が機能すること（今回の実装漏れの回帰テスト）、
  デザインJSON検証が`line_range`/`split_at`を正しく受理・拒否すること
- [x] 既存912件（追加修正前903件+今回9件）すべて成功（`pytest -q`で確認）

### 実データでの再検証

`/tmp`配下の専用コピーで修正後のデザインJSON（問いかけ=大・太字/補足説明=枠囲み中サイズ/注記=
小・muted、Page3は`split_at`でキャラクターT/Bを厳密分割、`padding`を30px超から8〜20px程度へ
縮小）を作成し`render-brushup`で再生成、11ページ全て成功・目視で改善を確認したうえで、
実際に`output/ocr_engine_eval/`（既存の評価用ディレクトリ本体）のデザインJSONを差し替えて
`render-brushup`を再実行し、11ページ全て成功したことを確認した。`editable/lesson_pages.json`・
元画像は変更していない。

## Phase 10.12 追加修正2: 再生成結果への第2回レビュー指摘（本文の分裂・2段組みの内容混入・改行位置）

上記の追加修正1を適用した再生成結果を人間が再度レビューし、次の指摘を受けた。

1. 「題名と本文の分け方が変。この構成なら①〜の部分は本文の中に入っているべき」（元画像は
   問いかけ「①〜」と補足説明が同じ1枚のカードに収まっているが、追加修正1では問いかけを
   `title`同様に枠なしで独立させてしまい、「本文の一部が本文の外に浮いている」ように見えていた）
2. 「３ぺーじ　無題転載禁止が本文になっているので抜く」（Page3の2段組みブロックの`line_range`が
   注記行（※無断転載禁止）まで含んでおり、右列の箇条書き最後の項目のように見えていた）
3. 「でそもそも本文が全く変更ないけど、文として１００点とおもっているってことなの？」（本文の
   文言を一切変更しない設計方針についての確認。Phase 10.7〜10.11から一貫する意図的な安全設計
   であり、文言の質自体は今回のスコープ外である旨を回答した。文言改善が必要な場合は別工程として
   追加検討する）
4. 「枠の余白が大きすぎて邪魔。それで中の文字が小さくなって読みにくくなるとか論外」（追加修正1の
   後日、Page3の2段組み内で「頭の固さ」「鼻が利く」を含む行が、左右均等割りの列幅にわずかに
   収まらず、閉じ括弧だけが次行へ追い出される不自然な改行が発生。「右ブロックをもう少し右に
   ずらせばいい」という具体的な指示を受けた）

### 実装（是正内容）

- [x] `src/brushup_renderer.py`: `type: "group"`ブロックを新設（`_measure_group()`/`_draw_group()`）。
  複数の子ブロック（`title`/`summary`/`body`のみ）を1つの共有背景の中へ上から順に積み重ねて
  描画する。子ブロックごとに`line_range`・文字サイズ・太さを変えられるが、背景は1つだけ
  （指摘1の是正）
- [x] Page3のデザインJSONを、2段組みブロックの`line_range`から注記行（インデックス14）を除外し、
  他ページと同様の独立した小さい注記ブロックへ分離（指摘2の是正）
- [x] `_measure_columns()`/`_fit_text_block()`/`_draw_paragraph_block()`に`column_ratio`
  （左列の幅比率。既定0.5）を追加。測定時と描画時で同じ計算式（`_column_widths()`）を使うことで
  ずれを防止。Page3の2段組みへ`column_ratio: 0.58`を適用し、左列（キャラクターTの箇条書き）を
  やや広げることで、「頭の固さ」「鼻が利く」を含む行が1行に収まるようにした（指摘4の是正）
- [x] `src/image_brushup_design.py`: `group`ブロックのスキーマ検証（子blockは`title`/`summary`/
  `body`のみ・`columns`不可・再帰的に`_validate_block()`で検証）、`column_ratio`の検証
  （0.1〜0.9の数値）を追加。`AI_IMAGE_BRUSHUP.md`指示書の4.3〜4.5節・5.7節を、`group`ブロックと
  `column_ratio`の使い方・第2回レビューで判明したルールを反映して更新

### テスト追加（6件）

- [x] `tests/test_brushup_renderer.py`（+6件）: `group`ブロックが1つの共有背景で描画されること、
  `group`の子blockに許可されない`type`を拒否、空の`blocks`を拒否、`_column_widths()`が
  `column_ratio`に応じて左右幅を変えること、`column_ratio`で不自然な改行が回避されること
  （均等割りでは2行になる行が、広げた列幅では1行に収まることを実測して確認）、範囲外の
  `column_ratio`を拒否
- [x] 既存918件（追加修正1時点912件+今回6件）すべて成功（`pytest -q`で確認）

### 実データでの再検証

`/tmp`配下の専用コピーで再修正版デザインJSON（Page1/2/4〜11は`group`で問いかけ+補足説明を
1枚のカードに統合、Page3は`group`（問いかけ+導入説明）+`column_ratio: 0.58`付き2段組み
（例1/例2）+独立した注記ブロックの3ブロック構成）を作成・検証（スキーマエラー0件）・
`render-brushup`実行（11/11成功、`text_match`全ページtrue、Page3の該当行が1行に収まることを
目視確認）したうえで、実際に`output/ocr_engine_eval/`のデザインJSONを差し替えて
`render-brushup`を再実行し、11ページ全て成功したことを確認した。`editable/lesson_pages.json`・
元画像は変更していない。

### 残課題（追加修正2時点）

- `group`は子ブロックに`title`/`summary`/`body`のみ許可し、`checklist`/`steps`/`quote`や
  ネストした`group`は今回未対応（必要になった場合は別途拡張を検討）
- `column_ratio`は数値を人間・AIエージェントが目視で判断して指定する運用であり、左右の
  実際の折り返し結果を見て自動調整する仕組みは無い
- 本文の文言そのものの質的改善（言い回し・分かりやすさ）は、上記指摘3への回答のとおり
  引き続き今回のスコープ外

## Phase 10.13: OCR確定原文を保持した教材本文ブラッシュアップ（`prepare-content-brushup` / `apply-content-brushup`）

Phase 10.12は「確定済み文字列を一字一句変更しない」という制約のもとで実装されたため、実際に
改善されたのは画像レイアウトだけで、文章表現自体は評価・改善されていなかった。本Phaseで、
OCR確定原文を変更不能な証拠として保持したまま、AI作業エージェント（Claude Code/Codex）が
教材本文を分かりやすく改善する候補を作成し、人間が明示操作（`--dry-run`→`--apply`）で
`editable/lesson_pages.json`へ反映する導線を実装した。本文が更新された場合、古いPhase 10.12
デザインJSONでそのまま描画してしまわないよう、`lesson_pages.json`のハッシュをデザイン
manifestへ記録・照合する仕組みも追加した。詳細仕様は
[`docs/18_content_brushup_workflow.md`](18_content_brushup_workflow.md)を参照。

### 実装

- [x] `src/content_brushup.py`（新規）: `resolve_paths()`（`ContentBrushupPaths`）、
  `build_snapshot()`/`write_snapshot()`/`check_snapshot_status()`（OCR確定原文スナップショットの
  作成・SHA-256記録・既存スナップショットとの一致/不一致判定。既存の作業中候補を黙って
  破棄しないための基盤）、`render_ai_content_brushup_instructions()`（AIエージェント向け指示書。
  「OCR確定は文章完成を意味しない」を明記し、本文全文は埋め込まない）、
  `validate_candidate_page()`/`validate_candidates_aggregate()`（`original`のスナップショット
  完全一致・`before`/`after`の実在確認・`change_type`/`risk_level`許可値・`risk: high`と
  `requires_human_review`の整合等を検証）、`render_content_diff()`（Phase 10.8と同じ
  「元の文字列を先に分割してからhtml.escape」の安全な手順を踏襲した、原文/改善案向けの独立した
  差分関数）、`render_review_html()`/`render_review_summary_markdown()`を実装
- [x] `src/content_brushup_apply.py`（新規）: `ContentApplyPlan`/`ContentApplyResult`
  データクラスと`validate_and_plan()`/`apply_document()`の2関数構成（Phase 10.11の
  `ocr_review_apply.py`と同じ設計パターン）。対象範囲内で1ページでも反映不可条件
  （`risk_level: high`・`requires_human_review: true`・スキーマ不正等）を満たす場合は
  対象範囲全体を反映不可として扱う「全体停止方式」を踏襲し、`--allow-high-risk`のような
  バイパスは提供しない。バックアップ（`editable/backups/..._before_content_brushup.json`）＋
  原子的書き込み（一時ファイル→`os.replace()`）も同パターンを踏襲
- [x] **冪等性の設計判断（重要）**: `lesson_pages.json`全体のハッシュとスナップショットの単純
  比較では、`--apply`成功後に本文が意図的に変わるため2回目以降のdry-run/applyが恒久的に
  失敗してしまうことが実装時に判明した。対象ページごとに「現在値が原文と一致する（未反映）」か
  「現在値が改善案と一致する（反映済み＝冪等）」かを個別に確認し、どちらでもない場合だけ
  他の変更との競合として拒否する方式に設計変更して解決した
- [x] `src/image_brushup_design.py`: `lesson_pages_sha256()`・`check_manifest_freshness()`を
  追加。`render_ai_image_brushup_instructions()`に現在の`lesson_pages.json`のSHA-256を埋め込み、
  AIエージェントが作成する`design_manifest.json`へ`source_lesson_pages_sha256`として記録させる
  よう指示書を更新
- [x] `src/brushup_renderer.py`: `load_design_pages()`に鮮度チェックを追加。
  `design_manifest.json`の`source_lesson_pages_sha256`が現在の`lesson_pages.json`のハッシュと
  一致しない場合（または記録されていない古いmanifestの場合）、`render-brushup`を拒否し
  `prepare-image-brushup`の再実行を促すメッセージを表示する
- [x] `src/cli.py`: `prepare-content-brushup`（`--output-dir`必須、`--force`任意）・
  `apply-content-brushup`（`--output-dir`必須、`--dry-run`/`--apply`相互排他必須、`--pages`任意）
  の2サブコマンドを追加。固定書式のバナー（`CONTENT_BRUSHUP_PREPARE:`/
  `CONTENT_BRUSHUP_APPLY_DRY_RUN:`/`CONTENT_BRUSHUP_APPLY:`）を表示し、`--apply`成功時は
  次に`prepare-image-brushup`を実行するよう案内する

### テスト追加（Phase 10.13、新規68件）

- [x] `tests/test_content_brushup.py`（29件）: スナップショットのSHA-256記録・既存/新規/古さ
  判定、`prepare-content-brushup`が`lesson_pages.json`を変更しないこと、指示書への本文非埋め込み・
  絶対パス非埋め込み・固定ページ数非依存（3/137ページ）・スナップショットハッシュ埋め込み、
  候補JSON検証（`original`一致・`proposed`空拒否・`before`/`after`実在確認・未知`change_type`
  拒否・不正`risk_level`拒否・`risk: high`時の`requires_human_review`必須・`page_no`/
  `source_image`不一致拒否）、集約JSON検証（スナップショットハッシュ不一致・重複・`source`不一致・
  `risk_counts`不整合の拒否）、差分レンダリングの安全なエスケープ、review.html/review_summary.md
  生成
- [x] `tests/test_content_brushup_apply.py`（20件）: `--pages`解析、dry-runの正常系（変更あり/
  なしページ判定）、`--pages`絞り込み、`risk: high`・`requires_human_review: true`による
  全体停止方式の拒否、`failed_pages`拒否、`--pages`存在しないページ拒否、apply実行結果
  （バックアップ作成・派生field再計算・metadata/source情報保持・スナップショット不変）、
  **冪等性（2回目のdry-run/applyが正しく成功すること。上記の設計変更の直接的な回帰テスト）**、
  未passed時の例外・無変更確認、反映結果が既存ローダーで読み戻せること、レポート生成
- [x] `tests/test_cli_content_brushup.py`（12件）: サブコマンド認識、スナップショット生成・
  コピー可能な1文表示・絶対パス非表示、`--force`無しでの古いスナップショット拒否・`--force`での
  上書き、`--dry-run`/`--apply`の相互排他・両方省略時のエラー、dry-run非破壊性、apply実行時の
  バックアップ作成と`prepare-image-brushup`案内、2回目applyの冪等性、`risk: high`による拒否時の
  非ゼロ終了コードと`lesson_pages.json`不変、`--pages`絞り込み
- [x] `tests/test_image_brushup_design.py`（+6件）: `lesson_pages_sha256()`が`hashlib`と一致、
  `check_manifest_freshness()`の一致/不一致/欠落判定、指示書・`write_design_entry_points()`への
  実際のハッシュ埋め込み
- [x] `tests/test_cli_image_brushup.py`（+1件）: 本文更新後に古い`design_manifest.json`のまま
  `render-brushup`を実行すると拒否され、画像が生成されないことのend-to-end確認
- [x] 既存986件（Phase 10.12完了時点918件+今回68件（新規29+20+12件・既存ファイルへの追加分
  6+1件）＝986件。`pytest -q`で確認）すべて成功

### 実データ確認（`output/ocr_engine_eval/`本体、11ページ）

`/tmp`配下の専用コピーで一連の導線を検証したうえで、実際に`output/ocr_engine_eval/`
（既存の評価用ディレクトリ本体）へ適用した。

- `prepare-content-brushup`実行後、`content_brushup/VERIFIED_OCR_SNAPSHOT.json`・
  `AI_CONTENT_BRUSHUP.md`・`README.md`が生成され、標準出力にコピー可能な1文が表示されることを
  確認した
- 実データ11ページすべてについて、AI作業エージェント役として実際に本文を読み、次の判断を行った。
  - **Page1**: 「・後で改めて見返して、変えてもOK」の重複表現（「改めて」＋「後で」）を整理し
    「・後で見返して、内容を変えてもOK」へ変更（`remove_redundancy`・`low`）
  - **Page3**: 1行に2項目が詰め込まれていた箇条書き2箇所を、項目ごとの独立した行へ分割
    （`hierarchy`・`medium`。内容・順序は変更していない）
  - **Page6**: 「〜考えたり」「〜というように、逆から考えるのも◎」と続く長い一文を、2つの
    提案を独立させた2文に分割（`split_sentence`・`medium`）
  - **Page8**: 文頭の三点リーダー「…など、具体性があるとより良いです」を「など、具体的に
    書けるとより良いです」という完結した文に整理（`clarify`・`low`）
  - **Page2/4/5/7/9/10/11（7ページ）**: 既に明確な文章と判断し、変更なし
    （`proposed`は`original`と同一、`risk_level: low`、`changes: []`）
  - `risk_counts`は`low: 9 / medium: 2 / high: 0`
- **高リスク候補の拒否確認**: `/tmp`配下の専用コピーで1ページの`risk_level`を`high`・
  `requires_human_review`を`true`に書き換えて`--apply`を実行したところ、
  `CONTENT_BRUSHUP_APPLY: failed`・終了コード非ゼロとなり、`lesson_pages.json`はバイト単位で
  無変更（MD5ハッシュ一致）だった
- `--dry-run`実行結果: `CONTENT_BRUSHUP_APPLY_DRY_RUN: passed`、変更予定ページ`1, 3, 6, 8`、
  変更なしページ`2, 4, 5, 7, 9, 10, 11`、反映不可ページなし
- `--apply`実行結果: 11ページ全て反映（4ページ変更・7ページ変更なし）、
  `editable/backups/`に1件バックアップ作成
- `VERIFIED_OCR_SNAPSHOT.json`が`--apply`前後で完全に不変であることを確認した
- `lesson_pages.json`のPage1の`image_text`/`canva_prompt`に「内容を変えても」が反映される等、
  派生fieldが新しい本文と正しく整合していることを確認した
- **冪等性**: 直後に再度`--dry-run`を実行すると全ページ「変更なし」となり、全体判定も
  `passed`（前述の設計変更により、スナップショットハッシュとの単純比較では失敗していたはずの
  ケースが正しく成功することを実データでも確認）
- **古いデザインの拒否確認**: 本文更新後、Phase 10.12時点の`design_manifest.json`
  （`source_lesson_pages_sha256`未記録）のまま`render-brushup`を実行するとエラーで拒否され、
  `prepare-image-brushup`の再実行を促すメッセージが表示されることを確認した
- `prepare-image-brushup`→（本文の行数変化に合わせてPage3・Page6のデザインJSONの行範囲を
  再計算）→`render-brushup`を実行し、11ページ全て成功。Page3の分割済み箇条書き・Page6の
  2文構成が、いずれも生成画像へ正しく反映されていることを目視で確認した
- 最終画像がブラッシュアップ済み本文（OCR確定原文ではない）を使用していることを、生成画像の
  文言とスナップショットの文言を比較して確認した

### 今回実装しなかったもの・制限事項

- `preserved_facts`（保持すべき重要情報の申告）が実際に改善後の本文へ含まれているかを機械的に
  検証する仕組みは無い（人間がreview.htmlで確認する前提）
- `changes`に記録されなかった箇所の変更（AIエージェントの記録漏れ）を検出する仕組みは無い
- 本文の質的な良し悪し（読みやすくなったかどうか）を自動評価する仕組みは無く、`risk_level`は
  AIエージェントの自己申告に依存する
- ページ構成（統合・分割・順序変更）のブラッシュアップは意図的にスコープ外（既存`restructure`
  モードまたは別工程の役割）
- 実データ確認は11ページだったが、指示書生成・検証ロジック自体は固定ページ数に依存しない設計・
  テスト（3ページ・137ページでの検証）で確認している

## Phase 10.14: 統一スライドマスターとCodex向け最終画像生成パッケージ

### 目的

```text
OCR確定原文 → 本文ブラッシュアップ → 構成・デザイン設計
→ Codexによる最終ビジュアル生成 → 確定済み日本語本文の決定論的合成 → 完成画像
```

Phase 10.12のプレビューはページごとに白いカードの寸法・位置が変わり、デッキ全体としての
統一感が無かった。本Phaseは、全ページ完全に共通のスライドマスター（`MASTER_LAYOUT.json`）を
定義し、Codex（次工程・Phase 10.15）が最終ビジュアルを生成するための自己完結パッケージを
作成する。**本Phase自体は完成画像（`rendered_final/`）を生成しない。**

詳細は[`19_final_image_package_workflow.md`](19_final_image_package_workflow.md)を参照。

### 実装内容

- [x] `src/final_image_package.py`（新規）: パス解決（`FinalImagePackagePaths`）、キャンバス
  正規化（`analyze_canvas_size`。元画像のアスペクト比を集計し16:9/4:3/1:1/3:4/9:16の標準比率へ
  正規化）、`MASTER_LAYOUT.json`組み立て（`build_master_layout`。1600x900基準テンプレートを
  実キャンバスサイズへ比例スケーリング）、鮮度検証（`check_master_layout_freshness`。
  Phase 10.12/10.13の`lesson_pages_sha256`/`check_manifest_freshness`と同じ仕組み）、本文構造
  分析（`analyze_page_text`。タイトル重複行の除外、`※`注記行の分離、`◎`強調行検出、
  「例1）」「例2）」2段組み検出）、ページ別内部レイアウト仕様生成（`build_page_spec`。
  `line_range`による段落参照のみで本文を複製しない）、2段組み列幅の自動提案
  （`_suggest_column_ratio`。両列の最長行を実測）、検証（`validate_page_spec`/
  `validate_master_layout`/`validate_text_snapshot`。マスター座標の上書き禁止・本文複製禁止・
  `emphasis.match`実在確認・ハッシュ整合確認）、Codex向け自己完結指示書生成
  （`render_codex_final_image_generation_instructions`）、背景生成プロンプト生成
  （`render_master_background_prompt`/`render_page_background_prompt`。「文字を一切生成しない」
  「固定領域に装飾を置かない」を明記）、`asset_manifest.json`/`package_manifest.json`組み立て
- [x] `src/final_image_renderer.py`（新規）: `brushup_renderer.py`の低レベル部品
  （`_fit_text_block`/`_draw_paragraph_block`/`_measure_columns`等）を再利用したカード内部の
  測定・描画（`_measure_card_blocks`/`_draw_card_blocks`。固定サイズの本文カード内で
  余白→行間→フォントサイズ→2段組みの順に縮小し、それでも収まらない場合は本文を切り詰めず
  ページ生成を失敗させる）、縦方向配置（`top`/`center`/`distributed`）、固定領域描画
  （タイトル・注記・ページ番号）、カード背景（角丸・罫線・簡易影）描画、マスターガイド画像生成
  （`render_master_guides`。キャンバス・4固定領域・カード内側パディングを座標付きで可視化）、
  比較確認HTML生成（`render_comparison_html`。自己完結・外部リンクなし）、一括実行本体
  （`write_final_image_package`。Phase 10.12の`brushup_renderer.load_design_pages()`を
  そのまま再利用して`brushup_design`の鮮度・完全性を検証してから処理を進める）
- [x] `src/cli.py`: `prepare-final-image-package`サブコマンド追加（`--output-dir`必須、
  `--font-path`任意）。標準出力に固定書式の判定バナー・共通キャンバス/カード情報・
  Codex向けの固定1文を表示

### 設計判断

- **カード内部レイアウトの自動決定**: Phase 10.12はAI作業エージェント（Claude Code/Codex）が
  ページごとにデザインJSONを設計する2段階フローだったが、本Phaseは
  `prepare-final-image-package`自身が本文構造（`◎`・「例N）」等の記号パターン）を機械的に
  分析してカード内部レイアウトを決定する1コマンド完結フローにした。理由: 本Phaseの主眼は
  「全ページ共通の固定マスター」の実現であり、カード内部の構成判断自体は既存の
  `line_range`/`group`/`column_ratio`（Phase 10.12）の枠組みで十分表現でき、実データ11ページで
  実際に正しく機能することを確認した（Page3の「例1）/例2）」2段組み検出、Page2/6/7/9の
  `◎`強調検出）。AIエージェントによるページ別の意匠判断を残すかどうかはCodexへの判断依頼事項
  とした（本節末尾参照）
- **`brushup_design`を「使うが再解析しない」**: 仕様は`brushup_design/design_manifest.json`を
  入力として明記しているが、Phase 10.12のブロック構成をそのまま転用するのではなく、
  「Phase 10.12の画像デザインが現在の本文と整合していることの前提確認」としてのみ再利用した
  （`brushup_renderer.load_design_pages()`をそのまま呼び出し、エラーがあれば
  `prepare-image-brushup`/`render-brushup`の再実行を促して停止する）。カード内部レイアウトは
  本Phase独自のロジックで新規に決定する
- **強調は段落単位**: 1行内の一部の文字だけをハイライトする表現は実装せず、`◎`を含む段落
  全体を独立ブロックとして大きく太字・アクセント色にする方式にした。既存の`line_range`機構を
  そのまま使えるため実装・検証コストが低く、実データでも視覚的に十分な強調効果を確認した
- **キャンバス正規化は標準比率の多数決＋固定テンプレートの比例スケーリング**: 1600x900を
  基準テンプレートとし、実際のキャンバスサイズに応じて`regions`の座標を比例スケーリングする
  方式にした。実データは全ページ16:9で統一されているためそのまま1600x900になるが、
  4:3/1:1等の他デッキでも同じロジックが機械的に動作することをテストで確認済み

### テスト

- [x] `tests/test_final_image_package.py`（新規29件）: キャンバス正規化（16:9→1600x900、
  4:3→1600x1200、元画像なし時のフォールバック）、`MASTER_LAYOUT.json`組み立て（内容量に
  関わらず同一の`content_card`座標・非基準キャンバスでのスケーリング）、鮮度検証、本文構造分析
  （タイトル重複行除外・`◎`検出・「例1）/例2）」2段組み検出とその分割位置・単一マーカー時は
  2段組みにしないこと）、`split_body_and_notice`、ページ仕様生成（強調ブロック分離・2段組み
  ブロック生成・`emphasis.match`が実在する部分文字列であること）、検証関数（正常ケース・
  `page_no`不一致・ハッシュ不一致・`emphasis.match`不在・マスター座標上書き試行・本文複製
  試行の拒否）、`asset_manifest`/`package_manifest`組み立て
- [x] `tests/test_final_image_renderer.py`（新規12件）: 単一ページのプレビュー生成成功、
  極端に長い本文でのオーバーフロー時の切り詰めなし失敗、内容量（少/多）に関わらずキャンバス・
  カードサイズが同一であることの確認、`write_final_image_package`の一括実行（全ファイル生成・
  `rendered_final/`を作らないこと・元画像/`lesson_pages.json`を変更しないこと・全ページで
  `content_card`座標が同一であること・任意ページ数対応・`brushup_design`欠落時/古い
  `lesson_pages`ハッシュ時の拒否）、マスターガイド画像のキャンバスサイズ一致、比較HTMLの
  自己完結性（外部URL不使用）
- [x] `tests/test_cli_final_image_package.py`（新規4件）: パッケージ一式の生成・固定文言の
  標準出力・`--output-dir`必須・`brushup_design`未整備時のクリーンな失敗・共通キャンバス/カード
  情報の表示
- [x] 既存1031件（Phase 10.13完了時点986件+今回45件）すべて成功（`pytest -q`で確認）

### 実データ確認（`output/ocr_engine_eval/`本体、11ページ）

`/tmp`配下の専用コピーで検証したうえで、実際に`output/ocr_engine_eval/`へ適用した。

- 元画像は全11ページとも1706x960（16:9）であることを確認し、`prepare-final-image-package`が
  キャンバスを`1600x900`に正規化することを確認した
- 全11ページの`MASTER_LAYOUT.json`の`content_card`（x=56, y=200, width=1488, height=590）・
  `notice_region`・`page_number_region`が完全に同一であることを、生成された全ページ別仕様JSONと
  突き合わせて確認した
- **Page3**（「例1）キャラクターT」「例2）キャラクターB」を含む）が自動的に`two_column`と
  判定され、`split_at`・実測に基づく`column_ratio`（0.6）で、Phase 10.12の実データレビューで
  人間が手動調整したのと同様の破綻のない2段組みが生成されることを目視で確認した
- **Page6**（短めの内容、9段落）が`distributed`配置となり、カード外形は他ページと同一のまま
  内部で自然に余白が分散配置されることを目視で確認した。**Page1**（6段落）は`center`配置で
  カード内に不自然に上詰めされないことを確認した
- Page2/6/7/9の`◎`を含む行（「参考にするのも◎」「考えるのも◎です」「差別化になります◎」）が、
  独立した太字・アクセント色ブロックとして強調表示されることを確認した
- 全11ページが成功（オーバーフロー・失敗なし）、`rendered_final/`が生成されていないこと、
  既存の`rendered_brushup/`・`rendered/`・`editable/lesson_pages.json`・元画像が一切変更
  されていないことを確認した
- テキストスナップショット（`text/page_003.json`・`text/page_006.json`）が、Phase 10.13で
  ブラッシュアップ済みの本文（Page3の箇条書き分割・Page6の2文分割）を使用していることを
  確認した（OCR確定原文の生の値ではない）
- 標準出力に、共通キャンバス・共通本文カード座標・Codex向けの固定1文
  （`output/ocr_engine_eval/final_image_package/CODEX_FINAL_IMAGE_GENERATION.mdを読み、
  記載された手順を最後まで実行してください。`）が表示されることを確認した

### 今回実装しなかったもの・制限事項

- カード内部レイアウト（1段組み/2段組み・強調箇所）の判定は記号パターンに基づく機械的な
  ルールベースであり、Phase 10.12のようなAI作業エージェントによるページ別の意匠判断は
  行っていない
- 強調は段落単位の一括スタイル変更であり、1行内の一部文字だけのハイライトは未対応
- Codexによる実際の背景生成・完成画像の合成（Phase 10.15）は未実装。本Phaseは入力パッケージと
  プレビューの生成までがスコープ
- `card`の影表現は単純な単色オフセット矩形によるプレビュー用の簡易実装であり、最終品質の
  影表現ではない（`preview/`はレイアウト確認用であることを明記済み）

### Codexに判断してほしい点

1. カード内部レイアウト・強調箇所の決定を、本Phaseのような機械的ルールベースのままとするか、
   Phase 10.12と同様にAI作業エージェントによるページ別の意匠判断を追加する工程を挟むか
2. 2段組みの列幅比率（`column_ratio`）の実測ベース自動提案の精度で十分か、Phase 10.12のように
   人間が実データを見て個別調整する工程を残すべきか
3. Phase 10.15（Codexによる最終ビジュアル生成）の実施順序・粒度（背景をデッキ共通1枚にするか
   ページごとに変えるか等）

## Phase 10.15: Codex生成背景 + 確定済み本文の決定論的合成による完成教材画像

### 目的

```text
OCR確定原文 → 本文ブラッシュアップ → 構成・デザイン設計
→ Codexによる最終ビジュアル生成 → 確定済み日本語本文の決定論的合成 → 完成画像
```

Codexが生成した文字なし共通背景（`rendered_final/background_master.png`）と、Phase 10.14が
確定した固定スライドマスター（`MASTER_LAYOUT.json`）・ページ別内部レイアウト仕様
（`final_image_package/pages/page_NNN.json`）・確定済み本文スナップショット
（`final_image_package/text/page_NNN.json`）から、完成画像（`rendered_final/page_NNN.png`）を
決定論的に合成する。詳細は[`20_final_image_render_workflow.md`](20_final_image_render_workflow.md)を参照。

### 実装内容

- [x] `src/final_slide_compositor.py`（新規）: パス解決（`resolve_paths`）、背景画像検証
  （`validate_background_image`。存在・`MASTER_LAYOUT.json`の`canvas`とのサイズ一致・破損検出・
  透明度検出）、入力一式の読み込み・検証（`load_and_validate`。Phase 10.14の
  `validate_master_layout`/`check_master_layout_freshness`/`validate_page_spec`/
  `validate_text_snapshot`を再利用しつつ、ページ欠落・重複・余剰ファイル検出
  （`_validate_package_completeness`）、`content_layout.blocks[].line_range`が本文スナップショット
  の段落数に収まっていることの確認（`_validate_line_ranges_against_snapshot`）、ページ仕様と
  本文スナップショットの注記有無一致確認（`_validate_notice_consistency`）、日本語フォント解決を
  追加）、本文スナップショット専用の軽量ページオブジェクト（`_SnapshotPage`）による
  Phase 10.14の測定・描画部品（`final_image_renderer._measure_card_blocks`等）の再利用、
  1ページ合成（`composite_page`。共通背景の複製へ固定領域を描画する。カード内部描画は本Phase
  独自の`_draw_card_blocks`で、強調ブロックへ左アクセントバーを追加）、一括実行本体
  （`write_final_images`）、レポート・比較HTML生成
  （`render_final_render_report_json`/`render_final_render_report_markdown`/
  `render_final_comparison_html`）
- [x] `src/cli.py`: `render-final-images`サブコマンド追加（`--output-dir`必須、`--background`/
  `--font-path`任意）。標準出力に固定書式の判定バナー・背景/完成画像/比較画面/レポートの
  パスを表示

### 設計判断

- **文字の取得元をtext snapshotに限定**: 画像へ描画する文字列は`text/page_NNN.json`の
  `title`/`body`/`notice`フィールドのみから取得し（軽量な`_SnapshotPage`をPhase 10.14の描画
  部品へ渡すことで実現）、`lesson_pages.json`（`LessonPage`）は入力検証（鮮度確認）にのみ使う。
  これにより「本文はtext/page_NNN.jsonから取得する」という要件を、Phase 10.14の描画ロジックを
  複製せずに満たした
- **`notice`フィールドが空文字列になる既知の癖への対応**: 実データ検証で、Phase 10.14の
  `final_image_package.split_body_and_notice()`が生の行（`"speaker: text"`形式）の先頭文字だけで
  注記を判定するため、話者が空文字列の行（`": ※無断転載禁止（おとスタ）"`のように保存される）を
  検出できず、`text/page_NNN.json`の`notice`フィールドが実データ全11ページで空文字列になっている
  ことが判明した。`prepare-final-image-package`（Phase 10.14・既存機能）自体は変更せず、本Phaseの
  レンダラー側で`body`を解析し直して注記を検出する`_derive_notice_text()`を実装することで対応した
  （詳細は[`20_final_image_render_workflow.md`](20_final_image_render_workflow.md)「5節」、
  本節末尾のCodexへの判断依頼事項も参照）
- **強調は左アクセントバーを追加するのみ**: Phase 10.14が既に太字・アクセント色で表現している
  強調ブロック（`style.color`がテーマの`accent`と一致するブロック）に対し、テキストの折り返し幅・
  開始位置を変えずに左アクセントバーだけを追加した。ブロックの測定結果（`fit`）を再利用したまま
  装飾だけを足せるため、Phase 10.14の折り返し計算とずれるリスクが無い
- **背景はデッキ共通1枚のみ対応**: Codexが生成したページ別背景差分（`prompts/page_NNN.md`が
  想定する運用）は本Phaseでは扱わず、`--background`で1枚の背景を明示的に差し替えられる機能のみ
  実装した。理由: 実データでは共通背景1枚（`background_master.png`）のみが生成されており、
  ページ別背景の運用を今回のスコープに含めると検証項目が大きく増えるため、まず単純な構成で
  実データを完成させることを優先した

### テスト

- [x] `tests/test_final_slide_compositor.py`（新規23件）: 正常系一括実行（全ページ生成・冪等な
  再実行・保護対象ファイル無改変・全ページ同一カード外形・2段組み判定・丸数字/波ダッシュ描画）、
  拒否系（背景不在・背景サイズ不一致・背景透明度・master不在・package manifest不在・stale
  lesson_pages・ページ仕様欠落・余剰ページ仕様・text snapshot不一致・フォント未検出）、
  オーバーフロー時の切り詰めなし失敗、`_derive_notice_text`の3パターン（明示的notice優先・
  空話者行からの復元・注記無し）、レポートJSON/比較HTMLの内容確認
- [x] `tests/test_cli_render_final_images.py`（新規6件）: `--output-dir`必須、パッケージ一式の
  生成・固定文言の標準出力、`--background`上書き、`prepare-final-image-package`未実行時/背景
  未整備時のクリーンな失敗、既存`rendered_brushup_preview/`への非影響
- [x] 既存1060件（Phase 10.14完了時点1031件+今回29件）すべて成功（`pytest -q`で確認。無関係な
  `tests/test_verification_evidence.py::test_generate_run_id_is_unique_across_calls`が実行ID末尾
  4桁のランダム衝突で稀に失敗することがあるが（20回抽選時の理論衝突率約2%）、本Phaseの変更とは
  無関係で単体では確実に成功することを確認済み。既存の既知の不安定挙動であり本Phaseで修正しない）

### 実データ確認（`output/ocr_engine_eval/`本体、11ページ）

- Codexが生成済みの`rendered_final/background_master.png`（1600x900・文字なし）を使い、
  `render-final-images --output-dir output/ocr_engine_eval`を実行し、11ページ全ての完成画像
  （`rendered_final/page_001.png`〜`page_011.png`）が生成されたことを確認した
- 全11ページを実際に目視確認した
  - **Page3**: 「例1）キャラクターT」「例2）キャラクターB」の2段組みが崩れず、左右列の開始位置が
    揃っていることを確認した
  - **Page6**: 白いカードが他ページと同一の幅・高さで、9段落の内容が`distributed`配置で
    上部へ偏りすぎず視覚的に均衡していること、「逆に「こうはなりたくない」〜」の強調行が
    左アクセントバー＋太字・アクセント色で強調されていることを確認した
  - **Page1**: 本文量が少ない（6段落・`center`配置）ページでもカード外形が他ページと同一である
    ことを確認した
  - **Page11**: 「⑩」が正しく描画されることを確認した
  - 全ページで、共通背景の装飾（外周のテクスチャ・色ムラ）が本文カード内の文字と競合せず、
    注記・ページ番号が全ページ同一位置で読める濃さで描画されていることを確認した
- 全11ページで`text_match: true`・`overflow: false`・`truncated: false`（`final_render_report.json`）
  であることを確認した
- 背景原本（`background_master.png`）・元画像（`assets/`）・`editable/lesson_pages.json`・
  既存の`rendered/`・`rendered_brushup/`・`rendered_brushup_preview/`・Phase 10.14の
  `final_image_package/`既存ファイル（`MASTER_LAYOUT.json`・`pages/`・`text/`）が一切変更されて
  いないことを、実行前後のバイト列比較で確認した
- `render-final-images`を2回連続実行し、2回とも11ページ全て成功することを確認した（冪等性）
- `final_image_package/final_comparison.html`に外部URL（`http://`/`https://`）が含まれないこと、
  元画像・Phase 10.14プレビュー・Phase 10.15完成画像の3枚がページごとに並ぶことを確認した

### 今回実装しなかったもの・制限事項

- カード内部レイアウト・強調箇所の判定はPhase 10.14が確定したものをそのまま使い、本Phase独自の
  再判定は行っていない
- 強調表示は左アクセントバー＋太字・アクセント色の固定的な表現であり、1行内の一部の文字だけの
  ハイライトは未対応
- ページ別背景差分（`prompts/page_NNN.md`が想定する運用）には未対応。共通背景1枚のみ
- `text/page_NNN.json`の`notice`フィールドが空文字列になる既知の癖（`split_body_and_notice()`の
  判定ロジック）自体は本Phaseでは修正していない（本Phaseのレンダラー側で吸収するに留めた）

### Codexに判断してほしい点（本節はPhase 10.15追加修正で更新。下記参照）

1. ~~`final_image_package.split_body_and_notice()`が空話者行の注記を検出できない問題~~ →
   Phase 10.15追加修正で正式に修正済み（下記「Phase 10.15 追加修正」参照）
2. 強調表示（左アクセントバー＋太字・アクセント色）の見た目で十分か、Phase 10.12のような人間の
   目視調整・追加の装飾（淡い背景等）を加える工程を挟むべきか
3. ページ別背景差分（`prompts/page_NNN.md`）を使う運用を今後サポートするか、共通背景1枚のみの
   運用で確定するか

## Phase 10.15 追加修正: 描画不具合の調査・視覚描画検証の分離・notice正式修正・sparse page改善

### 背景

Phase 10.15完了報告後、「Page3・Page11でタイトルが欠落し黒い矩形が発生している」「Page1・Page11の
本文がカード左側へ偏っている」という指摘を受けた。**タイトル欠落・黒い矩形については、指摘された
`output/ocr_engine_eval/rendered_final/page_003.png`・`page_011.png`を実際にピクセルレベルで
実測したところ再現しなかった**（下記「調査結果」参照）。一方、本文カード内の水平/垂直利用率が
低いページが存在するという指摘・`text_match`が文字列比較にすぎず実際の描画結果を検証していない
という指摘は妥当であったため、これらは実際に修正した。

### 調査結果（黒い矩形・タイトル欠落の再現確認）

- `output/ocr_engine_eval/rendered_final/page_003.png`・`page_011.png`（および他9ページ）の
  `title_region`/`content_card`/`notice_region`/`page_number_region`の4領域について、RGB各値が
  すべて40未満の「暗色ピクセル」の比率を実測したところ、**全11ページ・全4領域で0.0（0件）**
  だった（黒い矩形は存在しない）
- 同じ4領域について、`theme.primary_text`（タイトル色）に近い色のピクセル数を実測したところ、
  Page3で8,416px、Page11で8,416px、Page1で4,598px検出され、**タイトル文字は実際に描画されている**
  ことを確認した
- 目視でも、Read画像ツールで11ページ全てを確認し、タイトル欠落・黒矩形のいずれも確認できなかった
- 実装コード（`src/final_slide_compositor.py`・`src/final_image_renderer.py`）を確認したところ、
  RGBAレイヤーを作成して`paste()`する処理は一切存在せず（すべて`ImageDraw.Draw`による直接描画）、
  「透明レイヤーの暗黙の黒背景」「maskなしpaste」に起因する不具合が発生しうる構造になっていない
  ことも確認した
- 以上より、**「黒い矩形」「タイトル欠落」という具体的な症状は、当時生成されていたファイルには
  再現しなかった**。原因は不明（別環境での表示・別ファイルの参照・見え方の相違等の可能性がある）。
  ただし、この調査を機に「文字列としての一致(`text_match`)」と「実際に画像へ描画されたか」を
  分離すべきという指摘自体は妥当と判断し、以下の恒久対策を実装した

### 実装内容（視覚描画検証の分離）

- [x] `source_text_match`へ改称: 旧`text_match`は「描画処理へ渡した文字列がtext snapshotと
  一致するか」という文字列比較の意味しか持たないことを名前で明確にした
- [x] 合成後の完成画像を実測する`*_visually_rendered`一式を新規追加（`compute_visual_report`）
  - `_verify_ink_region`: regionを含む周辺（マージン込み）を`ImageChops`ベースの色マスクで実測し、
    対象色に近いピクセルのbbox・件数・regionをはみ出しているか（overflow）を検出
  - `_dark_region_ratio`: 安全領域（title_region/content_card/notice_region/page_number_region）
    内の暗色（RGB全チャンネル40未満）ピクセル比率を検出。文字色（primary_text等）はいずれか1
    チャンネルが40以上のため、文字マスクを別途除外しなくても誤検出しない設計
  - `_verify_title_region`/`_verify_body_region`/`_verify_notice_region`/`_verify_page_number_region`:
    上記を使い、`title_bbox`/`title_region`/`title_font_size`/`title_line_count`/
    `title_mask_nonempty`/`title_bbox_within_region`/`title_pixels_present`/
    `title_dark_artifact_detected`/`title_visually_rendered`、`body_bbox`/`content_inner_region`/
    `horizontal_utilization`/`vertical_utilization`/`body_visually_rendered`等をレポートへ記録
  - 成功条件を`source_text_match == true` かつ `overflow == false` かつ `truncated == false`
    かつ `all_regions_visually_rendered == true`に変更（`write_final_images`）。いずれか1つでも
    falseならページ全体を失敗扱いにする
- [x] 補助OCR確認（`_ocr_title_check`）: 既存OCR機能（`src/ocr_engine.py`・
  `src/ocr_environment.check_tesseract_environment`）でタイトル領域を再認識し、一致率を記録する。
  bbox/pixel検証を主判定とし、OCR結果は警告のみ（tesseract未導入環境でも安全にスキップする）
- [x] `final_render_report.json`（schema_version 2）・`final_render_report.md`・
  `final_comparison.html`へ、上記の全項目（bbox・利用率・暗色矩形検査結果・補助OCR結果・notice
  source等）を記録するよう更新

### 実装内容（本文カード内部の視覚的均衡・sparse page改善）

- [x] `_measure_card_blocks_with_growth`: `single_column`かつカード内の垂直方向利用率が既定で
  低い（60%未満）ページに限り、文字サイズを1.12倍→1.25倍→1.4倍と段階的に拡大しながら再測定し、
  最後に収まったスケールを採用する（本文カードの外寸・2段組みページ・既に十分埋まっているページは
  一切変更しない）
- [x] レポートへ`horizontal_utilization`/`vertical_utilization`/`body_bbox`/`content_inner_region`
  を記録し、低利用率（35%未満）の場合は警告として記録する（`body_low_utilization_warning`）

### 実装内容（notice抽出の正式修正、Phase 10.14）

- [x] `src/final_image_package.py`の`split_body_and_notice()`を修正: 従来は生の行
  （`"speaker: text"`形式）の先頭文字だけで注記判定していたため、話者が空文字列の行
  （`": ※無断転載禁止（おとスタ）"`のように保存される）を検出できず、実データ全11ページで
  `text/page_NNN.json`の`notice`フィールドが常に空文字列になっていた。`lesson_pages.parse_body_lines`
  と同じ話者・本文の分解ロジックを最終行にも適用し、分解後の本文部分が`※`で始まるかどうかで
  判定するよう修正した（`analyze_page_text`が使う`_paragraph_lines_for_field`と一貫した判定になる）
- [x] `prepare-final-image-package`を実データに対して再実行し、`final_image_package/text/page_NNN.json`
  の`notice`フィールドが正しく埋まることを確認した（`MASTER_LAYOUT.json`・`pages/`も再生成されたが、
  内容は座標・レイアウト種別ともに変化なし。`source_lesson_pages_sha256`のみ再生成時刻に伴い
  タイムスタンプが更新される）
- [x] `src/final_slide_compositor.py`の`_derive_notice_text()`は防御的フォールバックとして維持
  （`notice`フィールドが正しく埋まっている場合はそちらを優先し、`body`解析へは通常フォールバックしない）

### テスト（Phase 10.15追加修正、新規33件）

- [x] `tests/test_final_image_package.py`: `split_body_and_notice`が空話者行の注記を正しく検出する
  回帰テストを追加（新規1件）
- [x] `tests/test_final_slide_compositor_visual.py`（新規）: タイトルbbox/mask/黒矩形検出（欠落検出・
  正常描画検出・黒矩形検出・primary_text色を誤検出しないこと・region外はみ出し検出）、
  `_draw_title`の座標・折り返し（負座標なし・1行/2行・最小フォント縮小・切り詰めなし失敗）、
  sparse page文字サイズ拡大（single_columnのみ拡大・two_columnは不変・カード外寸不変）、
  完成判定の分離（`source_text_match`のみでは成功にならないこと・title/body/notice/page_number
  いずれかの視覚描画検証失敗で失敗になること・全て真の場合のみ成功）、レポートへのbbox/利用率/
  暗色矩形/補助OCR記録確認、notice正式修正の回帰確認、実データ相当の回帰（Page3型2段組み・Page11型
  sparse single column・Page1/3/11形状の3ページデッキ全成功）、補助OCR確認の単体・統合テスト
  （計32件）
- [x] 既存テスト（`tests/test_final_slide_compositor.py`・`tests/test_cli_render_final_images.py`）
  の`text_match`参照を`source_text_match`・新規視覚検証フィールドへ更新
- [x] 既存1060件+今回33件（`test_final_image_package.py`+1件、`test_final_slide_compositor_visual.py`
  +32件）すべて成功（`pytest -q`で確認）

### 実データ再確認（`output/ocr_engine_eval/`本体、11ページ）

- `prepare-final-image-package`（notice修正反映）→`render-final-images`の順に再実行し、11ページ
  全ての完成画像を再生成した
- 全11ページを実際に目視で再確認した（Page1〜11すべて）。タイトル欠落・黒矩形は元々発生していな
  かったことと一致して、再生成後も発生していないことを確認した
- **Page1**: 水平利用率0.591・垂直利用率0.529（拡大前は目視で左上に偏っていた文字が、拡大後は
  カード内でバランス良く配置されていることを確認）
- **Page11**: 水平利用率0.683・垂直利用率0.640（「⑩」を保持したまま、文字サイズが拡大され
  読みやすくなっていることを確認）
- **Page3**: タイトル完全表示・黒矩形なし・2段組み左右開始位置一致・水平利用率0.902・垂直利用率
  0.864を確認
- **Page6**: タイトル完全表示・黒矩形なし・「逆に『こうはなりたくない』〜」の強調・水平利用率
  0.964・垂直利用率0.628を確認（`distributed`配置は利用率がgrowthの閾値(0.6)以上のため拡大されず、
  Phase 10.15完了時点のレイアウトを維持）
- 全11ページで`final_render_report.json`の`all_regions_visually_rendered: true`・
  `title_dark_artifact_detected: false`・`body_dark_artifact_detected: false`・
  補助OCR一致率1.0を確認した
- `final_comparison.html`にtitle bbox/region・水平/垂直利用率・暗色矩形検査結果・補助OCR結果・
  notice sourceが表示されること、外部URLが含まれないことを確認した

### 今回実装しなかったもの・制限事項（追加修正分）

- 黒い矩形・タイトル欠落は実測で再現しなかったため、根本原因は特定できていない（発生した具体的な
  環境・手順の追加情報が無いと、これ以上の原因特定は困難）
- dark artifact検出は「安全領域内の暗色ピクセル比率」という単純な閾値判定であり、指摘にあった
  「矩形状の連続領域の検出」のような連結成分解析は行っていない（numpyを新規依存に追加せず、
  既存のPillow標準機能のみで実装する方針を優先したため）
- sparse page文字サイズ拡大は`single_column`のみに適用し、`two_column`・既に利用率が高いページは
  対象外（Page6は`distributed`配置で利用率0.628のため今回は拡大対象外のまま）

### Codexに判断してほしい点（追加）

1. 「黒い矩形」「タイトル欠落」の指摘について、実測では再現しなかった旨を確認したうえで、
   発生した具体的な環境（OS・画像ビューア等）や、指摘の元になった画像ファイルそのものの追加情報
   があれば共有してほしい。追加情報が無ければ、本Phaseで追加した視覚描画検証（bbox/pixel/暗色矩形
   検出）を今後の恒久的な安全網として運用する方針でよいか
2. dark artifact検出を、より厳密な連結成分解析（numpy等の追加依存が必要になる可能性がある）へ
   発展させるべきか、現状の閾値ベースの簡易実装で十分か
3. sparse page文字サイズ拡大の対象を`two_column`・`distributed`配置にも広げるべきか

## Phase 10.15 追加修正2: final_comparison.htmlの画像参照パス修正

### 背景

Phase 10.15完成画像は正しく生成されていたが、`final_image_package/final_comparison.html`が
元画像・Phase 10.14プレビュー・Phase 10.15完成画像のいずれも表示できないという指摘を受けた。

### 根本原因

`render_final_comparison_html()`が、Phase 10.14の`final_image_renderer.render_comparison_html()`
（`final_image_package/preview/comparison.html`に保存される。`preview/`からの相対パスのため
`../../assets/...`が正しい）の相対パス文字列をそのまま踏襲してしまい、`final_comparison.html`
自体は`final_image_package/`直下（`preview/`のような子ディレクトリではない）に保存されるにも
かかわらず、`../../assets/...`という2階層上のパスを使っていた。正しくは`../assets/...`（1階層上）
であり、`../../`は`output/`（`ocr_engine_eval`のさらに1つ上）を指してしまっていた。

実データでは偶然`output/assets/`という同名・同内容のディレクトリが別件で存在していたため、元画像
だけは誤ったパスでも「たまたま」表示されてしまっていたが、`rendered_final/`側には対応する
`output/rendered_final/`が存在しなかったため、完成画像は確実に表示できなかった。

### 修正内容

- [x] `relative_asset_path(html_path, target_path, *, allowed_root)`（新規）: HTMLの実際の
  保存先から画像の実際の保存先までの相対パスを`os.path.relpath()`で機械的に算出する共通関数。
  固定文字列の`../`/`../../`を手作業で選ぶ実装をやめた。POSIX区切りへ変換、`allowed_root`外の
  参照を拒否、存在しないファイル・ディレクトリを拒否する
- [x] `render_final_comparison_html()`に`html_path`引数を追加し、`relative_asset_path()`で
  元画像・Phase 10.14プレビュー・Phase 10.15完成画像の3種すべての相対パスを算出するよう修正
- [x] `_validate_comparison_assets_exist()`（新規）: HTML書き出し前に、各ページの必須参照
  （元画像・プレビューは常に必須、完成画像はそのページが成功した場合のみ必須）が実在するかを
  検証し、1件でも欠ければページ番号・区分・期待パス・理由を含むエラーでHTML生成そのものを拒否する
- [x] `validate_comparison_html_references(html_path, allowed_root)`（新規）: 書き出し済みの
  HTMLを`html.parser.HTMLParser`で実際に解析し、全`<img src>`について外部URL/絶対パス/`file://`
  でないこと・`allowed_root`内に解決されること・実在すること・Pillowで読み込めることを検証し、
  `image_reference_count`/`resolved_reference_count`/`missing_reference_count`/
  `broken_references`/`all_images_resolvable`を返す
- [x] `src/cli.py`: `render-final-images`の実行順序を変更し、`final_comparison.html`書き出し後に
  上記の検証を実行、結果を`final_render_report.json`（`comparison_html_validation`キー）・
  `final_render_report.md`・標準出力バナーへ記録する。検証に失敗した場合は非ゼロ終了する

### 監査（他の比較HTML生成機能）

同型の相対パス直書き問題が無いか、以下を実データで監査した（`validate_comparison_html_references`
を汎用的に転用して実施）。

| HTML | 画像参照数 | 解決成功数 | 結果 |
|---|---:|---:|---|
| `ocr_comparison/review.html` | 11 | 11 | 問題なし |
| `content_brushup/review.html` | 11 | 11 | 問題なし |
| `brushup_design/comparison.html` | 22 | 22 | 問題なし |
| `final_image_package/preview/comparison.html` | 22 | 22 | 問題なし（Phase 10.14。`preview/`から
  2階層上を正しく参照） |
| `final_image_package/final_comparison.html` | 33 | 33（修正後） | **修正前は元画像11件が偶然の
  同名ディレクトリで表示され、完成画像11件は表示不可だった** |

同型バグは`final_comparison.html`のみで確認された。他4件は既存のまま変更していない。

### テスト（新規17件、`tests/test_final_slide_compositor_paths.py`）

- [x] `relative_asset_path`: 同一ディレクトリ・1階層上・2階層上・子ディレクトリ・POSIX区切り・
  絶対パス不使用・`allowed_root`外拒否・不存在ファイル拒否・ディレクトリ参照拒否
- [x] `final_comparison.html`: 正しい相対パス（`../assets/...`等）を含み誤った`../../...`を
  含まないこと、ページ数×3件の画像参照、全参照解決可能・Pillow読込可能、プレビュー/元画像欠落時の
  拒否、外部URL・`file://`不使用
- [x] 任意のoutput-dir階層（`tmp_path/a/b/c/output/ocr_engine_eval`のような深いネスト）でも
  正しく動作することを確認（パス階層を固定で仮定しない）
- [x] Phase 10.14の`preview/comparison.html`が全参照解決可能であることの回帰確認
- [x] 既存の`tests/test_final_slide_compositor.py`の`render_final_comparison_html`呼び出しへ
  `html_path`引数を追加
- [x] 既存1092件+今回17件（`tests/test_final_slide_compositor_paths.py`）すべて成功

### 実データ確認

- `prepare-final-image-package` → `render-final-images`を再実行し、`background_master.png`が
  変更されていないことをMD5で確認した
- `final_comparison.html`の全`<img src>`が`../assets/page_NNN.jpeg`・
  `../rendered_brushup_preview/page_NNN.png`・`../rendered_final/page_NNN.png`（1階層上）に
  修正されたことを確認した
- 実データ11ページで、期待画像参照数33・実画像参照数33・解決成功数33・欠落数0
  （`final_render_report.json`の`comparison_html_validation`）を確認した
- 元画像11/11・Phase 10.14プレビュー11/11・Phase 10.15完成画像11/11がすべて表示されることを、
  簡易HTTPサーバ経由でブラウザに実際に読み込ませ、ネットワークログで全33件が200 OKであること・
  コンソールエラーが無いこと・ページテキスト抽出で全11ページの内容が正しく表示されていることを
  確認した

### 完了条件との対応

- [x] final_comparison.htmlの相対パスを修正
- [x] 文字列直書きではなくHTML位置から算出（`relative_asset_path`）
- [x] 元画像11/11表示・Phase 10.14画像11/11表示・Phase 10.15画像11/11表示
- [x] 全33参照を解決・欠落0・Pillow読込成功33/33
- [x] output外参照なし
- [x] 実ブラウザで比較可能（簡易HTTPサーバ経由。`file://`は本ブラウザツールで未対応のため使用不可
  だったが、HTTP経由での実ブラウザ確認は実施した）
- [x] 同型の他HTMLを監査（4件とも問題なし）
- [x] テスト成功
- [x] 実データで再生成・確認
- [x] 比較HTMLを実際に使用できる状態

### 残課題

- 実ブラウザ確認は`file://`ではなく簡易HTTPサーバ経由で実施した（本セッションのブラウザツールが
  `file://`ナビゲーションに対応していないため）。ユーザー環境で`open final_comparison.html`を
  直接実行した場合の動作は未確認だが、相対パス自体はブラウザのプロトコルに依存しないため、
  同様に動作すると考えられる

### Codexに判断してほしい点

1. 同様の相対パス算出ロジック（`relative_asset_path`）を、既存の4つの比較HTML生成機能
  （`ocr_comparison`/`content_brushup`/`brushup_design`/Phase 10.14 `preview/comparison.html`）
  へも将来的に統一するか、現状問題が無いため個別実装のままとするか
