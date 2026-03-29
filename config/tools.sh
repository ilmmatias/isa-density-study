set -euo pipefail

arch_bindir()        { echo "$TOOLCHAIN_ROOT/$1/bin"; }
arch_tool()          { echo "$(arch_bindir "$1")/$(arch_triple "$1")-$2"; }
arch_gcc()           { arch_tool "$1" gcc; }
arch_objdump()       { arch_tool "$1" objdump; }
arch_size()          { arch_tool "$1" size; }
arch_ar()            { arch_tool "$1" ar; }
arch_strip()         { arch_tool "$1" strip; }
arch_cross_compile() { echo "$(arch_bindir "$1")/$(arch_triple "$1")-"; }

verify_profile() {
    profile_cflags "$1" >/dev/null
}

verify_toolchain() {
    local arch="$1"
    local tool
    for tool in gcc objdump size ar; do
        if [[ ! -x "$(arch_tool "$arch" "$tool")" ]]; then
            echo "$arch: missing $(arch_tool "$arch" "$tool")" >&2
            return 1
        fi
    done
}

verify_toolchains() {
    local arch
    for arch in "${ARCHS[@]}"; do
        verify_toolchain "$arch"
    done
}

selected_profiles() {
    if [[ $# -gt 1 && -n "${2:-}" ]]; then
        verify_profile "$2"
        printf '%s\n' "$2"
        return 0
    fi

    local profile
    for profile in "${PROFILES[@]}"; do
        verify_profile "$profile"
        printf '%s\n' "$profile"
    done
}

selected_archs() {
    if [[ $# -gt 0 && -n "${1:-}" ]]; then
        verify_toolchain "$1"
        printf '%s\n' "$1"
        return 0
    fi

    local arch
    for arch in "${ARCHS[@]}"; do
        verify_toolchain "$arch"
        printf '%s\n' "$arch"
    done
}
