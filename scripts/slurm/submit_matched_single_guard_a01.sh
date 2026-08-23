#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/user/arash.hedayatzadeh/u26184/.project/dir.project/rag-master-thesis}"
cd "$PROJECT_ROOT"

run_tag="${RUN_TAG:-$(date -u +%Y%m%dT%H%M%SZ)}"
run_root="$PROJECT_ROOT/outputs/experiments/matched_single_guard_ablations/E01_A01_output_leakage_verifier_$run_tag"
source_root="$run_root/source_snapshot"

mkdir -p "$run_root/slurm" "$source_root/data" "$source_root/scripts/slurm"
cp -a code "$source_root/code"
cp -a data/SiSWiss_Testdaten.xlsx "$source_root/data/SiSWiss_Testdaten.xlsx"
cp -a sensitivity_policy.yaml sensitivity_overrides.yaml "$source_root/"
cp -a scripts/slurm/run_matched_single_guard_a01.sbatch "$source_root/scripts/slurm/"
cp -a scripts/slurm/submit_matched_single_guard_a01.sh "$source_root/scripts/slurm/"
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
from evaluation2.run_direct_cell_extraction import (
    TARGETS,
    WARMUP_PROMPTS,
    attack_prompt,
)

prompt_manifest = {
    "attack": "A01",
    "prompt_style": "neutral",
    "warmup_prompt_pool": WARMUP_PROMPTS,
    "conversation_lengths": {
        "1": [],
        "3": WARMUP_PROMPTS[:2],
        "5": WARMUP_PROMPTS[:4],
    },
    "targets": [
        {
            **asdict(target),
            "rendered_attack_prompt": attack_prompt(target, "neutral"),
        }
        for target in TARGETS
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

manifest = {
    "experiment_id": run_root.name,
    "created_at_utc": datetime.now(timezone.utc).isoformat(),
    "design": "matched single-guard ablation",
    "attack": "A01_direct_cell_extraction",
    "intervention": "output_leakage_verifier",
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
    "target_ids": [target.target_id for target in TARGETS],
    "prompt_style": "neutral",
    "arm_A_guard_off": {
        "output_leakage_verifier": False,
        "membership_guard": False,
        "embedding_probe_guard": False,
        "prompt_injection_guard": False,
        "access_change_memory_clear": True,
        "relation_access_guard": True,
    },
    "arm_B_guard_on": {
        "output_leakage_verifier": True,
        "membership_guard": False,
        "embedding_probe_guard": False,
        "prompt_injection_guard": False,
        "access_change_memory_clear": True,
        "relation_access_guard": True,
    },
    "expected_conversations_per_arm": 450,
    "expected_conversations_total": 900,
}
differences = [
    key for key in manifest["arm_A_guard_off"]
    if manifest["arm_A_guard_off"][key] != manifest["arm_B_guard_on"][key]
]
if differences != ["output_leakage_verifier"]:
    raise SystemExit(f"invalid intervention difference: {differences}")
manifest["validated_single_difference"] = differences
(run_root / "experiment_manifest.json").write_text(
    json.dumps(manifest, indent=2, ensure_ascii=False),
    encoding="utf-8",
)
PY

submission=$(sbatch \
  --job-name="a01-output-guard" \
  --output="$run_root/slurm/a01_%A_%a.out" \
  --error="$run_root/slurm/a01_%A_%a.err" \
  --export="ALL,PROJECT_ROOT=$PROJECT_ROOT,RUN_ROOT=$run_root,SOURCE_ROOT=$source_root" \
  "$source_root/scripts/slurm/run_matched_single_guard_a01.sbatch")

job_id="${submission##* }"
"$PROJECT_ROOT/env/rag/bin/python3" - "$run_root" "$job_id" <<'PY'
import json
import sys
from pathlib import Path

run_root = Path(sys.argv[1])
job_id = sys.argv[2]
path = run_root / "submission.json"
path.write_text(
    json.dumps({"slurm_job_id": job_id}, indent=2) + "\n",
    encoding="utf-8",
)
PY

echo "$submission"
echo "RUN_ROOT=$run_root"
