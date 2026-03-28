#!/usr/bin/env bash

set -euo pipefail

WORKLOAD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

. "$WORKLOAD_DIR/../../config/env.sh"
. "$WORKLOAD_DIR/../common.sh"

load_workload_config "$WORKLOAD_DIR"
prepare_workload

build_sqlite() {
    local arch="$1"
    local artifacts_dir="$WORKLOAD_ARTIFACTS_DIR/$arch"
    mkdir -p "$artifacts_dir"

    echo "$arch: sqlite: compiling..."
    "$(arch_gcc "$arch")" \
        $(workload_cflags "$arch") \
        -c "$WORKLOAD_SRC_DIR/sqlite3.c" \
        -o "$artifacts_dir/sqlite3.o"

    "$(arch_ar "$arch")" rcs "$artifacts_dir/libsqlite3.a" "$artifacts_dir/sqlite3.o"
    echo "$arch: sqlite: done"
}

if [[ $# -gt 0 ]]; then
    verify_toolchain "$1"
    build_sqlite "$1"
else
    verify_toolchains
    for arch in "${ARCHS[@]}"; do
        build_sqlite "$arch"
    done
fi
