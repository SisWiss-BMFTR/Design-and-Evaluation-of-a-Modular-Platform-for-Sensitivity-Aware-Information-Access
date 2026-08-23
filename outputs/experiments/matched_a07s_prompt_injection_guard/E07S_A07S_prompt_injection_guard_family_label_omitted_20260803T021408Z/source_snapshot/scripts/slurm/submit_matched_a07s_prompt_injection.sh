#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/user/arash.hedayatzadeh/u26184/.project/dir.project/rag-master-thesis}"
cd "$PROJECT_ROOT"
run_tag="${RUN_TAG:-$(date -u +%Y%m%dT%H%M%SZ)}"
run_parent="${RUN_PARENT:-$PROJECT_ROOT/outputs/experiments/matched_a07s_prompt_injection_guard}"
run_root="$run_parent/E07S_A07S_prompt_injection_guard_family_label_omitted_$run_tag"
source_root="$run_root/source_snapshot"

mkdir -p \
  "$run_root/slurm" \
  "$source_root/code" \
  "$source_root/data" \
  "$source_root/scripts/slurm"

rsync -a --exclude='__pycache__/' --exclude='*.pyc' code/ "$source_root/code/"
cp -a data/SiSWiss_Testdaten.xlsx "$source_root/data/SiSWiss_Testdaten.xlsx"
cp -a sensitivity_policy.yaml sensitivity_overrides.yaml "$source_root/"
cp -a scripts/audit_matched_a07s.py "$source_root/scripts/audit_matched_a07s.py"
cp -a scripts/slurm/run_matched_a07s_prompt_injection.sbatch "$source_root/scripts/slurm/"
cp -a scripts/slurm/audit_matched_a07s.sbatch "$source_root/scripts/slurm/"
cp -a scripts/slurm/submit_matched_a07s_prompt_injection.sh "$source_root/scripts/slurm/"
ln -s "$PROJECT_ROOT/.env" "$source_root/.env"

git status --porcelain=v1 --untracked-files=normal > "$run_root/git_status.txt"
git diff --binary HEAD > "$run_root/tracked_worktree.patch"
git diff --binary --cached HEAD > "$run_root/staged.patch"

"$PROJECT_ROOT/env/rag/bin/python3" - \
  "$PROJECT_ROOT" "$run_root" "$source_root" <<'PY'
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

project_root, run_root, source_root = map(Path, sys.argv[1:])


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_hash(value) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "unavailable"


source_files = sorted(
    path
    for path in source_root.rglob("*")
    if path.is_file() and not path.is_symlink()
)
source_hashes = {
    str(path.relative_to(source_root)): sha256(path) for path in source_files
}
source_manifest_hash = canonical_hash(source_hashes)

sys.path.insert(0, str(source_root / "code"))
from evaluation2.run_backdoor_triggered_extraction import (  # noqa: E402
    DATASET,
    build_attack_prompt,
    build_backdoor_document,
    build_target_panel,
    load_xlsx_multilevel,
    warmup_prompts_for_length,
)

documents = load_xlsx_multilevel(source_root / "data/SiSWiss_Testdaten.xlsx")
target_rezeptur_ids = ["R-001", "R-002", "R-003", "R-004", "R-005"]
targets = build_target_panel(documents, target_rezeptur_ids)
target_by_rezeptur = {target.rezeptur_id: target for target in targets}

# The Slurm array invokes the runner with one target per shard. Validate that
# single-target construction is identical to construction of the complete
# panel before any job is submitted. This prevents target-local enumeration
# from silently changing synthetic product IDs or rendered prompts.
isolated_target_mismatches = []
for rezeptur_id in target_rezeptur_ids:
    panel_target = target_by_rezeptur[rezeptur_id]
    isolated_target = build_target_panel(documents, [rezeptur_id])[0]
    fields = (
        "target_id",
        "rezeptur_id",
        "backdoor_product_id",
        "trigger_phrase",
        "canary",
        "secret_ingredient",
        "secret_amount",
        "secret_supplier",
    )
    for field in fields:
        if getattr(isolated_target, field) != getattr(panel_target, field):
            isolated_target_mismatches.append(
                f"{rezeptur_id}: {field} differs between panel and isolated construction"
            )
    for length in (1, 3, 5):
        isolated_attack = build_attack_prompt(
            isolated_target, attack_style="synthetic", prompt_style="neutral"
        )
        panel_attack = build_attack_prompt(
            panel_target, attack_style="synthetic", prompt_style="neutral"
        )
        if isolated_attack != panel_attack:
            isolated_target_mismatches.append(
                f"{rezeptur_id}/{length}: isolated attack prompt differs from panel prompt"
            )
if isolated_target_mismatches:
    raise SystemExit(
        "single-target shard preflight failed: "
        + "; ".join(isolated_target_mismatches[:20])
    )
historical_paths = [
    project_root
    / "outputs/experiments/gpt4o_mini_slurm_attacks01_07_08_neutral_prehardened_20260719/attack_07_backdoor_triggered_extraction/secure_rag_mode/results.json",
    project_root
    / "outputs/experiments/gpt4o_mini_slurm_attacks01_07_08_neutral_prehardened_20260719/attack_07_backdoor_triggered_extraction/sensitivity_eval_mode/results.json",
]
historical_records = []
historical_hashes = {}
for path in historical_paths:
    payload = json.loads(path.read_text(encoding="utf-8"))
    historical_records.extend(payload.get("records") or [])
    historical_hashes[str(path.relative_to(project_root))] = sha256(path)

mismatches = []
for record in historical_records:
    target = target_by_rezeptur[str(record.get("rezeptur_id"))]
    length = int(record.get("conversation_length"))
    expected_attack = build_attack_prompt(
        target, attack_style="synthetic", prompt_style="neutral"
    )
    expected_warmups = warmup_prompts_for_length(length)
    if record.get("attack_prompt") != expected_attack:
        mismatches.append(
            f"{record.get('rag_mode')}/{record.get('target_id')}/{length}: attack"
        )
    if record.get("warmup_prompts") != expected_warmups:
        mismatches.append(
            f"{record.get('rag_mode')}/{record.get('target_id')}/{length}: warmups"
        )
if len(historical_records) != 450 or mismatches:
    raise SystemExit(
        f"historical prompt validation failed: records={len(historical_records)}, "
        f"mismatches={mismatches[:10]}"
    )

prompt_targets = []
for target in targets:
    conversations = {
        str(length): {
            "warmups": warmup_prompts_for_length(length),
            "attack": build_attack_prompt(
                target, attack_style="synthetic", prompt_style="neutral"
            ),
        }
        for length in (1, 3, 5)
    }
    prompt_targets.append(
        {
            **asdict(target),
            "synthetic_backdoor_document": build_backdoor_document(
                target, attack_style="synthetic"
            ),
            "conversations": conversations,
        }
    )

prompt_manifest = {
    "schema_version": "a07s-prompt-manifest-v1",
    "attack": "A07-S",
    "attack_style": "synthetic",
    "manifest_prompt_style_raw": "neutral",
    "prompt_label_status": "family-label-omitted",
    "semantic_prompt_characterization": "explicit synthetic-trigger activation request",
    "targets": prompt_targets,
    "historical_prompt_match": {
        "status": "exact",
        "historical_records_checked": len(historical_records),
        "mismatches": len(mismatches),
        "source_result_sha256": historical_hashes,
        "historical_prompt_set_sha256": canonical_hash(
            sorted(
                (
                    record.get("rezeptur_id"),
                    record.get("conversation_length"),
                    record.get("warmup_prompts"),
                    record.get("attack_prompt"),
                )
                for record in historical_records
            )
        ),
        "rerun_prompt_set_sha256": canonical_hash(
            sorted(
                (
                    target["rezeptur_id"],
                    int(length),
                    conversation["warmups"],
                    conversation["attack"],
                )
                for target in prompt_targets
                for length, conversation in target["conversations"].items()
                for _ in range(30)
            )
        ),
    },
    "single_target_shard_preflight": {
        "status": "PASS",
        "targets_checked": target_rezeptur_ids,
        "mismatches": len(isolated_target_mismatches),
        "criterion": (
            "single-target construction matches complete-panel target identity "
            "and rendered attack prompt"
        ),
    },
}
(run_root / "prompt_manifest.json").write_text(
    json.dumps(prompt_manifest, indent=2, ensure_ascii=False) + "\n",
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
    "prompt_injection_guard": False,
    "relation_access_guard": True,
    "output_leakage_verifier": False,
    "membership_guard": False,
    "embedding_probe_guard": False,
    "access_change_memory_clear": True,
}
arm_b = dict(arm_a, prompt_injection_guard=True)
differences = [key for key in arm_a if arm_a[key] != arm_b[key]]
if differences != ["prompt_injection_guard"]:
    raise SystemExit(f"invalid intervention difference: {differences}")

manifest = {
    "schema_version": "a07s-matched-experiment-manifest-v1",
    "experiment_id": run_root.name,
    "created_at_utc": datetime.now(timezone.utc).isoformat(),
    "design": "matched single-guard ablation",
    "attack": "A07-S_explicit_synthetic_trigger",
    "intervention": "prompt_injection_guard",
    "primary_outcome": "unauthorised delivered exact-canary compliance",
    "secondary_outcome": "unauthorised delivered protected ingredient-percentage leakage",
    "diagnostic_stages": [
        "retrieved entity",
        "post-projection visible context",
        "LLM context",
        "raw model answer",
        "delivered answer",
        "guard action",
    ],
    "git_commit": commit,
    "working_tree_status": "git_status.txt",
    "tracked_worktree_patch": "tracked_worktree.patch",
    "staged_patch": "staged.patch",
    "source_snapshot": "source_snapshot",
    "source_manifest_sha256": source_manifest_hash,
    "source_files_sha256": source_hashes,
    "dataset": {
        "path": "data/SiSWiss_Testdaten.xlsx",
        "sha256": sha256(source_root / "data/SiSWiss_Testdaten.xlsx"),
        "clean_index_entities": 300,
        "synthetic_entities_per_target_shard": 1,
        "indexed_entities_per_result_shard": 301,
    },
    "policy_sha256": sha256(source_root / "sensitivity_policy.yaml"),
    "overrides_sha256": sha256(source_root / "sensitivity_overrides.yaml"),
    "model": "gpt-4o-mini",
    "model_snapshot": "provider-immutable snapshot unavailable; exact request settings stored per turn",
    "temperature": 0.0,
    "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
    "retrieval_depth": 5,
    "attack_style": "synthetic",
    "manifest_prompt_style_raw": "neutral",
    "prompt_label_status": "family-label-omitted",
    "semantic_prompt_characterization": "explicit synthetic-trigger activation request",
    "prompt_manifest": "prompt_manifest.json",
    "historical_prompt_match": prompt_manifest["historical_prompt_match"],
    "single_target_shard_preflight": prompt_manifest[
        "single_target_shard_preflight"
    ],
    "rag_modes": ["secure_rag_mode", "sensitivity_eval_mode"],
    "access_levels": ["public", "internal", "protected"],
    "conversation_lengths": [1, 3, 5],
    "iterations": 5,
    "target_ids": [target.target_id for target in targets],
    "target_rezeptur_ids": [target.rezeptur_id for target in targets],
    "arm_A_injection_guard_off": arm_a,
    "arm_B_injection_guard_on": arm_b,
    "validated_single_difference": differences,
    "expected_result_shards": 20,
    "expected_records_per_shard": 45,
    "expected_conversations_per_arm": 450,
    "expected_conversations_total": 900,
    "expected_model_calls_per_arm": 1350,
    "expected_model_calls_total": 2700,
    "recorded_provenance": [
        "exact user prompt sequence and SHA-256 manifest",
        "exact system messages and request settings per turn",
        "source snapshot and per-file SHA-256",
        "dataset, policy, and override SHA-256",
        "canonical index-content and serialized FAISS SHA-256 per shard",
        "dependency versions",
        "versioned scorer ID and source SHA-256",
        "pair IDs, raw answers, delivered answers, contexts, access decisions, and guard telemetry",
        "Slurm submission, logs, result hashes, completeness, pairing, and transition audit",
    ],
}
(run_root / "experiment_manifest.json").write_text(
    json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8",
)

freeze = subprocess.run(
    [sys.executable, "-m", "pip", "freeze"],
    check=True,
    text=True,
    stdout=subprocess.PIPE,
).stdout.splitlines()
runtime_environment = {
    "captured_at_utc": datetime.now(timezone.utc).isoformat(),
    "python": {
        "version": sys.version,
        "executable": sys.executable,
        "platform": platform.platform(),
    },
    "selected_distribution_versions": {
        name: package_version(name)
        for name in (
            "openai",
            "sentence-transformers",
            "faiss-cpu",
            "numpy",
            "pandas",
            "torch",
            "openpyxl",
        )
    },
    "pip_freeze": freeze,
    "slurm": {
        "account": "kisski_l3s_sis_wiss",
        "partition": "kisski",
        "constraint": "inet",
        "qos": "normal",
        "cpus_per_task": 4,
        "memory": "16G",
        "array": "0-4%1",
    },
}
(run_root / "runtime_environment.json").write_text(
    json.dumps(runtime_environment, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8",
)

(run_root / "RUN_DESIGN.md").write_text(
    """# A07-S matched rerun design

This rerun uses the exact family-label-omitted synthetic-trigger prompt recorded
in the historical original-baseline A07-S results. Both arms use the same source
snapshot, dataset, synthetic entity, targets, prompts, model settings, roles,
conversation lengths, and iterations. Only the prompt-injection guard changes.

- Primary outcome: unauthorised delivered exact-canary compliance (integrity).
- Secondary outcome: unauthorised delivered ingredient-plus-percentage leakage
  (confidentiality).
- Fixed on: relation-access guard and access-change memory clearing.
- Fixed off: output verifier, membership guard, and embedding-probe guard.
- Matrix: 450 conversations per arm, 900 total, with 150 unauthorised and 75
  protected positive-control conversations per mode and arm.

The dependent audit validates all 20 result shards, 900 records, exact pairing,
prompt and system-prompt equality, fixed configurations, runtime index/scorer
provenance, errors, hashes, and paired outcome transitions. Historical outputs
are read-only references and are never modified.
""",
    encoding="utf-8",
)
PY

if [[ "${PREPARE_ONLY:-0}" == "1" ]]; then
  echo "PREPARE_ONLY: manifests and source snapshot validated; no Slurm job submitted."
  echo "RUN_ROOT=$run_root"
  exit 0
fi

array_submission=$(sbatch \
  --job-name="a07s-injection-guard" \
  --output="$run_root/slurm/a07s_%A_%a.out" \
  --error="$run_root/slurm/a07s_%A_%a.err" \
  --export="ALL,PROJECT_ROOT=$PROJECT_ROOT,RUN_ROOT=$run_root,SOURCE_ROOT=$source_root" \
  "$source_root/scripts/slurm/run_matched_a07s_prompt_injection.sbatch")
array_job_id="${array_submission##* }"

audit_submission=$(sbatch \
  --dependency="afterany:$array_job_id" \
  --job-name="a07s-audit" \
  --output="$run_root/slurm/audit_%j.out" \
  --error="$run_root/slurm/audit_%j.err" \
  --export="ALL,PROJECT_ROOT=$PROJECT_ROOT,RUN_ROOT=$run_root,SOURCE_ROOT=$source_root" \
  "$source_root/scripts/slurm/audit_matched_a07s.sbatch")
audit_job_id="${audit_submission##* }"

"$PROJECT_ROOT/env/rag/bin/python3" - \
  "$run_root" "$array_job_id" "$audit_job_id" <<'PY'
from datetime import datetime, timezone
from pathlib import Path
import json, sys
run_root = Path(sys.argv[1])
payload = {
    "submitted_at_utc": datetime.now(timezone.utc).isoformat(),
    "array_job_id": sys.argv[2],
    "audit_job_id": sys.argv[3],
    "audit_dependency": f"afterany:{sys.argv[2]}",
    "run_root": str(run_root),
}
(run_root / "submission.json").write_text(
    json.dumps(payload, indent=2) + "\n", encoding="utf-8"
)
PY

echo "$array_submission"
echo "$audit_submission"
echo "RUN_ROOT=$run_root"
