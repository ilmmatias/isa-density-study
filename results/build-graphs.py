#!/usr/bin/env python3

import csv
import json
import math
import os
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import TwoSlopeNorm
from matplotlib.transforms import blended_transform_factory


SCRIPT_DIR = Path(__file__).parent.resolve()
REPO_ROOT = SCRIPT_DIR.parent

ARCH_DIR = REPO_ROOT / "arch"
WORKLOADS_DIR = REPO_ROOT / "workloads"

ARCH_INDEX = ARCH_DIR / "index.json"
DEFAULT_INPUT_CSV = SCRIPT_DIR / "data" / "results.csv"
DEFAULT_PLOTS_DIR = SCRIPT_DIR / "plots"


METRIC_INFO = {
    "text_bytes": {"title": ".text section size", "fmt": "+.1f", "slug": "text-size"},
    "instruction_count": {"title": "Instruction count", "fmt": "+.1f", "slug": "icount"},
    "bytes_per_instruction": {"title": "Bytes per instruction", "fmt": "+.1f", "slug": "bpi"},
}


def load_arch_config(
    index_path: Path,
    arch_root: Path,
) -> tuple[
    dict[str, str],
    dict[int, list[tuple[str, list[str]]]],
    dict[str, int],
    dict[int, str],
    list[tuple[str, str]],
]:
    with open(index_path, "r", encoding="utf-8") as f:
        index = json.load(f)

    labels: dict[str, str] = {}
    arch_bitness: dict[str, int] = {}
    groups_by_bitness: dict[int, list[tuple[str, list[str]]]] = {}
    normalize_by_bitness = {
        int(bits): arch_id for bits, arch_id in index["normalize"].items()
    }

    group_order = [(group["label"], group["archs"]) for group in index["groups"]]
    ordered_arch_ids: list[str] = []
    seen_arch_ids: set[str] = set()
    for _, arch_ids in group_order:
        for arch_id in arch_ids:
            if arch_id in seen_arch_ids:
                raise RuntimeError(f"duplicate architecture id in {index_path}: {arch_id}")
            ordered_arch_ids.append(arch_id)
            seen_arch_ids.add(arch_id)

    for arch_id in ordered_arch_ids:
        arch_path = arch_root / arch_id / "arch.json"
        with open(arch_path, "r", encoding="utf-8") as f:
            arch = json.load(f)

        if arch["id"] != arch_id:
            raise RuntimeError(f"{arch_path}: id mismatch ({arch['id']})")

        labels[arch_id] = arch["label"]
        arch_bitness[arch_id] = int(arch["bitness"])

    for bits, arch_id in normalize_by_bitness.items():
        if arch_id not in arch_bitness:
            raise RuntimeError(f"normalize target missing from {index_path}: {arch_id}")
        if arch_bitness[arch_id] != bits:
            raise RuntimeError(
                f"normalize target {arch_id} has bitness {arch_bitness[arch_id]}, expected {bits}"
            )

    for bits in sorted(set(arch_bitness.values())):
        groups: list[tuple[str, list[str]]] = []
        for group_label, arch_ids in group_order:
            filtered = [arch_id for arch_id in arch_ids if arch_bitness.get(arch_id) == bits]
            if filtered:
                groups.append((group_label, filtered))
        groups_by_bitness[bits] = groups

    profiles = [(profile["id"], profile["label"]) for profile in index["profiles"]]
    return labels, groups_by_bitness, arch_bitness, normalize_by_bitness, profiles


def load_workloads(workloads_dir: Path) -> list[tuple[str, str]]:
    workloads = []
    for config in sorted(workloads_dir.glob("*/workload.json")):
        with open(config, "r", encoding="utf-8") as f:
            data = json.load(f)
        workloads.append((data["id"], data["label"]))
    return workloads


def load_results(path: Path) -> list[dict]:
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["text_bytes"] = int(row["text_bytes"])
            row["instruction_count"] = int(row["instruction_count"])
            row["bytes_per_instruction"] = float(row["bytes_per_instruction"])
            rows.append(row)
    return rows


def filter_rows(
    rows: list[dict],
    profile: str,
    target_bitness: int,
    arch_bitness: dict[str, int],
) -> list[dict]:
    return [
        row for row in rows
        if row["profile"] == profile and arch_bitness.get(row["arch"]) == target_bitness
    ]


def build_metric_table(
    rows: list[dict],
    metric: str,
    normalize: str | None,
) -> dict[str, dict[str, float]]:
    raw: dict[str, dict[str, float]] = defaultdict(dict)

    for row in rows:
        raw[row["workload"]][row["arch"]] = float(row[metric])

    if normalize is None:
        return raw

    normalized: dict[str, dict[str, float]] = defaultdict(dict)
    for workload, arch_map in raw.items():
        base = arch_map.get(normalize)
        if base is None or base == 0:
            continue
        for arch, value in arch_map.items():
            normalized[workload][arch] = value / base
    return normalized


def existing_arches(
    rows: list[dict],
    arch_groups: list[tuple[str, list[str]]],
) -> list[str]:
    present = {row["arch"] for row in rows}
    ordered = [arch for _, group in arch_groups for arch in group if arch in present]
    extras = sorted(present - set(ordered))
    return ordered + extras


def build_matrix(
    rows: list[dict],
    metric: str,
    arch_groups: list[tuple[str, list[str]]],
    workloads: list[tuple[str, str]],
    normalize: str | None,
) -> tuple[np.ndarray, list[str], list[str], list[tuple[str, int, int]], bool]:
    table = build_metric_table(rows, metric, normalize)
    arches = existing_arches(rows, arch_groups)

    matrix = np.full((len(arches), len(workloads)), np.nan, dtype=float)
    for row_idx, arch in enumerate(arches):
        for col_idx, (workload_id, _) in enumerate(workloads):
            value = table.get(workload_id, {}).get(arch)
            if value is None or math.isnan(value):
                continue
            matrix[row_idx, col_idx] = (value - 1.0) * 100.0 if normalize else value

    workload_labels = [label for _, label in workloads]

    group_spans: list[tuple[str, int, int]] = []
    pos = 0
    present = set(arches)
    for group_label, group_arches in arch_groups:
        present_in_group = [arch for arch in group_arches if arch in present]
        if not present_in_group:
            continue

        start = pos
        end = pos + len(present_in_group) - 1
        group_spans.append((group_label, start, end))
        pos += len(present_in_group)

    return matrix, arches, workload_labels, group_spans, normalize is not None


def metric_range(matrix: np.ndarray) -> tuple[float, float]:
    finite = matrix[np.isfinite(matrix)]
    if finite.size == 0:
        return -1.0, 1.0

    bound = float(np.nanmax(np.abs(finite)))
    if bound == 0:
        return -1.0, 1.0
    return -bound, bound


def add_group_annotations(ax: plt.Axes, group_spans: list[tuple[str, int, int]]) -> None:
    trans = blended_transform_factory(ax.transAxes, ax.transData)

    for idx, (group_label, start, end) in enumerate(group_spans):
        if idx > 0:
            y = start - 0.5
            ax.plot(
                [-0.08, 1.02],
                [y, y],
                transform=trans,
                color="black",
                linewidth=1.4,
                alpha=0.65,
                solid_capstyle="butt",
                clip_on=False,
                zorder=6,
            )

        ax.text(
            -0.20,
            (start + end) / 2,
            group_label,
            transform=trans,
            ha="right",
            va="center",
            fontsize=12,
            alpha=0.95,
            clip_on=False,
        )


def annotate_cells(ax: plt.Axes, matrix: np.ndarray, fmt: str) -> None:
    for row in range(matrix.shape[0]):
        for col in range(matrix.shape[1]):
            value = matrix[row, col]
            if not np.isfinite(value):
                ax.text(col, row, "-", ha="center", va="center", fontsize=10, alpha=0.5)
                continue
            ax.text(col, row, f"{format(value, fmt)}%", ha="center", va="center", fontsize=10)


def plot_heatmap(
    ax: plt.Axes,
    matrix: np.ndarray,
    arch_labels: list[str],
    workload_labels: list[str],
    group_spans: list[tuple[str, int, int]],
    pretty_arch_labels: dict[str, str],
    metric: str,
    normalized: bool,
) -> None:
    masked = np.ma.masked_invalid(matrix)
    vmin, vmax = metric_range(matrix)
    image = ax.imshow(
        masked,
        aspect="auto",
        interpolation="nearest",
        cmap="coolwarm",
        norm=TwoSlopeNorm(vmin=vmin, vcenter=0.0, vmax=vmax),
    )

    ax.set_title(METRIC_INFO[metric]["title"])
    ax.set_xticks(np.arange(len(workload_labels)))
    ax.set_xticklabels(workload_labels)
    ax.set_yticks(np.arange(len(arch_labels)))
    ax.set_yticklabels([pretty_arch_labels.get(arch, arch) for arch in arch_labels])
    ax.set_xticks(np.arange(-0.5, len(workload_labels), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(arch_labels), 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=1.2)
    ax.tick_params(which="minor", bottom=False, left=False)

    add_group_annotations(ax, group_spans)
    annotate_cells(ax, matrix, METRIC_INFO[metric]["fmt"])

    cbar = plt.colorbar(image, ax=ax, fraction=0.046, pad=0.03)
    cbar.set_label("Delta vs baseline (%)" if normalized else METRIC_INFO[metric]["title"])


def plot_metric(
    rows: list[dict],
    output_path: Path,
    arch_labels_map: dict[str, str],
    arch_groups: list[tuple[str, list[str]]],
    workloads: list[tuple[str, str]],
    profile_label: str,
    target_bitness: int,
    metric: str,
    normalize: str | None,
) -> None:
    matrix, arches, workload_labels, group_spans, normalized = build_matrix(
        rows,
        metric,
        arch_groups,
        workloads,
        normalize,
    )
    if matrix.size == 0:
        return

    height = max(4.5, 0.52 * len(arches) + 1.4)
    width = max(6.0, 1.4 * len(workload_labels) + 3.6)
    fig, ax = plt.subplots(figsize=(width, height))
    fig.subplots_adjust(left=0.22, right=0.88)
    plot_heatmap(ax, matrix, arches, workload_labels, group_spans, arch_labels_map, metric, normalized)

    baseline_text = f"Baseline: {arch_labels_map.get(normalize, normalize)}" if normalize else None
    title = f"{profile_label} | {target_bitness}-bit"
    if baseline_text:
        title += f" | {baseline_text}"
    fig.suptitle(title, fontsize=12, y=0.98)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    plt.rcParams.update({
        "font.size": 12,
        "axes.titlesize": 15,
        "axes.labelsize": 13,
        "xtick.labelsize": 11,
        "ytick.labelsize": 11,
    })

    input_csv = Path(os.environ.get("RESULTS_CSV", str(DEFAULT_INPUT_CSV)))
    plots_dir = Path(os.environ.get("RESULTS_PLOTS_DIR", str(DEFAULT_PLOTS_DIR)))

    arch_labels_map, arch_groups_by_bitness, arch_bitness, normalize_by_bitness, profiles = load_arch_config(
        ARCH_INDEX,
        ARCH_DIR,
    )
    workloads = load_workloads(WORKLOADS_DIR)
    rows = load_results(input_csv)
    if not rows:
        raise RuntimeError(f"{input_csv} is empty")

    for profile_id, profile_label in profiles:
        for target_bitness, arch_groups in arch_groups_by_bitness.items():
            subset = filter_rows(rows, profile_id, target_bitness, arch_bitness)
            if not subset:
                continue

            normalize = normalize_by_bitness.get(target_bitness)
            for metric in ("text_bytes", "bytes_per_instruction", "instruction_count"):
                output_path = plots_dir / f"{profile_id}-{target_bitness}-bit-{METRIC_INFO[metric]['slug']}.png"
                plot_metric(
                    subset,
                    output_path,
                    arch_labels_map=arch_labels_map,
                    arch_groups=arch_groups,
                    workloads=workloads,
                    profile_label=profile_label,
                    target_bitness=target_bitness,
                    metric=metric,
                    normalize=normalize,
                )


if __name__ == "__main__":
    main()
