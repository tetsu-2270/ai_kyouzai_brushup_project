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
- 辞書に無い未知の誤認識文字は、構造的に完全で信頼度も一定以上ある場合は補完対象にならない（元画像に無い文字を推測で追加しない方針を優先）
