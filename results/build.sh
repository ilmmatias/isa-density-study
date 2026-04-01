#!/usr/bin/env bash

set -euo pipefail

RESULTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"$RESULTS_DIR/data/build.sh" "$@"
python3 "$RESULTS_DIR/graphs/build.py"
