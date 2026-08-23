#!/usr/bin/env python3
"""Completeness and consistency audit for the frozen A01/A02 replay."""

import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/verifier_validation/a01_a02_replay_v1_20260803"


def load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def sha(name):
    return hashlib.sha256((OUT / name).read_bytes()).hexdigest()


def main():
    corpus = load("replay_corpus.json")["items"]
    decisions = load("decision_log.json")["decisions"]
    summary = load("summary.json")
    checks = []
    def check(name, ok, detail):
        checks.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": detail})
    ids = [x["item_id"] for x in corpus]; dids = [x["item_id"] for x in decisions]
    check("unique_corpus_ids", len(ids) == len(set(ids)), f"{len(ids)} items; {len(set(ids))} unique")
    check("one_decision_per_item", Counter(ids) == Counter(dids), f"{len(decisions)} decisions")
    check("nonempty_inputs", all(x["input_text"].strip() for x in corpus), "all replay inputs nonempty")
    check("labels_precede_decisions", all("ground_truth" in x and isinstance(x["ground_truth"].get("should_replace"), bool) for x in corpus), "all labels materialised in corpus")
    check("historical_not_raw", all(x["input_provenance_type"] != "preserved_pre_delivery_raw_output" for x in corpus if x["item_id"].split(":")[1] == "historical"), "historical items explicitly delivered")
    check("matched_is_raw", all(x["input_provenance_type"] == "preserved_pre_delivery_raw_output" for x in corpus if ":matched_raw:" in x["item_id"]), "matched items explicitly raw")
    counts = Counter((x["attack"], x["input_provenance_type"]) for x in corpus)
    expected = {("A01", "historical_delivered_output"): 450, ("A02", "historical_delivered_output"): 450,
                ("A01", "preserved_pre_delivery_raw_output"): 450, ("A02", "preserved_pre_delivery_raw_output"): 450,
                ("A01", "preregistered_synthetic_benign_output"): 20, ("A02", "preregistered_synthetic_benign_output"): 30}
    check("expected_strata", all(counts[k] == v for k, v in expected.items()), {str(k): counts[k] for k in expected})
    decision_counts = Counter(x["outcome"] for x in decisions)
    check("summary_counts", dict(decision_counts) == summary["outcomes"], dict(decision_counts))
    artifacts = ["freeze_manifest.json", "replay_corpus.json", "decision_log.json", "metrics.csv", "confusion_matrices.csv", "per_field_detection.csv"]
    check("summary_hashes", all(summary["artifact_hashes"].get(n) == sha(n) for n in artifacts), {n: sha(n) for n in artifacts})
    result = {"schema_version": "a01-a02-verifier-replay-audit-v1", "status": "PASS" if all(c["status"] == "PASS" for c in checks) else "FAIL", "checks": checks}
    (OUT / "audit.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    raise SystemExit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
