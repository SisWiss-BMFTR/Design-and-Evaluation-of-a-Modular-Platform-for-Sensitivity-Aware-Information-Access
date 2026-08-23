#!/usr/bin/env python3
"""Check the thesis evidence classes, provenance, generated tables, and PDF."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse


ROOT = Path(__file__).resolve().parents[1]
CHAPTERS = ROOT / "thesis/chapters"
FIGURES = ROOT / "thesis/figures/results"
MODES = ("secure_rag_mode", "sensitivity_eval_mode")
ATTACKS = ("A01", "A02", "A03", "A04", "A05", "A06", "A07", "A08")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def require(text: str, token: str, reason: str, checks: list[dict[str, str]]) -> None:
    if token not in text:
        raise AssertionError(f"Missing {token!r}: {reason}")
    checks.append({"status": "pass", "check": reason, "token": token})


def reject(text: str, pattern: str, reason: str, checks: list[dict[str, str]]) -> None:
    if re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL):
        raise AssertionError(reason)
    checks.append({"status": "pass", "check": reason, "token": pattern})


def load(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--build-log", type=Path, required=True)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--skip-external-raw-rehash",
        action="store_true",
        help="Verify the compact raw manifest without following its historical file:// URI.",
    )
    args = parser.parse_args()
    args.evidence_dir = args.evidence_dir.resolve()
    args.build_log = args.build_log.resolve()
    args.pdf = args.pdf.resolve()
    args.report = args.report.resolve()
    metrics_path = args.evidence_dir / "matched_ablation_metric_summary.json"
    provenance_path = args.evidence_dir / "provenance_with_ablations.json"
    package_provenance_path = (
        args.evidence_dir / "package_comparison_provenance.json"
    )
    metrics = load(metrics_path)["metrics"]
    provenance = load(provenance_path)
    package_provenance = load(package_provenance_path)
    if not provenance.get("all_valid"):
        raise AssertionError("Matched-ablation provenance audit did not pass")
    if provenance.get("schema_version") != "matched-ablation-provenance-v2":
        raise AssertionError("Matched-ablation provenance schema is not v2")
    if (
        package_provenance.get("schema_version")
        != "package-comparison-provenance-v3"
    ):
        raise AssertionError("Package-comparison provenance schema is not v3")
    if any(
        "guard ablation" in str(item.get("evidence_purpose", ""))
        for item in package_provenance.get("entries", [])
    ):
        raise AssertionError("Package ledger contains superseded matched rows")
    prompt_audit_path = ROOT / package_provenance[
        "package_prompt_provenance_audit"
    ]
    prompt_audit = load(prompt_audit_path)
    if prompt_audit.get("schema_version") != "package-prompt-provenance-a01-a02-v1":
        raise AssertionError("A01/A02 package-prompt audit schema is not v1")
    if prompt_audit.get("status") != "PASS":
        raise AssertionError("A01/A02 package-prompt audit did not pass")
    if prompt_audit["a01"]["target_comparison"] != {
        "targets": 5,
        "identical": 0,
        "different": 5,
        "csv": "a01_target_prompt_comparison.csv",
        "json": "a01_target_prompt_comparison.json",
        "markdown": "a01_target_prompt_comparison.md",
    }:
        raise AssertionError("A01 five-target prompt comparison is not 0/5 identical")
    a02_prompt_counts = prompt_audit["a02"]["comparison"]
    expected_a02 = {
        "conditions": 450,
        "warmup_prompt_rows_compared": 900,
        "conditions_with_identical_warmups": 450,
        "conditions_with_different_warmups": 0,
        "conditions_with_identical_final_attack_prompt": 0,
        "conditions_with_different_final_attack_prompt": 450,
        "conditions_with_identical_complete_user_prompt_sequence": 0,
        "conditions_with_different_complete_user_prompt_sequence": 450,
    }
    for key, expected in expected_a02.items():
        if a02_prompt_counts.get(key) != expected:
            raise AssertionError(
                f"A02 prompt audit {key}={a02_prompt_counts.get(key)!r}, "
                f"expected {expected!r}"
            )

    supplemental_path = (
        ROOT
        / "outputs/final_thesis_supplemental_evidence_20260806/supplemental_component_evidence.json"
    )
    supplemental = load(supplemental_path)
    if supplemental.get("schema_version") != "final-thesis-supplemental-component-evidence-v2":
        raise AssertionError("Supplemental component-evidence schema is not v2")
    if supplemental.get("status") != "PASS":
        raise AssertionError("Supplemental component-evidence audit did not pass")
    for relative_path, expected_hash in supplemental.get(
        "source_artifacts_sha256", {}
    ).items():
        source_path = ROOT / relative_path
        if not source_path.is_file():
            raise AssertionError(f"Missing supplemental source artifact: {source_path}")
        if sha256(source_path) != expected_hash:
            raise AssertionError(
                f"Supplemental source-artifact hash changed: {relative_path}"
            )
    supplemental_classes = supplemental["evidence_classes"]
    replay = supplemental_classes["deterministic_replay"]
    if replay.get("outcomes") != {"TN": 1217, "TP": 205, "FP": 428}:
        raise AssertionError("Supplemental replay confusion counts changed")
    if replay.get("benign_outcomes") != {"TN": 44, "FP": 6}:
        raise AssertionError("Supplemental benign-control counts changed")
    pilot = supplemental_classes["pilot"]["summary"]
    if pilot["A01"]["off_delivered_leak"] != 0 or pilot["A01"]["pilot_gate_nonzero_off_leakage"]:
        raise AssertionError("A01 pilot no longer records a failed non-zero gate")
    if pilot["A02"]["off_delivered_leak"] != 4 or not pilot["A02"]["pilot_gate_nonzero_off_leakage"]:
        raise AssertionError("A02 pilot no longer records a passed non-zero gate")
    full_a02 = supplemental_classes["full_a02_challenge"]["summary"]
    expected_full_a02 = {
        "unauthorised_n": 150,
        "positive_control_n": 75,
        "off_policy_aware_leak": 12,
        "on_policy_aware_leak": 0,
        "verifier_detected": 62,
        "protected_full_row_off": 72,
        "protected_full_row_on": 72,
        "protected_verifier_detected": 0,
    }
    for key, expected in expected_full_a02.items():
        if full_a02.get(key) != expected:
            raise AssertionError(f"Full A02 supplemental {key} changed")
    if full_a02.get("confusion_matrix") != {"TP": 12, "FN": 0, "FP": 50, "TN": 88}:
        raise AssertionError("Full A02 confusion matrix changed")
    full_a02_class = supplemental_classes["full_a02_challenge"]
    if full_a02_class.get("role_confusion") != [
        {"group": "Role", "stratum": "Public", "n": 75, "TP": 12, "FN": 0, "FP": 25, "TN": 38},
        {"group": "Role", "stratum": "Internal", "n": 75, "TP": 0, "FN": 0, "FP": 25, "TN": 50},
    ]:
        raise AssertionError("Full A02 role confusion breakdown changed")
    target_counts = [(r["TP"], r["FN"], r["FP"], r["TN"]) for r in full_a02_class.get("target_confusion", [])]
    if target_counts != [(0, 0, 10, 20), (1, 0, 10, 19), (0, 0, 10, 20), (9, 0, 10, 11), (2, 0, 10, 18)]:
        raise AssertionError("Full A02 target confusion breakdown changed")
    if [r["count"] for r in full_a02_class.get("false_replacement_patterns", [])] != [35, 10, 5]:
        raise AssertionError("Full A02 false-replacement pattern breakdown changed")
    a07s = supplemental_classes["matched_a07s"]["metrics"]
    for mode in MODES:
        off = a07s["arm_A_injection_guard_off"][mode]
        on = a07s["arm_B_injection_guard_on"][mode]
        if off["unauthorized_canary_compliance"] != 150 or on["unauthorized_canary_compliance"] != 0:
            raise AssertionError(f"A07-S delivered canary transition changed for {mode}")
        if off["authorized_positive_control_success"] != 75 or on["authorized_positive_control_success"] != 75:
            raise AssertionError(f"A07-S positive control changed for {mode}")

    a06 = supplemental_classes["matched_a06"]
    a06_technical = a06["technical_audit"]
    if a06_technical.get("status") != "PASS":
        raise AssertionError("Supplemental A06 technical audit did not pass")
    if (
        a06_technical.get("interpretation_decision")
        != "SUPPORTS_GUARD_EFFECT_ON_PRIMARY_OUTCOME"
    ):
        raise AssertionError("Supplemental A06 interpretation gate changed")
    if not a06_technical.get("evidence_hash_binding_verified"):
        raise AssertionError("Supplemental A06 authoritative hash binding failed")
    if (
        a06_technical.get("authoritative_evidence_sha256_actual")
        != "5adfa65641e5c032daed6aa4b93ce3e6850923f57fa871b7092de0b278ba5512"
    ):
        raise AssertionError("Supplemental A06 authoritative evidence hash changed")

    a06_full = a06["full_confirmatory"]
    if a06_full.get("expected") != {
        "result_files": 20,
        "records_per_shard": 45,
        "records_per_arm": 450,
        "matched_pairs": 450,
    }:
        raise AssertionError("Supplemental A06 expected full-run matrix changed")
    if a06_full.get("observed") != {
        "result_files": 20,
        "records": 900,
        "records_by_arm": {
            "arm_A_guard_off": 450,
            "arm_B_guard_on": 450,
        },
    }:
        raise AssertionError("Supplemental A06 observed full-run matrix changed")
    a06_modes = {
        (row["mode"], row["arm"]): row for row in a06_full["mode_metrics"]
    }
    expected_a06_modes = {
        ("secure_rag_mode", "arm_A_guard_off"): (150, 150, 0, 0, 0),
        ("secure_rag_mode", "arm_B_guard_on"): (0, 0, 0, 0, 0),
        ("sensitivity_eval_mode", "arm_A_guard_off"): (150, 150, 0, 0, 0),
        ("sensitivity_eval_mode", "arm_B_guard_on"): (145, 0, 0, 0, 0),
    }
    for key, expected in expected_a06_modes.items():
        row = a06_modes[key]
        observed = (
            row["unauthorised_raw_canary"],
            row["unauthorised_delivered_canary"],
            row["unauthorised_raw_protected_leak"],
            row["unauthorised_delivered_protected_leak"],
            row["positive_control_success"],
        )
        if observed != expected or row["unauthorised_n"] != 150 or row["positive_control_n"] != 75:
            raise AssertionError(f"Supplemental A06 mode metrics changed for {key}")
    transitions = a06_full["paired_transitions"]
    if transitions.get("shared_pair_count") != 450:
        raise AssertionError("Supplemental A06 matched-pair count changed")
    if transitions.get("unauthorised_shared_pair_count") != 300:
        raise AssertionError("Supplemental A06 unauthorised pair count changed")
    if transitions.get("delivered_canary_transitions") != {"1->0": 300}:
        raise AssertionError("Supplemental A06 delivered transition changed")
    if transitions.get("raw_canary_transitions") != {"1->0": 155, "1->1": 145}:
        raise AssertionError("Supplemental A06 raw transition changed")

    a06_diagnostics = a06_full["retrieval_and_positive_control_diagnostics"]
    expected_a06_diagnostics = {
        "protected_records_n": 300,
        "protected_target_retrieved": 0,
        "protected_secret_in_retrieved_context": 0,
        "protected_secret_sent_to_llm_context": 0,
        "protected_positive_control_success": 0,
    }
    for key, expected in expected_a06_diagnostics.items():
        if a06_diagnostics.get(key) != expected:
            raise AssertionError(f"Supplemental A06 diagnostic {key} changed")
    a06_matching = a06_full["matching_and_runtime_provenance"]
    for key in (
        "frozen_prompt_sequence_mismatches",
        "cross_arm_user_prompt_mismatches",
        "cross_arm_system_prompt_mismatches",
        "cross_arm_request_setting_mismatches",
        "cross_arm_runtime_index_mismatches",
        "cross_arm_scorer_mismatches",
    ):
        if a06_matching.get(key) != 0:
            raise AssertionError(f"Supplemental A06 provenance mismatch: {key}")
    if a06_matching.get("shared_pairs") != 450:
        raise AssertionError("Supplemental A06 provenance pair count changed")
    if a06_matching.get("cross_arm_exact_api_message_mismatches") != 450:
        raise AssertionError("Supplemental A06 API-message difference count changed")
    if a06_matching.get("cross_arm_exact_api_message_mismatches_by_mode") != {
        "secure_rag_mode": 225,
        "sensitivity_eval_mode": 225,
    }:
        raise AssertionError("Supplemental A06 API-message mode breakdown changed")
    if a06_matching["index"].get("chunk_count_per_shard") != 301:
        raise AssertionError("Supplemental A06 index size changed")
    if a06_matching["scorer"] != {
        "scorer_id": "a06-poisoned-row-integrity-confidentiality-scorer",
        "scorer_version": "a06-poisoned-row-v1",
        "scorer_source_sha256": "090d7b1a4742e01005a1390b7554b8f73fd8e59d5b923c9e8a4ba68fda15a171",
    }:
        raise AssertionError("Supplemental A06 scorer provenance changed")
    execution = a06_full["execution_completeness"]
    if execution.get("per_record_execution_error_field_present"):
        raise AssertionError("A nonexistent A06 per-record error field is being claimed")
    if not execution.get("all_result_files_have_expected_cardinality"):
        raise AssertionError("Supplemental A06 shard completeness changed")
    if execution.get("fatal_pattern_match_count") != 0:
        raise AssertionError("Supplemental A06 logs contain a fatal pattern")
    scheduler = execution["scheduler_receipt"]
    scheduler_path = ROOT / scheduler["path"]
    if sha256(scheduler_path) != scheduler["sha256"]:
        raise AssertionError("Supplemental A06 scheduler receipt hash changed")
    scheduler_payload = load(scheduler_path)
    if scheduler_payload.get("validation") != {
        "full_array_tasks": 5,
        "audit_jobs": 1,
        "all_states_completed": True,
        "all_exit_codes_zero": True,
    }:
        raise AssertionError("Supplemental A06 scheduler completion changed")
    if len(scheduler_payload.get("jobs", [])) != 6:
        raise AssertionError("Supplemental A06 scheduler receipt is incomplete")
    for relative_path, expected_hash in execution["log_paths_sha256"].items():
        log_path = ROOT / relative_path
        if sha256(log_path) != expected_hash:
            raise AssertionError(f"Supplemental A06 execution log changed: {relative_path}")

    a06_run_root = (
        ROOT / a06_technical["authoritative_evidence_path"]
    ).parent
    source_manifest = load(a06_run_root / "source_manifest.json")
    if canonical_sha256(source_manifest["files_sha256"]) != source_manifest[
        "canonical_file_set_sha256"
    ]:
        raise AssertionError("Supplemental A06 source-manifest canonical hash changed")
    for relative_path, expected_hash in source_manifest["files_sha256"].items():
        source_path = a06_run_root / "source_snapshot" / relative_path
        if sha256(source_path) != expected_hash:
            raise AssertionError(f"Supplemental A06 source snapshot changed: {relative_path}")

    a06_pilot = a06["pilot_validation"]
    if a06_pilot.get("technical_audit_status") != "PASS":
        raise AssertionError("Supplemental A06 pilot audit did not pass")
    if a06_pilot.get("observed") != {
        "result_files": 32,
        "records": 384,
        "records_by_arm": {
            "arm_A_guard_off": 192,
            "arm_B_guard_on": 192,
        },
    }:
        raise AssertionError("Supplemental A06 pilot matrix changed")
    pilot_profiles = {
        (row["profile"], row["arm"]): row
        for row in a06_pilot["profile_summary_across_modes"]
    }
    expected_pilot_delivered = {
        ("workflow_follow_v1", "arm_A_guard_off"): 32,
        ("workflow_follow_v1", "arm_B_guard_on"): 0,
        ("localized_de_v1", "arm_A_guard_off"): 32,
        ("localized_de_v1", "arm_B_guard_on"): 0,
        ("audit_paraphrase_v1", "arm_A_guard_off"): 14,
        ("audit_paraphrase_v1", "arm_B_guard_on"): 0,
        ("benign_metadata_control_v1", "arm_A_guard_off"): 0,
        ("benign_metadata_control_v1", "arm_B_guard_on"): 0,
    }
    for key, expected in expected_pilot_delivered.items():
        row = pilot_profiles[key]
        if (
            row["unauthorised_delivered_canary"] != expected
            or row["unauthorised_delivered_protected_leak"] != 0
            or row["unauthorised_n"] != 32
        ):
            raise AssertionError(f"Supplemental A06 pilot profile changed for {key}")
    benign_a06 = a06["benign_metadata_post_hoc"]
    if benign_a06.get("analysis_status") != "POST_HOC_EXPLORATORY_NOT_PREREGISTERED":
        raise AssertionError("Supplemental A06 benign result lost its exploratory label")
    if benign_a06.get("delivered_exact_name_and_market") != 96 or benign_a06.get("n") != 96:
        raise AssertionError("Supplemental A06 benign 96/96 result changed")
    a06_root_cause = a06["positive_control_root_cause"]
    if a06_root_cause.get("finding") != "STRUCTURAL_ZERO_NON_INFORMATIVE_POSITIVE_CONTROL":
        raise AssertionError("Supplemental A06 positive-control diagnosis changed")
    a06_root_cause_path = ROOT / a06_root_cause["path"]
    if sha256(a06_root_cause_path) != a06_root_cause["sha256"]:
        raise AssertionError("Supplemental A06 root-cause audit hash changed")
    raw_archive_binding = a06["raw_result_archive"]
    raw_archive_path = ROOT / raw_archive_binding["path"]
    if sha256(raw_archive_path) != raw_archive_binding["sha256"]:
        raise AssertionError("Supplemental A06 raw archive manifest hash changed")
    raw_archive = load(raw_archive_path)
    if raw_archive.get("status") != "PRESENT_AT_CAPTURE_LOCATION_NOT_GIT_TRACKED":
        raise AssertionError("Supplemental A06 raw archive status changed")
    if raw_archive.get("result_json_files") != 52 or raw_archive.get("records") != 1284:
        raise AssertionError("Supplemental A06 raw archive inventory count changed")
    if canonical_sha256(raw_archive["inventory"]) != raw_archive[
        "canonical_inventory_sha256"
    ]:
        raise AssertionError("Supplemental A06 raw archive inventory hash changed")
    if raw_archive_binding.get("canonical_inventory_sha256") != raw_archive[
        "canonical_inventory_sha256"
    ]:
        raise AssertionError("Supplemental A06 ledger/archive binding changed")
    parsed_archive_uri = urlparse(raw_archive["capture_location"]["uri"])
    archive_root = Path(unquote(parsed_archive_uri.path))
    raw_archive_available = archive_root.is_dir() and not args.skip_external_raw_rehash
    if raw_archive_available:
        for item in raw_archive["inventory"]:
            raw_path = archive_root / item["path_relative_to_run_root"]
            if raw_path.stat().st_size != item["bytes"] or sha256(raw_path) != item["sha256"]:
                raise AssertionError(
                    "Supplemental A06 retained raw artifact changed: "
                    f"{item['path_relative_to_run_root']}"
                )

    chapter_text = {
        path.name: path.read_text(encoding="utf-8")
        for path in sorted(CHAPTERS.glob("chapter0[5-9]_*.tex"))
    }
    appendix_text = {
        path.name: path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "thesis/appendices").glob("*.tex"))
    }
    text = "\n".join([*chapter_text.values(), *appendix_text.values()])
    checks: list[dict[str, str]] = []
    checks.append(
        {
            "status": "pass",
            "check": (
                "A06 raw result archive rehashed at retained location"
                if raw_archive_available
                else "A06 raw result archive bound by tracked manifest; retained location unavailable"
            ),
            "token": raw_archive["canonical_inventory_sha256"],
        }
    )

    for token in (
        "Original baseline",
        "Hardened package",
        "Matched guard ablation",
        "Guards off",
        "Guards on",
    ):
        require(text, token, f"evidence-source terminology: {token}", checks)

    chapter6 = chapter_text["chapter06_results.tex"]
    reject(
        chapter6,
        r"guards?[- ](?:off|on)|matched guard|matched-ablation",
        "Chapter 6 remains original-baseline only",
        checks,
    )
    require(
        chapter_text["chapter07_vulnerability_analysis.tex"],
        r"\label{tab:guard-ablation-evidence-classes}",
        "guard-ablation evidence-class overview is included",
        checks,
    )
    require(
        chapter_text["chapter09_conclusion.tex"],
        "A07-S",
        "synthetic-trigger A07-S remains explicitly distinguished",
        checks,
    )
    for attack in ("A04", "A06"):
        experiment = next(
            item
            for item in provenance["experiments"]
            if item["attack"] == attack
        )
        prompt_provenance = experiment.get("prompt_provenance", {})
        if prompt_provenance.get("manifest_style_raw") != "neutral":
            raise AssertionError(
                f"{attack} authoritative matched experiment does not carry the "
                "historical family-label-omitted manifest style"
            )
        if "family-label-omitted" not in prompt_provenance.get(
            "label_statuses", []
        ):
            raise AssertionError(
                f"{attack} prompt provenance lacks family-label-omitted status"
            )
        checks.append(
            {
                "status": "pass",
                "check": f"{attack} family-label-omitted experiment selected",
                "token": experiment["experiment_root"],
            }
        )
    require(
        chapter_text["chapter07_vulnerability_analysis.tex"],
        "65/150 sensitivity-mode",
        "A04 family-label-omitted guards-off sensitivity result is reported",
        checks,
    )
    reject(
        text,
        r"\bneutral(?:-prompt| prompts?| A0[1-8]| runs?| experiment)",
        "historical manifest style is not overstated as semantic prompt neutrality",
        checks,
    )
    require(
        (CHAPTERS / "chapter03_system_architecture.tex").read_text(encoding="utf-8"),
        "300 indexed entities",
        "entity-level index unit is reported in the synchronized thesis source",
        checks,
    )
    require(
        appendix_text["appendix_experiment_protocols.tex"],
        r"\input{generated/a01_package_prompt_provenance_table}",
        "A01 five-target package-prompt table is included",
        checks,
    )
    require(
        text,
        "900/900 warm-up prompt rows",
        "A02 warm-up prompt equivalence is reported",
        checks,
    )
    require(
        text,
        "450/450 conditions",
        "A02 final-prompt difference is reported",
        checks,
    )
    for token, reason in (
        (r"\input{generated/verifier_replay_summary_table}", "verifier replay table is included"),
        (r"\input{generated/a02_full_verifier_challenge_table}", "full A02 challenge table is included"),
        (r"\input{generated/a02_full_verifier_breakdown_table}", "full A02 role/target breakdown table is included"),
        (r"\input{generated/a02_full_verifier_false_replacement_table}", "full A02 false-replacement table is included"),
        (r"\input{generated/a06_supplemental_pilot_profiles_table}", "supplemental A06 pilot-profile table is included"),
        (r"\input{generated/a06_supplemental_frozen_challenge_table}", "supplemental A06 full-challenge table is included"),
        (r"\input{generated/a07s_matched_ablation_table}", "matched A07-S table is included"),
        (
            "from 12/150 with the verifier off to 0/150 with it on",
            "full A02 identical-raw-answer transition is reported",
        ),
        ("50/138", "full A02 false-replacement denominator is reported"),
        ("72/75 in both", "full A02 protected positive-control preservation is reported"),
        ("6/50", "benign replay replacements are reported"),
        ("300/300 to 0/300", "supplemental A06 delivered-canary transition is reported"),
        ("145/150 raw canary", "supplemental A06 sensitivity-mode raw result is reported"),
        ("0/300 protected records", "supplemental A06 missing retrieval opportunity is reported"),
        ("96/96", "supplemental A06 exploratory benign result is reported"),
        ("450 paired API-message sequences differed", "supplemental A06 expected API-message differences are reported"),
        ("Exact frozen primary example", "supplemental A06 exact prompt and poison-body example is included"),
        ("family-label-omitted but mechanism-directed", "supplemental A06 prompt semantics are bounded"),
        ("It is not a neutral or generic product request", "supplemental A06 is not overstated as neutral"),
        ("no confidentiality reduction is claimed", "supplemental A06 confidentiality boundary is explicit"),
        ("neither utility preservation nor guard-caused utility loss", "supplemental A06 utility boundary is explicit"),
        ("A07-S now provides matched evidence", "A07-S is no longer left as missing future work"),
    ):
        require(text, token, reason, checks)
    reject(
        text,
        r"A07 still requires a matched A07-S|matched A07-S experiment.{0,40}remain necessary",
        "completed matched A07-S is not described as missing future work",
        checks,
    )
    require(
        text,
        "does not attribute the historical original-to-hardened package difference to the verifier",
        "supplemental verifier evidence is not used for retroactive package causality",
        checks,
    )
    reject(
        text,
        r"exact original prompt text is unavailable for A01|exact original prompts are unavailable for A01",
        "A01 is not mislabeled as simply exact-prompt unavailable",
        checks,
    )
    reject(
        text,
        r"supplemental A06.{0,160}(?:demonstrates|establishes|shows)\s+(?:a\s+)?(?:confidentiality reduction|utility preservation)",
        "supplemental A06 is not given a broad confidentiality or utility claim",
        checks,
    )
    reject(
        chapter_text["chapter05_experiments.tex"],
        r"submitted the ordinary-looking request|user prompt asked the ordinary-looking",
        "A06 mechanism-directed prompts are not called ordinary-looking",
        checks,
    )

    for experiment in provenance["experiments"]:
        index_provenance = experiment.get("index_provenance", {})
        scorer_provenance = experiment.get("scorer_provenance", {})
        for key in (
            "canonical_content_sha256",
            "serialized_faiss_sha256",
            "runtime_schema_versions",
            "embedding_model_distribution_versions",
            "faiss_distribution_versions",
        ):
            if not isinstance(index_provenance.get(key), list):
                raise AssertionError(
                    f"{experiment['attack']} index provenance {key} is not a list"
                )
        for key in ("ids", "versions", "source_sha256"):
            if not isinstance(scorer_provenance.get(key), list):
                raise AssertionError(
                    f"{experiment['attack']} scorer provenance {key} is not a list"
                )
        if (
            index_provenance.get("availability") == "unavailable"
            and index_provenance.get("match_across_arms") is not None
        ):
            raise AssertionError(
                f"{experiment['attack']} unavailable runtime provenance is "
                "incorrectly represented as a match/mismatch"
            )
    checks.append(
        {
            "status": "pass",
            "check": "provenance v2 uses typed arrays and null for unavailable matches",
            "token": "matched-ablation-provenance-v2",
        }
    )
    reject(
        text,
        r"(?:pre-hardening|original system).{0,100}guards off|guards off.{0,100}(?:pre-hardening|original system)",
        "guards-off arm is never called the historical original or pre-hardening system",
        checks,
    )

    for attack in ATTACKS:
        require(
            appendix_text["appendix_detailed_hardening.tex"],
            rf"\input{{generated/{attack.lower()}_matched_ablation_table}}",
            f"{attack} generated ablation table included",
            checks,
        )
        for suffix in (".pdf", ".png"):
            figure = FIGURES / f"{attack.lower()}_matched_guard_ablation{suffix}"
            if not figure.is_file() or figure.stat().st_size == 0:
                raise AssertionError(f"Missing figure: {figure}")
        checks.append(
            {
                "status": "pass",
                "check": f"{attack} generated ablation figures",
                "token": attack,
            }
        )
        for arm in ("guards_off", "guards_on"):
            for mode in MODES:
                values = metrics[attack][arm][mode]
                if values["unauthorised_n"] != 150:
                    raise AssertionError(
                        f"{attack} {arm} {mode}: unauthorised denominator is not 150"
                    )
                if values["positive_control_n"] != 75:
                    raise AssertionError(
                        f"{attack} {arm} {mode}: positive denominator is not 75"
                    )
        checks.append(
            {
                "status": "pass",
                "check": f"{attack} matched denominators",
                "token": "150/75",
            }
        )

    for stem in (
        "cross_attack_matched_guard_ablations",
        "historical_baseline_vs_matched_guards_off",
    ):
        for suffix in (".pdf", ".png"):
            figure = FIGURES / f"{stem}{suffix}"
            if not figure.is_file() or figure.stat().st_size == 0:
                raise AssertionError(f"Missing figure: {figure}")
        checks.append(
            {"status": "pass", "check": f"generated figure {stem}", "token": stem}
        )

    if not args.build_log.exists():
        raise AssertionError(f"Missing build log: {args.build_log}")
    log_text = args.build_log.read_text(encoding="utf-8", errors="replace")
    reject(log_text, r"Overfull \\\\hbox", "compiled layout has no overfull hbox", checks)
    reject(
        log_text,
        r"Undefined control sequence|LaTeX Error|Emergency stop|Fatal error",
        "compiled thesis has no TeX errors",
        checks,
    )
    if not args.pdf.exists() or args.pdf.stat().st_size == 0:
        raise AssertionError(f"Missing compiled PDF: {args.pdf}")

    artifacts = [
        ROOT / "thesis/main.tex",
        *[CHAPTERS / name for name in sorted(chapter_text)],
        metrics_path,
        provenance_path,
        package_provenance_path,
        prompt_audit_path,
        prompt_audit_path.parent / "a01_target_prompt_comparison.csv",
        prompt_audit_path.parent / "a02_prompt_sequence_comparison.csv",
        supplemental_path,
        ROOT / "outputs/final_thesis_supplemental_evidence_20260806/a06_full_mode_summary.csv",
        ROOT / "outputs/final_thesis_supplemental_evidence_20260806/a06_pilot_profile_summary.csv",
        ROOT / "outputs/final_thesis_supplemental_evidence_20260806/a06_full_result_file_provenance.csv",
        ROOT / "outputs/final_thesis_supplemental_evidence_20260806/a06_positive_control_root_cause_audit.json",
        raw_archive_path,
        scheduler_path,
        ROOT / "thesis/generated/verifier_replay_summary_table.tex",
        ROOT / "thesis/generated/a02_full_verifier_challenge_table.tex",
        ROOT / "thesis/generated/a02_full_verifier_breakdown_table.tex",
        ROOT / "thesis/generated/a02_full_verifier_false_replacement_table.tex",
        ROOT / "thesis/generated/a06_supplemental_pilot_profiles_table.tex",
        ROOT / "thesis/generated/a06_supplemental_frozen_challenge_table.tex",
        ROOT / "thesis/generated/a07s_matched_ablation_table.tex",
        args.evidence_dir / "README.md",
        args.pdf,
    ]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(
            {
                "status": "pass",
                "checks": checks,
                "artifact_sha256": {
                    str(path.relative_to(ROOT)): sha256(path) for path in artifacts
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(args.report)


if __name__ == "__main__":
    main()
