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
2. **依頼内容**: ChatGPT/Claude等に何を確認・指摘してほしいか（`mode`により内容が変わる。4.1節参照）
3. **作業ルール**: 元教材の意図を尊重するためのルール（`mode`により内容が変わる。4.1節参照）
4. **出力してほしい形式**: LLMの回答をそのまま人間の編集作業に使いやすくするための、期待する回答フォーマット（構成チェック・ページ別改善案・編集時の注意の3部構成）
5. **全体情報**: `project_title`/`target_audience`/`mode`/ページ数等
6. **ページごとのデータ**: `page_no`/`role`/`source_page_no`/`source_image`/`assets`/`title`/`summary`/`body`/`layout_instruction`/`notes`（欠損している項目は出力から省略され、エラーにはなりません）
7. **注意事項**: 自動取り込みは行わないこと、`source_page_no`等の内部情報は通常編集しないこと等
8. **改善提案欄**: 人間がLLMの回答を見ながら編集メモを取るためのテンプレート

### 4.1 modeによる依頼内容・作業ルールの切り替え

このプロジェクトは教材に限らず、将来的にさまざまな資料・文章の編集や再構成に使う可能性があります。そのため、`llm-handoff`の依頼文・作業ルールは特定の教材・特定の年代/属性に固定せず、`editable/lesson_pages.json`の`mode`（`lesson_pages.json`の`metadata.mode`。`proofread`/`restructure`/`generate`のいずれか）に応じて切り替えます。

| mode | 依頼文・作業ルールの方針 |
|---|---|
| `proofread` | 元資料を最も強く尊重する。誤字脱字・表現の分かりにくさ・説明不足・読みにくさを中心に改善案を出してもらう。大きな構成変更（ページの追加・削除・入れ替え）は提案しない。「**憲法第1条：ブラッシュアップであって、作り直しではない**」を重要ルールとして明記する |
| `restructure` | 元資料の意図・雰囲気は尊重しつつ、ページの統合・分割・順序整理・見出し整理などの構成改善は提案してもらう。「憲法第1条」は維持しつつ「構成整理は許容する」と併記する |
| `generate` | 新規教材生成寄りのモードとして扱う。「憲法第1条」は最重要ルールとして固定表示しない。代わりに目的・対象読者・トーン・元情報を守ることを重視し、必要な説明補足やページ構成案の追加を許容する（ただし元情報にない断定・根拠のない内容追加は避ける） |
| 上記以外（mode不明・未指定） | 汎用レビューとして扱う。元資料の意図を尊重しつつ、過度な作り替えは避けるという弱めの表現にとどめ、`generate`のような新規追加も`proofread`のような強い固定も行わない |

### 4.2 target_audience（対象読者）の扱い

`target_audience`は、`lesson_pages.json`の`metadata.target_audience`（または元の`pages`形式JSONの`target_reader`）から取得する**可変情報**であり、コードに固定文言として埋め込まれた値ではありません。

- `target_audience`が実質的に指定されている場合（システムの既定値「教材制作者」以外が設定されている場合）: その値をそのまま「対象読者」として全体情報欄に表示し、作業ルールにも「対象読者『（指定値）』に合わせて分かりやすく調整する」と入れます。
- `target_audience`が未指定（既定値のまま、または空）の場合: 特定の年代・属性を勝手に補完しません。代わりに「想定読者が明示されていないため、元資料の文脈から過度に決め打ちせず、一般的に分かりやすい表現に整える」という汎用的な文言にします。

**例**: ある教材の`target_reader`に「50〜60代の受講者」と指定した場合、生成される`llm_handoff.md`にはその値がそのまま反映されます。これはあくまで**その教材固有のデータとして反映される例**であり、`llm-handoff`コマンド自体が特定の年代を前提にしているわけではありません。`target_audience`には教材の対象読者を表す任意の文字列を指定できます（例: 「初めてプログラミングに触れる社会人」「海外向けビジネス文書の読み手」等）。

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
