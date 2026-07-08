# Claude Code向け補足

作業開始前に必ず以下を確認してください。

- `CLAUDE_START_HERE.md`
- `CLAUDE_RULES.md`
- `docs/README.md`（docs配下の各文書の役割一覧。まずここで何を読むべきか確認する）
- `docs/00_redesign_v2.md`（現行の3モード[proofread/restructure/generate]・restructure再構成ロジックの正式な設計書。必ず読むこと）
- `docs/06_claude_code_workflow.md`

必要に応じて `docs/07_api_integration_design.md`（将来のローカルLLM活用・API連携設計。プロジェクト方針上、優先はローカルLLMで外部API連携は必要になった場合の選択肢）・`docs/08_user_acceptance_test.md`（Phase 8: 作成者向けの主導線。元資料[画像/PDF/PPTX]を置いて`build-all`を実行する実利用テスト手順）・`docs/99_implementation_review_brief.md`と`docs/99_phase7_review_2026-07-05.md`（レビュー履歴・既知の制約）も確認してください。

**作成者向けの主導線は`build-all`コマンドです。** `examples/sample_pages.json`のようなpages形式JSONを直接手作業で作らせる運用は不採用です（開発・テスト用の内部形式として`examples/`に残すのは可）。

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
