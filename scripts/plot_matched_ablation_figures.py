#!/usr/bin/env python3
"""Generate thesis figures from the audited matched-ablation metric summary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
MODES = ("secure_rag_mode", "sensitivity_eval_mode")
MODE_LABELS = ("Secure mode", "Sensitivity-evaluation mode")
ARMS = ("guards_off", "guards_on")
ARM_LABELS = ("Guards off", "Guards on")
ATTACK_LABELS = {
    "A01": "A01 direct-cell leakage",
    "A02": "A02 policy-aware leakage",
    "A03": "A03 post-downgrade leakage",
    "A04": "A04 relation-edge leakage",
    "A05": "A05 protected-record existence confirmation",
    "A06": "A06 poisoned-row integrity",
    "A07": "A07-N natural validation leakage",
    "A08": "A08 retrieval-framed numeric leakage",
}
STAGE_FIELDS = {
    "A01": ("model_visible_exposure", "Model-visible exposure", "guard_triggered"),
    "A02": ("model_visible_exposure", "Model-visible exposure", "guard_triggered"),
    "A03": ("state_exposure_after_role_change", "State exposure", "guard_triggered"),
    "A04": ("model_visible_exposure", "Model-visible exposure", None),
    "A05": ("retrieval_exposure", "Retrieval exposure", "answer_replaced"),
    "A06": ("model_visible_exposure", "Model-visible protected exposure", "guard_checked"),
    "A07": ("model_visible_exposure", "Model-visible protected exposure", None),
    "A08": ("retrieval_exposure", "Protected-target retrieval", "guard_triggered"),
}
RAW_FIELDS = {
    "A01": "raw_unsafe",
    "A02": "raw_unsafe",
    "A03": "raw_unsafe",
    "A04": "raw_unsafe",
    "A05": "raw_unsafe",
    "A06": "raw_integrity",
    "A07": "raw_unsafe",
    "A08": "raw_unsafe",
}
RAW_LABELS = {
    "A06": "Raw canary compliance",
}
PRIMARY_LABELS = {
    "A06": "Delivered canary compliance",
}
DIAGNOSTIC_ATTACKS = ("A01", "A02", "A03", "A04", "A05", "A08")
COLORS = {
    "off": "#c65f49",
    "on": "#3274a1",
    "utility_off": "#d9a441",
    "utility_on": "#4c9f70",
    "exposure": "#7a6fac",
    "raw": "#d17c37",
    "delivered": "#b43c39",
    "action": "#417f8a",
}


def load(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def annotate(
    ax: plt.Axes,
    bars: Any,
    denominators: list[int],
    *,
    rotation: int = 0,
) -> None:
    for bar, denominator in zip(bars, denominators):
        value = int(round(bar.get_height()))
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max(1.5, ax.get_ylim()[1] * 0.015),
            f"{value}/{denominator}",
            ha="center",
            va="bottom",
            fontsize=8,
            rotation=rotation,
        )


def attack_figure(
    attack: str, metrics: dict[str, Any], output_dir: Path
) -> dict[str, Any]:
    fig = plt.figure(figsize=(8.4, 7.1))
    grid = fig.add_gridspec(2, 2, height_ratios=(1.0, 1.12), hspace=0.48)
    axes = [
        fig.add_subplot(grid[0, 0]),
        fig.add_subplot(grid[0, 1]),
        fig.add_subplot(grid[1, :]),
    ]
    x = np.arange(2)
    width = 0.34

    off_primary = [
        metrics[attack]["guards_off"][mode]["primary"] for mode in MODES
    ]
    on_primary = [
        metrics[attack]["guards_on"][mode]["primary"] for mode in MODES
    ]
    unauth_n = [
        metrics[attack]["guards_off"][mode]["unauthorised_n"] for mode in MODES
    ]
    bars_off = axes[0].bar(
        x - width / 2, off_primary, width, label="Guards off", color=COLORS["off"]
    )
    bars_on = axes[0].bar(
        x + width / 2, on_primary, width, label="Guards on", color=COLORS["on"]
    )
    axes[0].set_title(
        f"A. {PRIMARY_LABELS.get(attack, 'Primary unauthorised outcome')}"
    )
    axes[0].set_xticks(x, ("Secure", "Sensitivity eval."))
    axes[0].set_ylabel("Conversations")
    axes[0].set_ylim(0, max(165, max(off_primary + on_primary, default=0) * 1.18 + 5))
    annotate(axes[0], bars_off, unauth_n)
    annotate(axes[0], bars_on, unauth_n)
    axes[0].legend(frameon=False, fontsize=8, loc="upper right")

    off_utility = [
        metrics[attack]["guards_off"][mode]["positive_control"] for mode in MODES
    ]
    on_utility = [
        metrics[attack]["guards_on"][mode]["positive_control"] for mode in MODES
    ]
    positive_n = [
        metrics[attack]["guards_off"][mode]["positive_control_n"] for mode in MODES
    ]
    utility_off = axes[1].bar(
        x - width / 2,
        off_utility,
        width,
        label="Guards off",
        color=COLORS["utility_off"],
    )
    utility_on = axes[1].bar(
        x + width / 2,
        on_utility,
        width,
        label="Guards on",
        color=COLORS["utility_on"],
    )
    axes[1].set_title("B. Authorised positive-control task success")
    axes[1].set_xticks(x, ("Secure", "Sensitivity eval."))
    axes[1].set_ylim(0, max(83, max(off_utility + on_utility, default=0) * 1.18 + 3))
    annotate(axes[1], utility_off, positive_n)
    annotate(axes[1], utility_on, positive_n)
    axes[1].legend(frameon=False, fontsize=8, loc="lower right")

    exposure_field, exposure_label, action_field = STAGE_FIELDS[attack]
    raw_field = RAW_FIELDS[attack]
    stage_labels = [
        exposure_label,
        RAW_LABELS.get(attack, "Raw unsafe output"),
        PRIMARY_LABELS.get(attack, "Delivered unsafe outcome"),
    ]
    off_stage = [
        metrics[attack]["guards_off"]["sensitivity_eval_mode"].get(exposure_field, 0),
        metrics[attack]["guards_off"]["sensitivity_eval_mode"].get(raw_field, 0),
        metrics[attack]["guards_off"]["sensitivity_eval_mode"].get("primary", 0),
    ]
    on_stage = [
        metrics[attack]["guards_on"]["sensitivity_eval_mode"].get(exposure_field, 0),
        metrics[attack]["guards_on"]["sensitivity_eval_mode"].get(raw_field, 0),
        metrics[attack]["guards_on"]["sensitivity_eval_mode"].get("primary", 0),
    ]
    if attack == "A06":
        stage_labels.append("Delivered secret leakage")
        off_stage.append(
            metrics[attack]["guards_off"]["sensitivity_eval_mode"].get(
                "confidentiality_leak", 0
            )
        )
        on_stage.append(
            metrics[attack]["guards_on"]["sensitivity_eval_mode"].get(
                "confidentiality_leak", 0
            )
        )
    if action_field:
        stage_labels.append("Guard action")
        off_stage.append(
            metrics[attack]["guards_off"]["sensitivity_eval_mode"].get(
                action_field, 0
            )
        )
        on_stage.append(
            metrics[attack]["guards_on"]["sensitivity_eval_mode"].get(
                action_field, 0
            )
        )
    sx = np.arange(len(stage_labels))
    stage_off = axes[2].bar(
        sx - width / 2, off_stage, width, label="Guards off", color=COLORS["off"]
    )
    stage_on = axes[2].bar(
        sx + width / 2, on_stage, width, label="Guards on", color=COLORS["on"]
    )
    axes[2].set_title("C. Sensitivity-mode stages")
    axes[2].set_xticks(sx, stage_labels, rotation=12, ha="right")
    axes[2].set_ylim(0, max(165, max(off_stage + on_stage, default=0) * 1.15 + 5))
    sens_n = metrics[attack]["guards_off"]["sensitivity_eval_mode"][
        "unauthorised_n"
    ]
    annotate(
        axes[2],
        stage_off,
        [sens_n] * len(stage_labels),
        rotation=90,
    )
    annotate(
        axes[2],
        stage_on,
        [sens_n] * len(stage_labels),
        rotation=90,
    )
    axes[2].legend(frameon=False, fontsize=8, loc="upper right")

    for ax in axes:
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", color="#dddddd", linewidth=0.6, alpha=0.8)
        ax.set_axisbelow(True)
    fig.suptitle(f"{ATTACK_LABELS[attack]}: matched guard ablation", fontsize=12)
    fig.subplots_adjust(top=0.91, left=0.09, right=0.98, bottom=0.12)
    stem = output_dir / f"{attack.lower()}_matched_guard_ablation"
    fig.savefig(stem.with_suffix(".pdf"), bbox_inches="tight")
    fig.savefig(stem.with_suffix(".png"), dpi=180, bbox_inches="tight")
    plt.close(fig)
    return {
        "attack": attack,
        "pdf": str(stem.with_suffix(".pdf")),
        "png": str(stem.with_suffix(".png")),
        "source_values": {
            "off_primary": off_primary,
            "on_primary": on_primary,
            "off_utility": off_utility,
            "on_utility": on_utility,
            "off_stage": off_stage,
            "on_stage": on_stage,
        },
    }


def cross_attack_heatmap(metrics: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    # A06 has separate integrity and confidentiality outcomes and is therefore
    # kept out of this one-outcome-per-row heat map.  Its individual figure
    # displays both outcomes without designating either as a substitute.
    attacks = [attack for attack in ATTACK_LABELS if attack != "A06"]
    columns = [
        ("guards_off", "secure_rag_mode", "Secure\nguards off"),
        ("guards_on", "secure_rag_mode", "Secure\nguards on"),
        ("guards_off", "sensitivity_eval_mode", "Sensitivity\nguards off"),
        ("guards_on", "sensitivity_eval_mode", "Sensitivity\nguards on"),
    ]
    matrix = np.array(
        [
            [metrics[attack][arm][mode]["primary"] for arm, mode, _ in columns]
            for attack in attacks
        ]
    )
    fig, ax = plt.subplots(figsize=(7.5, 5.4))
    image = ax.imshow(matrix, cmap="YlOrRd", vmin=0, vmax=150, aspect="auto")
    ax.set_xticks(range(len(columns)), [label for _, _, label in columns])
    ax.set_yticks(range(len(attacks)), [ATTACK_LABELS[a] for a in attacks])
    for row in range(matrix.shape[0]):
        for col in range(matrix.shape[1]):
            ax.text(
                col,
                row,
                f"{matrix[row, col]}/150",
                ha="center",
                va="center",
                color="white" if matrix[row, col] > 85 else "black",
                fontsize=9,
            )
    ax.set_title("Matched-ablation selected delivered outcomes (A06 separate)")
    cbar = fig.colorbar(image, ax=ax, pad=0.02)
    cbar.set_label("Attack-specific selected outcome count")
    fig.tight_layout()
    stem = output_dir / "cross_attack_matched_guard_ablations"
    fig.savefig(stem.with_suffix(".pdf"), bbox_inches="tight")
    fig.savefig(stem.with_suffix(".png"), dpi=180, bbox_inches="tight")
    plt.close(fig)
    return {
        "pdf": str(stem.with_suffix(".pdf")),
        "png": str(stem.with_suffix(".png")),
        "matrix": matrix.tolist(),
    }


def historical_vs_off(
    metrics: dict[str, Any],
    historical: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    attacks = list(DIAGNOSTIC_ATTACKS)
    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.2), sharey=True)
    values: dict[str, Any] = {}
    x = np.arange(len(attacks))
    width = 0.36
    for ax, mode, mode_label in zip(axes, MODES, MODE_LABELS):
        baseline = [historical[a][mode]["primary"] for a in attacks]
        guards_off = [metrics[a]["guards_off"][mode]["primary"] for a in attacks]
        values[mode] = {"historical": baseline, "guards_off": guards_off}
        b1 = ax.bar(
            x - width / 2,
            baseline,
            width,
            label="Historical original baseline",
            color="#777777",
        )
        b2 = ax.bar(
            x + width / 2,
            guards_off,
            width,
            label="Matched guards off",
            color=COLORS["off"],
        )
        ax.set_title(mode_label)
        ax.set_xticks(x, attacks)
        ax.set_ylim(0, 170)
        annotate(ax, b1, [150] * len(attacks))
        annotate(ax, b2, [150] * len(attacks))
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", color="#dddddd", linewidth=0.6)
        ax.set_axisbelow(True)
    axes[0].set_ylabel("Attack-specific primary outcome count")
    axes[1].legend(frameon=False, fontsize=8, loc="upper right")
    fig.suptitle("Diagnostic comparison: historical baseline and matched guards-off arm")
    fig.tight_layout()
    stem = output_dir / "historical_baseline_vs_matched_guards_off"
    fig.savefig(stem.with_suffix(".pdf"), bbox_inches="tight")
    fig.savefig(stem.with_suffix(".png"), dpi=180, bbox_inches="tight")
    plt.close(fig)
    return {
        "pdf": str(stem.with_suffix(".pdf")),
        "png": str(stem.with_suffix(".png")),
        "values": values,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metric-summary", type=Path, required=True)
    parser.add_argument(
        "--historical-metrics",
        type=Path,
        default=ROOT / "outputs/final_thesis_evidence_20260725/metrics.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "thesis/figures/results",
    )
    parser.add_argument("--validation-output", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    metric_document = load(args.metric_summary)
    metrics = metric_document["metrics"]
    historical = load(args.historical_metrics)["descriptive_baseline"]
    generated = [
        attack_figure(attack, metrics, args.output_dir)
        for attack in ATTACK_LABELS
    ]
    cross = cross_attack_heatmap(metrics, args.output_dir)
    diagnostic = historical_vs_off(metrics, historical, args.output_dir)
    args.validation_output.write_text(
        json.dumps(
            {
                "metric_summary": str(args.metric_summary),
                "historical_metrics": str(args.historical_metrics),
                "attack_figures": generated,
                "cross_attack": cross,
                "historical_vs_guards_off": diagnostic,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
