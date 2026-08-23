#!/usr/bin/env python3
"""Record exact pilot prompt evidence and compare it with frozen renderer v1."""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from a02_verifier_challenge_prompts import PROMPT_RENDERER_VERSION, challenge_final_prompt

PILOT = ROOT / "outputs/experiments/verifier_challenge_pilot/VCP_A01_A02_20260803T024529Z"


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def main():
    exact = []
    renderer_mismatches = []
    for path in sorted((PILOT / "raw_generation/A02").glob("*/results.json")):
        data = json.loads(path.read_text())
        target = data["targets"][0]
        target_obj = type("Target", (), target)
        seen = set()
        for record in data["records"]:
            length = record["conversation_length"]
            prompts = [turn["prompt"] for turn in record["turns"]]
            key = (target["target_id"], length, tuple(prompts))
            if key in seen:
                continue
            seen.add(key)
            rendered = challenge_final_prompt(target_obj, length, data["design"]["scored_fields"])
            if prompts[-1] != rendered:
                renderer_mismatches.append({"target_id": target["target_id"], "conversation_length": length})
            exact.append({"target_id": target["target_id"], "rezeptur_id": target["rezeptur_id"],
                          "rohstoff": target["rohstoff"], "conversation_length": length, "prompts": prompts})
    exact.sort(key=lambda x: (x["target_id"], x["conversation_length"]))
    prereg = json.loads((PILOT / "preregistration.json").read_text())
    result = {"schema_version": "verifier-challenge-pilot-prompt-audit-v1",
              "status": "PASS" if len(exact) == 4 and not renderer_mismatches else "FAIL",
              "prompt_renderer_version": PROMPT_RENDERER_VERSION,
              "exact_prompt_sequences": exact, "exact_prompt_sequence_set_sha256": canonical_hash(exact),
              "renderer_mismatches": renderer_mismatches,
              "original_preregistration_prompt_set_sha256": prereg["prompt_set_sha256"],
              "provenance_note": "The original preregistration prompt descriptions omitted warm-ups and the appended field list. Exact prompts remain directly preserved in records and the source renderer was included in the frozen source manifest."}
    (PILOT / "prompt_audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k:v for k,v in result.items() if k != "exact_prompt_sequences"}, indent=2))
    raise SystemExit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__": main()
