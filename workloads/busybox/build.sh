#!/usr/bin/env bash

set -euo pipefail

WORKLOAD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

. "$WORKLOAD_DIR/../../config/env.sh"
. "$WORKLOAD_DIR/../common.sh"

load_workload_config "$WORKLOAD_DIR"
prepare_workload

mapfile -t BUSYBOX_APPLETS < <(jq -r '.applets[]' "$WORKLOAD_DIR/workload.json")

build_busybox() {
    local arch="$1"
    local build_dir="$WORKLOAD_WORK_DIR/$arch"
    local artifacts_dir="$WORKLOAD_ARTIFACTS_DIR/$arch"
    mkdir -p "$build_dir" "$artifacts_dir"

    echo "$arch: busybox: configuring..."
    make -C "$WORKLOAD_SRC_DIR" O="$build_dir" \
        CROSS_COMPILE="$(arch_cross_compile "$arch")" \
        allnoconfig

    sed -i 's/# CONFIG_STATIC is not set/CONFIG_STATIC=y/' "$build_dir/.config"
    sed -i 's/# CONFIG_LFS is not set/CONFIG_LFS=y/'       "$build_dir/.config"

    for applet in "${BUSYBOX_APPLETS[@]}"; do
        sed -i "s/# ${applet} is not set/${applet}=y/" "$build_dir/.config"
    done

    make -C "$WORKLOAD_SRC_DIR" O="$build_dir" \
        CROSS_COMPILE="$(arch_cross_compile "$arch")" \
        CFLAGS="$(workload_cflags "$arch")" \
        oldconfig

    echo "$arch: busybox: building..."
    make -C "$WORKLOAD_SRC_DIR" O="$build_dir" \
        CROSS_COMPILE="$(arch_cross_compile "$arch")" \
        CFLAGS="$(workload_cflags "$arch")" \
        -j"$(nproc)"

    cp "$build_dir/busybox" "$artifacts_dir/busybox"
    echo "$arch: busybox: done"
}

if [[ $# -gt 0 ]]; then
    verify_toolchain "$1"
    build_busybox "$1"
else
    verify_toolchains
    for arch in "${ARCHS[@]}"; do
        build_busybox "$arch"
    done
fi
