#!/usr/bin/env bash

set -euo pipefail

RESULTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$RESULTS_DIR/../config/env.sh"

verify_toolchains

WORKLOADS_DIR="$REPO_ROOT/workloads"
mkdir -p "$RESULTS_DIR"

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

analyze_regular() {
    local workload="$1" arch="$2" file="$3"
    if [[ ! -f "$file" ]]; then
        echo "Warning: missing file $file" >&2
        return
    fi

    local text inst bpi
    text=$(text_size "$arch" "$file")
    inst=$(count_insts "$arch" "$file")
    if [[ "$inst" -eq 0 ]]; then
        bpi="NaN"
    else
        bpi=$(awk "BEGIN { printf \"%.4f\", $text / $inst }")
    fi

    printf '%s,%s,%s,%s,%s\n' "$workload" "$arch" "$text" "$inst" "$bpi"
}

analyze_archive() {
    local workload="$1" arch="$2" archive="$3"
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

    printf '%s,%s,%s,%s,%s\n' "$workload" "$arch" "$text_total" "$inst_total" "$bpi"
}

echo "workload,arch,text_bytes,instruction_count,bytes_per_instruction" \
    > "$RESULTS_DIR/results.csv"

for arch in "${ARCHS[@]}"; do
    analyze_regular "busybox" "$arch" \
        "$WORKLOADS_DIR/busybox/.artifacts/$arch/busybox"
done >> "$RESULTS_DIR/results.csv"

for arch in "${ARCHS[@]}"; do
    analyze_regular "sqlite" "$arch" \
        "$WORKLOADS_DIR/sqlite/.artifacts/$arch/sqlite3.o"
done >> "$RESULTS_DIR/results.csv"

for arch in "${ARCHS[@]}"; do
    analyze_archive "zlib" "$arch" \
        "$WORKLOADS_DIR/zlib/.artifacts/$arch/libz.a"
done >> "$RESULTS_DIR/results.csv"
