set -euo pipefail

export ARCH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export REPO_ROOT="$(cd "$ARCH_DIR/.." && pwd)"
export TOOLCHAIN_ROOT="${TOOLCHAIN_ROOT:-$ARCH_DIR}"

export ARCH_TARBALL_DIR="$REPO_ROOT/.tarballs"
export ARCH_WORK_DIR="$ARCH_DIR/.work"

ARCH_INDEX="$ARCH_DIR/index.json"

mapfile -t PROFILES < <(jq -r '.profiles[].id' "$ARCH_INDEX")

declare -A PROFILE_LABELS
declare -A PROFILE_CFLAGS
declare -A ARCH_TRIPLES
declare -A ARCH_BITNESS
declare -A ARCH_EXTRA_CFLAGS
declare -A NORMALIZE_ARCHES

while IFS=$'\t' read -r id label cflags; do
    PROFILE_LABELS[$id]="$label"
    PROFILE_CFLAGS[$id]="$cflags"
done < <(jq -r '.profiles[] | [.id, .label, .cflags] | @tsv' "$ARCH_INDEX")

mapfile -t INDEX_ARCHS < <(jq -r '.groups[].archs[]' "$ARCH_INDEX")
ARCHS=()
declare -A SEEN_ARCHS

for arch in "${INDEX_ARCHS[@]}"; do
    if [[ -v SEEN_ARCHS[$arch] ]]; then
        echo "$arch: duplicate architecture id in $ARCH_INDEX" >&2
        exit 1
    fi

    arch_meta="$ARCH_DIR/$arch/arch.json"
    arch_ctng="$ARCH_DIR/$arch/cross.config"
    if [[ ! -f "$arch_meta" ]]; then
        echo "$arch: missing architecture metadata at $arch_meta" >&2
        exit 1
    fi
    if [[ ! -f "$arch_ctng" ]]; then
        echo "$arch: missing crosstool-NG fragment at $arch_ctng" >&2
        exit 1
    fi

    IFS=$'\t' read -r id triple bitness cflags < <(
        jq -r '[.id, .triple, (.bitness | tostring), .cflags] | @tsv' "$arch_meta"
    )

    if [[ "$id" != "$arch" ]]; then
        echo "$arch: arch.json id mismatch ($id)" >&2
        exit 1
    fi

    ARCH_TRIPLES[$id]="$triple"
    ARCH_BITNESS[$id]="$bitness"
    ARCH_EXTRA_CFLAGS[$id]="$cflags"
    ARCHS+=("$id")
    SEEN_ARCHS[$id]=1
done

while IFS=$'\t' read -r bitness arch; do
    if [[ ! -v ARCH_TRIPLES[$arch] ]]; then
        echo "$arch: normalize target missing from index" >&2
        exit 1
    fi
    if [[ "${ARCH_BITNESS[$arch]}" != "$bitness" ]]; then
        echo "$arch: normalize target has bitness ${ARCH_BITNESS[$arch]}, expected $bitness" >&2
        exit 1
    fi

    NORMALIZE_ARCHES[$bitness]="$arch"
done < <(jq -r '.normalize | to_entries[] | [.key, .value] | @tsv' "$ARCH_INDEX")

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

normalize_arch() {
    if [[ ! -v NORMALIZE_ARCHES[$1] ]]; then
        echo "$1: invalid bitness" >&2
        return 1
    fi

    echo "${NORMALIZE_ARCHES[$1]}"
}

arch_cflags() {
    local arch="$1" profile="$2"
    local extra
    extra="$(arch_extra_cflags "$arch")"
    echo "$(profile_cflags "$profile")${extra:+ $extra}"
}

. "$ARCH_DIR/tools.sh"
