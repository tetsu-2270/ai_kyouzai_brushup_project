#!/usr/bin/env bash
set -euo pipefail
python -m src.cli generate --input examples/sample_pages.json --output output/brushup.md
python -m src.cli canva --input examples/sample_pages.json --output output/canva_design.md
