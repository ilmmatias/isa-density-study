#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"$ROOT_DIR/arch/build.sh"
"$ROOT_DIR/workloads/build.sh"
"$ROOT_DIR/results/build.sh"
