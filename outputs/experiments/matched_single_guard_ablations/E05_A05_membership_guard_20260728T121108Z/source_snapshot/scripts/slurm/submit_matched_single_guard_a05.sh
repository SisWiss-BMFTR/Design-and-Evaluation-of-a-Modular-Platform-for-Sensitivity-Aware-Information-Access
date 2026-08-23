#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/user/arash.hedayatzadeh/u26184/.project/dir.project/rag-master-thesis}"
cd "$PROJECT_ROOT"

run_tag="${RUN_TAG:-$(date -u +%Y%m%dT%H%M%SZ)}"
run_root="$PROJECT_ROOT/outputs/experiments/matched_single_guard_ablations/E05_A05_membership_guard_$run_tag"
source_root="$run_root/source_snapshot"

mkdir -p "$run_root/slurm" "$source_root/data" "$source_root/scripts/slurm"
cp -a code "$source_root/code"
cp -a data/SiSWiss_Testdaten.xlsx "$source_root/data/SiSWiss_Testdaten.xlsx"
cp -a sensitivity_policy.yaml sensitivity_overrides.yaml "$source_root/"
cp -a scripts/slurm/run_matched_single_guard_a05.sbatch "$source_root/scripts/slurm/"
cp -a scripts/slurm/submit_matched_single_guard_a05.sh "$source_root/scripts/slurm/"
ln -s "$PROJECT_ROOT/.env" "$source_root/.env"

git status --porcelain=v1 --untracked-files=all > "$run_root/git_status.txt"
git diff --binary HEAD > "$run_root/tracked_worktree.patch"
git diff --binary --cached HEAD > "$run_root/staged.patch"

"$PROJECT_ROOT/env/rag/bin/python3" - "$PROJECT_ROOT" "$run_root" "$source_root" <<'PY'
import hashlib
import json
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

project_root, run_root, source_root = map(Path, sys.argv[1:])

def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

source_files = sorted(
    path for path in source_root.rglob("*")
    if path.is_file() and not path.is_symlink()
)
source_hashes = {
    str(path.relative_to(source_root)): sha256(path)
    for path in source_files
}
source_manifest_hash = hashlib.sha256(
    json.dumps(source_hashes, sort_keys=True, separators=(",", ":")).encode()
).hexdigest()

sys.path.insert(0, str(source_root / "code"))
from evaluation2.run_rank_probing_membership_inference_batch import (
    DATASET,
    build_attack_prompt,
    build_target_panel,
    load_xlsx_multilevel,
    warmup_prompts_for_length,
)

targets = build_target_panel(
    documents=load_xlsx_multilevel(DATASET),
    target_ids=["R-001", "R-002", "R-003", "R-004", "R-005"],
)
prompt_manifest = {
    "attack": "A05",
    "targets": [
        {
            **asdict(target),
            "conversations": {
                str(length): {
                    "warmups": warmup_prompts_for_length(length),
                    "attack": build_attack_prompt(target),
                }
                for length in (1, 3, 5)
            },
        }
        for target in targets
    ],
}
(run_root / "prompt_manifest.json").write_text(
    json.dumps(prompt_manifest, indent=2, ensure_ascii=False),
    encoding="utf-8",
)

commit = subprocess.run(
    ["git", "rev-parse", "HEAD"],
    cwd=project_root,
    check=True,
    text=True,
    stdout=subprocess.PIPE,
).stdout.strip()

arm_a = {
    "membership_guard": False,
    "output_leakage_verifier": False,
    "embedding_probe_guard": False,
    "prompt_injection_guard": False,
    "access_change_memory_clear": True,
    "relation_access_guard": True,
}
arm_b = dict(arm_a, membership_guard=True)
differences = [key for key in arm_a if arm_a[key] != arm_b[key]]
if differences != ["membership_guard"]:
    raise SystemExit(f"invalid intervention difference: {differences}")

manifest = {
    "experiment_id": run_root.name,
    "created_at_utc": datetime.now(timezone.utc).isoformat(),
    "design": "matched single-guard ablation",
    "attack": "A05_rank_probing_membership_inference",
    "intervention": "membership_guard",
    "git_commit": commit,
    "source_manifest_sha256": source_manifest_hash,
    "source_files_sha256": source_hashes,
    "dataset": {
        "path": "data/SiSWiss_Testdaten.xlsx",
        "sha256": sha256(source_root / "data/SiSWiss_Testdaten.xlsx"),
    },
    "policy_sha256": sha256(source_root / "sensitivity_policy.yaml"),
    "overrides_sha256": sha256(source_root / "sensitivity_overrides.yaml"),
    "model": "gpt-4o-mini",
    "temperature": 0.0,
    "rag_modes": ["secure_rag_mode", "sensitivity_eval_mode"],
    "access_levels": ["public", "internal", "protected"],
    "conversation_lengths": [1, 3, 5],
    "iterations": 5,
    "target_ids": [target.target_id for target in targets],
    "target_rezeptur_ids": [target.rezeptur_id for target in targets],
    "arm_A_guard_off": arm_a,
    "arm_B_guard_on": arm_b,
    "validated_single_difference": differences,
    "expected_conversations_per_arm": 450,
    "expected_conversations_total": 900,
    "maximum_expected_model_calls_per_arm": 1350,
    "maximum_expected_model_calls_total": 2700,
    "note": "Guard-on secure-mode membership probes may be refused before retrieval, reducing actual model calls.",
}
(run_root / "experiment_manifest.json").write_text(
    json.dumps(manifest, indent=2, ensure_ascii=False),
    encoding="utf-8",
)
PY

submission=$(sbatch \
  --job-name="a05-membership-guard" \
  --output="$run_root/slurm/a05_%A_%a.out" \
  --error="$run_root/slurm/a05_%A_%a.err" \
  --export="ALL,PROJECT_ROOT=$PROJECT_ROOT,RUN_ROOT=$run_root,SOURCE_ROOT=$source_root" \
  "$source_root/scripts/slurm/run_matched_single_guard_a05.sbatch")

job_id="${submission##* }"
"$PROJECT_ROOT/env/rag/bin/python3" - "$run_root" "$job_id" <<'PY'
import json
import sys
from pathlib import Path

run_root = Path(sys.argv[1])
job_id = sys.argv[2]
(run_root / "submission.json").write_text(
    json.dumps({"slurm_job_id": job_id}, indent=2) + "\n",
    encoding="utf-8",
)
PY

echo "$submission"
echo "RUN_ROOT=$run_root"
