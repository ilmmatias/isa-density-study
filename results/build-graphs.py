#!/usr/bin/env python3

import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import TwoSlopeNorm
from matplotlib.transforms import blended_transform_factory


SCRIPT_DIR = Path(__file__).parent.resolve()
REPO_ROOT = SCRIPT_DIR.parent

CONFIG_DIR = REPO_ROOT / "config"
WORKLOADS_DIR = REPO_ROOT / "workloads"

INPUT_CSV = SCRIPT_DIR / "results.csv"
OUTPUT_TEXT_SIZE_PNG = SCRIPT_DIR / "results-text-size.png"
OUTPUT_BPI_PNG = SCRIPT_DIR / "results-bpi.png"
OUTPUT_ICOUNT_PNG = SCRIPT_DIR / "results-icount.png"

ARCH_CONFIG = CONFIG_DIR / "archs.json"


METRIC_INFO = {
    "text_bytes": {
        "title": ".text section size",
        "fmt": "+.1f",
    },
    "instruction_count": {
        "title": "Instruction count",
        "fmt": "+.1f",
    },
    "bytes_per_instruction": {
        "title": "Bytes per instruction",
        "fmt": "+.1f",
    },
}


def load_arch_config(path: Path) -> tuple[dict[str, str], list[tuple[str, list[str]]], str | None]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    labels: dict[str, str] = {}
    groups: list[tuple[str, list[str]]] = []
    for group in data["groups"]:
        arch_ids = []
        for arch in group["archs"]:
            labels[arch["id"]] = arch["label"]
            arch_ids.append(arch["id"])
        groups.append((group["label"], arch_ids))

    return labels, groups, data.get("normalize_to")


def load_workloads(workloads_dir: Path) -> list[tuple[str, str]]:
    workloads = []
    for config in sorted(workloads_dir.glob("*/workload.json")):
        with open(config, "r", encoding="utf-8") as f:
            data = json.load(f)
        workloads.append((data["id"], data["label"]))
    return workloads


def load_results(path: Path) -> list[dict]:
    rows = []
    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["text_bytes"] = int(row["text_bytes"])
            row["instruction_count"] = int(row["instruction_count"])
            row["bytes_per_instruction"] = float(row["bytes_per_instruction"])
            rows.append(row)
    return rows


def build_metric_table(
    rows: list[dict],
    metric: str,
    normalize_to: str | None = None,
) -> dict[str, dict[str, float]]:
    raw: dict[str, dict[str, float]] = defaultdict(dict)

    for row in rows:
        raw[row["workload"]][row["arch"]] = float(row[metric])

    if normalize_to is None:
        return raw

    normalized: dict[str, dict[str, float]] = defaultdict(dict)
    for workload, arch_map in raw.items():
        base = arch_map.get(normalize_to)
        if base is None or base == 0:
            continue
        for arch, value in arch_map.items():
            normalized[workload][arch] = value / base

    return normalized


def existing_arches(rows: list[dict], arch_groups: list[tuple[str, list[str]]]) -> list[str]:
    present = {row["arch"] for row in rows}
    ordered = [arch for _, group in arch_groups for arch in group if arch in present]
    extras = sorted(present - set(ordered))
    return ordered + extras


def build_matrix(
    rows: list[dict],
    metric: str,
    arch_groups: list[tuple[str, list[str]]],
    workloads: list[tuple[str, str]],
    normalize_to: str | None,
) -> tuple[np.ndarray, list[str], list[str], list[tuple[str, int, int]], bool]:
    table = build_metric_table(rows, metric, normalize_to=normalize_to)
    arches = existing_arches(rows, arch_groups)

    matrix = np.full((len(arches), len(workloads)), np.nan, dtype=float)
    for row_idx, arch in enumerate(arches):
        for col_idx, (workload_id, _) in enumerate(workloads):
            value = table.get(workload_id, {}).get(arch)
            if value is not None and not math.isnan(value):
                if normalize_to is not None:
                    matrix[row_idx, col_idx] = (value - 1.0) * 100.0
                else:
                    matrix[row_idx, col_idx] = value

    labels = [arch for _, arch in workloads]
    arch_labels = arches

    group_spans: list[tuple[str, int, int]] = []
    pos = 0
    present_set = set(arches)
    for group_label, group_arches in arch_groups:
        present_in_group = [a for a in group_arches if a in present_set]
        if not present_in_group:
            continue
        start = pos
        end = pos + len(present_in_group) - 1
        group_spans.append((group_label, start, end))
        pos += len(present_in_group)

    return matrix, arch_labels, labels, group_spans, normalize_to is not None


def metric_range(matrix: np.ndarray) -> tuple[float, float]:
    finite = matrix[np.isfinite(matrix)]
    if finite.size == 0:
        return -1.0, 1.0

    bound = float(np.nanmax(np.abs(finite)))
    if bound == 0:
        bound = 1.0
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
                ax.text(col, row, "–", ha="center", va="center", fontsize=10, alpha=0.5)
                continue

            text = f"{format(value, fmt)}%"
            ax.text(col, row, text, ha="center", va="center", fontsize=10)


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
    ax.set_yticklabels([pretty_arch_labels.get(a, a) for a in arch_labels])

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
    arch_labels: dict[str, str],
    arch_groups: list[tuple[str, list[str]]],
    workloads: list[tuple[str, str]],
    metric: str,
    normalize_to: str | None,
) -> None:
    matrix, arches, workload_labels, group_spans, normalized = build_matrix(
        rows, metric, arch_groups, workloads, normalize_to
    )

    height = max(4.5, 0.52 * len(arches) + 1.4)
    width = max(6.0, 1.4 * len(workload_labels) + 3.6)

    fig, ax = plt.subplots(figsize=(width, height))
    fig.subplots_adjust(left=0.22, right=0.88)
    plot_heatmap(ax, matrix, arches, workload_labels, group_spans, arch_labels, metric, normalized)

    baseline_text = f"Baseline: {arch_labels.get(normalize_to, normalize_to)}" if normalized and normalize_to else None
    if baseline_text:
        fig.suptitle(baseline_text, fontsize=12, y=0.98)

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

    arch_labels, arch_groups, normalize_to = load_arch_config(ARCH_CONFIG)
    workloads = load_workloads(WORKLOADS_DIR)

    rows = load_results(INPUT_CSV)
    if not rows:
        raise RuntimeError("results.csv is empty")

    for output, metric in [
        (OUTPUT_TEXT_SIZE_PNG, "text_bytes"),
        (OUTPUT_BPI_PNG, "bytes_per_instruction"),
        (OUTPUT_ICOUNT_PNG, "instruction_count"),
    ]:
        plot_metric(
            rows,
            output,
            arch_labels=arch_labels,
            arch_groups=arch_groups,
            workloads=workloads,
            metric=metric,
            normalize_to=normalize_to,
        )


if __name__ == "__main__":
    main()
