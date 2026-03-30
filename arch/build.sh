#!/usr/bin/env bash

set -euo pipefail

ARCH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$ARCH_DIR/env.sh"

render_toolchain_config() {
    local arch="$1"
    local output="$2"
    local prefix="$3"
    local base="$ARCH_DIR/base.config"
    local target="$ARCH_DIR/${arch}/cross.config"

    if [[ ! -f "$base" ]]; then
        echo "missing base config: $base" >&2
        return 1
    fi

    if [[ ! -f "$target" ]]; then
        echo "$arch: no target fragment exists" >&2
        return 1
    fi

    cp "$base" "$output"
    {
        printf '\n# Target overrides for %s\n' "$arch"
        cat "$target"
        printf '\nCT_PREFIX_DIR="%s"\n' "$prefix"
    } >> "$output"
}

build_toolchain() {
    local arch="$1"
    local prefix
    prefix="$(arch_prefix_dir "$arch")"

    if [[ -d "$prefix" ]]; then
        echo "$arch: skipping existing toolchain"
        return 0
    fi

    echo "$arch: building toolchain..."
    mkdir -p "$ARCH_TARBALL_DIR" "$ARCH_WORK_DIR"
    cd "$ARCH_WORK_DIR"
    render_toolchain_config "$arch" .config "$prefix"
    ct-ng olddefconfig
    cp .config rendered.config
    ct-ng build
    rm -f .config .config.old build.log
}

if [[ $# -gt 0 ]]; then
    build_toolchain "$1"
else
    for arch in "${ARCHS[@]}"; do
        build_toolchain "$arch"
    done
fi
