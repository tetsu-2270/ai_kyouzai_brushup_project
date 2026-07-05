#!/usr/bin/env bash
set -euo pipefail

# レビュー・配布用ZIPを作成する。
# input/ (利用者投入データ) と output/ (生成物) は、機密情報混入防止・容量削減のため常に除外する。
# logs/ (実行ログ) は意図的にZIP対象に含める（.gitignoreではlogs/*を除外しているが、
# ZIPでは除外しない。詳細はdocs/04_output_spec.md「プロジェクト標準output構成」参照）。

cd "$(dirname "$0")/.."

OUTPUT_NAME="${1:-ai_kyouzai_brushup_project_$(date +%Y%m%d_%H%M%S).zip}"

zip -r "${OUTPUT_NAME}" . \
  -x "input/*" \
  -x "output/*" \
  -x ".git/*" \
  -x "*/__pycache__/*" \
  -x "*.pyc" \
  -x ".pytest_cache/*" \
  -x "*.egg-info/*" \
  -x ".DS_Store" \
  -x "*/.DS_Store" \
  -x ".env" \
  -x ".claude/settings.local.json" \
  -x "*.zip"

echo "作成しました: ${OUTPUT_NAME}"
