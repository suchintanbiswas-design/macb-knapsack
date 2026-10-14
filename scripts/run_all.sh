#!/usr/bin/env bash
# Reproduce everything: validation -> benchmark -> tables & figures.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 scripts/run_validation.py
python3 scripts/run_benchmark.py
python3 scripts/analyze.py
python3 scripts/environment_info.py
