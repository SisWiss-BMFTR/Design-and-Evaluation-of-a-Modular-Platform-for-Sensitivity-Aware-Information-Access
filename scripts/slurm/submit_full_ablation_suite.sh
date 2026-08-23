#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/user/arash.hedayatzadeh/u26184/.project/dir.project/rag-master-thesis}"
cd "$PROJECT_ROOT"

RUN_TAG="${RUN_TAG:-$(date +%Y%m%d_%H%M%S)}"
OUTPUT_ROOT="${OUTPUT_ROOT:-outputs/experiments/gpt4o_mini_full_hardening_${RUN_TAG}}"
mkdir -p "$OUTPUT_ROOT/slurm" logs

MANIFEST="$OUTPUT_ROOT/RUN_MANIFEST.txt"
{
  echo "created=$(date -Is)"
  echo "model=gpt-4o-mini"
  echo "temperature=0.0"
  echo "profiles=guards_on guards_off"
  echo "rag_modes=secure_rag_mode sensitivity_eval_mode"
  echo "access=all"
  echo "conversation_lengths=1 3 5"
  echo "iterations=5"
  echo "targets=all (five-target panels)"
  echo "output_root=$OUTPUT_ROOT"
  echo "git_commit=$(git rev-parse HEAD)"
} > "$MANIFEST"

for attack_id in 01 02 03 04 05 06 07 08; do
  submission=$(sbatch \
    --job-name="gpt4o-a${attack_id}-abl" \
    --output="$OUTPUT_ROOT/slurm/attack_${attack_id}_%A_%a.out" \
    --error="$OUTPUT_ROOT/slurm/attack_${attack_id}_%A_%a.err" \
    --export="ALL,ATTACK_ID=$attack_id,OUTPUT_ROOT=$OUTPUT_ROOT" \
    scripts/slurm/run_full_ablation_attack.sbatch)
  echo "$submission" | tee -a "$MANIFEST"
done

echo "OUTPUT_ROOT=$OUTPUT_ROOT"
