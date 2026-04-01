#!/usr/bin/env python3

import csv
import json
import math
import numpy as np
import os

from collections import defaultdict
from pathlib import Path


os.environ.setdefault("MPLCONFIGDIR", str(Path("/tmp") / "isa-density-study-matplotlib"))

import matplotlib.pyplot as plt

from matplotlib.colors import TwoSlopeNorm
from matplotlib.transforms import blended_transform_factory


GRAPHS_DIR = Path(__file__).parent.resolve()
RESULTS_DIR = GRAPHS_DIR.parent
REPO_ROOT = RESULTS_DIR.parent

ARCH_DIR = REPO_ROOT / "arch"
WORKLOADS_DIR = REPO_ROOT / "workloads"

ARCH_INDEX = ARCH_DIR / "index.json"
DEFAULT_INPUT_CSV = RESULTS_DIR / "data" / "results.csv"

METRIC_ORDER = ("text_bytes", "bytes_per_instruction", "instruction_count")
OVERVIEW_ROW_ORDER = ((32, "CISC"), (32, "RISC"), (64, "CISC"), (64, "RISC"))

METRIC_INFO = {
    "text_bytes": {
        "title": ".text section size",
        "fmt": "+.1f",
        "slug": "text-size",
        "overview_label": ".text size",
    },
    "instruction_count": {
        "title": "Instruction count",
        "fmt": "+.1f",
        "slug": "icount",
        "overview_label": "Instruction count",
    },
    "bytes_per_instruction": {
        "title": "Bytes per instruction",
        "fmt": "+.1f",
        "slug": "bpi",
        "overview_label": "Bytes per\ninstruction",
    },
}


def load_arch_config(
    index_path: Path,
    arch_root: Path,
) -> tuple[
    dict[str, str],
    list[tuple[str, list[str]]],
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
        arch_path = arch_root / "config" / f"{arch_id}.json"
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
    return (
        labels,
        group_order,
        groups_by_bitness,
        arch_bitness,
        normalize_by_bitness,
        profiles,
    )


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
        row
        for row in rows
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


def build_detailed_matrix(
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


def build_overview_matrix(
    rows: list[dict],
    profile_id: str,
    arch_groups_by_bitness: dict[int, list[tuple[str, list[str]]]],
    arch_bitness: dict[str, int],
    normalize_by_bitness: dict[int, str],
    workloads: list[tuple[str, str]],
) -> tuple[np.ndarray, list[str], list[str]]:
    matrix = np.full((len(OVERVIEW_ROW_ORDER), len(METRIC_ORDER)), np.nan, dtype=float)
    profile_rows = [row for row in rows if row["profile"] == profile_id]
    workload_ids = [workload_id for workload_id, _ in workloads]
    group_lookup = {
        bits: {group_label: arch_ids for group_label, arch_ids in groups}
        for bits, groups in arch_groups_by_bitness.items()
    }

    bitness_tables: dict[int, dict[str, dict[str, dict[str, float]]]] = {}
    for bits in {bits for bits, _ in OVERVIEW_ROW_ORDER}:
        bitness_rows = filter_rows(profile_rows, profile_id, bits, arch_bitness)
        normalize = normalize_by_bitness.get(bits)
        bitness_tables[bits] = {
            metric: build_metric_table(bitness_rows, metric, normalize)
            for metric in METRIC_ORDER
        }

    row_labels = [f"{bits}-bit {group_label}" for bits, group_label in OVERVIEW_ROW_ORDER]
    col_labels = [METRIC_INFO[metric]["overview_label"] for metric in METRIC_ORDER]

    for row_idx, (bits, group_label) in enumerate(OVERVIEW_ROW_ORDER):
        group_arches = group_lookup.get(bits, {}).get(group_label, [])
        normalize = normalize_by_bitness.get(bits)

        for col_idx, metric in enumerate(METRIC_ORDER):
            values = []
            table = bitness_tables.get(bits, {}).get(metric, {})
            for workload_id in workload_ids:
                arch_map = table.get(workload_id, {})
                for arch in group_arches:
                    value = arch_map.get(arch)
                    if value is None or math.isnan(value):
                        continue
                    values.append((value - 1.0) * 100.0 if normalize else value)

            if values:
                matrix[row_idx, col_idx] = float(np.mean(values))

    return matrix, row_labels, col_labels


def metric_range(matrix: np.ndarray) -> tuple[float, float]:
    finite = matrix[np.isfinite(matrix)]
    if finite.size == 0:
        return -1.0, 1.0

    bound = float(np.nanmax(np.abs(finite)))
    if bound == 0:
        return -1.0, 1.0
    return -bound, bound


def detailed_output_path(graphs_dir: Path, profile_id: str, bitness: int, metric: str) -> Path:
    return (
        graphs_dir
        / "detailed"
        / profile_id
        / f"{bitness}-bit"
        / f"{METRIC_INFO[metric]['slug']}.png"
    )


def overview_output_path(graphs_dir: Path, profile_id: str) -> Path:
    return graphs_dir / "overview" / f"{profile_id}.png"


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


def annotate_cells(ax: plt.Axes, matrix: np.ndarray, fmt: str, suffix: str = "%") -> None:
    for row in range(matrix.shape[0]):
        for col in range(matrix.shape[1]):
            value = matrix[row, col]
            if not np.isfinite(value):
                ax.text(col, row, "-", ha="center", va="center", fontsize=10, alpha=0.5)
                continue
            ax.text(col, row, f"{format(value, fmt)}{suffix}", ha="center", va="center", fontsize=10)


def plot_detailed_heatmap(
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


def plot_overview_heatmap(
    ax: plt.Axes,
    matrix: np.ndarray,
    row_labels: list[str],
    col_labels: list[str],
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

    ax.set_xticks(np.arange(len(col_labels)))
    ax.set_xticklabels(col_labels)
    ax.set_yticks(np.arange(len(row_labels)))
    ax.set_yticklabels(row_labels)
    ax.set_xticks(np.arange(-0.5, len(col_labels), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(row_labels), 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=1.2)
    ax.tick_params(which="minor", bottom=False, left=False)

    annotate_cells(ax, matrix, "+.1f")

    cbar = plt.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Mean delta vs baseline (%)")


def render_detailed_plots(
    rows: list[dict],
    graphs_dir: Path,
    arch_labels_map: dict[str, str],
    arch_groups_by_bitness: dict[int, list[tuple[str, list[str]]]],
    arch_bitness: dict[str, int],
    normalize_by_bitness: dict[int, str],
    workloads: list[tuple[str, str]],
    profiles: list[tuple[str, str]],
) -> None:
    for profile_id, profile_label in profiles:
        for target_bitness, arch_groups in arch_groups_by_bitness.items():
            subset = filter_rows(rows, profile_id, target_bitness, arch_bitness)
            if not subset:
                continue

            normalize = normalize_by_bitness.get(target_bitness)
            for metric in METRIC_ORDER:
                matrix, arches, workload_labels, group_spans, normalized = build_detailed_matrix(
                    subset,
                    metric,
                    arch_groups,
                    workloads,
                    normalize,
                )
                if matrix.size == 0:
                    continue

                height = max(4.5, 0.52 * len(arches) + 1.4)
                width = max(6.0, 1.4 * len(workload_labels) + 3.6)
                fig, ax = plt.subplots(figsize=(width, height))
                fig.subplots_adjust(left=0.22, right=0.88)
                plot_detailed_heatmap(
                    ax,
                    matrix,
                    arches,
                    workload_labels,
                    group_spans,
                    arch_labels_map,
                    metric,
                    normalized,
                )

                baseline_text = (
                    f"Baseline: {arch_labels_map.get(normalize, normalize)}"
                    if normalize
                    else None
                )
                title = f"{profile_label} | {target_bitness}-bit"
                if baseline_text:
                    title += f" | {baseline_text}"
                fig.suptitle(title, fontsize=12, y=0.98)

                output_path = detailed_output_path(
                    graphs_dir,
                    profile_id,
                    target_bitness,
                    metric,
                )
                output_path.parent.mkdir(parents=True, exist_ok=True)
                fig.savefig(output_path, dpi=220, bbox_inches="tight")
                plt.close(fig)


def render_overview_plots(
    rows: list[dict],
    graphs_dir: Path,
    arch_labels_map: dict[str, str],
    arch_groups_by_bitness: dict[int, list[tuple[str, list[str]]]],
    arch_bitness: dict[str, int],
    normalize_by_bitness: dict[int, str],
    profiles: list[tuple[str, str]],
    workloads: list[tuple[str, str]],
) -> None:
    baseline_parts = []
    for bits in sorted(normalize_by_bitness):
        baseline_arch = normalize_by_bitness[bits]
        baseline_parts.append(f"{bits}-bit baseline: {arch_labels_map.get(baseline_arch, baseline_arch)}")
    baseline_text = " | ".join(baseline_parts)

    for profile_id, profile_label in profiles:
        matrix, row_labels, col_labels = build_overview_matrix(
            rows,
            profile_id,
            arch_groups_by_bitness,
            arch_bitness,
            normalize_by_bitness,
            workloads,
        )
        if not np.isfinite(matrix).any():
            continue

        fig, ax = plt.subplots(figsize=(8.2, 4.8))
        fig.subplots_adjust(left=0.24, right=0.88, top=0.80, bottom=0.16)
        plot_overview_heatmap(ax, matrix, row_labels, col_labels)
        fig.suptitle(f"{profile_label} overview", fontsize=13, y=0.97)
        if baseline_text:
            ax.set_title(baseline_text, fontsize=10, pad=12)

        output_path = overview_output_path(graphs_dir, profile_id)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=220, bbox_inches="tight")
        plt.close(fig)


def main() -> None:
    plt.rcParams.update(
        {
            "font.size": 12,
            "axes.titlesize": 15,
            "axes.labelsize": 13,
            "xtick.labelsize": 11,
            "ytick.labelsize": 11,
        }
    )

    input_csv = Path(os.environ.get("RESULTS_CSV", str(DEFAULT_INPUT_CSV)))
    graphs_dir = Path(os.environ.get("RESULTS_GRAPHS_DIR", str(GRAPHS_DIR)))

    (
        arch_labels_map,
        _group_order,
        arch_groups_by_bitness,
        arch_bitness,
        normalize_by_bitness,
        profiles,
    ) = load_arch_config(ARCH_INDEX, ARCH_DIR)
    workloads = load_workloads(WORKLOADS_DIR)
    rows = load_results(input_csv)
    if not rows:
        raise RuntimeError(f"{input_csv} is empty")

    render_detailed_plots(
        rows,
        graphs_dir,
        arch_labels_map,
        arch_groups_by_bitness,
        arch_bitness,
        normalize_by_bitness,
        workloads,
        profiles,
    )
    render_overview_plots(
        rows,
        graphs_dir,
        arch_labels_map,
        arch_groups_by_bitness,
        arch_bitness,
        normalize_by_bitness,
        profiles,
        workloads,
    )


if __name__ == "__main__":
    main()
