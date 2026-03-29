#!/usr/bin/env bash

set -euo pipefail

WORKLOAD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

. "$WORKLOAD_DIR/../../config/env.sh"
. "$WORKLOAD_DIR/../common.sh"

load_workload_config "$WORKLOAD_DIR"
prepare_workload

build_sqlite() {
    local arch="$1" profile="$2"
    local artifacts_dir="$WORKLOAD_ARTIFACTS_DIR/$profile/$arch"
    mkdir -p "$artifacts_dir"

    echo "$arch/$profile: sqlite: compiling..."
    "$(arch_gcc "$arch")" \
        $(workload_cflags "$arch" "$profile") \
        -c "$WORKLOAD_SRC_DIR/sqlite3.c" \
        -o "$artifacts_dir/sqlite3.o"

    "$(arch_ar "$arch")" rcs "$artifacts_dir/libsqlite3.a" "$artifacts_dir/sqlite3.o"
    echo "$arch/$profile: sqlite: done"
}

mapfile -t TARGET_ARCHS < <(selected_archs "${1:-}")
mapfile -t TARGET_PROFILES < <(selected_profiles "${1:-}" "${2:-}")

for profile in "${TARGET_PROFILES[@]}"; do
    for arch in "${TARGET_ARCHS[@]}"; do
        build_sqlite "$arch" "$profile"
    done
done
