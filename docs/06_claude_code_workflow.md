# Claude Codeでの実装手順

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

最低限、以下を実行できる状態を目指す。

```bash
python -m src.cli --input examples/sample_pages.json --output output
```

または、READMEに記載された最新の実行方法に従う。

## 8. 完成時の指示

```text
現在の実装状態に合わせてREADME.mdとdocs配下を更新してください。
初めて見る人でも、clone後に実行できる状態にしてください。
```
