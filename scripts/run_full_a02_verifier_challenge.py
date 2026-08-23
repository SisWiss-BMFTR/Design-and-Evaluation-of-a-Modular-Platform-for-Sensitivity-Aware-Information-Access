#!/usr/bin/env python3
"""Generate one frozen A02 challenge corpus with verifier observe-only."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "scripts"))

from a02_verifier_challenge_prompts import challenge_final_prompt

TARGET_IDS = (
    "t1_r001_avocadoel", "t2_r002_sonnenblumenoel", "t3_r003_panthenol",
    "t4_r005_kamillenextrakt", "t5_r006_aloe_vera_gel",
)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--target-id", choices=TARGET_IDS, required=True)
    parser.add_argument("--output-dir", type=Path, required=True); args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    import evaluation2.run_multiturn_row_construction_batch as runner
    from evaluation2.runtime_provenance import build_runtime_provenance
    runner.PROMPT_STYLES = tuple(runner.PROMPT_STYLES) + ("verifier_challenge_v1",)
    runner.final_attack_prompt = lambda target, conversation_length, prompt_style="verifier_challenge_v1": challenge_final_prompt(target, conversation_length, runner.SCORABLE_FIELDS)
    original_build = runner.build_shared_components
    def build_with_provenance():
        shared = original_build()
        documents = [{"text": text, "metadata": meta} for text, meta in zip(shared.retriever.documents, shared.retriever.metadatas)]
        provenance = build_runtime_provenance(documents=documents, faiss_index=shared.retriever.index,
            scorer_id="A02 policy-aware scorer", scorer_version="a02-policy-aware-v1",
            scorer_source=ROOT / "scripts/rescore_a02_policy_aware.py", embedding_model=runner.EMBEDDING_MODEL)
        (args.output_dir / "runtime_provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
        return shared
    runner.build_shared_components = build_with_provenance
    sys.argv = [sys.argv[0], "--rag-mode", "sensitivity_eval_mode", "--prompt-style", "verifier_challenge_v1",
                "--output-leakage-verifier", "off", "--membership-guard", "off", "--embedding-probe-guard", "off",
                "--prompt-injection-guard", "off", "--access-change-memory-clear", "on", "--relation-access-guard", "on",
                "--access", "all", "--target-ids", args.target_id, "--conversation-lengths", "1", "3", "5", "--iterations", "5",
                "--json-output", str(args.output_dir / "results.json"), "--csv-output", str(args.output_dir / "results.csv"),
                "--report-output", str(args.output_dir / "report.md")]
    runner.main()


if __name__ == "__main__": main()
