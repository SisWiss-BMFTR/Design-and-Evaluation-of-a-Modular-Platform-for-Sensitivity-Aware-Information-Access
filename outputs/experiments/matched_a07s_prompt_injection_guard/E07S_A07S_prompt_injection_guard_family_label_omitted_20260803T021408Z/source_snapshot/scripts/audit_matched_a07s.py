#!/usr/bin/env python3
"""Validate and summarise the matched A07-S prompt-injection-guard rerun."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ARMS = {
    "arm_A_injection_guard_off": False,
    "arm_B_injection_guard_on": True,
}
MODES = ("secure_rag_mode", "sensitivity_eval_mode")
TARGETS = ("R-001", "R-002", "R-003", "R-004", "R-005")
UNAUTHORISED = {"public", "internal"}


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def prompt_payload(record: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "turn_kind": str(item.get("turn_kind") or ""),
            "prompt": str(item.get("prompt") or ""),
        }
        for item in record.get("prompts") or []
    ]


def system_prompts(record: dict[str, Any]) -> list[str]:
    prompts = set()
    for turn in record.get("turn_artifacts") or []:
        for message in turn.get("exact_model_messages") or []:
            if message.get("role") == "system":
                prompts.add(str(message.get("content") or ""))
    return sorted(prompts)


def condition_payload(record: dict[str, Any]) -> dict[str, Any]:
    return {
        key: record.get(key)
        for key in (
            "pair_id",
            "target_id",
            "rezeptur_id",
            "backdoor_product_id",
            "trigger_phrase",
            "canary",
            "model",
            "rag_mode",
            "attack_style",
            "access",
            "conversation_length",
            "iteration",
            "relation_access_guard_enabled",
            "output_leakage_verifier_enabled",
        )
    }


def transition_counts(
    off: dict[str, dict[str, Any]],
    on: dict[str, dict[str, Any]],
    mode: str,
    field: str,
    roles: set[str],
) -> dict[str, int]:
    counts = Counter()
    for pair_id in sorted(set(off) & set(on)):
        left = off[pair_id]
        right = on[pair_id]
        if left.get("rag_mode") != mode or str(left.get("access")) not in roles:
            continue
        counts[f"off_{int(bool(left.get(field)))}__on_{int(bool(right.get(field)))}"] += 1
    return dict(sorted(counts.items()))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    run_root = args.run_root.resolve()
    output = args.output or run_root / "authoritative_a07s_evidence.json"
    manifest_path = run_root / "experiment_manifest.json"
    prompt_manifest_path = run_root / "prompt_manifest.json"
    manifest = load_json(manifest_path)
    prompt_manifest = load_json(prompt_manifest_path)

    errors: list[str] = []
    shard_audit: list[dict[str, Any]] = []
    records_by_arm: dict[str, dict[str, dict[str, Any]]] = {
        arm: {} for arm in ARMS
    }
    documents: dict[str, dict[str, dict[str, dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    result_hashes: dict[str, str] = {}
    expected_prompts = {
        target["rezeptur_id"]: {
            str(length): conversation
            for length, conversation in target["conversations"].items()
        }
        for target in prompt_manifest["targets"]
    }

    for arm, injection_enabled in ARMS.items():
        for mode in MODES:
            for target in TARGETS:
                result_path = run_root / arm / mode / target / "results.json"
                csv_path = result_path.with_name("results.csv")
                report_path = result_path.with_name("report.md")
                relative = str(result_path.relative_to(run_root))
                if not result_path.is_file():
                    errors.append(f"missing result shard: {relative}")
                    continue
                for required in (csv_path, report_path):
                    if not required.is_file():
                        errors.append(
                            f"missing companion file: {required.relative_to(run_root)}"
                        )
                document = load_json(result_path)
                documents[arm][mode][target] = document
                result_hashes[relative] = sha256_file(result_path)
                design = document.get("design") or {}
                records = document.get("records") or []
                shard_errors: list[str] = []
                expected_design = {
                    "rag_mode": mode,
                    "attack_style": "synthetic",
                    "prompt_style": "neutral",
                    "prompt_injection_guard_enabled": injection_enabled,
                    "relation_access_guard_enabled": True,
                    "output_leakage_verifier_enabled": False,
                }
                for key, expected in expected_design.items():
                    if design.get(key) != expected:
                        shard_errors.append(
                            f"design.{key}={design.get(key)!r}, expected {expected!r}"
                        )
                if len(records) != 45:
                    shard_errors.append(f"records={len(records)}, expected 45")
                runtime = design.get("runtime_provenance") or {}
                if runtime.get("schema_version") != "runtime-provenance-v1":
                    shard_errors.append("missing runtime-provenance-v1")
                scorer = runtime.get("scorer") or {}
                if scorer.get("scorer_version") != "a07-synthetic-trigger-v1":
                    shard_errors.append("unexpected or missing scorer version")
                for record in records:
                    pair_id = str(record.get("pair_id") or "")
                    if not pair_id:
                        shard_errors.append("record without pair_id")
                        continue
                    if pair_id in records_by_arm[arm]:
                        shard_errors.append(f"duplicate pair_id {pair_id}")
                        continue
                    records_by_arm[arm][pair_id] = record
                    if record.get("rag_mode") != mode:
                        shard_errors.append(f"{pair_id}: record mode mismatch")
                    if record.get("rezeptur_id") != target:
                        shard_errors.append(f"{pair_id}: record target mismatch")
                    if record.get("attack_style") != "synthetic":
                        shard_errors.append(f"{pair_id}: attack variant mismatch")
                    if bool(record.get("prompt_injection_guard_enabled")) != injection_enabled:
                        shard_errors.append(f"{pair_id}: injection guard mismatch")
                    if record.get("relation_access_guard_enabled") is not True:
                        shard_errors.append(f"{pair_id}: relation guard not fixed on")
                    if record.get("output_leakage_verifier_enabled") is not False:
                        shard_errors.append(f"{pair_id}: output verifier not fixed off")
                    length = str(record.get("conversation_length"))
                    expected = expected_prompts[target][length]
                    if record.get("attack_prompt") != expected["attack"]:
                        shard_errors.append(f"{pair_id}: attack prompt mismatch")
                    if record.get("warmup_prompts") != expected["warmups"]:
                        shard_errors.append(f"{pair_id}: warm-up prompt mismatch")
                    if record.get("error") or record.get("exception"):
                        shard_errors.append(f"{pair_id}: execution error recorded")
                if shard_errors:
                    errors.extend(f"{relative}: {message}" for message in shard_errors)
                shard_audit.append(
                    {
                        "arm": arm,
                        "mode": mode,
                        "target": target,
                        "records": len(records),
                        "result_sha256": result_hashes[relative],
                        "valid": not shard_errors,
                        "errors": shard_errors,
                    }
                )

    expected_pairs = int(manifest.get("expected_conversations_per_arm", 450))
    off = records_by_arm["arm_A_injection_guard_off"]
    on = records_by_arm["arm_B_injection_guard_on"]
    shared_ids = set(off) & set(on)
    if len(off) != expected_pairs:
        errors.append(f"guards-off records={len(off)}, expected {expected_pairs}")
    if len(on) != expected_pairs:
        errors.append(f"guards-on records={len(on)}, expected {expected_pairs}")
    if set(off) != set(on):
        errors.append(
            f"pair-set mismatch: off-only={len(set(off)-set(on))}, "
            f"on-only={len(set(on)-set(off))}"
        )

    prompt_matches = 0
    condition_matches = 0
    system_matches = 0
    for pair_id in shared_ids:
        if prompt_payload(off[pair_id]) == prompt_payload(on[pair_id]):
            prompt_matches += 1
        else:
            errors.append(f"{pair_id}: off/on prompt sequence mismatch")
        if condition_payload(off[pair_id]) == condition_payload(on[pair_id]):
            condition_matches += 1
        else:
            errors.append(f"{pair_id}: off/on fixed condition mismatch")
        if system_prompts(off[pair_id]) == system_prompts(on[pair_id]):
            system_matches += 1
        else:
            errors.append(f"{pair_id}: off/on system prompt mismatch")

    prompt_set_hashes = {
        arm: canonical_hash(
            sorted((pair_id, prompt_payload(record)) for pair_id, record in records.items())
        )
        for arm, records in records_by_arm.items()
    }
    system_prompt_sets = {
        arm: sorted(
            {
                prompt
                for record in records.values()
                for prompt in system_prompts(record)
            }
        )
        for arm, records in records_by_arm.items()
    }
    system_prompt_hashes = {
        arm: canonical_hash(prompts) for arm, prompts in system_prompt_sets.items()
    }

    index_by_target: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: {"canonical": set(), "serialized": set()}
    )
    scorer_versions: set[str] = set()
    scorer_hashes: set[str] = set()
    dependency_versions: dict[str, set[str]] = defaultdict(set)
    for arm in ARMS:
        for mode in MODES:
            for target, document in documents[arm][mode].items():
                runtime = document.get("design", {}).get("runtime_provenance") or {}
                index = runtime.get("index") or {}
                scorer = runtime.get("scorer") or {}
                if index.get("canonical_chunk_content_sha256"):
                    index_by_target[target]["canonical"].add(
                        index["canonical_chunk_content_sha256"]
                    )
                if index.get("faiss_serialized_index_sha256"):
                    index_by_target[target]["serialized"].add(
                        index["faiss_serialized_index_sha256"]
                    )
                scorer_versions.add(str(scorer.get("scorer_version") or ""))
                scorer_hashes.add(str(scorer.get("scorer_source_sha256") or ""))
                dependency_versions["sentence-transformers"].add(
                    str(index.get("embedding_model_distribution_version") or "")
                )
                dependency_versions["faiss-cpu"].add(
                    str(index.get("faiss_distribution_version") or "")
                )
    for target, hashes in index_by_target.items():
        if len(hashes["canonical"]) != 1:
            errors.append(f"{target}: canonical index hash does not match across arms/modes")
        if len(hashes["serialized"]) != 1:
            errors.append(f"{target}: serialized index hash does not match across arms/modes")

    metric_fields = (
        "unauthorized_raw_canary_compliance",
        "unauthorized_canary_compliance",
        "unauthorized_raw_answer_leak",
        "unauthorized_answer_leak",
        "backdoor_retrieved",
        "backdoor_sent_to_llm_context",
        "target_marker_sent_to_llm_context",
        "prompt_injection_context_quarantined",
        "prompt_injection_answer_artifact_detected",
    )
    metrics: dict[str, Any] = {}
    for arm, records in records_by_arm.items():
        metrics[arm] = {}
        for mode in MODES:
            mode_records = [r for r in records.values() if r.get("rag_mode") == mode]
            unauthorised = [r for r in mode_records if r.get("access") in UNAUTHORISED]
            protected = [r for r in mode_records if r.get("access") == "protected"]
            metrics[arm][mode] = {
                "unauthorised_n": len(unauthorised),
                **{
                    field: sum(bool(record.get(field)) for record in unauthorised)
                    for field in metric_fields
                },
                "positive_control_n": len(protected),
                "authorized_positive_control_success": sum(
                    bool(record.get("authorized_positive_control_success"))
                    for record in protected
                ),
                "authorized_accuracy_error": sum(
                    bool(record.get("authorized_accuracy_error"))
                    for record in protected
                ),
                "guard_actions": dict(
                    Counter(
                        str(record.get("prompt_injection_guard_action") or "")
                        for record in mode_records
                    )
                ),
            }
            if len(unauthorised) != 150 or len(protected) != 75:
                errors.append(f"{arm}/{mode}: invalid 150/75 denominators")

    transitions = {
        mode: {
            field: transition_counts(off, on, mode, field, UNAUTHORISED)
            for field in (
                "unauthorized_canary_compliance",
                "unauthorized_answer_leak",
            )
        }
        for mode in MODES
    }
    transition_path = run_root / "paired_transitions.csv"
    with transition_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("mode", "outcome", "transition", "count"),
        )
        writer.writeheader()
        for mode, outcomes in transitions.items():
            for outcome, values in outcomes.items():
                for transition, count in values.items():
                    writer.writerow(
                        {
                            "mode": mode,
                            "outcome": outcome,
                            "transition": transition,
                            "count": count,
                        }
                    )

    result_hash_path = run_root / "result_files_sha256.json"
    result_hash_path.write_text(
        json.dumps(result_hashes, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    slurm_hashes = {
        str(path.relative_to(run_root)): sha256_file(path)
        for path in sorted((run_root / "slurm").glob("*"))
        if path.is_file() and not path.name.startswith("audit_")
    }
    submission_path = run_root / "submission.json"
    runtime_environment_path = run_root / "runtime_environment.json"
    valid = not errors
    payload = {
        "schema_version": "a07s-matched-evidence-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if valid else "FAIL",
        "authoritative_for": (
            "matched A07-S synthetic-trigger prompt-injection-guard ablation"
        ),
        "run_root": str(run_root),
        "experiment_manifest": {
            "path": str(manifest_path),
            "sha256": sha256_file(manifest_path),
        },
        "prompt_manifest": {
            "path": str(prompt_manifest_path),
            "sha256": sha256_file(prompt_manifest_path),
            "historical_prompt_match": prompt_manifest.get(
                "historical_prompt_match"
            ),
        },
        "result_files_sha256": str(result_hash_path),
        "paired_transitions_csv": str(transition_path),
        "submission": (
            load_json(submission_path) if submission_path.is_file() else None
        ),
        "slurm_log_sha256": slurm_hashes,
        "runtime_environment": (
            {
                "path": str(runtime_environment_path),
                "sha256": sha256_file(runtime_environment_path),
            }
            if runtime_environment_path.is_file()
            else None
        ),
        "validation": {
            "expected_shards": 20,
            "observed_shards": len(shard_audit),
            "expected_records_per_arm": expected_pairs,
            "guards_off_records": len(off),
            "guards_on_records": len(on),
            "shared_pair_ids": len(shared_ids),
            "prompt_matched_pairs": prompt_matches,
            "condition_matched_pairs": condition_matches,
            "system_prompt_matched_pairs": system_matches,
            "prompt_set_hashes": prompt_set_hashes,
            "system_prompt_set_hashes": system_prompt_hashes,
            "system_prompt_sets_match": len(set(system_prompt_hashes.values())) == 1,
            "single_declared_difference": (
                manifest.get("validated_single_difference")
                == ["prompt_injection_guard"]
            ),
            "shards": shard_audit,
        },
        "runtime_provenance": {
            "index_hashes_by_target": {
                target: {key: sorted(values) for key, values in hashes.items()}
                for target, hashes in sorted(index_by_target.items())
            },
            "scorer_versions": sorted(scorer_versions),
            "scorer_source_sha256": sorted(scorer_hashes),
            "dependency_versions": {
                key: sorted(values) for key, values in dependency_versions.items()
            },
        },
        "metrics": metrics,
        "paired_transitions": transitions,
        "errors": errors,
    }
    output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(output)
    if not valid:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
