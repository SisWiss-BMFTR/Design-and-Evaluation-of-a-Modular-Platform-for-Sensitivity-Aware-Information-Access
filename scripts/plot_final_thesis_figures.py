#!/usr/bin/env python3
"""Generate the final thesis figures from the traceable evidence JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "outputs/final_thesis_evidence_20260725/metrics.json"
OUT = ROOT / "thesis/figures/results"

SECURE = "#4472C4"
SENSITIVITY = "#ED7D31"
SECURITY = "#C44E52"
EXPOSURE = "#8C8C8C"
UTILITY = "#55A868"
GUARD_ON = "#2A9D8F"
GUARD_OFF = "#9E9E9E"
INTEGRITY = "#8172B2"


def load() -> dict[str, Any]:
    with EVIDENCE.open(encoding="utf-8") as handle:
        return json.load(handle)


def style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.labelsize": 9,
            "legend.fontsize": 8,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.dpi": 160,
            "savefig.bbox": "tight",
        }
    )


def save(fig: plt.Figure, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}.pdf")
    fig.savefig(OUT / f"{name}.png", dpi=220)
    plt.close(fig)


def annotate(ax: plt.Axes, bars: Iterable[Any], denominator: int) -> None:
    for bar in bars:
        value = int(round(bar.get_height()))
        ax.annotate(
            f"{value}/{denominator}",
            (bar.get_x() + bar.get_width() / 2, bar.get_height()),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=8,
        )


def source_note(fig: plt.Figure, text: str) -> None:
    fig.text(0.01, 0.005, text, ha="left", va="bottom", fontsize=6.5, color="#555555")


def two_mode_stages(
    data: dict[str, Any],
    attack: str,
    stages: list[tuple[str, str]],
    title: str,
    name: str,
) -> None:
    modes = ["secure_rag_mode", "sensitivity_eval_mode"]
    labels = ["Secure mode", "Sensitivity-evaluation mode"]
    x = np.arange(len(labels))
    width = 0.72 / len(stages)
    fig, ax = plt.subplots(figsize=(6.8, 3.6))
    for index, (field, label) in enumerate(stages):
        values = [data[attack][mode].get(field, 0) for mode in modes]
        positions = x - 0.36 + width / 2 + index * width
        bars = ax.bar(
            positions,
            values,
            width,
            label=label,
            color=[EXPOSURE, SECURITY, INTEGRITY, UTILITY][index % 4],
        )
        annotate(ax, bars, 150)
    ax.set_xticks(x, labels)
    ax.set_ylim(0, 170)
    ax.set_ylabel("Unauthorised conversations")
    ax.set_title(title)
    ax.legend(frameon=False, ncol=min(len(stages), 3), loc="upper center")
    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    source_note(fig, "Source: generated evidence ledger; original attack-family-label-free baseline JSON.")
    save(fig, name)


def plot_a02(data: dict[str, Any]) -> None:
    baseline = data["descriptive_baseline"]["A02"]
    modes = ["secure_rag_mode", "sensitivity_eval_mode"]
    labels = ["Secure mode", "Sensitivity-evaluation mode"]
    partial = np.array([baseline[mode]["partial"] for mode in modes])
    full = np.array([baseline[mode]["full"] for mode in modes])
    x = np.arange(2)
    fig, ax = plt.subplots(figsize=(6.8, 3.7))
    bars_partial = ax.bar(x, partial, 0.55, color=SECURITY, label="Partial policy-aware reconstruction")
    bars_full = ax.bar(x, full, 0.55, bottom=partial, color=INTEGRITY, label="Full policy-aware reconstruction")
    for index, total in enumerate(partial + full):
        ax.text(index, total + 4, f"{int(total)}/150", ha="center", fontsize=8)
    for index, value in enumerate(full):
        if value:
            ax.text(index, partial[index] + value / 2, f"{int(value)} full", ha="center", va="center", color="white", fontsize=8)
    ax.set_xticks(x, labels)
    ax.set_ylim(0, 145)
    ax.set_ylabel("Unauthorised conversations")
    ax.set_title("A02 policy-aware delivered row reconstruction")
    ax.legend(frameon=False, loc="upper left")
    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    source_note(fig, "Source: A02 policy-aware rescoring v1 of original baseline JSON; raw pre-delivery answers were not logged.")
    save(fig, "a02_policy_aware_reconstruction")


def plot_a04(data: dict[str, Any]) -> None:
    baseline = data["descriptive_baseline"]["A04"]
    modes = ["secure_rag_mode", "sensitivity_eval_mode"]
    labels = ["Secure mode", "Sensitivity-evaluation mode"]
    x = np.arange(2)
    width = 0.34
    fig, ax = plt.subplots(figsize=(6.8, 3.6))
    nodes = ax.bar(x - width / 2, [baseline[m]["node"] for m in modes], width, color=EXPOSURE, label="Protected node disclosed")
    edges = ax.bar(x + width / 2, [baseline[m]["primary"] for m in modes], width, color=SECURITY, label="Complete relation edge disclosed")
    annotate(ax, nodes, 150)
    annotate(ax, edges, 150)
    ax.set_xticks(x, labels)
    ax.set_ylim(0, 170)
    ax.set_ylabel("Unauthorised conversations")
    ax.set_title("A04 delivered relation-structure leakage")
    ax.legend(frameon=False, loc="upper left")
    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    source_note(fig, "Source: original attack-family-label-free baseline JSON; node and complete-edge outcomes are distinct.")
    save(fig, "a04_relation_structure")


def plot_a05(data: dict[str, Any]) -> None:
    baseline = data["descriptive_baseline"]["A05"]
    modes = ["secure_rag_mode", "sensitivity_eval_mode"]
    labels = ["Secure mode", "Sensitivity-evaluation mode"]
    fig, ax = plt.subplots(figsize=(6.8, 3.6))
    bars = ax.bar(
        labels,
        [baseline[mode]["primary"] for mode in modes],
        color=[SECURE, SENSITIVITY],
        width=0.58,
    )
    annotate(ax, bars, 150)
    ax.set_title("A05 original-baseline membership confirmation")
    ax.set_ylabel("Unauthorised conversations")
    ax.set_ylim(0, 170)
    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    source_note(fig, "Source: original attack-family-label-free baseline JSON.")
    save(fig, "a05_membership_baseline")


def plot_a06(data: dict[str, Any]) -> None:
    baseline = data["descriptive_baseline"]["A06"]
    modes = ["secure_rag_mode", "sensitivity_eval_mode"]
    labels = ["Secure mode", "Sensitivity-evaluation mode"]
    x = np.arange(2)
    width = 0.34
    fig, ax = plt.subplots(figsize=(6.8, 3.6))
    canary = ax.bar(x - width / 2, [baseline[m]["canary"] for m in modes], width, color=INTEGRITY, label="Canary compliance (integrity)")
    secret = ax.bar(x + width / 2, [baseline[m]["primary"] for m in modes], width, color=SECURITY, label="Protected-value leakage (confidentiality)")
    annotate(ax, canary, 150)
    annotate(ax, secret, 150)
    ax.set_xticks(x, labels)
    ax.set_ylim(0, 20)
    ax.set_ylabel("Unauthorised conversations")
    ax.set_title("A06 integrity and confidentiality outcomes")
    ax.legend(frameon=False, loc="upper left")
    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    source_note(fig, "Source: original attack-family-label-free baseline JSON; the two outcome classes are not combined.")
    save(fig, "a06_integrity_confidentiality")


def plot_a07(data: dict[str, Any]) -> None:
    baseline = data["descriptive_baseline"]["A07"]
    modes = ["secure_rag_mode", "sensitivity_eval_mode"]
    labels = ["Secure mode", "Sensitivity-evaluation mode"]
    x = np.arange(2)
    width = 0.34
    fig, axes = plt.subplots(1, 2, figsize=(8.6, 3.8))
    canary = axes[0].bar(x - width / 2, [baseline[m]["primary"] for m in modes], width, color=INTEGRITY, label="Canary compliance (integrity)")
    leakage = axes[0].bar(x + width / 2, [baseline[m]["confidentiality"] for m in modes], width, color=SECURITY, label="Protected-value leakage")
    annotate(axes[0], canary, 150)
    annotate(axes[0], leakage, 150)
    axes[0].set_xticks(x, labels)
    axes[0].set_ylim(0, 205)
    axes[0].set_ylabel("Unauthorised conversations")
    axes[0].set_title("Security outcomes (denominator 150)")
    axes[0].legend(frameon=False, loc="upper center")
    axes[0].grid(axis="y", alpha=0.2)

    utility = axes[1].bar(x, [baseline[m]["positive_control"] for m in modes], 0.5, color=UTILITY)
    annotate(axes[1], utility, 75)
    axes[1].set_xticks(x, labels)
    axes[1].set_ylim(0, 88)
    axes[1].set_ylabel("Protected conversations")
    axes[1].set_title("Authorised positive-control task success (denominator 75)")
    axes[1].grid(axis="y", alpha=0.2)
    fig.suptitle("A07 original-baseline integrity, confidentiality, and positive-control outcome")
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    source_note(fig, "Source: original attack-family-label-free synthetic-trigger baseline JSON.")
    save(fig, "a07_baseline_integrity_confidentiality_utility")


def plot_guard_paths(data: dict[str, Any]) -> None:
    corrected = data["correction_runs_as_recorded"]
    labels = ["A01 secure", "A01 sensitivity", "A05 secure", "A05 sensitivity", "A07-S secure", "A07-S sensitivity"]
    pre_refusal = [
        corrected["A01"]["post_hardening"]["secure_rag_mode"]["pre_retrieval_refusal"],
        corrected["A01"]["post_hardening"]["sensitivity_eval_mode"]["pre_retrieval_refusal"],
        corrected["A05"]["post_hardening"]["secure_rag_mode"]["pre_retrieval_refusals"],
        corrected["A05"]["post_hardening"]["sensitivity_eval_mode"]["pre_retrieval_refusals"],
        corrected["A07-S"]["post_hardening"]["secure_rag_mode"]["pre_retrieval_refusal"],
        corrected["A07-S"]["post_hardening"]["sensitivity_eval_mode"]["pre_retrieval_refusal"],
    ]
    membership = [
        corrected["A01"]["post_hardening"]["secure_rag_mode"]["answer_replaced"],
        corrected["A01"]["post_hardening"]["sensitivity_eval_mode"]["answer_replaced"],
        corrected["A05"]["post_hardening"]["secure_rag_mode"]["guard_replacements"],
        corrected["A05"]["post_hardening"]["sensitivity_eval_mode"]["guard_replacements"],
        corrected["A07-S"]["post_hardening"]["secure_rag_mode"]["membership_guard_replacement"],
        corrected["A07-S"]["post_hardening"]["sensitivity_eval_mode"]["membership_guard_replacement"],
    ]
    verifier_or_quarantine = [
        corrected["A01"]["post_hardening"]["secure_rag_mode"]["output_verifier_replacement"],
        corrected["A01"]["post_hardening"]["sensitivity_eval_mode"]["output_verifier_replacement"],
        0,
        0,
        corrected["A07-S"]["post_hardening"]["secure_rag_mode"]["prompt_injection_quarantine"],
        corrected["A07-S"]["post_hardening"]["sensitivity_eval_mode"]["prompt_injection_quarantine"],
    ]
    y = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(8.2, 4.1))
    ax.barh(y, pre_refusal, color=SECURE, label="Pre-retrieval refusal")
    ax.barh(y, membership, left=pre_refusal, color=GUARD_ON, label="Membership-guard replacement")
    left = np.array(pre_refusal) + np.array(membership)
    ax.barh(y, verifier_or_quarantine, left=left, color=INTEGRITY, label="Output verifier / injection quarantine")
    for index, (pre, member, other) in enumerate(zip(pre_refusal, membership, verifier_or_quarantine)):
        ax.text(pre + member + other + 3, index, f"{pre}, {member}, {other}", va="center", fontsize=7.5)
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.set_xlim(0, 320)
    ax.set_xlabel("Recorded guard events (not mutually exclusive)")
    ax.set_title("Observed guard paths in matched guards-on runs")
    ax.legend(frameon=False, ncol=3, loc="lower center", bbox_to_anchor=(0.5, -0.28))
    ax.grid(axis="x", alpha=0.2)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    source_note(fig, "Source: correction telemetry. Labels after each row give pre-refusal, membership replacement, other guard.")
    save(fig, "guard_path_telemetry")


def plot_cross_baseline(data: dict[str, Any]) -> None:
    baseline = data["descriptive_baseline"]
    attacks = [f"A0{i}" for i in range(1, 9)]
    secure = [baseline[a]["secure_rag_mode"]["primary"] for a in attacks]
    sensitivity = [baseline[a]["sensitivity_eval_mode"]["primary"] for a in attacks]
    x = np.arange(8)
    width = 0.38
    fig, ax = plt.subplots(figsize=(9.0, 4.0))
    first = ax.bar(x - width / 2, secure, width, color=SECURE, label="Secure mode")
    second = ax.bar(x + width / 2, sensitivity, width, color=SENSITIVITY, label="Sensitivity-evaluation mode")
    for bars in (first, second):
        for bar in bars:
            value = int(round(bar.get_height()))
            ax.annotate(
                f"{value}",
                (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                xytext=(0, 3),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=8,
            )
    ax.set_xticks(x, attacks)
    ax.set_ylim(0, 160)
    ax.set_yticks([0, 25, 50, 75, 100, 125, 150])
    ax.axhline(150, color="#555555", linewidth=0.8, linestyle="--", alpha=0.7)
    ax.set_ylabel("Attack-specific outcomes (of 150)")
    ax.legend(frameon=False, ncol=2, loc="upper center", bbox_to_anchor=(0.5, 1.12))
    ax.grid(axis="y", alpha=0.2)
    ax.text(
        0.5,
        -0.21,
        "Metrics differ by attack: delivered confidentiality (A01–A03, A06, A08), relation edge (A04), "
        "membership confirmation (A05), and canary compliance (A07).",
        transform=ax.transAxes,
        ha="center",
        va="top",
        fontsize=7.5,
    )
    fig.tight_layout(rect=(0, 0.09, 1, 0.93))
    source_note(fig, "Source: generated evidence ledger from the original attack-family-label-free baseline JSON.")
    save(fig, "cross_attack_descriptive_baseline")


def plot_cross_utility(data: dict[str, Any]) -> None:
    baseline = data["descriptive_baseline"]
    post = data["descriptive_hardened_package"]
    attacks = [f"A0{i}" for i in range(1, 9)]
    mode_names = [("secure_rag_mode", "Secure mode"), ("sensitivity_eval_mode", "Sensitivity-evaluation mode")]
    fig, axes = plt.subplots(2, 1, figsize=(9.0, 6.0), sharex=True)
    x = np.arange(8)
    width = 0.38
    for ax, (mode, title) in zip(axes, mode_names):
        pre_values = [baseline[a][mode]["positive_control"] for a in attacks]
        post_values = [post[a][mode]["positive_control"] for a in attacks]
        before = ax.bar(x - width / 2, pre_values, width, color=GUARD_OFF, label="Original baseline")
        after = ax.bar(x + width / 2, post_values, width, color=UTILITY, label="Hardened package")
        for bar in (before[6], after[6]):
            bar.set_hatch("///")
            bar.set_edgecolor("#333333")
        annotate(ax, before, 75)
        annotate(ax, after, 75)
        ax.axvline(5.5, color="#666666", linestyle="--", linewidth=0.9)
        ax.text(6, 94, "A07: different variants", ha="center", va="top", fontsize=7.5)
        ax.set_ylim(0, 98)
        ax.set_ylabel("Positive controls")
        ax.set_title(title)
        ax.grid(axis="y", alpha=0.2)
    axes[0].legend(frameon=False, ncol=2, loc="lower left")
    axes[1].set_xticks(x, attacks)
    fig.suptitle("Authorised positive-control task success (descriptive package evidence)")
    fig.tight_layout(rect=(0, 0.035, 1, 0.96))
    source_note(fig, "Sources: original baseline and hardened-package JSON. Hatched A07 bars use different attack variants and are not a direct pair.")
    save(fig, "cross_attack_utility")


def plot_package_comparisons(data: dict[str, Any]) -> None:
    baseline = data["descriptive_baseline"]
    post = data["descriptive_hardened_package"]
    attacks = ["A01", "A02", "A03", "A04", "A05", "A06", "A08"]
    labels = attacks
    x = np.arange(len(attacks))
    width = 0.38
    fig, axes = plt.subplots(2, 1, figsize=(8.5, 6.0), sharex=True)
    for ax, mode, title in (
        (axes[0], "secure_rag_mode", "Secure mode"),
        (axes[1], "sensitivity_eval_mode", "Sensitivity-evaluation mode"),
    ):
        before = ax.bar(x - width / 2, [baseline[a][mode]["primary"] for a in attacks], width, color=GUARD_OFF, label="Original baseline")
        after = ax.bar(x + width / 2, [post[a][mode]["primary"] for a in attacks], width, color=GUARD_ON, label="Hardened package")
        annotate(ax, before, 150)
        annotate(ax, after, 150)
        ax.set_ylim(0, 175)
        ax.set_ylabel("Primary outcomes")
        ax.set_title(title)
        ax.grid(axis="y", alpha=0.2)
    axes[0].legend(frameon=False, ncol=2)
    axes[1].set_xticks(x, labels)
    fig.suptitle("Descriptive package-level security outcomes")
    fig.tight_layout(rect=(0, 0.06, 1, 0.96))
    source_note(fig, "Source: original-baseline and hardened-package evidence ledger. Full comparability qualifications are given in the caption.")
    save(fig, "cross_attack_package_comparison")


def main() -> None:
    style()
    data = load()
    baseline = data["descriptive_baseline"]
    two_mode_stages(
        baseline,
        "A01",
        [("exposure", "Retrieval exposure"), ("primary", "Delivered confidentiality leakage")],
        "A01 exposure and delivered leakage",
        "a01_exposure_delivery",
    )
    plot_a02(data)
    two_mode_stages(
        baseline,
        "A03",
        [("exposure", "Retrieval exposure"), ("state_exposure", "Memory/state exposure"), ("primary", "Delivered leakage")],
        "A03 exposure and post-downgrade delivery",
        "a03_state_delivery",
    )
    plot_a04(data)
    plot_a05(data)
    plot_a06(data)
    plot_a07(data)
    two_mode_stages(
        baseline,
        "A08",
        [("exposure", "Target retrieval exposure"), ("primary", "Delivered numeric leakage")],
        "A08 embedding/rank probe exposure and delivery",
        "a08_exposure_delivery",
    )
    plot_cross_baseline(data)
    plot_cross_utility(data)
    plot_package_comparisons(data)
    print(OUT)


if __name__ == "__main__":
    main()
