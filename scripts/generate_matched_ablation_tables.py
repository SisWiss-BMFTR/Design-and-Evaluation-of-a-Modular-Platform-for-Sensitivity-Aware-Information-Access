#!/usr/bin/env python3
"""Generate compact LaTeX tables from audited matched-ablation artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MODES = ("secure_rag_mode", "sensitivity_eval_mode")
MODE_LABELS = {
    "secure_rag_mode": "Secure",
    "sensitivity_eval_mode": "Sensitivity evaluation",
}
ATTACK_NAMES = {
    "A01": "Direct Cell Extraction",
    "A02": "Multi-Turn Row Construction",
    "A03": "Access-Level Downgrade",
    "A04": "Relational Join-Path Inference",
    "A05": "Protected-Record Membership/Existence Probe",
    "A06": "Prompt Injection through a Poisoned Row",
    "A07": "Natural Backdoor/Validation Request (A07-N)",
    "A08": "Embedding/Rank-Framed Retrieval Probe",
}
INTERVENTIONS = {
    "A01": "Exact-value delivery verifier",
    "A02": "Structured restricted-field verifier",
    "A03": "Access-change state clearing",
    "A04": "Relation-access guard",
    "A05": "Membership guard",
    "A06": "Prompt-injection guard",
    "A07": "Relation-access guard",
    "A08": "Embedding-probe guard",
}
INTERNAL_FIELDS = {
    "A01": ("model_visible_exposure", "model-visible exposure"),
    "A02": ("model_visible_exposure", "model-visible restricted-field exposure"),
    "A03": ("state_exposure_after_role_change", "state exposure after role change"),
    "A04": ("model_visible_exposure", "model-visible relation exposure"),
    "A05": ("retrieval_exposure", "target retrieval exposure"),
    "A06": ("model_visible_exposure", "model-visible protected-value exposure"),
    "A07": ("model_visible_exposure", "model-visible protected-value exposure"),
    "A08": ("retrieval_exposure", "protected-target retrieval exposure"),
}
ACTION_FIELDS = {
    "A01": ("guard_triggered", "answer replacement"),
    "A02": ("guard_triggered", "verifier replacement"),
    "A03": ("guard_triggered", "state clearing"),
    "A04": (None, "not available"),
    "A05": ("answer_replaced", "answer replacement"),
    "A06": ("guard_checked", "prompt-injection guard execution"),
    "A07": (None, "not available"),
    "A08": ("guard_triggered", "embedding-probe guard activation"),
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
DIAGNOSTIC_ATTACKS = ("A01", "A02", "A03", "A04", "A05", "A08")


def load(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def esc(value: Any) -> str:
    text = str(value)
    replacements = {
        "\\": r"\textbackslash{}",
        "_": r"\_",
        "%": r"\%",
        "&": r"\&",
        "#": r"\#",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def fraction(value: Any, denominator: Any) -> str:
    if value is None:
        return r"\textit{N/A}"
    return f"{int(value)}/{int(denominator)}"


def pair_cell(off: dict[str, Any], on: dict[str, Any], field: str, denominator: str) -> str:
    return (
        f"{fraction(off.get(field), off[denominator])}"
        r" $\rightarrow$ "
        f"{fraction(on.get(field), on[denominator])}"
    )


def attack_table(attack: str, metrics: dict[str, Any]) -> str:
    if attack == "A06":
        rows = []
        for mode in MODES:
            off = metrics[attack]["guards_off"][mode]
            on = metrics[attack]["guards_on"][mode]
            rows.append(
                " & ".join(
                    [
                        MODE_LABELS[mode],
                        pair_cell(off, on, "primary", "unauthorised_n"),
                        pair_cell(off, on, "raw_integrity", "unauthorised_n"),
                        pair_cell(
                            off, on, "confidentiality_leak", "unauthorised_n"
                        ),
                        pair_cell(
                            off, on, "model_visible_exposure", "unauthorised_n"
                        ),
                        pair_cell(off, on, "guard_checked", "unauthorised_n"),
                        pair_cell(
                            off, on, "positive_control", "positive_control_n"
                        ),
                    ]
                )
                + r" \\"
            )
        return "\n".join(
            [
                r"\begin{table}[htbp]",
                r"\centering",
                r"\footnotesize",
                r"\setlength{\tabcolsep}{2.2pt}",
                r"\begin{tabularx}{\textwidth}{@{}l*{6}{>{\centering\arraybackslash}X}@{}}",
                r"\toprule",
                r"Mode & Delivered canary & Raw canary & Secret leakage & Model-visible exposure & Guard checked & Positive control \\",
                r"\midrule",
                *rows,
                r"\bottomrule",
                r"\end{tabularx}",
                (
                    r"\caption[A06 matched prompt-injection-guard ablation]{A06 "
                    r"matched prompt-injection-guard ablation. Cells show guards "
                    r"off $\rightarrow$ guards on. Canary compliance is an integrity "
                    r"outcome and secret leakage is a separate confidentiality "
                    r"outcome. Security denominators are 150 and positive-control "
                    r"denominators are 75 per mode and arm.}"
                ),
                r"\label{tab:a06-matched-ablation}",
                r"\end{table}",
                "",
            ]
        )

    internal_field, internal_label = INTERNAL_FIELDS[attack]
    action_field, action_label = ACTION_FIELDS[attack]
    rows = []
    for mode in MODES:
        off = metrics[attack]["guards_off"][mode]
        on = metrics[attack]["guards_on"][mode]
        action = (
            pair_cell(off, on, action_field, "unauthorised_n")
            if action_field
            else r"\textit{not available}"
        )
        rows.append(
            " & ".join(
                [
                    MODE_LABELS[mode],
                    pair_cell(off, on, "primary", "unauthorised_n"),
                    pair_cell(
                        off, on, RAW_FIELDS[attack], "unauthorised_n"
                    ),
                    pair_cell(off, on, internal_field, "unauthorised_n"),
                    action,
                    pair_cell(off, on, "positive_control", "positive_control_n"),
                ]
            )
            + r" \\"
        )
    metric_name = esc(
        metrics[attack]["guards_off"]["secure_rag_mode"]["primary_metric"]
    )
    return "\n".join(
        [
            r"\begin{table}[htbp]",
            r"\centering",
            r"\small",
            r"\setlength{\tabcolsep}{3pt}",
            r"\begin{tabularx}{\textwidth}{@{}l*{5}{>{\centering\arraybackslash}X}@{}}",
            r"\toprule",
            r"Mode & Primary & Raw unsafe & Internal evidence & Guard action & Positive control \\",
            r"\midrule",
            *rows,
            r"\bottomrule",
            r"\end{tabularx}",
            (
                rf"\caption[{attack} matched guard ablation]{{{attack} matched "
                rf"guard ablation. Cells show guards off $\rightarrow$ guards on. "
                rf"The primary metric is {metric_name}; internal evidence is "
                rf"{esc(internal_label)}; guard action is {esc(action_label)}. "
                r"Unauthorised denominators are 150 and positive-control denominators "
                r"are 75 per mode and arm.}"
            ),
            rf"\label{{tab:{attack.lower()}-matched-ablation}}",
            r"\end{table}",
            "",
        ]
    )


def cross_table(metrics: dict[str, Any]) -> str:
    def count_pair(off: dict[str, Any], on: dict[str, Any], field: str) -> str:
        off_value = off.get(field)
        on_value = on.get(field)
        if off_value is None or on_value is None:
            return r"\textit{N/A}"
        return f"{int(off_value)}" + r"$\to$" + f"{int(on_value)}"

    rows = []
    for attack in ATTACK_NAMES:
        secure_off = metrics[attack]["guards_off"]["secure_rag_mode"]
        secure_on = metrics[attack]["guards_on"]["secure_rag_mode"]
        sens_off = metrics[attack]["guards_off"]["sensitivity_eval_mode"]
        sens_on = metrics[attack]["guards_on"]["sensitivity_eval_mode"]
        secondary_field = (
            "confidentiality_leak"
            if attack == "A06"
            else INTERNAL_FIELDS[attack][0]
        )
        secondary = (
            r"\shortstack{S: "
            + count_pair(secure_off, secure_on, secondary_field)
            + r"\\SE: "
            + count_pair(sens_off, sens_on, secondary_field)
            + "}"
        )
        rows.append(
            " & ".join(
                [
                    attack,
                    esc(INTERVENTIONS[attack]),
                    count_pair(secure_off, secure_on, "primary"),
                    count_pair(sens_off, sens_on, "primary"),
                    secondary,
                    count_pair(secure_off, secure_on, "positive_control"),
                    count_pair(sens_off, sens_on, "positive_control"),
                ]
            )
            + r" \\"
        )
    return "\n".join(
        [
            r"\begin{table}[htbp]",
            r"\centering",
            r"\scriptsize",
            r"\setlength{\tabcolsep}{2pt}",
            r"\begin{tabularx}{\textwidth}{@{}l>{\raggedright\arraybackslash}p{30mm}*{5}{>{\centering\arraybackslash}X}@{}}",
            r"\toprule",
            r"Attack & Tested control & \shortstack{S\\outcome} & \shortstack{SE\\outcome} & \shortstack{Secondary\\evidence} & \shortstack{S\\positive task} & \shortstack{SE\\positive task} \\",
            r"\midrule",
            *rows,
            r"\bottomrule",
            r"\end{tabularx}",
            r"\caption[Cross-attack matched-ablation summary]{Cross-attack matched-ablation summary. Every numerical cell reports the raw count with guards off $\rightarrow$ guards on; security counts have denominator 150 and authorised positive-control task counts denominator 75. Selected outcomes are attack-specific and must not be interpreted as one homogeneous measure. For A06, the selected outcome is canary compliance and the secondary column is the separate delivered confidentiality outcome.}",
            r"\label{tab:cross-attack-matched-ablation}",
            r"\end{table}",
            "",
        ]
    )


def diagnostic_table(
    metrics: dict[str, Any], historical: dict[str, Any]
) -> str:
    rows = []
    for attack in DIAGNOSTIC_ATTACKS:
        secure_baseline = historical[attack]["secure_rag_mode"]["primary"]
        secure_off = metrics[attack]["guards_off"]["secure_rag_mode"]["primary"]
        sens_baseline = historical[attack]["sensitivity_eval_mode"]["primary"]
        sens_off = metrics[attack]["guards_off"]["sensitivity_eval_mode"]["primary"]
        rows.append(
            f"{attack} & {secure_baseline}/150 vs. {secure_off}/150"
            f" & {sens_baseline}/150 vs. {sens_off}/150 \\\\"
        )
    return "\n".join(
        [
            r"\begin{table}[htbp]",
            r"\centering",
            r"\small",
            r"\begin{tabularx}{\textwidth}{@{}lXX@{}}",
            r"\toprule",
            r"Attack & Secure: historical vs.\ guards off & Sensitivity: historical vs.\ guards off \\",
            r"\midrule",
            *rows,
            r"\bottomrule",
            r"\end{tabularx}",
            r"\caption[Historical baseline versus guards-off diagnostic]{Diagnostic comparison of the historical original baseline with the matched guards-off arm. The sources use different implementation stages and are not matched; the table is not causal evidence. Values are attack-specific primary outcomes.}",
            r"\label{tab:historical-vs-guards-off}",
            r"\end{table}",
            "",
        ]
    )


def availability_table(metrics: dict[str, Any]) -> str:
    rows = []
    for attack in ATTACK_NAMES:
        action = ACTION_FIELDS[attack][0]
        rows.append(
            " & ".join(
                [
                    attack,
                    esc(INTERNAL_FIELDS[attack][1]),
                    "available",
                    "available",
                    esc(ACTION_FIELDS[attack][1]) if action else "not available",
                ]
            )
            + r" \\"
        )
    return "\n".join(
        [
            r"\begin{table}[htbp]",
            r"\centering",
            r"\small",
            r"\begin{tabularx}{\textwidth}{@{}lXXXX@{}}",
            r"\toprule",
            r"Attack & Internal evidence & Raw answer & Delivered answer & Guard action \\",
            r"\midrule",
            *rows,
            r"\bottomrule",
            r"\end{tabularx}",
            r"\caption[Matched-ablation telemetry availability]{Availability and meaning of measurement-stage evidence in the matched ablations. Internal evidence is attack-specific and is not itself delivered leakage.}",
            r"\label{tab:matched-telemetry-availability}",
            r"\end{table}",
            "",
        ]
    )


def provenance_tables(provenance: list[dict[str, Any]]) -> tuple[str, str]:
    intervention_rows = []
    validity_rows = []
    for item in provenance:
        attack = item["attack"]
        changed = ", ".join(
            rf"\path{{{value}}}" for value in item["actual_changed_controls"]
        )
        fixed = "; ".join(
            rf"\path{{{key}}}={'on' if value else 'off'}"
            for key, value in item["controls_held_fixed"].items()
        )
        intervention_rows.append(
            f"{attack} & {changed} & {fixed} \\\\"
        )
        validity_rows.append(
            f"{attack} & {item['valid_matched_pairs']}/450"
            f" & {item['prompt_matched_pairs']}/450"
            f" & {item['condition_matched_pairs']}/450"
            f" & {'yes' if item['valid_matched_ablation'] else 'no'} \\\\"
        )
    interventions = "\n".join(
        [
            r"\begin{table}[htbp]",
            r"\centering",
            r"\footnotesize",
            r"\begin{tabularx}{\textwidth}{@{}l>{\raggedright\arraybackslash}p{45mm}>{\raggedright\arraybackslash}X@{}}",
            r"\toprule",
            r"Attack & Changed control & Recorded controls held fixed \\",
            r"\midrule",
            *intervention_rows,
            r"\bottomrule",
            r"\end{tabularx}",
            r"\caption[Matched-ablation interventions]{Actual configuration difference and controls explicitly held fixed in the matched experiments. Each experiment changed one recorded control. For A03, unrelated inherited guard values were not individually materialised in the top-level manifest.}",
            r"\label{tab:matched-ablation-interventions}",
            r"\end{table}",
            "",
        ]
    )
    validity = "\n".join(
        [
            r"\begin{table}[htbp]",
            r"\centering",
            r"\small",
            r"\begin{tabularx}{\textwidth}{@{}l*{4}{>{\centering\arraybackslash}X}@{}}",
            r"\toprule",
            r"Attack & Valid pairs & Prompt match & Condition match & Valid ablation \\",
            r"\midrule",
            *validity_rows,
            r"\bottomrule",
            r"\end{tabularx}",
            r"\caption[Matched-ablation pair validation]{Record-level validation of the matched experiment arms. Every attack contains 450 off/on pairs, corresponding to 900 conversations.}",
            r"\label{tab:matched-ablation-validation}",
            r"\end{table}",
            "",
        ]
    )
    return interventions, validity


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metric-summary", type=Path, required=True)
    parser.add_argument("--provenance", type=Path, required=True)
    parser.add_argument(
        "--historical-metrics",
        type=Path,
        default=ROOT / "outputs/final_thesis_evidence_20260725/metrics.json",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    metrics = load(args.metric_summary)["metrics"]
    provenance = load(args.provenance)["experiments"]
    historical = load(args.historical_metrics)["descriptive_baseline"]
    for attack in ATTACK_NAMES:
        (args.output_dir / f"{attack.lower()}_matched_ablation_table.tex").write_text(
            attack_table(attack, metrics), encoding="utf-8"
        )
    (args.output_dir / "cross_attack_matched_ablation_table.tex").write_text(
        cross_table(metrics), encoding="utf-8"
    )
    (args.output_dir / "historical_vs_guards_off_table.tex").write_text(
        diagnostic_table(metrics, historical), encoding="utf-8"
    )
    (args.output_dir / "matched_telemetry_availability_table.tex").write_text(
        availability_table(metrics), encoding="utf-8"
    )
    interventions, validity = provenance_tables(provenance)
    (args.output_dir / "matched_ablation_interventions_table.tex").write_text(
        interventions, encoding="utf-8"
    )
    (args.output_dir / "matched_ablation_validation_table.tex").write_text(
        validity, encoding="utf-8"
    )


if __name__ == "__main__":
    main()
