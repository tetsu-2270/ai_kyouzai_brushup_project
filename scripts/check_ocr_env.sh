#!/usr/bin/env bash
# OCR環境（tesseract/日本語言語データ/Homebrew）を診断するスクリプト。
# インストールは行わない。存在確認・案内表示のみを行う。
# 個々のコマンドが見つからなくても、スクリプト全体は最後まで実行する（set -eは使わない）。

set -uo pipefail

BREW_PATHS=("/opt/homebrew/bin/brew" "/usr/local/bin/brew")
TESSERACT_PATHS=("/opt/homebrew/bin/tesseract" "/usr/local/bin/tesseract")

echo "=== PATH ==="
echo "$PATH"
echo ""

echo "=== Homebrew ==="
BREW_ON_PATH="$(command -v brew 2>/dev/null || true)"
if [ -n "$BREW_ON_PATH" ]; then
  echo "brew: found on PATH ($BREW_ON_PATH)"
else
  echo "brew: not found on PATH"
fi

BREW_COMMON_PATH=""
for candidate in "${BREW_PATHS[@]}"; do
  if [ -x "$candidate" ]; then
    BREW_COMMON_PATH="$candidate"
    ls -l "$candidate" 2>/dev/null || true
  fi
done
if [ -z "$BREW_ON_PATH" ] && [ -n "$BREW_COMMON_PATH" ]; then
  echo "brew found at $BREW_COMMON_PATH (not on PATH)"
fi
echo ""

echo "=== Tesseract ==="
TESSERACT_ON_PATH="$(command -v tesseract 2>/dev/null || true)"
if [ -n "$TESSERACT_ON_PATH" ]; then
  echo "tesseract: found on PATH ($TESSERACT_ON_PATH)"
else
  echo "tesseract: not found on PATH"
fi

TESSERACT_COMMON_PATH=""
for candidate in "${TESSERACT_PATHS[@]}"; do
  if [ -x "$candidate" ]; then
    TESSERACT_COMMON_PATH="$candidate"
    ls -l "$candidate" 2>/dev/null || true
  fi
done
if [ -z "$TESSERACT_ON_PATH" ] && [ -n "$TESSERACT_COMMON_PATH" ]; then
  echo "tesseract found at $TESSERACT_COMMON_PATH (not on PATH)"
fi

RESOLVED_TESSERACT="${TESSERACT_ON_PATH:-$TESSERACT_COMMON_PATH}"
if [ -n "$RESOLVED_TESSERACT" ]; then
  echo ""
  echo "--- tesseract --version ---"
  "$RESOLVED_TESSERACT" --version 2>&1 || true
  echo "--- tesseract --list-langs ---"
  "$RESOLVED_TESSERACT" --list-langs 2>&1 || true
fi
echo ""

echo "=== Action required / 対応が必要な場合の案内 ==="
ACTION_NEEDED=0

if [ -z "$BREW_ON_PATH" ] && [ -n "$BREW_COMMON_PATH" ]; then
  ACTION_NEEDED=1
  echo "brew: not found on PATH"
  echo "brew found at $BREW_COMMON_PATH"
  echo ""
  echo "Run:"
  echo "  eval \"\$($BREW_COMMON_PATH shellenv)\""
  echo "To make it permanent:"
  echo "  echo 'eval \"\$($BREW_COMMON_PATH shellenv)\"' >> ~/.zprofile"
  echo ""
elif [ -z "$BREW_ON_PATH" ] && [ -z "$BREW_COMMON_PATH" ]; then
  ACTION_NEEDED=1
  echo "Homebrew was not found on PATH or common install locations."
  echo "Please install Homebrew first, or install Tesseract manually."
  echo ""
fi

if [ -z "$TESSERACT_ON_PATH" ] && [ -z "$TESSERACT_COMMON_PATH" ]; then
  ACTION_NEEDED=1
  echo "Tesseract was not found on PATH or common install locations."
  echo "macOS with Homebrew:"
  echo "  brew install tesseract"
  echo "  brew install tesseract-lang"
  echo ""
elif [ -z "$TESSERACT_ON_PATH" ] && [ -n "$TESSERACT_COMMON_PATH" ]; then
  ACTION_NEEDED=1
  echo "Tesseract was found at $TESSERACT_COMMON_PATH, but it is not available on PATH."
  echo ""
fi

if [ -n "$RESOLVED_TESSERACT" ]; then
  if ! "$RESOLVED_TESSERACT" --list-langs 2>/dev/null | grep -q "^jpn$"; then
    ACTION_NEEDED=1
    echo "Japanese OCR language data 'jpn' was not found."
    echo "macOS with Homebrew:"
    echo "  brew install tesseract-lang"
    echo ""
  fi
fi

if [ "$ACTION_NEEDED" -eq 0 ]; then
  echo "OCR environment looks ready. / OCR環境は利用可能です。"
fi

echo ""
echo "詳細な診断は次のコマンドでも確認できます: python3 -m src.cli check-ocr"
