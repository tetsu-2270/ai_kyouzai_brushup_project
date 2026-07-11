#!/usr/bin/env bash
# Apple Vision OCRヘルパー（tools/apple_vision_ocr/）をビルドする。
# macOS以外・Swiftツールチェーンが無い環境ではビルドせず、案内のみ表示して終了する
# （build-all等の通常導線を壊さないため。ビルド不能はエラー終了ではなく警告扱い）。
#
# ビルド成果物: tools/apple_vision_ocr/.build/release/apple-vision-ocr
# （.build/はGit管理対象外。ビルド済みバイナリ自体もGitへコミットしない）

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_DIR="$SCRIPT_DIR/../tools/apple_vision_ocr"

if [ "$(uname -s)" != "Darwin" ]; then
  echo "このスクリプトはmacOS専用です（Apple Vision OCRはmacOS標準のVisionフレームワークを使用します）。"
  echo "このプラットフォームではビルドをスキップします。TesseractのみのOCR処理は引き続き利用できます。"
  exit 0
fi

if ! command -v swift >/dev/null 2>&1; then
  echo "Swiftツールチェーンが見つかりませんでした（Xcode Command Line Toolsが必要です）。"
  echo "インストール手順:"
  echo "  xcode-select --install"
  echo "インストール後、このスクリプトを再実行してください。"
  echo "ビルドをスキップします。TesseractのみのOCR処理は引き続き利用できます。"
  exit 0
fi

echo "=== Apple Vision OCRヘルパーをビルドします ==="
echo "対象: $PACKAGE_DIR"

if ! (cd "$PACKAGE_DIR" && swift build -c release); then
  echo ""
  echo "ビルドに失敗しました。上記のエラーを確認してください。"
  echo "ビルドが無くても、TesseractのみのOCR処理（--ocr-engine tesseract、既定）は引き続き利用できます。"
  exit 1
fi

BINARY_PATH="$PACKAGE_DIR/.build/release/apple-vision-ocr"
if [ ! -x "$BINARY_PATH" ]; then
  echo "ビルドは成功しましたが、実行ファイルが見つかりませんでした: $BINARY_PATH"
  exit 1
fi

echo ""
echo "ビルド完了: $BINARY_PATH"
echo "動作確認: $BINARY_PATH --input <画像パス>"
