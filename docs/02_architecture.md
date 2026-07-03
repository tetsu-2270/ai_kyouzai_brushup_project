# 02 アーキテクチャ設計

## 全体構成

```text
input/
  raw_images/             # 元画像
  transcripts/            # 文字起こし済みテキスト
examples/
  sample_pages.json       # サンプル入力
src/
  cli.py                  # CLI入口
  models.py               # データ構造
  parser.py               # 入力JSON読み込み
  renderer.py             # Markdown生成
  canva_renderer.py       # Canva設計書生成
output/
  brushup.md              # 教材ブラッシュアップ設計書
  canva_design.md         # Canva向け設計書
```

## データ処理フロー
1. JSONでページ情報を受け取る。
2. ページ番号順に並べる。
3. 文字起こし・登場人物・改善方針を構造化する。
4. 教材ブラッシュアップ設計書を生成する。
5. Canva向けレイアウト指示を生成する。

## データモデル
- Project
- Page
- DialogueLine
- CanvaLayout

## 出力形式
初期版はMarkdown固定。将来的にHTML、DOCX、PDFへ拡張する。
