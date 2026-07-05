# 03 データ形式

> 本ドキュメントが扱うのは、`lesson-pages`コマンドの`proofread`/`restructure`モードで使う**入力側**（`--input`）のJSON形式（`pages`形式）です。正データである`lesson_pages.json`自体のスキーマ（`metadata`/`source_page_no`/`role`等を含む）は[`docs/04_output_spec.md`](04_output_spec.md)を参照してください。3モード（`proofread`/`restructure`/`generate`）の全体像は[`docs/01_requirements.md`](01_requirements.md)を参照してください。`generate`モードは本フォーマットではなく`requirements.json`（README参照）のみを使います。
>
> **作成者がこのJSONを直接手作業で作る必要はありません。** 元資料（画像/PDF/PPTX）から`import-source`/`build-all`コマンドが自動生成する`imported_pages.json`もこの`pages`形式です（詳細は`docs/04_output_spec.md`「元資料の自動取り込み」、`docs/08_user_acceptance_test.md`を参照）。本ドキュメントは主に開発者・自動テスト向けにスキーマそのものを定義します。

## JSON形式

```json
{
  "project_title": "教材ブラッシュアップ設計書 v1.0",
  "target_reader": "教材制作者・Canva作業者",
  "pages": [
    {
      "page_no": 1,
      "source_image": "page_01.png",
      "source_assets": [],
      "title": "記事名・番号",
      "summary": "このページの概要",
      "lines": [
        {"speaker": "状況説明者", "text": "説明文"},
        {"speaker": "まじょこ", "text": "台詞"},
        {"speaker": "その他", "text": "台詞"}
      ],
      "improvement_points": [
        "文字量を減らす",
        "重要語句を強調する"
      ],
      "canva": {
        "layout_type": "縦長SNS教材",
        "main_visual": "左上に人物、右側に吹き出し",
        "notes": "スマホ閲覧前提で余白を広めに取る"
      }
    }
  ]
}
```

`source_assets`は任意項目（省略時は空配列）。`source_image`以外に保持している関連画像（PPTXのスライド内に複数の埋め込み画像がある場合など）の一覧。

## 話者分類ルール
- 状況説明者: ナレーション、背景説明、記事説明
- まじょこ: 主人公または中心人物
- その他: 相手役、家族、先生、補足人物など

## ページ順ルール
画像ファイル名に番号がある場合は番号順。
`IMG9999` の次に `IMG0001` が来るケースを考慮する。
