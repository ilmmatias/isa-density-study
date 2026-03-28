#!/usr/bin/env bash

set -euo pipefail

RESULTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"$RESULTS_DIR/build-data.sh"
python3 "$RESULTS_DIR/build-graphs.py"
