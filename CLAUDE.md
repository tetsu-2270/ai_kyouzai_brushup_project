# Claude Code向け補足（プロジェクト薄入口）

このファイルは、Claude Codeがこのプロジェクトで作業する際の薄い入口です。全開発共通ルールやプロジェクト固有ルールの全文はここに置かず、以下の正本を参照してください。

```text
全開発共通ルールは ~/ai-development-rules/DEVELOPMENT_RULES.md を正とする。
このプロジェクト固有ルールは PROJECT_RULES.md を正とする。
Claude Code固有の実装手順・完了報告方法は CLAUDE_RULES.md を正とする。
CLAUDE.md にはClaude Code固有の入口と必読案内だけを記載する。
```

## 1. 読む順序

1. `~/ai-development-rules/DEVELOPMENT_RULES.md`（全開発共通ルールの正本）
2. `~/.claude/CLAUDE.md`（Claude Codeグローバル入口。上記1を前提とする）
3. [`PROJECT_RULES.md`](PROJECT_RULES.md)（このプロジェクト固有ルールの正本）
4. [`CLAUDE_RULES.md`](CLAUDE_RULES.md)（Claude Code固有の実装手順・完了報告方法）
5. [`CLAUDE_START_HERE.md`](CLAUDE_START_HERE.md)（起動直後に貼る指示テンプレート。上記4件を含む必読順を明記）

`~/ai-development-rules/DEVELOPMENT_RULES.md`が存在しない環境では、`PROJECT_RULES.md`と`CLAUDE_RULES.md`だけで安全に作業できます。共通ルールが無いことだけを理由に作業を止めないでください。

## 2. 必要な必読文書

`PROJECT_RULES.md`「7. このプロジェクトの必読設計書」を参照してください。特に`docs/README.md`（docs配下の役割一覧）と`docs/00_redesign_v2.md`（3モードの正式な設計書）は必ず読んでください。

過去の初回実装指示書（Phase 1時点）は[`archive/CLAUDE_initial_implementation_instructions.md`](archive/CLAUDE_initial_implementation_instructions.md)に保管しています（実行済み・現行ルールでは参照不要）。
