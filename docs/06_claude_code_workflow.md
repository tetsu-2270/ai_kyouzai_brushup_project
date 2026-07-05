# Claude Codeでの実装手順

## 0. 実行確認について（重要）

通常のファイル編集・テスト実行（`pytest`）・サンプル実行（`run_sample.sh`）・ドキュメント更新は、作業ごとに「実行してよいですか」と確認せず、指示された範囲を最後まで進めてください。事前確認が必要なのは、認証・課金・外部サービスへの反映など「ユーザー本人の操作が必要になる可能性がある」場合のみです。詳細なルールは[`CLAUDE_RULES.md`](../CLAUDE_RULES.md)「実行確認の運用ルール（重要）」を参照してください。

### Claude Codeの権限モードに関する注記

- Claude Codeの通常モードでは、ツール実行時（特にBashコマンド）に確認ダイアログが出る場合がある。これはClaude Code本体の権限モード・安全機構によるものであり、上記「実行確認について」のルールとは別物である。
- 確認を減らしたい場合は、Claude Code側で`acceptEdits`モードを使う。
- `acceptEdits`でも、すべてのBashコマンド確認が消えるとは限らない。
- 危険な権限バイパスモード（`--dangerously-skip-permissions`等）は通常運用では推奨しない。
- Claude Code側の権限確認ダイアログが出た場合は、ユーザーが承認する必要がある。
- ただし、Claude Code自身は「実行してよいですか」といった作業ごとの確認質問をしない。権限確認が出そうな作業は、開始前にまとめて宣言し（例:「この作業ではpytest実行・run_sample.sh実行を行います。Bash実行時に確認ダイアログが出る可能性があります」）、以降は個別に確認せず進める。

## 1. ZIPを展開する

```bash
unzip ai_kyouzai_brushup_project.zip
cd ai_kyouzai_brushup_project
```

## 2. Claude Codeを起動する

```bash
claude
```

## 3. 最初に読むファイルを指定する

Claude Codeに以下を貼る。

```text
CLAUDE_START_HERE.md を読んで、その指示に従ってください。
```

## 4. 実装前レビューをさせる

Claude Codeがプロジェクトを読み込んだら、まず以下を確認する。

- 目的理解が正しいか
- 実装順序が妥当か
- 不足ファイルがないか
- 勝手な仕様変更がないか

## 5. 実装を開始する

問題なければ以下を貼る。

```text
承認します。Task 1から実装してください。
```

## 6. タスクごとの確認

各タスク完了時に以下を確認する。

- 変更内容
- 追加ファイル
- テスト結果
- 次タスク
- Gitコミット有無

## 7. 動作確認

最低限、以下を実行できる状態を目指す（`bash scripts/run_sample.sh`と同じ内容）。

```bash
python3 -m src.cli lesson-pages --mode proofread --input examples/sample_pages.json --output output/lesson_pages.json
python3 -m src.cli generate --input output/lesson_pages.json --output output/brushup.md
```

または、READMEに記載された最新の実行方法（`bash scripts/run_sample.sh`）に従う。

## 8. 完成時の指示

```text
現在の実装状態に合わせてREADME.mdとdocs配下を更新してください。
初めて見る人でも、clone後に実行できる状態にしてください。
```
