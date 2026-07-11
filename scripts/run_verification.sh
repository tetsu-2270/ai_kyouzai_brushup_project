#!/usr/bin/env bash
# 正式な検証入口。pytest → run_sample.sh の順に実行し、結果をlogs/evidence/<run_id>/へ
# 保存する（詳細はREADME/docs/04_output_spec.md「検証エビデンス」参照）。
#
# 意図的に`set -e`は使わない。片方のコマンドが失敗しても、もう片方は続けて実行し、
# 最終的な終了コードは失敗を反映する（判定・記録ロジックはsrc/verification_runner.py側）。
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

python3 -m src.verification_runner "$@"
exit $?
