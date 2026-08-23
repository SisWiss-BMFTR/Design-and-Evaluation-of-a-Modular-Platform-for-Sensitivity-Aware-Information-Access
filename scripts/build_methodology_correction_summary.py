#!/usr/bin/env python3
"""Build the authoritative machine-readable summary for the corrected thesis results."""

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


MODES = ("secure_rag_mode", "sensitivity_eval_mode")


def load(path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def prompt_hash(records):
    rendered = "\n".join(str(record.get("attack_prompt") or "") for record in records)
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def count(records, field):
    return sum(bool(record.get(field)) for record in records)


def split(data):
    records = data["records"]
    return (
        [r for r in records if r.get("access", r.get("access_after")) in {"public", "internal"}],
        [r for r in records if r.get("access", r.get("access_after")) == "protected"],
    )


def result_manifest(path, stage, attack, dataset_hash, git_commit):
    data = load(path)
    design = data.get("design") or {}
    records = data.get("records") or []
    return {
        "experiment_name": attack,
        "created_at": data.get("generated_at"),
        "system_stage": stage,
        "git_commit": git_commit,
        "dataset": data.get("dataset", "data/SiSWiss_Testdaten.xlsx"),
        "dataset_hash": dataset_hash,
        "index_size": design.get("indexed_chunks"),
        "model": design.get("model", "gpt-4o-mini"),
        "temperature": design.get("temperature", 0.0),
        "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
        "retrieval_k": 5,
        "targets": 5,
        "roles": ["public", "internal", "protected"],
        "conversation_lengths": [1, 3, 5],
        "iterations": 5,
        "guards": {
            "post_generation_verifier": stage == "post_hardening",
            "prompt_injection_guard": stage == "post_hardening",
            "access_change_memory_clear": stage == "post_hardening",
        },
        "attack_prompt_version": "matched-label-free-v1",
        "prompt_hash": prompt_hash(records) if any("attack_prompt" in r for r in records) else None,
        "scorer_version": "methodology-correction-v1",
        "source_result_folder": str(path.parent),
        "record_count": len(records),
        "result_sha256": sha256_file(path),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)

    root = Path("outputs/experiments/methodology_correction_20260722T160300Z")
    a01_root = Path("outputs/experiments/methodology_correction_a01_20260723T090000Z/A01")
    a02_root = Path("outputs/rescoring/a02_policy_aware_20260722T155853Z")
    pre_root = Path("outputs/experiments/gpt4o_mini_slurm_attacks01_07_08_neutral_prehardened_20260719")
    post_root = Path("outputs/experiments/post hardened 1-8")
    dataset = Path("data/SiSWiss_Testdaten.xlsx")
    dataset_hash = sha256_file(dataset)
    git_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], universal_newlines=True
    ).strip()
    summary = {"generated_at": datetime.now(timezone.utc).isoformat(), "dataset_hash": dataset_hash}
    manifests = []

    summary["A01"] = {}
    for stage in ("pre_hardening", "post_hardening"):
        summary["A01"][stage] = {}
        for mode in MODES:
            path = a01_root / stage / mode / "results.json"
            data = load(path); unauth, protected = split(data)
            summary["A01"][stage][mode] = {
                "unauthorized_n": len(unauth), "raw_retrieval_exposure": count(unauth, "raw_retrieval_secret_present"),
                "prompt_context_exposure": count(unauth, "prompt_context_secret_present"),
                "raw_answer_leak": count(unauth, "raw_answer_leak"), "delivered_answer_leak": count(unauth, "delivered_answer_leak"),
                "membership_guard_triggered": count(unauth, "membership_guard_triggered"),
                "pre_retrieval_refusal": count(unauth, "pre_retrieval_refusal"),
                "answer_replaced": count(unauth, "answer_replaced"),
                "output_verifier_replacement": sum(r.get("output_guard_action") == "replace_with_refusal" for r in unauth),
                "positive_control": count(protected, "delivered_answer_leak"), "positive_control_n": len(protected),
            }
            manifests.append(result_manifest(path, stage, "A01", dataset_hash, git_commit))

    summary["A02"] = load(a02_root / "summary.json")["summaries"]

    summary["A05"] = {}
    for stage in ("pre_hardening", "post_hardening"):
        summary["A05"][stage] = {}
        for mode in MODES:
            path = root / "A05" / stage / mode / "results.json"
            data = load(path); unauth, protected = split(data)
            summary["A05"][stage][mode] = {
                "unauthorized_n": len(unauth),
                "membership_confirmations": sum(bool(r.get("unauthorized_answer_membership_confirmation", r.get("unauthorized_answer_leak"))) for r in unauth),
                "detail_leaks": count(unauth, "unauthorized_answer_detail_leak"),
                "pre_retrieval_refusals": sum(r.get("membership_guard_action") == "replace_before_retrieval" for r in unauth),
                "guard_replacements": count(unauth, "answer_replaced_by_membership_guard"),
                "positive_control": count(protected, "authorized_positive_control_success"), "positive_control_n": len(protected),
            }
            manifests.append(result_manifest(path, stage, "A05", dataset_hash, git_commit))

    summary["A06"] = {}
    for stage, base in (("pre_hardening", pre_root), ("post_hardening", post_root)):
        summary["A06"][stage] = {}
        for mode in MODES:
            path = base / "attack_06_prompt_injection_poisoned_row" / mode / "results.json"
            data = load(path); unauth, protected = split(data)
            summary["A06"][stage][mode] = {
                "unauthorized_n": len(unauth),
                "canary_compliance": sum(bool(r.get("answer_contains_canary", r.get("canary_in_answer"))) for r in unauth),
                "protected_value_leakage": count(unauth, "secret_in_answer"),
                "positive_control": count(protected, "authorized_positive_control_success"), "positive_control_n": len(protected),
            }

    for attack in ("A07-S", "A07-N"):
        summary[attack] = {}
        for stage in ("pre_hardening", "post_hardening"):
            summary[attack][stage] = {}
            for mode in MODES:
                path = root / attack / stage / mode / "results.json"
                data = load(path); unauth, protected = split(data)
                summary[attack][stage][mode] = {
                    "unauthorized_n": len(unauth), "canary_compliance": count(unauth, "canary_in_answer"),
                    "protected_value_leakage": count(unauth, "secret_in_answer"),
                    "pre_retrieval_refusal": count(unauth, "pre_retrieval_refusal"),
                    "membership_guard_replacement": sum(r.get("membership_guard_action") in {"replace_before_retrieval", "replace_with_refusal"} for r in unauth),
                    "prompt_injection_quarantine": count(unauth, "prompt_injection_context_quarantined"),
                    "positive_control": count(protected, "authorized_positive_control_success"), "positive_control_n": len(protected),
                }
                manifests.append(result_manifest(path, stage, attack, dataset_hash, git_commit))

    with (args.output_dir / "authoritative_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2); handle.write("\n")
    with (args.output_dir / "experiment_manifests.json").open("w", encoding="utf-8") as handle:
        json.dump(manifests, handle, ensure_ascii=False, indent=2); handle.write("\n")
    print(args.output_dir)


if __name__ == "__main__":
    main()
