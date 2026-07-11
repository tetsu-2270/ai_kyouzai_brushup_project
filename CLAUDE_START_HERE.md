# Claude Code 起動直後に最初に読む指示

このファイルは、Claude Codeを起動した直後に最初に読み込ませるための指示書です。

**必読順（開発ルールの3階層）**: 1. `~/ai-development-rules/DEVELOPMENT_RULES.md`（全開発共通ルールの正本） → 2. `~/.claude/CLAUDE.md`（Claude Codeグローバル入口） → 3. `PROJECT_RULES.md`（このプロジェクト固有ルールの正本） → 4. `CLAUDE_RULES.md`（Claude Code固有の実装手順・完了報告方法） → 5. プロジェクトの設計書（下記「最初にClaude Codeへ貼る指示」参照）。`~/ai-development-rules/DEVELOPMENT_RULES.md`が存在しない環境では、`PROJECT_RULES.md`と`CLAUDE_RULES.md`だけで作業してください。

**実行確認について**: 通常のファイル編集・`pytest`実行・`run_sample.sh`実行・ドキュメント更新は、都度「実行してよいですか」と確認せず最後まで進めてください。認証・課金・外部反映などユーザー本人の操作が必要になる場合のみ事前に明示してください。詳細は`~/ai-development-rules/DEVELOPMENT_RULES.md`「2. 確認を減らす」を参照。

**検証・テスト結果の報告について**: 実装完了後は、個別に`pytest`や`run_sample.sh`を実行して画面出力をそのまま報告するのではなく、正式な検証入口`bash scripts/run_verification.sh --purpose "<今回の目的>"`を実行し、結果は`logs/evidence/<run_id>/`へ保存してください。完了報告では長い実行ログを貼らず、エビデンス保存先（`logs/evidence/latest.json`が指す`run_id`）と総合結果だけを短く報告してください。詳細は`PROJECT_RULES.md`「9. このプロジェクトの正式な検証入口とエビデンス保存先」・[`docs/04_output_spec.md`](docs/04_output_spec.md)「検証エビデンス」参照。

## 最初にClaude Codeへ貼る指示

```text
このプロジェクト一式を読み込んでください。

最初に必ず以下を確認してください。

- ~/ai-development-rules/DEVELOPMENT_RULES.md（存在する場合。全開発共通ルールの正本）
- ~/.claude/CLAUDE.md（存在する場合。Claude Codeグローバル入口）
- PROJECT_RULES.md（このプロジェクト固有ルールの正本）
- CLAUDE_RULES.md
- README.md
- CLAUDE.md
- docs/README.md（docs配下の各文書の役割一覧。まずここで何を読むべきか確認する）
- docs/00_redesign_v2.md（現行の3モード[proofread/restructure/generate]・restructure再構成ロジックの正式な設計書。必ず読むこと）
- docs/01_requirements.md
- docs/02_architecture.md
- docs/03_data_format.md
- docs/04_output_spec.md
- docs/05_implementation_tasks.md
- prompts/ 配下
- examples/ 配下
- src/ 配下
- tests/ 配下

必要に応じて以下も確認してください（任意機能や将来拡張・実利用テスト・レビュー履歴の背景を把握したい場合）。

- docs/07_api_integration_design.md（将来のローカルLLM活用・API連携の設計メモ。プロジェクト方針上、優先はローカルLLMで外部API連携は必要になった場合の選択肢。現時点では未実装）
- docs/08_user_acceptance_test.md（Phase 8: 作成者向けの主導線。元資料[画像/PDF/PPTX]を置いて`build-all`を実行する実利用テスト手順・評価観点）
- docs/99_implementation_review_brief.md（Phase 1〜4のレビュー提出用ブリーフ。既知の制約・変更履歴の記録）
- docs/99_phase7_review_2026-07-05.md（Phase 7完了時点のレビュー・スナップショット）

確認後、すぐに実装を始めず、以下を報告してください。

1. このシステムの目的理解
2. 現在の構成理解
3. 実装済み部分と未実装部分
4. 仕様上あいまいな点
5. 実装を進める順番の提案

勝手に仕様変更しないでください。
不明点がある場合は質問してください。
承認を得てから、docs/05_implementation_tasks.md の Task 1 から順番に進めてください。
```

## 実装開始時に貼る指示

```text
承認します。

CLAUDE_RULES.md の開発ルールに従って、docs/05_implementation_tasks.md の Task 1 から実装してください。

1タスク完了ごとに以下を報告してください。

- 実施した内容
- 変更・追加したファイル
- テスト結果
- 次に進めるタスク

Git commit / tag / push はあなた（Claude Code）自身では実行しないでください。
`CLAUDE_RULES.md`「Claude Code運用ルール」6節のとおり、Git保存が必要な場合は
ユーザー側手動コマンドとして別途提示してください。
```

## エラー時に貼る指示

```text
エラー内容を確認し、原因を特定してください。
そのうえで、最小限の修正で解決してください。
修正後は、再実行方法と確認結果を報告してください。
```

## README更新時に貼る指示

```text
現在の実装状態に合わせて README.md を更新してください。
初めてこのリポジトリを見る人が、clone後に迷わず実行できる内容にしてください。
```
