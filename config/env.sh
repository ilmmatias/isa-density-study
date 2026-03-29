set -euo pipefail

CONFIG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export REPO_ROOT="$(cd "$CONFIG_DIR/.." && pwd)"
export TOOLCHAIN_ROOT="${TOOLCHAIN_ROOT:-$REPO_ROOT/cross/.prefix}"

ARCH_CONFIG="$CONFIG_DIR/archs.json"

mapfile -t PROFILES < <(jq -r '.profiles[].id' "$ARCH_CONFIG")
mapfile -t ARCHS < <(jq -r '.bitness[].groups[].archs[].id' "$ARCH_CONFIG")

declare -A PROFILE_LABELS
declare -A PROFILE_CFLAGS
declare -A ARCH_TRIPLES
declare -A ARCH_BITNESS
declare -A ARCH_EXTRA_CFLAGS

while IFS=$'\t' read -r id label cflags; do
    PROFILE_LABELS[$id]="$label"
    PROFILE_CFLAGS[$id]="$cflags"
done < <(jq -r '.profiles[] | [.id, .label, .cflags] | @tsv' "$ARCH_CONFIG")

while IFS=$'\t' read -r id triple bitness cflags; do
    ARCH_TRIPLES[$id]="$triple"
    ARCH_BITNESS[$id]="$bitness"
    ARCH_EXTRA_CFLAGS[$id]="$cflags"
done < <(
    jq -r '
        .bitness[] as $bitness
        | $bitness.groups[].archs[]
        | [.id, .triple, ($bitness.bits | tostring), .cflags]
        | @tsv
    ' "$ARCH_CONFIG"
)

profile_label() {
    if [[ ! -v PROFILE_LABELS[$1] ]]; then
        echo "$1: invalid profile" >&2
        return 1
    fi

    echo "${PROFILE_LABELS[$1]}"
}

profile_cflags() {
    if [[ ! -v PROFILE_CFLAGS[$1] ]]; then
        echo "$1: invalid profile" >&2
        return 1
    fi

    echo "${PROFILE_CFLAGS[$1]}"
}

arch_triple() {
    if [[ ! -v ARCH_TRIPLES[$1] ]]; then
        echo "$1: invalid architecture" >&2
        return 1
    fi

    echo "${ARCH_TRIPLES[$1]}"
}

arch_bitness() {
    if [[ ! -v ARCH_BITNESS[$1] ]]; then
        echo "$1: invalid architecture" >&2
        return 1
    fi

    echo "${ARCH_BITNESS[$1]}"
}

arch_extra_cflags() {
    if [[ ! -v ARCH_EXTRA_CFLAGS[$1] ]]; then
        echo "$1: invalid architecture" >&2
        return 1
    fi

    echo "${ARCH_EXTRA_CFLAGS[$1]}"
}

arch_cflags() {
    local arch="$1" profile="$2"
    local extra
    extra="$(arch_extra_cflags "$arch")"
    echo "$(profile_cflags "$profile")${extra:+ $extra}"
}

. "$CONFIG_DIR/tools.sh"
