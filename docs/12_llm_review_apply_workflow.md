# 12 LLM回答の採用判断・反映ワークフロー（`edit-plan-template`）

> `llm-handoff`でChatGPT/Claude等から改善案を受け取った後、それをそのまま`editable/lesson_pages.json`へ反映するのではなく、いったん「採用判断シート（`edit_plan_template.md`）」に整理してから人間が手編集するための運用ガイドです。プロジェクト方針（README.md「プロジェクト方針：外部API非依存・ローカルLLM移行前提」・[`docs/07_api_integration_design.md`](07_api_integration_design.md)参照）のとおり、**この機能もLLMを呼び出さず、LLM出力の自動取り込みも行いません**。

## 1. このフローの目的

[`docs/11_llm_handoff_workflow.md`](11_llm_handoff_workflow.md)の`llm-handoff`で改善案を受け取った後、次に何をすればよいか分かりにくいという課題がありました。特に、次の3ステップが曖昧でした。

```text
4. 人間が頑張って判断する
5. editable/lesson_pages.json を手編集する
6. regenerate で再出力する
```

このドキュメントは、この3ステップを「採用判断シート」という具体的な成果物を介すことで、迷わず進められるようにするためのものです。

## 2. なぜLLM回答をそのまま反映しないのか

- LLM（ChatGPT/Claude等）の回答は、そのままコピーして`editable/lesson_pages.json`に貼り付けてよい形式とは限りません。
- 提案の一部だけ採用したい、あるいは元資料と照らし合わせて確認してから採用したい場合があります。
- 「採用する／採用しない／一部採用」を明示的に記録しておくことで、後から「なぜこの内容にしたか」を追跡できます。
- LLM出力の自動取り込み・自動マージは今回は実装していません（プロジェクト方針上、当面は外部API連携もローカルLLM本体も導入しないため）。あくまで人間の判断を補助するテンプレートです。

## 3. `llm-handoff`から`edit-plan-template`への流れ

```text
build-all または lesson-pages で editable/lesson_pages.json を作る
↓
llm-handoff で llm_handoff.md を作る
↓
llm_handoff.md をChatGPT/Claude等の製品画面へ貼る
↓
返ってきた改善案を読む
↓
edit-plan-template で edit_plan_template.md を作る
↓
改善案を読みながら edit_plan_template.md に採用判断を整理する
↓
edit_plan_template.md を見ながら editable/lesson_pages.json を手編集する
↓
regenerate で出力を作り直す
↓
edit_plan_template.md末尾の確認チェックリストで出力を確認する
```

```bash
python3 -m src.cli edit-plan-template --input output/editable/lesson_pages.json --output output/edit_plan_template.md
```

- `--input`: `lesson_pages.json`形式（`output/editable/lesson_pages.json`を想定）。
- `--output`: 出力Markdownのパス（省略時は`output/edit_plan_template.md`）。

## 4. LLM回答の読み方・採用判断の考え方

`edit_plan_template.md`の「3. 採用判断ルール」には、`editable/lesson_pages.json`の`mode`（`proofread`/`restructure`/`generate`）に応じた判断の目安が書かれています。

| mode | 採用判断の目安 |
|---|---|
| `proofread` | 誤字脱字・分かりにくさ・説明不足の改善が中心。ページの追加・削除・順序変更の提案は採用しない |
| `restructure` | ページの統合・分割・順序整理の提案は採用を検討してよいが、元資料の意図・雰囲気を大きく変える提案は採用しない |
| `generate` | 必要な説明補足・ページ構成案の追加提案は採用を検討してよいが、元情報にない断定や根拠のない内容追加は採用しない |
| 上記以外 | 汎用的な判断基準として扱い、元資料の意図を尊重し過度な作り替えとなる提案は採用しない |

共通の判断基準として、以下も`edit_plan_template.md`に明記されています。

- 元資料にない断定・誇張表現を含む提案は採用しない。
- 提案の意図が分からない場合は、いったん保留にして元資料を確認する。
- 迷った場合は、採用しない方を選ぶ（改善は次の反復でも行える）。

## 5. `edit_plan_template.md`の使い方

1. `llm_handoff.md`をChatGPT/Claude等へ貼り付け、改善案を受け取る。
2. `edit-plan-template`コマンドで`edit_plan_template.md`を生成する。
3. 改善案を読みながら、ページごとの「採用判断」欄（`title`/`summary`/`body`/`layout_instruction`/`notes`それぞれについて「採用する／採用しない／一部採用」）にチェックを入れる。
4. 「採用する改善内容」欄に、実際に反映する文面を書き写す。
5. 「判断メモ」欄に、採用理由・採用しない理由・元資料確認が必要な点を記録する。

## 6. `lesson_pages.json`の編集対象

編集してよい項目（`edit_plan_template.md`にも明記）:

- `title`
- `summary`
- `body`
- `layout_instruction`
- `notes`

通常編集しない項目:

- `page_no`
- `role`
- `source_page_no`
- `source_image`
- `assets`
- `generated_at`
- `metadata`
- project設定

`restructure`でページ構成の整理（`role`やページ順の見直し）が必要な場合は、直接編集する前に人間が慎重に判断し、`source_page_no`との対応が壊れていないか確認してください。編集全般の詳細は[`docs/09_editable_regenerate_guide.md`](09_editable_regenerate_guide.md)も参照してください。

## 7. `regenerate`の実行例

```bash
python3 -m src.cli regenerate --input output/editable/lesson_pages.json --output-format all
```

## 8. 再生成後のチェックリスト

`edit_plan_template.md`の末尾（「8. 出力確認チェックリスト」）に、以下のチェック項目が含まれます。

- [ ] `regenerate`がエラーなく完了した
- [ ] PDF / DOCX / Markdown / PNG等が生成された
- [ ] 変更したtitle / summary / bodyが出力に反映されている
- [ ] 元資料との対応関係が壊れていない
- [ ] source_page_no / source_imageが意図せず変わっていない
- [ ] 誇張表現や元資料にない断定が増えていない
- [ ] ページ数が意図せず変わっていない
- [ ] レイアウトが大きく崩れていない
- [ ] 人間が最終確認した

## 9. 今回実装していないこと・今後の方針

- **LLM回答の自動取り込みは行いません。** `edit_plan_template.md`への採用判断の記入、`editable/lesson_pages.json`への反映は、いずれも人間の手作業です。
- `editable/lesson_pages.json`の自動マージ機能は実装していません。
- OpenAI API・Gamma API・Canva API等の外部API連携、ローカルLLM本体の実装は行っていません。

将来的には、この採用判断シートを土台に、LLM回答の取り込み支援（例: 採用判断シートの内容を半自動で反映する補助機能）や、ローカルLLMによる構成チェック・文章改善の組み込みへ発展させる可能性があります。詳細な方針は[`docs/07_api_integration_design.md`](07_api_integration_design.md)を参照してください。
