# 文字起こしプロンプト

以下の教材画像を読み取り、話者ごとに整理してください。

## 指示
- 画像ファイル名（例: `page_01.png`）を `source_image` にそのまま入れる。
- 1ページ目は記事名と番号だけ読み取る。
- 2ページ目以降は台詞を順番通りに並べる。
- 話者は「状況説明者」「まじょこ」「その他」に分類する。
- 読めない箇所は推測せず「判読不能」と書き、`unreadable_parts` にも追記する。
- 誤字脱字を勝手に直さず、原文に近い形で出力する。

## 出力形式
`docs/03_data_format.md` のページ形式に合わせて出力してください。
`unreadable_parts` はこの工程専用の確認用フィールドで、`examples/*.json` には含めません（`pages`配列に転記する前に、判読不能箇所を人が確認し空にしてください）。

```json
{
  "page_no": 1,
  "source_image": "page_01.png",
  "title": "",
  "lines": [
    {"speaker": "状況説明者", "text": ""}
  ],
  "unreadable_parts": []
}
```

## 次の工程への引き渡し
この出力の `page_no` / `source_image` / `title` / `lines` は、そのまま `pages` 配列の要素として使えます。
`summary` / `improvement_points` / `canva` は含まれていないため、`brushup_prompt.md`・`canva_design_prompt.md` の工程で追記してください。
