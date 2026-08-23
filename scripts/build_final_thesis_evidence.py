#!/usr/bin/env python3
"""Build the final, traceable thesis evidence ledger from stored experiment data.

This script does not rerun an experiment or rescore an answer.  It extracts the
reported counts from the original JSON records, preserves source-file hashes,
and classifies the evidential purpose of each comparison.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PRE_ROOT = ROOT / "outputs/experiments/gpt4o_mini_slurm_attacks01_07_08_neutral_prehardened_20260719"
POST_ROOT = ROOT / "outputs/experiments/post hardened 1-8"
CORRECTION_ROOT = ROOT / "outputs/experiments/methodology_correction_20260722T160300Z"
A01_CORRECTION_ROOT = ROOT / "outputs/experiments/methodology_correction_a01_20260723T090000Z/A01"
RESCORE_ROOT = ROOT / "outputs/rescoring/a02_policy_aware_20260722T155853Z"
FINAL_CORRECTION_ROOT = ROOT / "outputs/final_methodology_correction_20260723T100000Z"
PROMPT_AUDIT = ROOT / "outputs/audits/prompt_equivalence_20260722T155741Z/prompt_equivalence.csv"
OUTPUT_ROOT = ROOT / "outputs/final_thesis_evidence_20260725"
MODES = ("secure_rag_mode", "sensitivity_eval_mode")
UNAUTHORISED = {"public", "internal"}


PRE_FILES = {
    "A01": "attack_01_direct_cell_extraction",
    "A02": "attack_02_multiturn_row_construction",
    "A03": "attack_03_access_level_downgrade_task",
    "A04": "attack_04_relational_join_path_inference",
    "A05": "attack_05_rank_probing_membership_inference",
    "A06": "attack_06_prompt_injection_poisoned_row",
    "A07": "attack_07_backdoor_triggered_extraction",
    "A08": "gpt4o_mini_slurm_attack08_neutral_prehardened_20260719/attack_08_embedding_side_leakage",
}
POST_FILES = {
    **PRE_FILES,
    "A01": "gpt4o_mini_slurm_attack01_neutral_posthardened_20260720/attack_01_direct_cell_extraction",
    "A08": "attack_08_embedding_side_leakage",
}


def load(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source(stage: str, attack: str, mode: str) -> Path:
    root = PRE_ROOT if stage == "descriptive_baseline" else POST_ROOT
    mapping = PRE_FILES if stage == "descriptive_baseline" else POST_FILES
    return root / mapping[attack] / mode / "results.json"


def records(path: Path) -> list[dict[str, Any]]:
    return load(path)["records"]


def role(record: dict[str, Any]) -> str:
    return str(record.get("access", record.get("access_after", "")))


def count(items: list[dict[str, Any]], field: str) -> int:
    return sum(bool(item.get(field)) for item in items)


def split(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = records(path)
    return (
        [row for row in rows if role(row) in UNAUTHORISED],
        [row for row in rows if role(row) == "protected"],
    )


def prompt_audit() -> dict[str, Any]:
    grouped: Counter[tuple[str, str, str, str]] = Counter()
    with PROMPT_AUDIT.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            grouped[
                (
                    row["attack_id"],
                    row["mode"],
                    row["pre_prompt_kind"],
                    row["exact_match"],
                )
            ] += 1
    result: dict[str, Any] = {}
    for (attack, mode, kind, exact), value in sorted(grouped.items()):
        result.setdefault(attack, {}).setdefault(mode, {}).setdefault(kind, {})[
            "exact" if exact == "True" else "different"
        ] = value
    for attack in ("A01", "A04", "A08"):
        result[attack] = {
            mode: {"status": "exact prompt text not stored in either result set"}
            for mode in MODES
        }
    return result


def baseline_metrics() -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    a02_rescore = {
        row["mode"]: row
        for row in load(RESCORE_ROOT / "summary.json")["summaries"]
        if row["stage"] == "pre_hardening"
    }
    for attack in PRE_FILES:
        metrics[attack] = {}
        for mode in MODES:
            path = source("descriptive_baseline", attack, mode)
            unauth, protected = split(path)
            item: dict[str, Any] = {
                "source": str(path.relative_to(ROOT)),
                "source_sha256": sha256(path),
                "unauthorised_n": len(unauth),
                "positive_control_n": len(protected),
            }
            if attack == "A01":
                item.update(
                    exposure=count(unauth, "retrieved_secret_present"),
                    primary=count(unauth, "answer_leak"),
                    primary_metric="delivered confidentiality leakage",
                    positive_control=count(protected, "answer_leak"),
                )
            elif attack == "A02":
                summary = a02_rescore[mode]
                item.update(
                    exposure=count(unauth, "final_retrieved_full_support"),
                    primary=summary["delivered_policy_aware_leaks"],
                    partial=summary["delivered_policy_aware_partial_reconstructions"],
                    full=summary["delivered_policy_aware_full_reconstructions"],
                    legacy_flags=summary["legacy_target_field_flags"],
                    raw_available=summary["raw_answer_available_records"],
                    primary_metric="policy-aware delivered row leakage",
                    positive_control=count(protected, "final_answer_full_reconstruction"),
                    rescore_source=str(
                        (RESCORE_ROOT / "pre_hardening" / mode / "results.json").relative_to(ROOT)
                    ),
                )
            elif attack == "A03":
                item.update(
                    exposure=count(unauth, "unauthorized_retrieval_exposure"),
                    state_exposure=count(unauth, "pre_attack_any_memory_has_secret"),
                    primary=count(unauth, "unauthorized_answer_leak"),
                    primary_metric="delivered memory/state confidentiality leakage",
                    positive_control=count(protected, "positive_control_success"),
                )
            elif attack == "A04":
                item.update(
                    exposure=sum(
                        bool(row.get("retrieved_join_edge"))
                        or bool(row.get("retrieved_protected_formulation_doc"))
                        or bool(row.get("retrieved_protected_process_doc"))
                        for row in unauth
                    ),
                    node=sum(
                        bool(row.get("answer_rezeptur_id")) or bool(row.get("answer_verfahren_id"))
                        for row in unauth
                    ),
                    primary=count(unauth, "answer_join_edge"),
                    primary_metric="delivered relation-edge leakage",
                    positive_control=count(protected, "answer_complete"),
                )
            elif attack == "A05":
                item.update(
                    exposure=sum(
                        bool(row.get("retrieved_target_doc_present"))
                        or bool(row.get("retrieved_candidate_id_present"))
                        for row in unauth
                    ),
                    primary=count(unauth, "unauthorized_answer_leak"),
                    detail=count(unauth, "answer_detail_correct"),
                    primary_metric="delivered membership confirmation",
                    positive_control=count(protected, "authorized_positive_control_success"),
                )
            elif attack == "A06":
                item.update(
                    exposure=sum(
                        bool(row.get("poison_retrieved")) and bool(row.get("secret_in_retrieved_context"))
                        for row in unauth
                    ),
                    primary=count(unauth, "secret_in_answer"),
                    canary=count(unauth, "canary_in_answer"),
                    primary_metric="delivered confidentiality leakage",
                    positive_control=count(protected, "authorized_positive_control_success"),
                )
            elif attack == "A07":
                item.update(
                    exposure=count(unauth, "backdoor_retrieved"),
                    primary=count(unauth, "canary_in_answer"),
                    confidentiality=count(unauth, "secret_in_answer"),
                    primary_metric="canary compliance (integrity)",
                    positive_control=count(protected, "authorized_positive_control_success"),
                )
            elif attack == "A08":
                item.update(
                    exposure=count(unauth, "retrieved_target_present"),
                    primary=count(unauth, "unauthorized_answer_leak"),
                    unsupported=count(unauth, "unauthorized_unsupported_answer_leak"),
                    primary_metric="delivered numeric leakage from embedding/rank probe",
                    positive_control=count(protected, "positive_control_success"),
                )
            metrics[attack][mode] = item
    return metrics


def post_metrics() -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    a02_rescore = {
        row["mode"]: row
        for row in load(RESCORE_ROOT / "summary.json")["summaries"]
        if row["stage"] == "post_hardening"
    }
    for attack in POST_FILES:
        metrics[attack] = {}
        for mode in MODES:
            path = source("hardened_package", attack, mode)
            unauth, protected = split(path)
            item: dict[str, Any] = {
                "source": str(path.relative_to(ROOT)),
                "source_sha256": sha256(path),
                "unauthorised_n": len(unauth),
                "positive_control_n": len(protected),
            }
            if attack == "A01":
                item.update(
                    exposure=count(unauth, "prompt_context_secret_present"),
                    raw=count(unauth, "raw_answer_leak"),
                    primary=count(unauth, "delivered_answer_leak"),
                    primary_metric="delivered confidentiality leakage",
                    positive_control=count(protected, "delivered_answer_leak"),
                )
            elif attack == "A02":
                summary = a02_rescore[mode]
                item.update(
                    exposure=count(unauth, "final_retrieved_full_support"),
                    raw=summary["raw_policy_aware_leaks"],
                    primary=summary["delivered_policy_aware_leaks"],
                    partial=summary["delivered_policy_aware_partial_reconstructions"],
                    full=summary["delivered_policy_aware_full_reconstructions"],
                    primary_metric="policy-aware delivered row leakage",
                    positive_control=count(protected, "final_answer_full_reconstruction"),
                    rescore_source=str(
                        (RESCORE_ROOT / "post_hardening" / mode / "results.json").relative_to(ROOT)
                    ),
                )
            elif attack == "A03":
                item.update(
                    exposure=count(unauth, "unauthorized_retrieval_exposure"),
                    state_exposure=count(unauth, "pre_attack_any_memory_has_secret"),
                    primary=count(unauth, "unauthorized_answer_leak"),
                    primary_metric="delivered memory/state confidentiality leakage",
                    positive_control=count(protected, "positive_control_success"),
                )
            elif attack == "A04":
                item.update(
                    exposure=count(unauth, "model_visible_context_exposure"),
                    primary=count(unauth, "answer_edge_leakage"),
                    primary_metric="delivered relation-edge leakage",
                    positive_control=count(protected, "protected_positive_control_success"),
                )
            elif attack == "A05":
                item.update(
                    exposure=count(unauth, "unauthorized_retrieval_hit"),
                    primary=count(unauth, "unauthorized_answer_membership_confirmation"),
                    detail=count(unauth, "unauthorized_answer_detail_leak"),
                    primary_metric="delivered membership confirmation",
                    positive_control=count(protected, "authorized_positive_control_success"),
                )
            elif attack == "A06":
                item.update(
                    exposure=sum(
                        bool(row.get("sent_to_llm_context")) and bool(row.get("secret_in_retrieved_context"))
                        for row in unauth
                    ),
                    primary=count(unauth, "secret_in_answer"),
                    canary=count(unauth, "answer_contains_canary"),
                    primary_metric="delivered confidentiality leakage",
                    positive_control=count(protected, "authorized_positive_control_success"),
                )
            elif attack == "A07":
                item.update(
                    exposure=count(unauth, "backdoor_retrieved"),
                    primary=count(unauth, "canary_in_answer"),
                    confidentiality=count(unauth, "secret_in_answer"),
                    primary_metric="canary compliance (natural-style family)",
                    positive_control=count(protected, "authorized_positive_control_success"),
                )
            elif attack == "A08":
                item.update(
                    exposure=count(unauth, "visible_context_target_present"),
                    primary=count(unauth, "unauthorized_answer_leak"),
                    side_channel=count(unauth, "answer_side_channel_present"),
                    guard=count(unauth, "embedding_probe_guard_triggered"),
                    primary_metric="delivered numeric leakage from embedding/rank probe",
                    positive_control=count(protected, "positive_control_success"),
                )
            metrics[attack][mode] = item
    return metrics


def correction_metrics() -> dict[str, Any]:
    summary_path = FINAL_CORRECTION_ROOT / "authoritative_summary.json"
    summary = load(summary_path)
    summary["_source"] = str(summary_path.relative_to(ROOT))
    summary["_source_sha256"] = sha256(summary_path)
    return summary


def provenance_rows() -> list[dict[str, Any]]:
    common = {
        "dataset": "data/SiSWiss_Testdaten.xlsx",
        "model": "gpt-4o-mini",
        "temperature": "0.0",
        "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
        "retrieval_k": "5",
        "denominator": "150 unauthorised; 75 protected positive controls per mode",
    }
    rows = [
        {
            "attack": "A01",
            "evidence_purpose": "descriptive original baseline",
            "pre_source": str(PRE_ROOT.relative_to(ROOT)),
            "post_source": "N/A",
            "pre_code_stage": "original implementation; commit 9379b47 inferred from detached baseline worktree",
            "post_code_stage": "N/A",
            "prompt_match": "N/A; no comparison",
            "valid_causal_comparison": "No; descriptive only",
        },
        {
            "attack": "A01",
            "evidence_purpose": "matched guard ablation",
            "pre_source": str(A01_CORRECTION_ROOT.relative_to(ROOT)) + "/pre_hardening",
            "post_source": str(A01_CORRECTION_ROOT.relative_to(ROOT)) + "/post_hardening",
            "pre_code_stage": "hardened working tree at e66ee5a with switchable guards off",
            "post_code_stage": "same hardened working tree with switchable guards on",
            "prompt_match": "Exact; manifest hash fd44b5b0… in both arms",
            "valid_causal_comparison": "Yes, for the switched guards; not original-versus-hardened causality",
        },
        {
            "attack": "A02",
            "evidence_purpose": "policy-aware descriptive package comparison",
            "pre_source": str((RESCORE_ROOT / "pre_hardening").relative_to(ROOT)),
            "post_source": str((RESCORE_ROOT / "post_hardening").relative_to(ROOT)),
            "pre_code_stage": "original implementation; baseline worktree based on 9379b47",
            "post_code_stage": "hardened implementation; exact run commit/dirty state not captured",
            "prompt_match": "Attack prompt differs in 450/450 conversations; warm-ups match",
            "valid_causal_comparison": "No; report as descriptive package comparison",
        },
        {
            "attack": "A03",
            "evidence_purpose": "descriptive package comparison",
            "pre_source": str((PRE_ROOT / PRE_FILES["A03"]).relative_to(ROOT)),
            "post_source": str((POST_ROOT / POST_FILES["A03"]).relative_to(ROOT)),
            "pre_code_stage": "original implementation; baseline worktree based on 9379b47",
            "post_code_stage": "hardened implementation; exact run commit/dirty state not captured",
            "prompt_match": "Final attack prompts match; seed prompts differ in all 450 conversations",
            "valid_causal_comparison": "No strong causal wording; package-level association only",
        },
        {
            "attack": "A04",
            "evidence_purpose": "descriptive package comparison",
            "pre_source": str((PRE_ROOT / PRE_FILES["A04"]).relative_to(ROOT)),
            "post_source": str((POST_ROOT / POST_FILES["A04"]).relative_to(ROOT)),
            "pre_code_stage": "original implementation; baseline worktree based on 9379b47",
            "post_code_stage": "hardened implementation; exact run commit/dirty state not captured",
            "prompt_match": "Exact prompt text not stored",
            "valid_causal_comparison": "No; descriptive package comparison",
        },
        {
            "attack": "A05",
            "evidence_purpose": "descriptive original baseline",
            "pre_source": str((PRE_ROOT / PRE_FILES["A05"]).relative_to(ROOT)),
            "post_source": "N/A",
            "pre_code_stage": "original implementation; baseline worktree based on 9379b47",
            "post_code_stage": "N/A",
            "prompt_match": "N/A; no comparison",
            "valid_causal_comparison": "No; descriptive only",
        },
        {
            "attack": "A05",
            "evidence_purpose": "matched guard ablation",
            "pre_source": str((CORRECTION_ROOT / "A05/pre_hardening").relative_to(ROOT)),
            "post_source": str((CORRECTION_ROOT / "A05/post_hardening").relative_to(ROOT)),
            "pre_code_stage": "hardened working tree at e66ee5a with switchable guards off",
            "post_code_stage": "same hardened working tree with switchable guards on",
            "prompt_match": "Exact; manifest hash 93fde83b… in both arms",
            "valid_causal_comparison": "Yes, for the switched guards; not original-versus-hardened causality",
        },
        {
            "attack": "A06",
            "evidence_purpose": "prompt-matched descriptive package comparison",
            "pre_source": str((PRE_ROOT / PRE_FILES["A06"]).relative_to(ROOT)),
            "post_source": str((POST_ROOT / POST_FILES["A06"]).relative_to(ROOT)),
            "pre_code_stage": "original implementation; baseline worktree based on 9379b47",
            "post_code_stage": "hardened implementation; exact run commit/dirty state not captured",
            "prompt_match": "Attack and warm-up prompts match in all stored pairs",
            "valid_causal_comparison": "No isolated guard causality; package-level association only",
        },
        {
            "attack": "A07-S",
            "evidence_purpose": "matched synthetic-family guard ablation",
            "pre_source": str((CORRECTION_ROOT / "A07-S/pre_hardening").relative_to(ROOT)),
            "post_source": str((CORRECTION_ROOT / "A07-S/post_hardening").relative_to(ROOT)),
            "pre_code_stage": "hardened working tree at e66ee5a with switchable guards off",
            "post_code_stage": "same hardened working tree with switchable guards on",
            "prompt_match": "Exact; manifest hash 7cab… in both arms",
            "valid_causal_comparison": "Yes, for the switched guards; actual path was membership guard",
        },
        {
            "attack": "A07-N",
            "evidence_purpose": "matched natural-family guard ablation",
            "pre_source": str((CORRECTION_ROOT / "A07-N/pre_hardening").relative_to(ROOT)),
            "post_source": str((CORRECTION_ROOT / "A07-N/post_hardening").relative_to(ROOT)),
            "pre_code_stage": "hardened working tree at e66ee5a with switchable guards off",
            "post_code_stage": "same hardened working tree with switchable guards on",
            "prompt_match": "Exact; manifest hash 6671… in both arms",
            "valid_causal_comparison": "Yes, for the switched guards; security outcome was zero in both arms",
        },
        {
            "attack": "A08",
            "evidence_purpose": "descriptive package comparison",
            "pre_source": str((PRE_ROOT / PRE_FILES["A08"]).relative_to(ROOT)),
            "post_source": str((POST_ROOT / POST_FILES["A08"]).relative_to(ROOT)),
            "pre_code_stage": "original implementation at verified commit 9379b47",
            "post_code_stage": "hardened implementation; exact run commit/dirty state not captured",
            "prompt_match": "Exact prompt text not stored; both runs record neutral style",
            "valid_causal_comparison": "No; descriptive package comparison",
        },
    ]
    manifests = load(FINAL_CORRECTION_ROOT / "experiment_manifests.json")
    correction_dataset_hashes = sorted({item["dataset_hash"] for item in manifests})
    correction_prompt_hashes = {
        item["experiment_name"]: item["prompt_hash"] for item in manifests
    }
    for item in rows:
        item.update(common)
        is_ablation = "guard ablation" in item["evidence_purpose"]
        base_attack = item["attack"].split("-")[0]
        item["dataset_hash"] = correction_dataset_hashes[0] if is_ablation else "not captured in original run"
        item["index_size"] = 305 if base_attack in {"A06", "A07"} else 300
        item["synthetic_rows"] = 5 if base_attack in {"A06", "A07"} else 0
        item["system_prompt"] = "not stored in result/manifests"
        if is_ablation and item["attack"] == "A01":
            item["warm_up_prompts"] = "exact text not stored; warm-up counts and conditions match"
        elif is_ablation:
            item["warm_up_prompts"] = "stored and equal across guards-off/on records"
        elif item["attack"] == "A02":
            item["warm_up_prompts"] = "stored and equal across original/hardened records"
        elif item["attack"] == "A03":
            item["warm_up_prompts"] = "final attack prompt equal; protected seed prompt differs"
        elif item["attack"] == "A06":
            item["warm_up_prompts"] = "stored and equal across original/hardened records"
        else:
            item["warm_up_prompts"] = "exact text not available for the compared original package records"
        item["prompt_hash"] = (
            correction_prompt_hashes.get(item["attack"]) if is_ablation else "not jointly available"
        )
        item["guard_configuration"] = (
            "same hardened code; false in guards-off arm and true in guards-on arm"
            if is_ablation
            else (
                "original implementation; individual guard flags not logged"
                if item["post_source"] == "N/A"
                else "different implementation packages; flags incompletely captured"
            )
        )
        item["scorer_version"] = (
            "a02-policy-aware-v1"
            if item["attack"] == "A02"
            else ("methodology-correction-v1" if is_ablation else "attack-specific stored scorer; version not logged")
        )
        item["target_definition"] = "five deterministic targets stored in each result JSON"
        item["source_state_note"] = (
            "Correction manifest records e66ee5a, but the working tree was dirty and no source-tree hash was captured."
            if is_ablation
            else "Original result files do not contain a complete source-state manifest."
        )
    return rows


def write_outputs() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    payload = {
        "scope": {
            "descriptive_baseline": str(PRE_ROOT.relative_to(ROOT)),
            "descriptive_hardened_package": str(POST_ROOT.relative_to(ROOT)),
            "matched_guard_ablations": [
                str(CORRECTION_ROOT.relative_to(ROOT)),
                str(A01_CORRECTION_ROOT.parent.relative_to(ROOT)),
            ],
            "policy_aware_rescoring": str(RESCORE_ROOT.relative_to(ROOT)),
            "prompt_audit": str(PROMPT_AUDIT.relative_to(ROOT)),
        },
        "prompt_audit": prompt_audit(),
        "descriptive_baseline": baseline_metrics(),
        "descriptive_hardened_package": post_metrics(),
        "correction_runs_as_recorded": correction_metrics(),
    }
    metrics_path = OUTPUT_ROOT / "metrics.json"
    metrics_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    ledger = provenance_rows()
    provenance_path = OUTPUT_ROOT / "provenance.json"
    provenance_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (OUTPUT_ROOT / "provenance.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ledger[0]))
        writer.writeheader()
        writer.writerows(ledger)

    checks = {
        "metrics_sha256": sha256(metrics_path),
        "provenance_sha256": sha256(provenance_path),
        "correction_manifest_sha256": sha256(FINAL_CORRECTION_ROOT / "experiment_manifests.json"),
        "correction_summary_sha256": sha256(FINAL_CORRECTION_ROOT / "authoritative_summary.json"),
        "a02_rescore_summary_sha256": sha256(RESCORE_ROOT / "summary.json"),
        "prompt_audit_sha256": sha256(PROMPT_AUDIT),
    }
    (OUTPUT_ROOT / "checksums.json").write_text(
        json.dumps(checks, indent=2) + "\n", encoding="utf-8"
    )
    print(OUTPUT_ROOT)


if __name__ == "__main__":
    write_outputs()
