# Claude Code向け補足

作業開始前に必ず以下を確認してください。

- `CLAUDE_START_HERE.md`
- `CLAUDE_RULES.md`
- `docs/06_claude_code_workflow.md`

---

# Claude Code 実装指示書

あなたはこのプロジェクトの実装担当です。
ユーザーは開発専任ではないため、説明よりも動く成果物を優先してください。

## 最重要方針
- 既存設計を壊さない。
- 不明点で止まらず、合理的な仮定で実装する。
- 変更したファイル、実行コマンド、次にやることを最後に短く示す。
- 1タスクずつコミットしやすい単位で作業する。

## 実装順序
1. `docs/01_requirements.md` を読み、要件を把握する。
2. `docs/02_architecture.md` を読み、構成に従う。
3. `src/` 配下のCLI雛形を完成させる。
4. `examples/sample_pages.json` を入力にしてMarkdown生成を動かす。
5. `tests/` を追加・実行する。

## 禁止事項
- 勝手に大規模フレームワークへ変更しない。
- ユーザーに何度も確認質問をしない。
- APIキーや秘密情報をコードに直書きしない。
- 出力形式を勝手に変えない。

## 完了条件
以下が動けば初期実装完了。

```bash
python -m src.cli generate --input examples/sample_pages.json --output output/brushup.md
python -m src.cli canva --input examples/sample_pages.json --output output/canva_design.md
```
