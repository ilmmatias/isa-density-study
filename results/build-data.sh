#!/usr/bin/env bash

set -euo pipefail

RESULTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$RESULTS_DIR/../arch/env.sh"
. "$RESULTS_DIR/../workloads/common.sh"

RESULTS_DATA_DIR="${RESULTS_DATA_DIR:-$RESULTS_DIR/data}"
RESULTS_CSV="${RESULTS_CSV:-$RESULTS_DATA_DIR/results.csv}"
WORKLOADS_DIR="$REPO_ROOT/workloads"

mapfile -t TARGET_PROFILES < <(selected_profiles "${1:-}" "${2:-}")
mapfile -t TARGET_ARCHS < <(selected_archs "${1:-}")

mkdir -p "$RESULTS_DATA_DIR"

tmpdirs=()
cleanup() {
    local d
    for d in "${tmpdirs[@]:-}"; do
        [[ -d "$d" ]] && rm -rf "$d"
    done
}
trap cleanup EXIT

count_insts() {
    local arch="$1" file="$2"
    "$(arch_objdump "$arch")" -d "$file" 2>/dev/null | awk '
        /^[[:space:]]*[0-9a-f]+:/ { count++ }
        END { print count+0 }'
}

text_size() {
    local arch="$1" file="$2"
    "$(arch_size "$arch")" -A -d "$file" 2>/dev/null | awk '
        $1 == ".text" { sum += $2 }
        END { print sum+0 }'
}

analyze_archive() {
    local workload="$1" arch="$2" profile="$3" archive="$4"
    if [[ ! -f "$archive" ]]; then
        echo "Warning: missing archive $archive" >&2
        return
    fi

    local tmp
    tmp=$(mktemp -d)
    tmpdirs+=("$tmp")

    pushd "$tmp" >/dev/null
    "$(arch_ar "$arch")" x "$archive"

    local text_total=0 inst_total=0
    shopt -s nullglob
    for f in *.o; do
        text_total=$((text_total + $(text_size "$arch" "$f")))
        inst_total=$((inst_total + $(count_insts "$arch" "$f")))
    done
    shopt -u nullglob
    popd >/dev/null

    local bpi
    if [[ "$inst_total" -eq 0 ]]; then
        bpi="NaN"
    else
        bpi=$(awk "BEGIN { printf \"%.4f\", $text_total / $inst_total }")
    fi

    printf '%s,%s,%s,%s,%s,%s\n' \
        "$workload" "$arch" "$profile" "$text_total" "$inst_total" "$bpi"
}

echo "workload,arch,profile,text_bytes,instruction_count,bytes_per_instruction" \
    > "$RESULTS_CSV"

for workload_dir in "$WORKLOADS_DIR"/*; do
    [[ -f "$workload_dir/workload.json" ]] || continue
    load_workload_config "$workload_dir"

    for profile in "${TARGET_PROFILES[@]}"; do
        for arch in "${TARGET_ARCHS[@]}"; do
            analyze_archive "$WORKLOAD_ID" "$arch" "$profile" \
                "$WORKLOAD_ARTIFACTS_DIR/$profile/$arch/$WORKLOAD_ARTIFACT"
        done
    done
done >> "$RESULTS_CSV"
