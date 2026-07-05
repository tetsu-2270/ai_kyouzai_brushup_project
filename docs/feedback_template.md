# 実利用テスト フィードバックシート

このファイルをコピーして（例: `feedback_2026-07-06.md`）、確認結果を記入してください。
コピー先は`output/`配下など、Git管理対象外の場所を推奨します（実材料の内容が含まれる場合があるため）。

## 基本情報

- 確認日:
- 使用した元資料（画像枚数 / PDF / PPTXなど）:
- 使用した`--mode`（proofread / restructure）:
- `--requirements`を使った場合、そのファイル:
- OCRは機能したか（tesseract本体インストール済みか）:

## チェックリスト

各項目に `OK` / `要改善` / `NG` を記入し、気になった点があれば「メモ」に具体的に書いてください（該当ページ番号があると次の判断がしやすくなります）。

| # | 観点 | 対象出力 | 判定 | メモ |
|---|---|---|---|---|
| 1 | 元教材の内容が欠落していないか | `imported_pages.json` / `lesson_pages.json` / `brushup.md` | | |
| 2 | 文章が読みやすくなっているか（誤字脱字・表現の自然さ） | `brushup.md` | | |
| 3 | ページ構成が自然か（順序・まとまり） | `brushup.md` / `lesson_pages.json`の`source_page_no` | | |
| 4 | 導入ページが教材全体の要点を掴めているか（restructureのみ） | `brushup.md` Page 1 | | |
| 5 | 実践ページが実際に手を動かせる内容になっているか（restructureのみ） | `brushup.md`の`role: practice`ページ | | |
| 6 | まとめページが要点を的確に振り返れているか（restructureのみ） | `brushup.md`の`role: summary`ページ | | |
| 7 | Canva向けレイアウト指示が実際に使えそうか | `canva_design.md` | | |
| 8 | Canva AI投入用プロンプトがそのまま使えそうか | `canva_design.md` | | |
| 9 | DOCXとして配布できる見た目か（誤字・崩れ・不要な記号がないか） | `brushup.docx` | | |
| 10 | PDFとして配布できる見た目か（日本語の文字化けがないか） | `brushup.pdf` | | |
| 11 | scenario出力が動画・音声化にそのまま使えそうか | `scenario/voicevox.txt` / `scenario/scene.json` | | |
| 12 | 不自然な記号やMarkdown記法（`#`や`-`の連続、二重の箇条書き記号等）が残っていないか | 全出力 | | |
| 13 | `source_page_no`・`role`など内部管理情報が配布物（DOCX/PDF/brushup.md/canva_design.md）に出ていないか | DOCX / PDF / `brushup.md` / `canva_design.md` | | |
| 14 | 元画像・スライド画像への参照（「元画像: assets/...」）が各ページで正しく出ているか | `canva_design.md` | | |

## 総合評価

- 総合判定（そのまま配布できる／軽微な手直しで配布できる／作り直しが必要）:
- 最も気になった点（1〜2個に絞る）:
- 次に試したいこと（別の元教材で試す／`--mode`を変えて試す／手直しして再実行する 等）:

## 次のアクション（記入者の判断）

- [ ] このまま配布物として使う
- [ ] `output/lesson_pages.json`の`body`/`summary`/`layout_instruction`/`notes`を手直しして再生成する
- [ ] 別の元教材・別の`--mode`で試す
- [ ] 改善タスクとして起票する（内容: ）
