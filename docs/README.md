# docs/ 一覧

このプロジェクトのドキュメント一式です。**初めて見る人は、まず[`00_redesign_v2.md`](00_redesign_v2.md)で3モード(`proofread`/`restructure`/`generate`)の背景を把握したうえで、[`01_requirements.md`](01_requirements.md)→[`02_architecture.md`](02_architecture.md)の順に読むことを推奨します。**

| ファイル | 位置づけ | 補足 |
|---|---|---|
| [`00_redesign_v2.md`](00_redesign_v2.md) | v2再設計時点の一次資料（歴史的資料） | 3モード構想・restructure再設計の背景。Phase6以降の`role`/`--plan-output`/`review-report`等は反映されていないため、細部は`01`〜`04`を正とする |
| [`01_requirements.md`](01_requirements.md) | **現行要件** | 実装済みCLIコマンド、3モードの方針、`lesson_pages.json`正データ方針、`input/`/`output/`除外方針など |
| [`02_architecture.md`](02_architecture.md) | **現行アーキテクチャ** | 実在する`src/`モジュール構成、実在するデータモデル、処理フロー |
| [`03_data_format.md`](03_data_format.md) | データ形式（開発者向け） | `pages`形式JSONのスキーマ（`imported_pages.json`もこの形式。作成者は直接作らない） |
| [`04_output_spec.md`](04_output_spec.md) | **CLI・出力仕様** | 元資料自動取り込み（`import-source`/`build-all`）、OCR前提の事前チェック・`check-ocr`診断・`build-all`のOCR必須モード（`proofread`/`restructure`）がOCR不能時にエラー終了する仕様・`--allow-empty-ocr`（Phase 10.1）、実行ログ（`logs/`）の標準仕様・成功判定の方針（Phase 10.2）、完成output形式選択・editable中間ファイル・再生成（`--output-format`/`regenerate`。Phase 9）、正式output（`editable/`/`canva/`/`exports/`）と後方互換output（`compat/`）の整理（Phase 9.1〜9.2）、`lesson_pages.json`のスキーマ、各派生出力の生成元、restructureプラン・`review-report`のCLI仕様 |
| [`05_implementation_tasks.md`](05_implementation_tasks.md) | 実装タスク進捗 | Phase 1〜9の完了状況チェックリスト |
| [`06_claude_code_workflow.md`](06_claude_code_workflow.md) | Claude Code運用手順 | ZIP展開〜実装〜確認までの一般的な進め方 |
| [`07_api_integration_design.md`](07_api_integration_design.md) | 将来のローカルLLM活用・API連携設計メモ | OCR/ブラッシュアップ/Canva設計へのローカルLLM組み込み構想（外部API連携は必要になった場合の選択肢。未実装・設計のみ） |
| [`08_user_acceptance_test.md`](08_user_acceptance_test.md) | **実利用テスト手順（Phase 8〜9・作成者向けの主導線）** | 元資料（画像/PDF/PPTX）の置き方、`build-all`の実行手順・`--output-format`の選び方、`editable/lesson_pages.json`の再生成（`regenerate`）、確認順序、評価観点 |
| [`09_editable_regenerate_guide.md`](09_editable_regenerate_guide.md) | **editable編集・再生成ガイド（Phase 10）** | `output/editable/lesson_pages.json`の編集してよい項目・編集しない方がよい項目、`regenerate`の具体例、日本語フォント（`--font-path`）の指定方法・トラブルシューティング |
| [`11_llm_handoff_workflow.md`](11_llm_handoff_workflow.md) | **LLM手作業投入ワークフロー** | `llm-handoff`コマンドの使い方、ChatGPT/Claude等への貼り付け手順、生成されるMarkdownの内容、LLM出力を`editable/lesson_pages.json`へ反映する運用（自動取り込みは行わない） |
| [`12_llm_review_apply_workflow.md`](12_llm_review_apply_workflow.md) | **LLM回答の採用判断・反映ワークフロー** | `edit-plan-template`コマンドの使い方、LLM回答をそのまま反映せず採用判断シートに整理する理由、`lesson_pages.json`の編集対象、`regenerate`実行例、再生成後チェックリスト |
| [`13_ocr_quality_check_workflow.md`](13_ocr_quality_check_workflow.md) | **OCR品質チェック・補正候補データ生成ワークフロー** | `ocr-check`コマンドの使い方、なぜLLM投入前にOCR確認が必要か、`ocr_check_report.md`/`ocr_correction_candidates.json`の読み方、重要度の見方、よくあるOCR誤認識例、システムと人間の役割分担 |
| [`14_apply_ocr_corrections_workflow.md`](14_apply_ocr_corrections_workflow.md) | **承認済みOCR補正候補の反映ワークフロー** | `apply-ocr-corrections`コマンドの使い方、`status: approved`の候補だけを反映する仕組み、元ファイルを上書きしないこと、`ocr_apply_report.md`の読み方、反映されない主な理由 |
| [`15_llm_suggestion_candidates_workflow.md`](15_llm_suggestion_candidates_workflow.md) | **LLM改善案の構造化候補生成ワークフロー** | `apply-llm-suggestions`コマンドの使い方、LLM回答Markdownの想定形式・表記揺れ対応、`llm_suggestion_candidates.json`の読み方、statusの使い方、将来の`apply-approved-llm-suggestions`へのつながり |
| [`feedback_template.md`](feedback_template.md) | フィードバックシート（テンプレート） | 実利用テストの結果を記録するチェックリスト。コピーして使う |
| [`99_implementation_review_brief.md`](99_implementation_review_brief.md) | 時点レビュー・スナップショット | Phase 1〜4完了時点（2026-07-04）の記録。以降更新しない運用ルールは同ファイル冒頭を参照 |
| [`99_phase7_review_2026-07-05.md`](99_phase7_review_2026-07-05.md) | 時点レビュー・スナップショット | Phase 7（restructure品質改善・出力のMarkdown混入対策一式）完了時点（2026-07-05）の記録 |

## 迷ったときは

- **「今何ができるか」を知りたい** → `01_requirements.md`、または`README.md`の「必須機能・任意機能」節
- **「コードのどこに何があるか」を知りたい** → `02_architecture.md`
- **「入力JSON・出力JSONの形式」を知りたい** → `03_data_format.md`（入力）/ `04_output_spec.md`（`lesson_pages.json`・派生出力）
- **「このプロジェクトはどこまで終わっているか」を知りたい** → `05_implementation_tasks.md` と `python3 -m pytest -q` の実行結果
- **元資料（画像/PDF/PPTX）があり、実際の教材素材で試したい** → `08_user_acceptance_test.md`（`build-all`の手順）と`feedback_template.md`（結果の記録）
- **元資料が無く、要件定義だけから新規に教材を作りたい（新規構築）** → `README.md`「`lesson-pages`の3モード（v2.0）」の`generate`モード（`build-all`は元資料前提のため対象外）
- **output構成・editable中間ファイル・source情報の扱いという共通設計ルールを確認したい** → `04_output_spec.md`「プロジェクト標準output構成（Phase 9.2時点で確定・共通設計ルール）」（要約は`CLAUDE_RULES.md`「プロジェクト設計ルール」にもある）
- **`output/editable/lesson_pages.json`を編集して再生成したい・日本語フォントの文字化けを直したい** → `09_editable_regenerate_guide.md`
- **画像取り込み後にテキストが空になる・OCRがうまくいかない・`build-all --mode proofread`がエラー終了する** → `python3 -m src.cli check-ocr`または`bash scripts/check_ocr_env.sh`で診断（`04_output_spec.md`「OCR前提の事前チェック」、`08_user_acceptance_test.md`「OCRについての注意」参照）
- **なぜエラーになったか・実行内容を後から確認したい** → `logs/YYYYMMDD_HHMMSS_<command>.log`（`04_output_spec.md`「実行ログ（logs/）の標準仕様」、`08_user_acceptance_test.md`「実行ログと成功判定の考え方」参照）
- **教材の構成チェック・文章のブラッシュアップ案をChatGPT/Claude等にもらいたい** → `11_llm_handoff_workflow.md`（`llm-handoff`コマンド。LLM出力の自動取り込みは行わない）
- **LLMの改善案をどう`editable/lesson_pages.json`に反映すればよいか迷う** → `12_llm_review_apply_workflow.md`（`edit-plan-template`コマンドで採用判断シートを作ってから手編集する）
- **`llm-handoff`のLLM回答がOCR誤字の指摘ばかりになる** → `13_ocr_quality_check_workflow.md`（`ocr-check`コマンドでLLM投入前にOCR崩れ候補・修正候補を先に確認する）
- **OCR補正候補を承認したので`lesson_pages.json`に反映したい** → `14_apply_ocr_corrections_workflow.md`（`apply-ocr-corrections`コマンドで`status: approved`の候補だけを安全に反映する）
- **ChatGPT/Claude等の改善案をどう`lesson_pages.json`に反映すればよいか迷う** → `15_llm_suggestion_candidates_workflow.md`（`apply-llm-suggestions`コマンドでLLM回答を構造化候補に変換してから採用判断する）
- **過去のレビュー経緯を知りたい** → `99_implementation_review_brief.md`（ただし現行仕様の正ではない点に注意）

## `05_*` と `99_*` の運用ルール（重要）

- **`05_implementation_tasks.md`**: 実装進捗・Phase管理用。コード・CLI・出力仕様・テストに変更を加えたら、このファイルを更新するか「更新不要」と判断するかを必ず確認する。
- **`99_*`**: 時点レビュー・スナップショット用。作成時点の記録であり、現行仕様の正ではない。**既存の`99_*`ファイルは上書きしない**。新しいレビューを残す場合は`docs/99_review_2026-08.md`のように日付/バージョン付きの別ファイルとして追加する。
- **作業完了報告には、`05_implementation_tasks.md`を更新したか／更新不要と判断したか、`99_*`を新規追加したか／追加不要と判断したかを必ず含める。**

詳細は[`CLAUDE_RULES.md`](../CLAUDE_RULES.md)「ドキュメント整合性の運用ルール」を参照。
