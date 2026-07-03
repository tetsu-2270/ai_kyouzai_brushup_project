# Claude Code 起動直後に最初に読む指示

このファイルは、Claude Codeを起動した直後に最初に読み込ませるための指示書です。

## 最初にClaude Codeへ貼る指示

```text
このプロジェクト一式を読み込んでください。

最初に必ず以下を確認してください。

- README.md
- CLAUDE.md
- CLAUDE_RULES.md
- docs/01_requirements.md
- docs/02_architecture.md
- docs/03_data_format.md
- docs/04_output_spec.md
- docs/05_implementation_tasks.md
- prompts/ 配下
- examples/ 配下
- src/ 配下
- tests/ 配下

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

可能な範囲で、タスク完了ごとにGitコミットしてください。
コミットメッセージは日本語でお願いします。
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
