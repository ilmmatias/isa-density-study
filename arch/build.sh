#!/usr/bin/env bash

set -euo pipefail

ARCH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$ARCH_DIR/env.sh"

render_ctng_fragment() {
    local arch_meta="$1"
    jq -r '
        .fragments // {} | to_entries[] |
        if .value == true then "CT_\(.key)=y"
        elif .value == false then "# CT_\(.key) is not set"
        else "CT_\(.key)=\"\(.value)\""
        end
    ' "$arch_meta"
}

render_toolchain_config() {
    local arch="$1"
    local output="$2"
    local prefix="$3"
    local base="$ARCH_DIR/base.config"
    local arch_meta="$ARCH_DIR/config/${arch}.json"
    local arch_bitness
    arch_bitness="$(arch_bitness "$arch")"

    if [[ ! -f "$base" ]]; then
        echo "$arch: missing base config: $base" >&2
        return 1
    fi

    if [[ ! -f "$arch_meta" ]]; then
        echo "$arch: missing arch metadata" >&2
        return 1
    fi

    cp "$base" "$output"
    {
        printf '\n\nCT_PREFIX_DIR="%s"\n' "$prefix"
        printf '\nCT_ARCH_%d=y\n' "$arch_bitness"
        render_ctng_fragment "$arch_meta"
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
    rm -f .config .config.old rendered.config build.log
}

if [[ $# -gt 0 ]]; then
    build_toolchain "$1"
else
    for arch in "${ARCHS[@]}"; do
        build_toolchain "$arch"
    done
fi
