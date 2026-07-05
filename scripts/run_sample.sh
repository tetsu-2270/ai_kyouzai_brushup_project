#!/usr/bin/env bash
set -euo pipefail

# 1. サンプル入力(pages形式)から正データ lesson_pages.json を生成する（デフォルトはproofreadモード）
python3 -m src.cli lesson-pages --mode proofread --input examples/sample_pages.json --output output/lesson_pages.json

# 2. 以降の成果物はすべて lesson_pages.json から生成する
#    （brushup.md と canva_design.md は同じページデータに由来するため、常にページ番号・タイトルが一致する）
python3 -m src.cli generate --input output/lesson_pages.json --output output/brushup.md
python3 -m src.cli canva --input output/lesson_pages.json --output output/canva_design.md
python3 -m src.cli docx --input output/lesson_pages.json --output output/brushup.docx
python3 -m src.cli pdf --input output/lesson_pages.json --output output/brushup.pdf
python3 -m src.cli scenario --input output/lesson_pages.json --output-dir output/scenario
