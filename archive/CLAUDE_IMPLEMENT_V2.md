# Claude Code 実装指示 v2.0

`docs/00_redesign_v2.md` を読み込み、この設計書に従って実装してください。

重要事項：

- 設計変更は勝手に行わない
- 不明点があれば実装前に質問する
- 正データは `lesson_pages.json` とする
- `brushup.md` / `canva_design.md` / DOCX / PDF / scenario は派生出力とする
- `proofread` / `restructure` / `generate` の3モードを実装する
- Canva API連携とWordPress連携は任意機能のままにする
- 修正後は pytest を全件実行する

完了後、以下を報告してください。

1. 修正ファイル
2. 追加ファイル
3. 追加テスト
4. pytest結果
5. proofread / restructure / generate の実行例
6. 既存CLI互換性
7. 残課題
