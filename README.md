# AI教材ブラッシュアップシステム 実装プロジェクト一式

## 目的
既存教材の画像・テキストを読み取り、学習者に伝わりやすい教材へブラッシュアップする。あわせてCanva等で再現しやすい画像設計書・ページ別レイアウト指示を生成する。

## Claude Codeでの使い方
1. このフォルダを任意のGitリポジトリに配置する。
2. `CLAUDE.md` をClaude Codeに読ませる。
3. `docs/01_requirements.md` から順に確認させる。
4. `docs/05_implementation_tasks.md` のタスク順に実装させる。
5. 入力データは `input/`、生成物は `output/` に置く。

## 想定成果物
- 教材ブラッシュアップ設計書 Markdown
- ページ別改善指示書
- Canva画像生成用プロンプト
- 台詞・状況説明者・登場人物別の文字起こし
- 教材全体の構成改善案
- Claude Codeで拡張可能なCLI雛形

## 推奨実行環境
- Python 3.11以上
- uv または pip
- Git / GitHub
- Claude Code

## 初期実装方針
最初は完全自動化を狙わず、以下の順で作る。

1. 入力画像・テキストをページ単位で管理
2. 手入力またはAI出力済みテキストを構造化JSONへ変換
3. ブラッシュアップ指示書をMarkdown生成
4. Canva向け画像設計書をMarkdown生成
5. 最後にOCR/API連携を追加

## Claude Codeで実装する場合

最初に `CLAUDE_START_HERE.md` をClaude Codeへ読み込ませてください。

```text
CLAUDE_START_HERE.md を読んで、その指示に従ってください。
```

詳細手順は `docs/06_claude_code_workflow.md`、開発ルールは `CLAUDE_RULES.md` を参照してください。
