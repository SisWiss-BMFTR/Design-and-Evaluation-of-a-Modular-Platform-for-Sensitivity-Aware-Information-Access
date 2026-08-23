#!/usr/bin/env python3
"""Build the frozen final figure/table provenance manifest.

This script hashes existing thesis assets and their recorded generators/inputs.
It does not regenerate figures, tables, evidence, or experiments.  A null
generator explicitly means that the historical generation command was not
reliably retained and is therefore not reconstructed here.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "manifests/FIGURE_TABLE_PROVENANCE.json"

HISTORICAL_INPUT = "outputs/final_thesis_evidence_20260725/metrics.json"
MATCHED_INPUT = (
    "outputs/final_thesis_evidence_20260803_prompt_provenance_v3/"
    "matched_ablation_metric_summary.json"
)
MATCHED_PROVENANCE = (
    "outputs/final_thesis_evidence_20260803_prompt_provenance_v3/"
    "provenance_with_ablations.json"
)
SUPPLEMENTAL_20260803 = (
    "outputs/final_thesis_supplemental_evidence_20260803/"
    "supplemental_component_evidence.json"
)
SUPPLEMENTAL_20260806 = (
    "outputs/final_thesis_supplemental_evidence_20260806/"
    "supplemental_component_evidence.json"
)
A01_PROMPT_AUDIT = (
    "outputs/audits/package_prompt_provenance_a01_a02_20260803/summary.json"
)


def sha256(relative_path: str) -> str:
    path = ROOT / relative_path
    if not path.is_file():
        raise FileNotFoundError(relative_path)
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def entry(
    output_path: str,
    generator: str | None,
    principal_input: str,
    command: str | None,
    note: str | None = None,
) -> dict[str, str | None]:
    return {
        "output_path": output_path,
        "output_sha256": sha256(output_path),
        "generating_script": generator,
        "generating_script_sha256": sha256(generator) if generator else None,
        "principal_input": principal_input,
        "principal_input_sha256": sha256(principal_input),
        "generation_command": command,
        "provenance_note": note,
    }


def main() -> None:
    historical_stems = (
        "a01_exposure_delivery",
        "a02_policy_aware_reconstruction",
        "a03_state_delivery",
        "a04_relation_structure",
        "a05_membership_baseline",
        "a06_integrity_confidentiality",
        "a07_baseline_integrity_confidentiality_utility",
        "a08_exposure_delivery",
        "cross_attack_descriptive_baseline",
        "cross_attack_package_comparison",
        "cross_attack_utility",
    )
    historical_command = "python scripts/plot_final_thesis_figures.py"

    matched_stems = tuple(f"a0{i}_matched_guard_ablation" for i in range(1, 9)) + (
        "cross_attack_matched_guard_ablations",
        "historical_baseline_vs_matched_guards_off",
    )
    matched_command = (
        "python scripts/plot_matched_ablation_figures.py "
        "--metric-summary outputs/final_thesis_evidence_20260803_prompt_provenance_v3/"
        "matched_ablation_metric_summary.json "
        "--historical-metrics outputs/final_thesis_evidence_20260725/metrics.json "
        "--output-dir thesis/figures/results "
        "--validation-output outputs/final_thesis_evidence_20260803_prompt_provenance_v3/"
        "matched_ablation_figure_validation.json"
    )

    figures: list[dict[str, str | None]] = []
    for stem in historical_stems:
        for suffix in ("pdf", "png"):
            figures.append(
                entry(
                    f"thesis/figures/results/{stem}.{suffix}",
                    "scripts/plot_final_thesis_figures.py",
                    HISTORICAL_INPUT,
                    historical_command,
                )
            )
    for stem in matched_stems:
        for suffix in ("pdf", "png"):
            figures.append(
                entry(
                    f"thesis/figures/results/{stem}.{suffix}",
                    "scripts/plot_matched_ablation_figures.py",
                    MATCHED_INPUT,
                    matched_command,
                    "The generator also reads the historical metrics ledger.",
                )
            )

    matched_tables = tuple(f"a0{i}_matched_ablation_table.tex" for i in range(1, 9)) + (
        "cross_attack_matched_ablation_table.tex",
        "historical_vs_guards_off_table.tex",
        "matched_telemetry_availability_table.tex",
        "matched_ablation_interventions_table.tex",
        "matched_ablation_validation_table.tex",
    )
    matched_table_command = (
        "python scripts/generate_matched_ablation_tables.py "
        "--metric-summary outputs/final_thesis_evidence_20260803_prompt_provenance_v3/"
        "matched_ablation_metric_summary.json "
        "--provenance outputs/final_thesis_evidence_20260803_prompt_provenance_v3/"
        "provenance_with_ablations.json "
        "--historical-metrics outputs/final_thesis_evidence_20260725/metrics.json "
        "--output-dir thesis/generated"
    )
    tables: list[dict[str, str | None]] = []
    for name in matched_tables:
        input_path = MATCHED_PROVENANCE if name.startswith("matched_ablation_") else MATCHED_INPUT
        tables.append(
            entry(
                f"thesis/generated/{name}",
                "scripts/generate_matched_ablation_tables.py",
                input_path,
                matched_table_command,
                "The generator also reads matched metrics/provenance and historical metrics as applicable.",
            )
        )

    supplemental_tables = (
        "verifier_replay_summary_table.tex",
        "a02_full_verifier_challenge_table.tex",
        "a02_full_verifier_breakdown_table.tex",
        "a02_full_verifier_false_replacement_table.tex",
        "a07s_matched_ablation_table.tex",
    )
    supplemental_command = "python scripts/build_supplemental_component_validation_evidence.py"
    for name in supplemental_tables:
        tables.append(
            entry(
                f"thesis/generated/{name}",
                "scripts/build_supplemental_component_validation_evidence.py",
                SUPPLEMENTAL_20260803,
                supplemental_command,
                "The ledger is the compact principal evidence output; the generator reads the frozen raw roots recorded in its source.",
            )
        )

    unknown_generation = (
        (
            "a01_package_prompt_provenance_table.tex",
            A01_PROMPT_AUDIT,
            "The exact historical table-generation command was not retained; it is intentionally not reconstructed.",
        ),
        (
            "a06_supplemental_pilot_profiles_table.tex",
            SUPPLEMENTAL_20260806,
            "Frozen final table bound to the audited supplemental ledger; exact historical table-generation command was not retained.",
        ),
        (
            "a06_supplemental_frozen_challenge_table.tex",
            SUPPLEMENTAL_20260806,
            "Frozen final table bound to the audited supplemental ledger; exact historical table-generation command was not retained.",
        ),
        (
            "cross_attack_claim_status_table.tex",
            SUPPLEMENTAL_20260806,
            "Interpretive final claim-status table; exact historical table-generation command was not retained.",
        ),
    )
    for name, input_path, note in unknown_generation:
        tables.append(
            entry(
                f"thesis/generated/{name}",
                None,
                input_path,
                None,
                note,
            )
        )

    observed_figures = sorted(
        str(path.relative_to(ROOT))
        for path in (ROOT / "thesis/figures/results").iterdir()
        if path.is_file() and path.suffix in {".pdf", ".png"}
    )
    observed_tables = sorted(
        str(path.relative_to(ROOT))
        for path in (ROOT / "thesis/generated").glob("*.tex")
    )
    declared_figures = sorted(str(item["output_path"]) for item in figures)
    declared_tables = sorted(str(item["output_path"]) for item in tables)
    if observed_figures != declared_figures:
        raise RuntimeError("figure declarations do not exactly cover frozen result assets")
    if observed_tables != declared_tables:
        raise RuntimeError("table declarations do not exactly cover frozen generated tables")

    document = {
        "schema_version": "internal-thesis-figure-table-provenance-v1",
        "status": "PASS",
        "scope": "Existing frozen scientific result assets; no regeneration performed.",
        "figures": figures,
        "tables": tables,
        "coverage": {
            "figure_files_declared": len(figures),
            "figure_files_observed": len(observed_figures),
            "table_files_declared": len(tables),
            "table_files_observed": len(observed_tables),
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(OUTPUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
