set -euo pipefail

CONFIG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export REPO_ROOT="$(cd "$CONFIG_DIR/.." && pwd)"
export TOOLCHAIN_ROOT="${TOOLCHAIN_ROOT:-$REPO_ROOT/cross/.prefix}"

ARCH_CONFIG="$CONFIG_DIR/archs.json"

COMMON_CFLAGS="$(jq -r '.cflags' "$ARCH_CONFIG")"

mapfile -t ARCHS < <(jq -r '.groups[].archs[].id' "$ARCH_CONFIG")

declare -A ARCH_TRIPLES
declare -A ARCH_EXTRA_CFLAGS

while IFS=$'\t' read -r id triple cflags; do
    ARCH_TRIPLES[$id]="$triple"
    ARCH_EXTRA_CFLAGS[$id]="$cflags"
done < <(jq -r '.groups[].archs[] | [.id, .triple, .cflags] | @tsv' "$ARCH_CONFIG")

arch_triple() {
    if [[ ! -v ARCH_TRIPLES[$1] ]]; then
        echo "$1: invalid architecture" >&2
        return 1
    fi

    echo "${ARCH_TRIPLES[$1]}"
}

arch_extra_cflags() {
    if [[ ! -v ARCH_EXTRA_CFLAGS[$1] ]]; then
        echo "$1: invalid architecture" >&2
        return 1
    fi

    echo "${ARCH_EXTRA_CFLAGS[$1]}"
}

arch_cflags() {
    local extra
    extra="$(arch_extra_cflags "$1")"
    echo "${COMMON_CFLAGS}${extra:+ $extra}"
}

. "$CONFIG_DIR/tools.sh"