#!/usr/bin/env bash
# macOSでOCR環境（Tesseract + 日本語言語データ）をセットアップするスクリプト。
#
# 重要: このスクリプトはユーザーが明示的に実行するためのものです。
# Claude Code・CLI本体（src/cli.py）が自動的にこのスクリプトを実行することはありません。
# Homebrewが無い環境ではHomebrew自体のインストールも行いません（案内のみ表示します）。
#
# 使い方:
#   bash scripts/setup_ocr_macos.sh

set -uo pipefail

BREW_PATHS=("/opt/homebrew/bin/brew" "/usr/local/bin/brew")

BREW_CMD="$(command -v brew 2>/dev/null || true)"
if [ -z "$BREW_CMD" ]; then
  for candidate in "${BREW_PATHS[@]}"; do
    if [ -x "$candidate" ]; then
      BREW_CMD="$candidate"
      break
    fi
  done
fi

if [ -z "$BREW_CMD" ]; then
  echo "Homebrewが見つかりませんでした。"
  echo "https://brew.sh の手順に従って、先にHomebrewをインストールしてください。"
  echo "このスクリプトはHomebrew自体のインストールは行いません。"
  exit 1
fi

echo "Homebrewを使用します: $BREW_CMD"

if ! command -v brew >/dev/null 2>&1; then
  echo ""
  echo "brewコマンドが現在のシェルのPATHに見つかりませんでした。"
  echo "以下を実行してからこのスクリプトを再実行してください。"
  echo "  eval \"\$($BREW_CMD shellenv)\""
  exit 1
fi

echo ""
echo "Tesseractをインストールします: brew install tesseract"
"$BREW_CMD" install tesseract

echo ""
echo "日本語言語データをインストールします: brew install tesseract-lang"
"$BREW_CMD" install tesseract-lang

echo ""
echo "インストールを確認します。"
which tesseract || true
tesseract --list-langs || true

echo ""
echo "完了しました。python3 -m src.cli check-ocr で最終確認してください。"
