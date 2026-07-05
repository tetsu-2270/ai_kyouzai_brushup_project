# Canva設計プロンプト

以下の教材内容（`brushup_prompt.md` 適用後のページ内容）をCanvaで再現できるように、具体的なレイアウト設計書にしてください。
ここでの出力は `pages[].canva` の3項目（`layout_type` / `main_visual` / `notes`）を決めるための下書きです。
最終的な「Canva AI投入用プロンプト」は `src/canva_renderer.py` がJSONから自動生成するため、ここで作る必要はありません。

## 必須項目
- キャンバスサイズ
- 背景色
- 文字サイズ
- 吹き出し位置
- 人物・アイコン配置
- 余白
- 強調色
- ページ内の視線誘導

## 出力形式
- ページ番号（`page_no`）
- レイアウト概要 → `canva.layout_type`
- 配置指示・テキスト配置 → `canva.main_visual`
- 手動修正ポイント・上記必須項目の詳細 → `canva.notes`
