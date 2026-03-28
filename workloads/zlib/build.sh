#!/usr/bin/env bash

set -euo pipefail

WORKLOAD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

. "$WORKLOAD_DIR/../../config/env.sh"
. "$WORKLOAD_DIR/../common.sh"

load_workload_config "$WORKLOAD_DIR"
prepare_workload

build_zlib() {
    local arch="$1"
    local build_dir="$WORKLOAD_WORK_DIR/$arch"
    local artifacts_dir="$WORKLOAD_ARTIFACTS_DIR/$arch"
    mkdir -p "$build_dir" "$artifacts_dir"

    echo "$arch: zlib: configuring..."
    cd "$build_dir"
    CC="$(arch_gcc "$arch")" \
    AR="$(arch_ar "$arch")" \
    RANLIB="$(arch_tool "$arch" ranlib)" \
    CFLAGS="$(workload_cflags "$arch")" \
    "$WORKLOAD_SRC_DIR/configure" --static

    echo "$arch: zlib: building..."
    make libz.a -j"$(nproc)"

    cp "$build_dir/libz.a" "$artifacts_dir/libz.a"
    echo "$arch: zlib: done"
}

if [[ $# -gt 0 ]]; then
    verify_toolchain "$1"
    build_zlib "$1"
else
    verify_toolchains
    for arch in "${ARCHS[@]}"; do
        build_zlib "$arch"
    done
fi
