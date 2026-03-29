#!/usr/bin/env bash

set -euo pipefail

WORKLOAD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

. "$WORKLOAD_DIR/../../config/env.sh"
. "$WORKLOAD_DIR/../common.sh"

load_workload_config "$WORKLOAD_DIR"
prepare_workload

build_pcre2() {
    local arch="$1" profile="$2"
    local build_dir="$WORKLOAD_WORK_DIR/$profile/$arch"
    local artifacts_dir="$WORKLOAD_ARTIFACTS_DIR/$profile/$arch"
    mkdir -p "$build_dir" "$artifacts_dir"

    echo "$arch/$profile: pcre2: configuring..."
    cd "$build_dir"
    CC="$(arch_gcc "$arch")" \
    AR="$(arch_ar "$arch")" \
    RANLIB="$(arch_tool "$arch" ranlib)" \
    CFLAGS="$(workload_cflags "$arch" "$profile")" \
    "$WORKLOAD_SRC_DIR/configure" \
        --host="$(arch_triple "$arch")" \
        --disable-shared \
        --enable-static \
        --disable-jit

    echo "$arch/$profile: pcre2: building..."
    make libpcre2-8.la -j"$(nproc)"

    cp "$build_dir/.libs/libpcre2-8.a" "$artifacts_dir/libpcre2-8.a"
    echo "$arch/$profile: pcre2: done"
}

mapfile -t TARGET_ARCHS < <(selected_archs "${1:-}")
mapfile -t TARGET_PROFILES < <(selected_profiles "${1:-}" "${2:-}")

for profile in "${TARGET_PROFILES[@]}"; do
    for arch in "${TARGET_ARCHS[@]}"; do
        build_pcre2 "$arch" "$profile"
    done
done
