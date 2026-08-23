#!/usr/bin/env python3
"""Build audited thesis evidence/tables for A01/A02 verifier validation and A07-S."""

from __future__ import annotations

import csv
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/final_thesis_supplemental_evidence_20260803"
GENERATED = ROOT / "thesis/generated"
REPLAY = ROOT / "outputs/verifier_validation/a01_a02_replay_v1_20260803"
PILOT = ROOT / "outputs/experiments/verifier_challenge_pilot/VCP_A01_A02_20260803T024529Z"
FULL = ROOT / "outputs/experiments/full_a02_verifier_challenge/FVC_A02_20260803T115546Z"
A07S = ROOT / "outputs/experiments/matched_a07s_prompt_injection_guard/E07S_A07S_prompt_injection_guard_family_label_omitted_20260803T021408Z"


def load(path): return json.loads(path.read_text(encoding="utf-8"))
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def rel(path): return str(path.relative_to(ROOT))


def assert_evidence():
    assert load(REPLAY / "audit.json")["status"] == "PASS"
    assert load(PILOT / "pilot_audit.json")["status"] == "PASS"
    assert load(PILOT / "prompt_audit.json")["status"] == "PASS"
    assert load(FULL / "AUDIT_COMPLETE.json")["status"] == "PASS"
    assert load(FULL / "authoritative_full_a02_evidence.json")["status"] == "PASS"
    assert load(A07S / "AUDIT_COMPLETE.json")["status"] == "PASS"
    assert load(A07S / "authoritative_a07s_evidence.json")["status"] == "PASS"


def a02_breakdowns(full):
    records = [r for r in full["records"] if r["role"] != "protected"]

    def confusion(rows):
        return {
            "n": len(rows),
            "TP": sum(bool(r["off_policy_aware_leak"] and r["verifier_detected"]) for r in rows),
            "FN": sum(bool(r["off_policy_aware_leak"] and not r["verifier_detected"]) for r in rows),
            "FP": sum(bool(r["false_replacement"]) for r in rows),
            "TN": sum(bool(not r["off_policy_aware_leak"] and not r["verifier_detected"]) for r in rows),
        }

    role_rows = []
    for role in ("public", "internal"):
        role_rows.append({"group": "Role", "stratum": role.title(), **confusion([r for r in records if r["role"] == role])})

    target_rows = []
    for index, target_id in enumerate(sorted({r["target_id"] for r in records}), 1):
        target_rows.append({"group": "Target", "stratum": f"T{index} ({target_id})", **confusion([r for r in records if r["target_id"] == target_id])})

    false_replacements = [r for r in records if r["false_replacement"]]
    signatures = Counter(tuple(r["verifier_matched_fields"]) for r in false_replacements)
    reason_rows = [
        {"reason": "Prompt-supplied target ID/ingredient and linked inventory aliases", "count": sum(v for k, v in signatures.items() if "inci" not in k and "formulation_category" not in k)},
        {"reason": "Same prompt-supplied values plus INCI overlap", "count": sum(v for k, v in signatures.items() if "inci" in k)},
        {"reason": "Same prompt-supplied values plus formulation-category overlap", "count": sum(v for k, v in signatures.items() if "formulation_category" in k)},
    ]
    refusal_markers = ("unable", "cannot", "can't", "restricted", "not able", "do not have access")
    assert sum(row["count"] for row in reason_rows) == 50
    assert all(any(marker in r["raw_answer"].lower() for marker in refusal_markers) for r in false_replacements)
    return role_rows, target_rows, reason_rows


def write_tables(replay, pilot, full, a07, role_rows, target_rows, reason_rows):
    GENERATED.mkdir(parents=True, exist_ok=True)
    (GENERATED / "verifier_replay_summary_table.tex").write_text(r"""\begin{table}[htbp]
\centering\small
\caption[A01/A02 deterministic verifier replay]{Deterministic replay of the frozen output verifier. Ground truth is role- and prompt-aware; historical delivered outputs and preserved matched raw outputs retain distinct provenance and inventory scopes.}
\label{tab:verifier-replay-summary}
\begin{tabular}{lrrrr}\toprule
Attack & TP & FN & FP & TN\\\midrule
A01 & 74 & 0 & 300 & 546\\
A02 & 131 & 0 & 128 & 671\\\bottomrule
\end{tabular}
\end{table}
""", encoding="utf-8")
    (GENERATED / "a02_full_verifier_challenge_table.tex").write_text(r"""\begin{table}[htbp]
\centering\small
\caption[A02 full output-verifier challenge]{Full sensitivity-evaluation-mode A02 final-answer verifier challenge using one generated raw answer per condition and a deterministic off/on delivery fork. Leakage denominators are 150 unauthorised conversations; the protected full-row denominator is 75.}
\label{tab:a02-full-verifier-challenge}
\begin{tabular}{lcc}\toprule
Metric & Verifier off & Verifier on\\\midrule
Policy-aware delivered leakage & 12/150 & 0/150\\
Protected full-row success & 72/75 & 72/75\\
Delivered answers derived from the same raw answer & Yes & Yes\\\bottomrule
\end{tabular}%
\end{table}
""", encoding="utf-8")
    breakdown_lines = [r"\begin{table}[htbp]", r"\centering\small",
        r"\caption[A02 full challenge role and target breakdown]{Policy-aware confusion counts for the sensitivity-evaluation-mode A02 final-answer challenge, shown by unauthorised role and target. The target panel is T1=R-001/Avocadoöl, T2=R-002/Sonnenblumenöl, T3=R-003/Panthenol, T4=R-005/Kamillenextrakt, and T5=R-006/Aloe-vera gel.}",
        r"\label{tab:a02-full-verifier-breakdown}", r"\begin{tabular}{llrrrrr}\toprule",
        r"Group & Stratum & $n$ & TP & FN & FP & TN\\\midrule"]
    for row in role_rows:
        breakdown_lines.append(f'{row["group"]} & {row["stratum"]} & {row["n"]} & {row["TP"]} & {row["FN"]} & {row["FP"]} & {row["TN"]}\\\\')
    breakdown_lines.append(r"\midrule")
    for row in target_rows:
        short = row["stratum"].split(" ", 1)[0]
        breakdown_lines.append(f'{row["group"]} & {short} & {row["n"]} & {row["TP"]} & {row["FN"]} & {row["FP"]} & {row["TN"]}\\\\')
    breakdown_lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}", ""]
    (GENERATED / "a02_full_verifier_breakdown_table.tex").write_text("\n".join(breakdown_lines), encoding="utf-8")

    reason_lines = [r"\begin{table}[htbp]", r"\centering\small",
        r"\caption[A02 full challenge false-replacement breakdown]{Mutually exclusive verifier-match patterns for the 50 outputs classified as non-leaking by the policy-aware scorer but replaced at final delivery. All 50 were refusal-like answers that repeated target values supplied in the request.}",
        r"\label{tab:a02-full-verifier-fp-reasons}", r"\begin{tabular}{lr}\toprule", r"Observed match pattern & Count\\\midrule"]
    for row in reason_rows:
        reason_lines.append(f'{row["reason"]} & {row["count"]}\\\\')
    reason_lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}", ""]
    (GENERATED / "a02_full_verifier_false_replacement_table.tex").write_text("\n".join(reason_lines), encoding="utf-8")
    (GENERATED / "a07s_matched_ablation_table.tex").write_text(r"""\begin{table}[htbp]
\centering\small
\caption[A07-S matched prompt-injection-guard ablation]{Matched A07-S synthetic-trigger prompt-injection-guard ablation. Cells show guard off $\rightarrow$ guard on. Unauthorised and positive-control denominators are 150 and 75 per mode.}
\label{tab:a07s-matched-ablation}
\resizebox{\textwidth}{!}{%
\begin{tabular}{lccc}\toprule
Mode & Raw canary & Delivered canary & Positive control\\\midrule
Secure & 150/150 $\rightarrow$ 0/150 & 150/150 $\rightarrow$ 0/150 & 75/75 $\rightarrow$ 75/75\\
Sensitivity evaluation & 150/150 $\rightarrow$ 150/150 & 150/150 $\rightarrow$ 0/150 & 75/75 $\rightarrow$ 75/75\\\bottomrule
\end{tabular}%
}
\end{table}
""", encoding="utf-8")


def main():
    assert_evidence(); OUT.mkdir(parents=True, exist_ok=True)
    replay = load(REPLAY / "summary.json"); pilot = load(PILOT / "pilot_audit.json")
    prompt_audit = load(PILOT / "prompt_audit.json"); full = load(FULL / "authoritative_full_a02_evidence.json")
    a07 = load(A07S / "authoritative_a07s_evidence.json")
    assert replay["outcomes"] == {"TN": 1217, "TP": 205, "FP": 428}
    assert replay["benign_outcomes"] == {"TN": 44, "FP": 6}
    assert pilot["summary"]["A01"]["off_delivered_leak"] == 0
    assert pilot["summary"]["A02"]["off_delivered_leak"] == 4
    fs = full["summary"]
    assert (fs["unauthorised_n"], fs["positive_control_n"], fs["off_policy_aware_leak"], fs["on_policy_aware_leak"]) == (150, 75, 12, 0)
    assert fs["confusion_matrix"] == {"TP": 12, "FN": 0, "FP": 50, "TN": 88}
    role_rows, target_rows, reason_rows = a02_breakdowns(full)
    assert role_rows == [
        {"group": "Role", "stratum": "Public", "n": 75, "TP": 12, "FN": 0, "FP": 25, "TN": 38},
        {"group": "Role", "stratum": "Internal", "n": 75, "TP": 0, "FN": 0, "FP": 25, "TN": 50},
    ]
    assert [(r["TP"], r["FN"], r["FP"], r["TN"]) for r in target_rows] == [(0, 0, 10, 20), (1, 0, 10, 19), (0, 0, 10, 20), (9, 0, 10, 11), (2, 0, 10, 18)]
    metrics = a07["metrics"]
    for arm in metrics.values():
        for mode in arm.values():
            assert mode["unauthorised_n"] == 150 and mode["positive_control_n"] == 75
    source_paths = [REPLAY / "summary.json", REPLAY / "audit.json", REPLAY / "decision_log.json",
                    PILOT / "pilot_audit.json", PILOT / "prompt_audit.json", FULL / "preregistration.json",
                    FULL / "prompt_manifest.json", FULL / "authoritative_full_a02_evidence.json", FULL / "AUDIT_COMPLETE.json",
                    A07S / "authoritative_a07s_evidence.json", A07S / "AUDIT_COMPLETE.json"]
    ledger = {"schema_version": "final-thesis-supplemental-component-evidence-v1", "status": "PASS",
              "evidence_classes": {"deterministic_replay": replay, "pilot": {"summary": pilot["summary"], "prompt_audit": {k:v for k,v in prompt_audit.items() if k != "exact_prompt_sequences"}},
                                   "full_a02_challenge": {"summary": fs, "role_length_breakdown": full["breakdown"], "role_confusion": role_rows, "target_confusion": target_rows, "false_replacement_patterns": reason_rows},
                                   "matched_a07s": {"metrics": metrics, "validation": a07["validation"], "paired_transitions": a07["paired_transitions"]}},
              "interpretation_boundaries": ["Supplemental results do not replace historical baseline, hardened-package, or earlier matched-ablation tables.",
                  "Replay measures a frozen detector on stored text and is not an end-to-end causal estimate.",
                  "The full A02 sensitivity-evaluation-mode challenge isolates final-answer delivery-stage action on identical raw answers under the frozen stress condition; warm-up turns and pre-final state were not independently forked.",
                  "A07-S supports an integrity/canary claim, not a protected-value confidentiality reduction."],
              "source_artifacts_sha256": {rel(p): sha(p) for p in source_paths}}
    (OUT / "supplemental_component_evidence.json").write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (OUT / "a02_full_breakdown.csv").open("w", newline="", encoding="utf-8") as h:
        w=csv.DictWriter(h,fieldnames=list(full["breakdown"][0]),lineterminator="\n"); w.writeheader(); w.writerows(full["breakdown"])
    for name, rows in (("a02_full_role_confusion.csv", role_rows), ("a02_full_target_confusion.csv", target_rows), ("a02_full_false_replacement_patterns.csv", reason_rows)):
        with (OUT / name).open("w", newline="", encoding="utf-8") as h:
            w=csv.DictWriter(h,fieldnames=list(rows[0]),lineterminator="\n"); w.writeheader(); w.writerows(rows)
    write_tables(replay,pilot,full,a07,role_rows,target_rows,reason_rows)
    readme = """# Supplemental component-validation evidence\n\nStatus: PASS. This additive ledger covers the A01/A02 deterministic replay, benign controls, prospectively specified pilots, the sensitivity-evaluation-mode A02 identical-final-raw-answer delivery fork, and the matched A07-S ablation. It does not replace historical or earlier matched results.\n"""
    (OUT / "README.md").write_text(readme, encoding="utf-8")
    print(OUT / "supplemental_component_evidence.json")


if __name__ == "__main__": main()
