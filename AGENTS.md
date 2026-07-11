# Codex向け補足（プロジェクト薄入口）

このファイルは、Codexがこのプロジェクトで作業する際の薄い入口です。全開発共通ルールやプロジェクト固有ルールの全文はここに置かず、以下の正本を参照してください。

```text
全開発共通ルールは ~/ai-development-rules/DEVELOPMENT_RULES.md を正とする。
このプロジェクト固有ルールは PROJECT_RULES.md を正とする。
AGENTS.md にはCodex固有の入口と補足だけを記載する。
```

## 1. 読む順序

1. `~/ai-development-rules/DEVELOPMENT_RULES.md`（全開発共通ルールの正本。役割分担・確認方針・即席シェルコマンド・正式な検証入口・完了レポート[主確認手段]・エビデンス[補助確認手段]・ローカル開発の合否基準・Git安全ルール）
2. `~/.codex/AGENTS.md`（Codexグローバル入口。上記1を前提とする）
3. [`PROJECT_RULES.md`](PROJECT_RULES.md)（このプロジェクト固有ルールの正本）
4. 本ファイルの「2. Codex固有のプロジェクト補足」
5. 「3. 必要な必読文書」

`~/ai-development-rules/DEVELOPMENT_RULES.md`が存在しない環境では、`PROJECT_RULES.md`とリポジトリ内のルールファイルだけで安全に作業できます。共通ルールが無いことだけを理由に作業を止めないでください。

## 2. Codex固有のプロジェクト補足

- このプロジェクトでは、**ChatGPT（Codex）が設計し、Claude Codeが実装する**（役割分担そのものは`~/.codex/AGENTS.md`「Codexの役割」参照）。
- ユーザーが「指示文を出して」「実装指示を作って」などと依頼した場合、出力先はClaude Codeである。Codex向けの指示文を作らない。
- Claude Code向け実装指示文を作る際は、`~/.codex/AGENTS.md`「Claude Code向け実装指示文を作る際の注意」に従う（不要な権限確認を避ける実行方法・一時ファイル削除範囲の限定・正式な検証入口の直接実行・自己完結した完了レポートの出力）。
- 実装指示文には、`PROJECT_RULES.md`「9. このプロジェクトの正式な検証入口とエビデンス保存先」の具体的なコマンド（`bash scripts/run_verification.sh --purpose "..."`）と、完了報告は`CLAUDE_RULES.md`のテンプレートを`python3 -m src.completion_report`でHTML Artifact化して出力することを指定する（`PROJECT_RULES.md`「9. このプロジェクトの正式な検証入口とエビデンス保存先」参照）。固定コマンドを他プロジェクトへ使い回さない。

## 3. 必要な必読文書

`PROJECT_RULES.md`「7. このプロジェクトの必読設計書」を参照してください。特に`docs/README.md`（docs配下の役割一覧）と`docs/00_redesign_v2.md`（3モードの正式な設計書）は必ず読んでください。

## 4. このプロジェクトでのCodex確認入口

- Claude Codeの実装完了後は、まずユーザーから貼られたHTML Artifact（`output/reports/latest_claude_completion_report.html`相当）のコピーMarkdown内容を確認する。レポートが自己完結していれば、原則として`logs/evidence/`等を追加で読まない（詳細は`~/.codex/AGENTS.md`「Codex固有のレビュー方法」・`~/ai-development-rules/DEVELOPMENT_RULES.md`「6.4 Codex側の確認方針」「6.5 出力形式（HTML Artifact）」参照）。
- 追加確認が必要な場合の索引は`PROJECT_RULES.md`「9. このプロジェクトの正式な検証入口とエビデンス保存先」（`logs/evidence/latest.json`）を使う。Artifact本体の保存先は`PROJECT_RULES.md`「9.」の`output/reports/`を参照。

過去の初回起動時Codex向け指示書（Phase 1時点）は[`archive/AGENTS_initial_codex_instructions.md`](archive/AGENTS_initial_codex_instructions.md)に保管しています（実行済み・現行ルールでは参照不要）。
