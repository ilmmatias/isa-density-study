#!/usr/bin/env bash

set -euo pipefail

WORKLOAD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

. "$WORKLOAD_DIR/../../arch/env.sh"
. "$WORKLOAD_DIR/../common.sh"

load_workload_config "$WORKLOAD_DIR"
prepare_workload

build_zlib() {
    local arch="$1" profile="$2"
    local build_dir="$WORKLOAD_WORK_DIR/$profile/$arch"
    local artifacts_dir="$WORKLOAD_ARTIFACTS_DIR/$profile/$arch"
    mkdir -p "$build_dir" "$artifacts_dir"

    echo "$arch/$profile: zlib: configuring..."
    cd "$build_dir"
    CC="$(arch_gcc "$arch")" \
    AR="$(arch_ar "$arch")" \
    RANLIB="$(arch_tool "$arch" ranlib)" \
    CFLAGS="$(workload_cflags "$arch" "$profile")" \
    "$WORKLOAD_SRC_DIR/configure" --static

    echo "$arch/$profile: zlib: building..."
    make libz.a -j"$(nproc)"

    cp "$build_dir/libz.a" "$artifacts_dir/libz.a"
    echo "$arch/$profile: zlib: done"
}

mapfile -t TARGET_ARCHS < <(selected_archs "${1:-}")
mapfile -t TARGET_PROFILES < <(selected_profiles "${1:-}" "${2:-}")

for profile in "${TARGET_PROFILES[@]}"; do
    for arch in "${TARGET_ARCHS[@]}"; do
        build_zlib "$arch" "$profile"
    done
done
