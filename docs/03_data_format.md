# 03 データ形式

## JSON形式

```json
{
  "project_title": "教材ブラッシュアップ設計書 v1.0",
  "target_reader": "教材制作者・Canva作業者",
  "pages": [
    {
      "page_no": 1,
      "source_image": "page_01.png",
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

## 話者分類ルール
- 状況説明者: ナレーション、背景説明、記事説明
- まじょこ: 主人公または中心人物
- その他: 相手役、家族、先生、補足人物など

## ページ順ルール
画像ファイル名に番号がある場合は番号順。
`IMG9999` の次に `IMG0001` が来るケースを考慮する。
