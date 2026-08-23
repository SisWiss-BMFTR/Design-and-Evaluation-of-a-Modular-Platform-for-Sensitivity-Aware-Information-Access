#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/user/arash.hedayatzadeh/u26184/.project/dir.project/rag-master-thesis}"
PROMPT_STYLE="${PROMPT_STYLE:-labeled}"
A03_JOB_ID="${A03_JOB_ID:-}"
cd "$PROJECT_ROOT"

run_tag="${RUN_TAG:-$(date -u +%Y%m%dT%H%M%SZ)}"
run_root="$PROJECT_ROOT/outputs/experiments/matched_single_guard_ablations/E04_A04_relation_access_guard_${PROMPT_STYLE}_$run_tag"
source_root="$run_root/source_snapshot"

mkdir -p "$run_root/slurm" "$source_root/data" "$source_root/scripts/slurm"
cp -a code "$source_root/code"
cp -a data/SiSWiss_Testdaten.xlsx "$source_root/data/SiSWiss_Testdaten.xlsx"
cp -a sensitivity_policy.yaml sensitivity_overrides.yaml "$source_root/"
cp -a scripts/slurm/run_matched_single_guard_a04.sbatch "$source_root/scripts/slurm/"
cp -a scripts/slurm/submit_matched_single_guard_a04.sh "$source_root/scripts/slurm/"
ln -s "$PROJECT_ROOT/.env" "$source_root/.env"

git status --porcelain=v1 --untracked-files=all > "$run_root/git_status.txt"
git diff --binary HEAD > "$run_root/tracked_worktree.patch"
git diff --binary --cached HEAD > "$run_root/staged.patch"

PROMPT_STYLE="$PROMPT_STYLE" "$PROJECT_ROOT/env/rag/bin/python3" - "$PROJECT_ROOT" "$run_root" "$source_root" "$A03_JOB_ID" "$PROMPT_STYLE" <<'PY'
import hashlib
import json
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

project_root, run_root, source_root = map(Path, sys.argv[1:4])
a03_job_id = sys.argv[4]
prompt_style = sys.argv[5]

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
from evaluation2.run_relational_join_path_inference_batch import (
    DATASET,
    build_warmup_prompts,
    load_xlsx_multilevel,
    select_evenly_spaced_targets,
    target_pool_from_documents,
)

documents = load_xlsx_multilevel(DATASET)
targets = select_evenly_spaced_targets(target_pool_from_documents(documents), 5)
expected_ids = [
    "p-001_r-001_v-001",
    "p-025_r-025_v-025",
    "p-050_r-050_v-050",
    "p-075_r-075_v-075",
    "p-100_r-100_v-100",
]
if [target.target_id for target in targets] != expected_ids:
    raise SystemExit("deterministic A04 target panel changed")

prompt_manifest = {
    "attack": "A04",
    "prompt_style": prompt_style,
    "targets": [
        {
            **asdict(target),
            "conversations": {
                str(length): {
                    "warmups": build_warmup_prompts(target)[: length - 1],
                    "attack": target.prompt,
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
    "relation_access_guard": False,
    "output_leakage_verifier": False,
    "membership_guard": False,
    "embedding_probe_guard": False,
    "prompt_injection_guard": False,
    "access_change_memory_clear": True,
}
arm_b = dict(arm_a, relation_access_guard=True)
differences = [key for key in arm_a if arm_a[key] != arm_b[key]]
if differences != ["relation_access_guard"]:
    raise SystemExit(f"invalid intervention difference: {differences}")

manifest = {
    "experiment_id": run_root.name,
    "created_at_utc": datetime.now(timezone.utc).isoformat(),
    "design": "matched single-guard ablation",
    "attack": "A04_relational_join_path_inference",
    "intervention": "relation_access_guard",
    "dependency": ({"type": "afterok", "a03_slurm_job_id": a03_job_id} if a03_job_id else None),
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
    "prompt_style": prompt_style,
    "rag_modes": ["secure_rag_mode", "sensitivity_eval_mode"],
    "access_levels": ["public", "internal", "protected"],
    "conversation_lengths": [1, 3, 5],
    "iterations": 5,
    "target_ids": expected_ids,
    "arm_A_guard_off": arm_a,
    "arm_B_guard_on": arm_b,
    "validated_single_difference": differences,
    "expected_conversations_per_arm": 450,
    "expected_conversations_total": 900,
    "expected_model_calls_per_arm": 1350,
    "expected_model_calls_total": 2700,
}
(run_root / "experiment_manifest.json").write_text(
    json.dumps(manifest, indent=2, ensure_ascii=False),
    encoding="utf-8",
)
PY

dependency_args=()
if [[ -n "$A03_JOB_ID" ]]; then
  dependency_args+=(--dependency="afterok:$A03_JOB_ID")
fi
submission=$(sbatch \
  "${dependency_args[@]}" \
  --job-name="a04-relation-guard" \
  --output="$run_root/slurm/a04_%A_%a.out" \
  --error="$run_root/slurm/a04_%A_%a.err" \
  --export="ALL,PROJECT_ROOT=$PROJECT_ROOT,RUN_ROOT=$run_root,SOURCE_ROOT=$source_root,PROMPT_STYLE=$PROMPT_STYLE" \
  "$source_root/scripts/slurm/run_matched_single_guard_a04.sbatch")

job_id="${submission##* }"
"$PROJECT_ROOT/env/rag/bin/python3" - "$run_root" "$job_id" "$A03_JOB_ID" <<'PY'
import json
import sys
from pathlib import Path

run_root = Path(sys.argv[1])
job_id = sys.argv[2]
a03_job_id = sys.argv[3]
(run_root / "submission.json").write_text(
    json.dumps(
        {
            "slurm_job_id": job_id,
            "dependency": f"afterok:{a03_job_id}" if a03_job_id else None,
        },
        indent=2,
    ) + "\n",
    encoding="utf-8",
)
PY

echo "$submission"
echo "DEPENDENCY=${A03_JOB_ID:+afterok:$A03_JOB_ID}"
echo "RUN_ROOT=$run_root"
