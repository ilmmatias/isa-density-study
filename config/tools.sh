set -euo pipefail

arch_bindir()        { echo "$TOOLCHAIN_ROOT/$1/bin"; }
arch_tool()          { echo "$(arch_bindir "$1")/$(arch_triple "$1")-$2"; }
arch_gcc()           { arch_tool "$1" gcc; }
arch_objdump()       { arch_tool "$1" objdump; }
arch_size()          { arch_tool "$1" size; }
arch_ar()            { arch_tool "$1" ar; }
arch_strip()         { arch_tool "$1" strip; }
arch_cross_compile() { echo "$(arch_bindir "$1")/$(arch_triple "$1")-"; }

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
