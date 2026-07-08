# 11 LLM手作業投入ワークフロー（`llm-handoff`）

> `output/editable/lesson_pages.json`を人間がChatGPT/Claude等の製品画面へ手作業で貼り付け、構成チェック・文章改善案を得るための中間ファイル生成コマンドです。プロジェクト方針（README.md「プロジェクト方針：外部API非依存・ローカルLLM移行前提」・[`docs/07_api_integration_design.md`](07_api_integration_design.md)参照）のとおり、**この機能はLLMを呼び出しません**。あくまで人間がコピー＆ペーストするための下準備です。

## 1. 目的

調査の結果、教材の「3. 構成チェック」「4. 文・構成改善」に相当する処理は実質未実装であることが確認されています（`restructure`は文字数閾値による機械的な構造操作にとどまり、本文の言い回し改善・要約・誇張チェック等は行われません）。当面はローカルLLM本体を実装せず、まず**人間がChatGPT/Claude等の既存サブスク製品を手作業で使う運用**を成立させることを優先します。`llm-handoff`コマンドは、その第一歩として、`editable/lesson_pages.json`の内容とプロンプト指示を1つの貼り付け可能なMarkdownにまとめます。

ここでの「ChatGPT/Claude」は当面の手作業検証用の製品名であり、「LLM」という言葉をChatGPT/Claude等の総称として曖昧には使いません。将来的な自動化対象は、あくまでローカルLLMです。

## 2. 使い方

```bash
python3 -m src.cli llm-handoff --input output/editable/lesson_pages.json --output output/llm_handoff.md
```

- `--input`: `lesson_pages.json`形式（`output/editable/lesson_pages.json`を想定）。旧`pages`形式JSONも自動判定して読み込めます。
- `--output`: 出力Markdownのパス（省略時は`output/llm_handoff.md`）。
- `--page-start` / `--page-end`: `page_no`基準で対象ページを絞り込みます（両端含む）。省略時は全ページが対象です。ページ数が多い場合、分量を分けて複数回貼り付けたい場合に使います。

### 実行例

```bash
# 全ページを対象に生成
python3 -m src.cli llm-handoff --input output/editable/lesson_pages.json --output output/llm_handoff.md

# 1〜5ページ目だけを対象に生成（分量を分けたい場合）
python3 -m src.cli llm-handoff --input output/editable/lesson_pages.json --output output/llm_handoff_p1-5.md --page-start 1 --page-end 5
```

## 3. 想定する運用フロー

```text
build-all または lesson-pages で editable/lesson_pages.json を作る
↓
llm-handoff コマンドで llm_handoff.md を作る
↓
llm_handoff.md の中身をChatGPT/Claude等へ貼り付ける
↓
出力された改善案を見ながら、人間が editable/lesson_pages.json を手編集する
↓
regenerate で完成outputを再出力する
```

**このコマンドはLLM出力の自動取り込みを行いません。** LLMの回答を見ながら`editable/lesson_pages.json`を編集するのは人間の作業です。編集後は`regenerate`（詳細は[`docs/09_editable_regenerate_guide.md`](09_editable_regenerate_guide.md)参照）で完成outputを作り直してください。

## 4. 生成されるファイルの内容

`llm_handoff.md`には、以下の8セクションが含まれます。

1. **目的**: このファイルが何のためのものか
2. **依頼内容**: ChatGPT/Claude等に何を確認・指摘してほしいか
3. **作業ルール**: 「憲法第1条：ブラッシュアップであって、作り直しではない」を含む、元教材の意図を尊重するためのルール
4. **出力してほしい形式**: LLMの回答をそのまま人間の編集作業に使いやすくするための、期待する回答フォーマット（構成チェック・ページ別改善案・編集時の注意の3部構成）
5. **全体情報**: `project_title`/`target_audience`/`mode`/ページ数等
6. **ページごとのデータ**: `page_no`/`role`/`source_page_no`/`source_image`/`assets`/`title`/`summary`/`body`/`layout_instruction`/`notes`（欠損している項目は出力から省略され、エラーにはなりません）
7. **注意事項**: 自動取り込みは行わないこと、`source_page_no`等の内部情報は通常編集しないこと等
8. **改善提案欄**: 人間がLLMの回答を見ながら編集メモを取るためのテンプレート

## 5. ChatGPT/Claude等への貼り付け手順

1. `llm_handoff.md`をテキストエディタで開く。
2. 内容全体をコピーする。
3. ChatGPT/Claude等のチャット画面に貼り付けて送信する。
4. 返ってきた回答（構成チェック・ページ別改善案）を確認する。
5. 回答を見ながら、`output/editable/lesson_pages.json`の該当ページの`title`/`summary`/`body`を人間が判断して手編集する（編集してよい項目・編集しない方がよい項目は[`docs/09_editable_regenerate_guide.md`](09_editable_regenerate_guide.md)を参照）。
6. `python3 -m src.cli regenerate --input output/editable/lesson_pages.json --output-format all`等で完成outputを再出力する。

## 6. 今回実装していないこと・今後の方針

- **LLM出力の自動取り込みは行いません。** `editable/lesson_pages.json`への反映は人間が手作業で行います。
- OpenAI API・Gamma API・Canva API等の外部API連携は行いません。
- ローカルLLM本体の実装は行いません。
- 大量ページの自動分割（`--page-start`/`--page-end`は手動指定のみ）、構成チェック用/文章改善用のテンプレート分離は、今回は最小実装のため見送りました（TODO）。

将来的には、ChatGPTに任せようとしていた構成チェック・文章改善処理を、段階的にローカルLLMへ置き換えていく方針です。詳細は[`docs/07_api_integration_design.md`](07_api_integration_design.md)を参照してください。
