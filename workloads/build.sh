#!/usr/bin/env bash

set -euo pipefail

WORKLOADS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mapfile -t WORKLOADS < <(
    for f in "$WORKLOADS_DIR"/*/build.sh; do
        [[ -x "$f" ]] && basename "$(dirname "$f")"
    done
)

for workload in "${WORKLOADS[@]}"; do
    "$WORKLOADS_DIR/$workload/build.sh" "$@"
done
