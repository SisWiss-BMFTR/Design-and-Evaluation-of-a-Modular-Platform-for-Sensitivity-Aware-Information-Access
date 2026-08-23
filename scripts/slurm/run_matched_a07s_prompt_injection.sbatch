#!/usr/bin/env bash
#SBATCH --job-name=a07s-injection-guard
#SBATCH --account=kisski_l3s_sis_wiss
#SBATCH --partition=kisski
#SBATCH --constraint=inet
#SBATCH --qos=normal
#SBATCH --time=04:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --array=0-4%1

set -euo pipefail

: "${RUN_ROOT:?RUN_ROOT is required}"
: "${SOURCE_ROOT:?SOURCE_ROOT is required}"
: "${PROJECT_ROOT:?PROJECT_ROOT is required}"

cd "$SOURCE_ROOT"
MODES=(secure_rag_mode sensitivity_eval_mode)
TARGETS=(R-001 R-002 R-003 R-004 R-005)
task_id="${SLURM_ARRAY_TASK_ID:?}"
target_id="${TARGETS[$task_id]}"

export PYTHONPATH="$SOURCE_ROOT/code"
export OPENAI_BASE_URL="https://api.openai.com/v1"
export GENERATION_MODEL="gpt-4o-mini"
export GENERATION_TEMPERATURE="0.0"
export OPENAI_MAX_RETRIES="${OPENAI_MAX_RETRIES:-12}"
export OPENAI_RETRY_BASE_SECONDS="${OPENAI_RETRY_BASE_SECONDS:-1}"
export OPENAI_RETRY_MAX_SECONDS="${OPENAI_RETRY_MAX_SECONDS:-20}"
export http_proxy="${http_proxy:-http://www-cache.gwdg.de:3128}"
export https_proxy="${https_proxy:-http://www-cache.gwdg.de:3128}"
export HTTP_PROXY="$http_proxy"
export HTTPS_PROXY="$https_proxy"
export HF_HOME="${HF_HOME:-/user/arash.hedayatzadeh/u26184/.cache/huggingface}"
export TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE:-$HF_HOME/hub}"
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export TOKENIZERS_PARALLELISM=false
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}"

for rag_mode in "${MODES[@]}"; do
  for arm_spec in \
    "arm_A_injection_guard_off:off" \
    "arm_B_injection_guard_on:on"
  do
    arm="${arm_spec%%:*}"
    injection_guard="${arm_spec##*:}"
    out_dir="$RUN_ROOT/$arm/$rag_mode/$target_id"
    mkdir -p "$out_dir" "$RUN_ROOT/slurm"
    echo "experiment=A07-S arm=$arm mode=$rag_mode target=$target_id"
    echo "guards injection=$injection_guard relation=on output=off membership=off embedding=off memory_clear=on"

    "$PROJECT_ROOT/env/rag/bin/python3" -u \
      code/evaluation2/run_backdoor_triggered_extraction.py \
      --rag-mode "$rag_mode" \
      --attack-style synthetic \
      --prompt-style neutral \
      --prompt-injection-guard "$injection_guard" \
      --relation-access-guard on \
      --output-leakage-verifier off \
      --access all \
      --target-ids "$target_id" \
      --conversation-lengths 1 3 5 \
      --iterations 5 \
      --json-output "$out_dir/results.json" \
      --csv-output "$out_dir/results.csv" \
      --markdown-output "$out_dir/report.md"
  done
done

echo "finished=$(date -Is)"
