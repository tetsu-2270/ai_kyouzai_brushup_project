# Claude Code 実装指示書（初期版・アーカイブ）

これは、旧`CLAUDE.md`に含まれていたClaude Code向けの初回実装指示書（Phase 1・初期CLI実装時点のもの）です。指示内容は実行済みで、対応する進捗は[`docs/05_implementation_tasks.md`](../docs/05_implementation_tasks.md)に反映されています。今後の実装作業では参照不要ですが、経緯の記録として削除せず保管しています。

現在のClaude Code向けルールは、リポジトリ直下の[`CLAUDE.md`](../CLAUDE.md)（薄い入口）→ `~/ai-development-rules/DEVELOPMENT_RULES.md`（全開発共通ルール）・[`PROJECT_RULES.md`](../PROJECT_RULES.md)（プロジェクト固有ルール）・[`CLAUDE_RULES.md`](../CLAUDE_RULES.md)（Claude Code固有の実装手順）を正としてください。

---

# Claude Code 実装指示書

あなたはこのプロジェクトの実装担当です。
ユーザーは開発専任ではないため、説明よりも動く成果物を優先してください。

## 最重要方針
- 既存設計を壊さない。
- 不明点で止まらず、合理的な仮定で実装する。
- 変更したファイル、実行コマンド、次にやることを最後に短く示す。
- 1タスクずつコミットしやすい単位で作業する。
- ファイル編集・`pytest`・`run_sample.sh`・ドキュメント更新は都度確認せず最後まで進める。認証・課金・外部反映が必要な場合のみ事前に明示する（詳細は`CLAUDE_RULES.md`「実行確認の運用ルール」参照）。

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
