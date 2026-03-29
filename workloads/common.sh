set -euo pipefail

load_workload_config() {
    local dir="$1"
    local json="$dir/workload.json"

    WORKLOAD_ID="$(jq -r '.id' "$json")"
    WORKLOAD_LABEL="$(jq -r '.label' "$json")"
    WORKLOAD_VERSION="$(jq -r '.version' "$json")"
    WORKLOAD_CFLAGS="$(jq -r '.cflags' "$json")"
    WORKLOAD_ARTIFACT="$(jq -r '.artifact' "$json")"

    local tarball url sha256 extract
    tarball="$(jq -r '.tarball' "$json")"
    url="$(jq -r '.url' "$json")"
    sha256="$(jq -r '.sha256 // empty' "$json")"
    extract="$(jq -r '.extract' "$json")"

    WORKLOAD_TARBALLS_DIR="$REPO_ROOT/.tarballs"
    WORKLOAD_WORK_DIR="$dir/.work"
    WORKLOAD_ARTIFACTS_DIR="$dir/.artifacts"
    WORKLOAD_TARBALL_FILE="$WORKLOAD_TARBALLS_DIR/$tarball"
    WORKLOAD_URL="$url"
    WORKLOAD_SHA256="$sha256"
    WORKLOAD_EXTRACT="$extract"

    local src_dir_override
    src_dir_override="$(jq -r '.src_dir // empty' "$json")"
    if [[ -n "$src_dir_override" ]]; then
        WORKLOAD_SRC_DIR="$WORKLOAD_WORK_DIR/$src_dir_override"
    else
        WORKLOAD_SRC_DIR="$WORKLOAD_WORK_DIR/${WORKLOAD_ID}-${WORKLOAD_VERSION}"
    fi

    declare -gA WORKLOAD_ARCH_CFLAGS
    while IFS=$'\t' read -r arch cflags; do
        WORKLOAD_ARCH_CFLAGS[$arch]="$cflags"
    done < <(jq -r '.arch_cflags | to_entries[] | [.key, .value] | @tsv' "$json")
}

prepare_workload() {
    mkdir -p "$WORKLOAD_TARBALLS_DIR" "$WORKLOAD_WORK_DIR"

    if [[ ! -f "$WORKLOAD_TARBALL_FILE" ]]; then
        echo "$WORKLOAD_ID: fetching $WORKLOAD_URL..."
        wget -q --show-progress -O "$WORKLOAD_TARBALL_FILE" "$WORKLOAD_URL"
    fi

    if [[ -n "$WORKLOAD_SHA256" ]]; then
        echo "$WORKLOAD_SHA256  $WORKLOAD_TARBALL_FILE" | sha256sum -c --quiet
    fi

    if [[ ! -d "$WORKLOAD_SRC_DIR" ]]; then
        echo "$WORKLOAD_ID: extracting..."
        case "$WORKLOAD_EXTRACT" in
            tar)   tar -C "$WORKLOAD_WORK_DIR" -xf "$WORKLOAD_TARBALL_FILE" ;;
            unzip) unzip -q "$WORKLOAD_TARBALL_FILE" -d "$WORKLOAD_WORK_DIR" ;;
            *) echo "unknown extract method: $WORKLOAD_EXTRACT" >&2; return 1 ;;
        esac
    fi
}

workload_cflags() {
    local arch="$1" profile="$2"
    local extra="${WORKLOAD_ARCH_CFLAGS[$arch]:-}"
    echo "$(arch_cflags "$arch" "$profile")${WORKLOAD_CFLAGS:+ $WORKLOAD_CFLAGS}${extra:+ $extra}"
}
