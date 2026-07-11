# プロジェクト固有ルール（正本）

このファイルは、AI教材ブラッシュアップシステム（本リポジトリ）固有のルールの正本です。

全開発共通ルール（役割分担・確認方針・即席シェルコマンド・正式な検証入口の一般原則・保存済みエビデンスの扱い・ローカル開発の合否基準・Git安全ルール）は`~/ai-development-rules/DEVELOPMENT_RULES.md`を正とします。**このファイルには、全開発共通ルールへ書くべき内容を重複記載しません。** エージェント固有の振る舞い（Codex固有の役割補足はプロジェクト直下`AGENTS.md`、Claude Code固有の実装手順は`CLAUDE_RULES.md`）も別ファイルを正とします。

`~/ai-development-rules/DEVELOPMENT_RULES.md`が存在しない環境（別マシン・別ユーザー等）でも、このファイルとリポジトリ内の他ルールファイルだけで安全に作業できることを前提にしています。共通ルールが無いことだけを理由に作業を止めないでください。

---

## 1. このプロジェクトの目的

既存教材の画像・テキストを読み取り、学習者に伝わりやすい教材へブラッシュアップする。あわせてCanva等で再現しやすい画像設計書・ページ別レイアウト指示を生成する。

完全自動化よりも、まずは人間が確認しやすい中間成果物を安定して出すことを優先する。目指す成果物は、教材本文のブラッシュアップ案・ページ構成の改善案・Canvaで再現しやすい画像/レイアウト設計書・最終的に人間が確認/修正しやすいMarkdown出力。

プロジェクト方針（外部API非依存・ローカルLLM移行前提）は[`README.md`](README.md)「プロジェクト方針：外部API非依存・ローカルLLM移行前提」・[`docs/07_api_integration_design.md`](docs/07_api_integration_design.md)を参照。

## 2. 作成者向けの主導線は`build-all`

**作成者向けの主導線は`build-all`コマンドです。** 元資料（画像/PDF/PPTX）の正式な置き場所は`input/source/`です。作成者がJSON・Markdown・TXTを手作業で作る必要はありません（`examples/sample_pages.json`のようなpages形式JSONを直接手作業で作らせる運用は不採用。開発・テスト用の内部形式として`examples/`に残すのは可）。

```bash
python3 -m src.cli build-all --input input/source --mode proofread --output-dir output --output-format image
```

元資料を差し替えて最初から作り直す場合は`--clean-output`を付ける（前回より少ないページ数に差し替えた場合、古い成果物が混在するのを防ぐ）。詳細は[`docs/08_user_acceptance_test.md`](docs/08_user_acceptance_test.md)・[`README.md`](README.md)「クイックスタート（作成者向け）」を参照。

## 3. `lesson-pages`の3モード

- `proofread`: 元資料の趣旨を維持して整形（最初はこちらを推奨）。
- `restructure`: 教材として再構築。対象読者・トーンを反映する`--requirements`を任意で指定できる。
- `generate`: 元資料が無く、要件定義（`requirements.json`）だけから新規に教材のたたき台を生成する（`build-all`は元資料前提のため対象外。`lesson-pages --mode generate`を使う）。

詳細な再構成ロジックは[`docs/00_redesign_v2.md`](docs/00_redesign_v2.md)（正式な設計書）・[`docs/01_requirements.md`](docs/01_requirements.md)を参照。

## 4. output構成

`build-all`が生成する`output/`配下は、以下の役割に分ける（詳細は[`docs/04_output_spec.md`](docs/04_output_spec.md)「プロジェクト標準output構成」を正とする）。

```text
output/
  editable/lesson_pages.json   # 正式な編集対象（再生成時にユーザーが編集するのはここのみ）
  rendered/page_NNN.png        # 正式な完成画像
  canva/canva_design.md        # 正式なCanva指示書（オプション出力）
  exports/material.{md,docx,pdf,pptx}  # 正式な完成output
  compat/                      # Phase 8以前の旧仕様との互換用output（--no-compat-outputで無効化可）
  imported_pages.json / assets/ / scenario/ / review_report.md  # 役割重複が無いためoutput_dir直下のまま
```

`output/editable/lesson_pages.json`を編集 → `regenerate` → `rendered/`/`exports/`を再生成、が編集の標準フロー（完成画像・PDF・DOCX・PPTXを直接編集しない）。`source_page_no`は内部メタデータとして保持し、通常は完成outputに表示しない（確認したい場合は`review-report`）。

## 5. OCR関連の前提

- 画像inputの取り込みにはOS側のtesseract本体・日本語言語データが必要（`brew install tesseract tesseract-lang`）。`python3 -m src.cli check-ocr`で事前診断できる。
- `build-all --mode proofread/restructure`は、画像inputでOCRが実質使えない場合（Tesseract未導入・日本語言語データ無し・全ページOCR結果が空）、警告のうえ空データで成功させず、エラー終了する（`--allow-empty-ocr`でスキップ可。テスト・開発用途向け）。
- OCR崩れの検出・修正候補生成は`ocr-check`、候補の一括承認は`approve-ocr-candidates`、反映は`apply-ocr-corrections`が担当する。自動承認・自動反映（画像から確定できない内容の推測）は行わない。詳細は[`docs/13_ocr_quality_check_workflow.md`](docs/13_ocr_quality_check_workflow.md)〜[`docs/15_llm_suggestion_candidates_workflow.md`](docs/15_llm_suggestion_candidates_workflow.md)参照。

## 6. input・output・logs・生成物のGit管理方針

| 対象 | Git |
|---|---|
| `input/` | 対象外 |
| `output/` | 対象外 |
| `logs/.gitkeep` | 対象 |
| `logs/*.log`（実行ログ本体） | 対象外 |
| `logs/evidence/.gitkeep` | 対象 |
| `logs/evidence/<run_id>/`・`logs/evidence/latest.json`（検証エビデンス本体） | 対象外 |

詳細は[`docs/04_output_spec.md`](docs/04_output_spec.md)「プロジェクト標準output構成」「実行ログ（logs/）の標準仕様」「検証エビデンス」、`.gitignore`を参照。

## 7. このプロジェクトの必読設計書

作業開始前に、最低限以下を確認する。

- [`docs/README.md`](docs/README.md)（docs配下の各文書の役割一覧。まずここで何を読むべきか確認する）
- [`docs/00_redesign_v2.md`](docs/00_redesign_v2.md)（現行の3モード・restructure再構成ロジックの正式な設計書。必ず読むこと）
- [`docs/01_requirements.md`](docs/01_requirements.md)〜[`docs/04_output_spec.md`](docs/04_output_spec.md)（要件・アーキテクチャ・データ形式・CLI/出力仕様）
- [`docs/05_implementation_tasks.md`](docs/05_implementation_tasks.md)（実装タスク進捗）

必要に応じて[`docs/07_api_integration_design.md`](docs/07_api_integration_design.md)（将来のローカルLLM活用・API連携設計）・[`docs/08_user_acceptance_test.md`](docs/08_user_acceptance_test.md)（作成者向け実利用テスト手順）・OCR関連の[`docs/13`](docs/13_ocr_quality_check_workflow.md)〜[`docs/15`](docs/15_llm_suggestion_candidates_workflow.md)・レビュー履歴（`docs/99_*`）も確認する。

## 8. 既存仕様を壊さないこと

- 既存の`build-all`導線・3モード・output構成・OCR候補承認/反映フローを壊さない。
- 仕様変更が必要な場合は、理由と影響範囲を説明して承認を得てから変更する。
- 大規模な作り替えが必要に見える場合は、まず最小変更で目的を満たせるか検討する。
- `docs/99_*`は時点スナップショット文書として扱い、既存ファイルを上書きしない。新しいレビュー結果を残す場合は日付/バージョン付きの新規ファイルとして追加する。

## 9. このプロジェクトの正式な検証入口とエビデンス保存先

正式な検証入口は次のコマンド（`pytest -q --junitxml=...` → `bash scripts/run_sample.sh`の順に実行し、片方が失敗してももう片方は続けて実行する）。

```bash
bash scripts/run_verification.sh --purpose "<今回の検証目的>"
```

結果は`logs/evidence/<run_id>/`（`manifest.json`/`summary.md`/コマンドログ/JUnit XML）へ保存される。過去の実行結果は上書きされない。最新の完了済み結果は次のファイルが指す。

```text
logs/evidence/latest.json
```

設計担当エージェント（Codex）は、まずこのファイルと対応する`manifest.json`/`summary.md`を確認し、対象コミット・作業ツリー状態・実行内容が一致する場合は同じ検証を再実行しない（合否基準は`~/ai-development-rules/DEVELOPMENT_RULES.md`「ローカル開発の合否基準」を参照。dirty状態だけを理由に不合格・再実行にしない）。詳細仕様は[`docs/04_output_spec.md`](docs/04_output_spec.md)「検証エビデンス」を参照。

## 10. このプロジェクト固有の禁止事項・制限事項

- ユーザー承認なしに技術スタックを大きく変更しない。不要に複雑な構成にしない。
- 外部API前提にしない（OpenAI API/Gamma API/Canva API等の外部LLM・API連携を前提にした実装をユーザー承認なしに追加しない）。
- 有料サービス前提にしない。ただし、ChatGPT・Claude Code・Canva・Gammaのような既存サブスク製品を、人が手動で使う運用（画面へのコピペ等）は禁止しない。
- 元教材の意図を無視して文章を大きく改変しない。Canvaで再現できないレイアウトを前提にしない。
- 「LLM」という言葉をChatGPT/Claude等の総称として曖昧に使わない。本プロジェクトの文脈でのLLM活用は、まずローカルLLMを指す（詳細は[`README.md`](README.md)「プロジェクト方針」・[`docs/07_api_integration_design.md`](docs/07_api_integration_design.md)参照）。
- APIキーや秘密情報をコードに直書きしない。出力形式を勝手に変えない。

## 11. ドキュメント整合性の運用ルール

- コード・CLI・出力仕様・テストに変更を加えた場合は、必ず`docs/05_implementation_tasks.md`のPhase/Task進捗を確認し、必要に応じて更新する。
- 仕様変更や新機能追加を行った場合は、README.mdおよび`docs/01_requirements.md`〜`docs/04_output_spec.md`の該当箇所に矛盾がないか確認する。
- 作業完了報告には、`docs/05_implementation_tasks.md`を更新したか・更新不要と判断したか、および`docs/99_*`を新規追加したか・追加不要と判断したかを必ず含める。
