# Claude Codeでの実装手順

## 0. 実行確認について（重要）

通常のファイル編集・テスト実行（`pytest`）・サンプル実行（`run_sample.sh`）・ドキュメント更新は、作業ごとに「実行してよいですか」と確認せず、指示された範囲を最後まで進めてください。事前確認が必要なのは、認証・課金・外部サービスへの反映など「ユーザー本人の操作が必要になる可能性がある」場合のみです。詳細なルールは`~/ai-development-rules/DEVELOPMENT_RULES.md`「2. 確認を減らす」を、Claude Code本体の権限モード（`acceptEdits`等）に関する注記は[`CLAUDE_RULES.md`](../CLAUDE_RULES.md)「Claude Codeの権限モードに関する注記」を参照してください。

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

## 7.5 検証結果をエビデンスとして残す

`pytest`・`run_sample.sh`をばらばらに実行して画面出力を貼るのではなく、正式な検証入口を実行してエビデンスを残す。

```bash
bash scripts/run_verification.sh --purpose "<今回の作業内容>"
```

結果は`logs/evidence/<run_id>/`（`manifest.json`/`summary.md`/コマンドログ/JUnit XML）へ保存される。過去の実行結果は上書きされない。Codex（設計担当）は、この保存済みエビデンス（`logs/evidence/latest.json`が指す最新結果）を直接確認し、対象コミット・作業ツリー状態が一致する限り同じ検証を再実行しない。詳細は[`PROJECT_RULES.md`](../PROJECT_RULES.md)「9. このプロジェクトの正式な検証入口とエビデンス保存先」・[`docs/04_output_spec.md`](04_output_spec.md)「検証エビデンス」を参照。

## 8. 完成時の指示

```text
現在の実装状態に合わせてREADME.mdとdocs配下を更新してください。
初めて見る人でも、clone後に実行できる状態にしてください。
```
