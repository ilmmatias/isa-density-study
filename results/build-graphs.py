#!/usr/bin/env python3

import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


SCRIPT_DIR = Path(__file__).parent.resolve()
REPO_ROOT = SCRIPT_DIR.parent

CONFIG_DIR = REPO_ROOT / "config"
WORKLOADS_DIR = REPO_ROOT / "workloads"

INPUT_CSV = SCRIPT_DIR / "results.csv"
OUTPUT_TEXT_SIZE_PNG = SCRIPT_DIR / "results-text-size.png"
OUTPUT_BPI_PNG = SCRIPT_DIR / "results-bpi.png"
OUTPUT_ICOUNT_PNG = SCRIPT_DIR / "results-icount.png"

ARCH_CONFIG = CONFIG_DIR / "archs.json"


def load_arch_config(path: Path) -> tuple[dict[str, str], list[tuple[str, list[str]]], str | None]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    labels = {}
    groups = []
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

def load_results(path: str) -> list[dict]:
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
    normalize_to: str | None = None
) -> dict[str, dict[str, float]]:
    raw: dict[str, dict[str, float]] = defaultdict(dict)

    for row in rows:
        workload = row["workload"]
        arch = row["arch"]
        raw[workload][arch] = float(row[metric])

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


def existing_arches(
    rows: list[dict],
    arch_groups: list[tuple[str, list[str]]]
) -> list[str]:
    present = {row["arch"] for row in rows}
    ordered = [arch for _, group in arch_groups for arch in group if arch in present]
    extras = sorted(present - set(ordered))
    return ordered + extras


def plot_metric(
    rows: list[dict],
    output_path: Path,
    arch_labels: dict[str, str],
    arch_groups: list[tuple[str, list[str]]],
    workloads: list[tuple[str, str]],
    metric: str = "text_bytes",
    normalize_to: str | None = None,
) -> None:
    table = build_metric_table(rows, metric, normalize_to=normalize_to)
    arches = existing_arches(rows, arch_groups)
    labels = [arch_labels.get(arch, arch) for arch in arches]

    x = np.arange(len(arches))
    width = 0.24

    plt.rcParams.update({
        "font.size": 13,
        "axes.titlesize": 16,
        "axes.labelsize": 14,
        "xtick.labelsize": 12,
        "ytick.labelsize": 12,
        "legend.fontsize": 12,
        "legend.title_fontsize": 12,
    })

    fig, ax = plt.subplots(figsize=(14, 7))
    max_value = 0.0

    for i, (workload_id, workload_label) in enumerate(workloads):
        values = []
        for arch in arches:
            value = table.get(workload_id, {}).get(arch)
            values.append(value if value is not None else math.nan)
            if value is not None and not math.isnan(value):
                max_value = max(max_value, value)

        offset = (i - (len(workloads) - 1) / 2) * width
        ax.bar(x + offset, values, width, label=workload_label, zorder=3)

    if metric == "text_bytes":
        ylabel = ".text section size"
    elif metric == "instruction_count":
        ylabel = "Instruction count"
    elif metric == "bytes_per_instruction":
        ylabel = "Bytes per instruction"
    else:
        ylabel = metric

    if normalize_to is not None:
        ylabel += " (normalized)"
    elif metric == "text_bytes":
        ylabel += " (bytes)"

    ax.set_ylabel(ylabel)
    ax.set_xlabel("Architecture")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)

    present_set = set(arches)
    pos = 0
    for group_label, group_arches in arch_groups:
        present_in_group = [a for a in group_arches if a in present_set]
        if not present_in_group:
            continue

        if pos > 0:
            ax.axvline(x=pos - 0.5, linestyle="--", linewidth=1,
                       alpha=0.35, zorder=1)

        start = arches.index(present_in_group[0])
        end = arches.index(present_in_group[-1])
        ax.text((start + end) / 2, 1.02, group_label,
                transform=ax.get_xaxis_transform(),
                ha="center", va="bottom", fontsize=12)

        pos += len(present_in_group)

    ax.grid(axis="y", alpha=0.25, zorder=0)
    ax.legend(title="Workload", loc="upper left", frameon=True)

    if max_value > 0:
        ax.set_ylim(0, max_value * (1.12 if normalize_to is not None else 1.08))

    ax.margins(x=0.03)
    fig.tight_layout()
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    arch_labels, arch_groups, normalize_to = load_arch_config(ARCH_CONFIG)
    workloads = load_workloads(WORKLOADS_DIR)

    rows = load_results(INPUT_CSV)
    if not rows:
        raise RuntimeError("results.csv is empty")

    for output, metric in [
        (OUTPUT_TEXT_SIZE_PNG, "text_bytes"),
        (OUTPUT_BPI_PNG,       "bytes_per_instruction"),
        (OUTPUT_ICOUNT_PNG,    "instruction_count"),
    ]:
        plot_metric(
            rows, output,
            arch_labels=arch_labels,
            arch_groups=arch_groups,
            workloads=workloads,
            metric=metric,
            normalize_to=normalize_to,
        )


if __name__ == "__main__":
    main()
