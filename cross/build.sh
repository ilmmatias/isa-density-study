#!/usr/bin/env bash

set -euo pipefail

CROSS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$CROSS_DIR/../config/env.sh"

build_toolchain() {
    local arch="$1"
    local config="$CROSS_DIR/${arch}.config"
    local prefix="$TOOLCHAIN_ROOT/${arch}"

    if [[ ! -f "$config" ]]; then
        echo "$arch: no toolchain config exists" >&2
        return 1
    fi

    if [[ -d "$prefix" ]]; then
        echo "$arch: skipping existing toolchain"
        return 0
    fi

    echo "$arch: building toolchain..."
    mkdir -p "$CROSS_DIR/.work"
    cd "$CROSS_DIR/.work"
    cp "$config" .config
    ct-ng build
    mv build.log "build.log.${arch}"
    rm -f .config
}

if [[ $# -gt 0 ]]; then
    build_toolchain "$1"
else
    for arch in "${ARCHS[@]}"; do
        build_toolchain "$arch"
    done
fi
