# 15 LLM改善案の構造化候補生成ワークフロー（`apply-llm-suggestions`）

> ChatGPT/Claude等（当面の手作業検証用の製品）から返ってきた教材改善案Markdownを読み込み、ページ・項目ごとの改善候補として構造化するコマンドです。プロジェクト方針（README.md「プロジェクト方針：外部API非依存・ローカルLLM移行前提」参照）のとおり、**LLM改善案の自動採用・`lesson_pages.json`への自動反映は行いません**。

## 1. `apply-llm-suggestions`の目的

これまでのワークフローで、以下は実現できています。

- OCR品質チェック（`ocr-check`）
- OCR補正候補JSON生成
- 承認済みOCR補正候補の反映（`apply-ocr-corrections`）
- LLM手作業投入用Markdown生成（`llm-handoff`）

しかし、ChatGPT/Claude等から返ってきた改善案を`editable/lesson_pages.json`に反映する作業は、まだ完全に人間の手作業でした。

`apply-llm-suggestions`は、LLM回答をそのまま直接反映するのではなく、まず**ページ・項目ごとの改善候補データ**に変換することで、人間が採用判断しやすくするためのコマンドです。

## 2. `llm-handoff`との関係

```text
build-all または lesson-pages で editable/lesson_pages.json を作る
↓
（必要であれば）ocr-check / apply-ocr-corrections でOCR補正を済ませる
↓
llm-handoff で LLM投入用Markdownを作る
↓
ChatGPT/Claude等へ貼り、改善案（Markdown）を受け取る
↓
apply-llm-suggestions で改善案Markdownを構造化候補に変換する
↓
llm_suggestion_candidates.json / llm_suggestion_report.md を人間が確認する
↓
採用する候補の status を approved に変更する
↓
（将来）apply-approved-llm-suggestions（未実装）で承認済み候補を反映する
```

## 3. LLM回答Markdownの想定形式

`llm-handoff`が依頼する回答形式（`docs/11_llm_handoff_workflow.md`参照）を前提にしています。

```markdown
# 教材全体の構成チェック

## 全体評価

## 大きく直す必要がある点

## 直しすぎない方がよい点

# ページ別改善案

## Page 1: タイトル

- 現状の問題点：
- 改善方針：
- title 改善案：
- summary 改善案：
- body 改善案：
- 注意点：

## Page 2: タイトル

（同様の形式で全ページ分）

# editable/lesson_pages.json 編集時の注意

- 直接置き換えてよい箇所：
- 人間が判断すべき箇所：
- 元資料確認が必要な箇所：
```

実際のLLM回答では表記揺れが起こり得るため、以下のようなページ見出しのバリエーションに対応しています。

- `## Page 1: タイトル`
- `## Page 1`
- `### Page 1: タイトル`
- `Page 1: タイトル`（見出し記号なし）
- `## ページ1`
- `## Page1`
- `## Page 01`

ラベルについても、以下のような表記揺れをある程度吸収します（空白の有無・全角半角は区別しません）。

- 現状の問題点 / 現状問題 / 問題点
- 改善方針
- title改善案 / title案 / タイトル改善案 / タイトル案
- summary改善案 / summary案 / 概要改善案 / 概要案
- body改善案 / body案 / 本文改善案 / 本文案
- notes改善案 / メモ改善案
- 注意点 / 注意

完璧な自然言語解析は行いません。想定外の表記は抽出できず、`parse_warnings`に記録されます。

## 4. 抽出できる項目

ページごとに以下を抽出します。

- `page_no` / `page_index`（`lesson_pages.json`側の対応するページ）
- `original_title` / `original_summary` / `original_body`（`lesson_pages.json`側の現在値。候補の`original`として保持）
- `title_suggestion` / `summary_suggestion` / `body_suggestion`（LLMの改善案）
- `issue`（現状の問題点） / `policy`（改善方針） / `caution`（注意点）
- `raw_block`（そのページのブロック全文。確認用）

全体評価として、以下も抽出します。

- `overall_evaluation`（全体評価）
- `major_points`（大きく直す必要がある点）
- `keep_as_is_points`（直しすぎない方がよい点）
- `editing_notes`（editable/lesson_pages.json編集時の注意。LLM側の記述）

## 5. `llm_suggestion_candidates.json`の読み方

```json
{
  "version": "1.0",
  "source_lesson_pages": "output/editable/lesson_pages.ocr_fixed.json",
  "source_suggestions": "output/llm_response.md",
  "generated_at": "2026-07-09T12:00:00+09:00",
  "mode": "llm_suggestions",
  "summary": {
    "total_pages": 27, "pages_with_suggestions": 20, "total_candidates": 35,
    "title_candidates": 10, "summary_candidates": 8, "body_candidates": 15, "notes_candidates": 2,
    "warnings": 1
  },
  "overall_review": {
    "overall_evaluation": "...", "major_points": "...", "keep_as_is_points": "...", "editing_notes": "..."
  },
  "candidates": [
    {
      "candidate_id": "llm-0001", "page_no": 1, "page_index": 0, "field": "title",
      "original": "...", "suggested": "...", "issue": "...", "policy": "...", "caution": "...",
      "source_page_no": [1], "source_image": "assets/page_001.jpeg",
      "status": "proposed", "human_note": "", "raw_block": "..."
    }
  ],
  "parse_warnings": [
    {"page_no": 1, "warning_type": "missing_body_suggestion", "message": "..."}
  ]
}
```

候補生成対象のfieldは`title`/`summary`/`body`/`notes`です。`source_page_no`/`source_image`/`assets`/`layout_instruction`は元資料対応・確認用として候補に含めますが、それ自体を改善候補の対象にはしません。

「変更なし」「現状維持」「そのままでよい」等の改善案は候補化しません。

## 6. statusの使い方

すべての候補は初期状態で`status: proposed`です。人間が候補ごとに以下のいずれかへ変更することを想定しています。

| status | 意味 |
|---|---|
| `proposed`（初期値） | まだ判断していない候補 |
| `approved` | 反映してよいと判断した候補 |
| `rejected` | 反映しないと判断した候補 |
| `needs_source_check` | 元資料（元画像・元テキスト）の確認が必要な候補 |
| `needs_human_review` | 改善案の妥当性そのものを人間が確認すべき候補 |

判断メモは`human_note`に記入してください。

**今回の`apply-llm-suggestions`は、候補を生成するだけで自動反映は行いません。** 将来的に`apply-approved-llm-suggestions`（仮称・未実装）のようなコマンドで、`status: approved`の候補だけを`lesson_pages.json`へ反映できるようにする想定です（`apply-ocr-corrections`と同様の設計方針。詳細は[`docs/14_apply_ocr_corrections_workflow.md`](14_apply_ocr_corrections_workflow.md)参照）。

## 7. 使い方・実行例

```bash
python3 -m src.cli apply-llm-suggestions \
  --lesson-pages output/editable/lesson_pages.ocr_fixed.json \
  --suggestions output/llm_response.md \
  --candidates-output output/llm_suggestion_candidates.json \
  --report output/llm_suggestion_report.md
```

- `--lesson-pages`: 元になる`lesson_pages.json`。**OCR崩れが残っている場合は、先に`ocr-check`/`apply-ocr-corrections`で補正済みの`lesson_pages.ocr_fixed.json`を作成し、それを指定してください。**
- `--suggestions`: ChatGPT/Claude等の回答をそのまま保存したMarkdownファイル。
- `--candidates-output`: 構造化した改善候補JSONの出力先（既定: `output/llm_suggestion_candidates.json`）。
- `--report`: 人間確認用Markdownレポートの出力先（既定: `output/llm_suggestion_report.md`）。

## 8. `llm_suggestion_report.md`の読み方

レポートは以下の構成です。

1. 目的 / 2. 使い方
2. **全体サマリー**: ページ数・改善案が見つかったページ数・候補総数（field別内訳）・parse_warnings件数
3. **教材全体へのLLM評価**: 全体評価・大きく直す必要がある点・直しすぎない方がよい点・LLM側の編集時の注意
4. **ページ別改善候補一覧**: ページごとの現状の問題点・改善方針・title/summary/body候補・注意点・候補ID
5. **field別候補一覧**: 全候補のテーブル
6. **parse_warnings**: 抽出できなかった箇所の一覧
7. **採用判断メモ**: statusの使い方の案内
8. **次に実行するコマンド例**: 将来の反映コマンド（TODO）の案内
9. **注意事項**

## 9. まだ自動反映しないこと・人間が採用判断すること

- LLM改善案を`lesson_pages.json`へ自動反映することは今回行いません。
- 候補の採用・不採用・元資料確認の要否は、すべて人間が`status`を変更して判断します。
- 現時点では、`llm_suggestion_candidates.json`を見ながら人間が`output/editable/lesson_pages.json`を直接編集してください。

## 10. 将来的な`apply-approved-llm-suggestions`へのつながり

将来的には、`status: approved`にした候補だけを`lesson_pages.json`へ反映する`apply-approved-llm-suggestions`（仮称）を追加できるよう、今回の候補JSON構造を設計しています。

```text
TODO（未実装。将来的な反映コマンドの案）:
python3 -m src.cli apply-approved-llm-suggestions --input output/editable/lesson_pages.ocr_fixed.json \
  --candidates output/llm_suggestion_candidates.json \
  --output output/editable/lesson_pages.llm_fixed.json --report output/llm_apply_report.md
```

## 11. 注意点

- LLM回答のMarkdown形式には表記揺れが起こり得ます。想定外の見出し・ラベル表記は抽出できず、`parse_warnings`に記録されます。抽出漏れがないか、レポートと元のLLM回答を見比べて確認してください。
- `--strict`のような厳格な形式チェックは今回は未実装です（TODO）。
- OCR補正済みファイルを使うこと: OCR崩れが残ったまま`llm-handoff`→`apply-llm-suggestions`を実行すると、改善案の多くが誤字修正になりがちです。先に[`docs/13_ocr_quality_check_workflow.md`](13_ocr_quality_check_workflow.md)・[`docs/14_apply_ocr_corrections_workflow.md`](14_apply_ocr_corrections_workflow.md)のフローでOCR補正を済ませることを推奨します。
