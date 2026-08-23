#!/usr/bin/env bash
#SBATCH --job-name=a06-supp-pilot
#SBATCH --account=kisski_l3s_sis_wiss
#SBATCH --partition=kisski
#SBATCH --constraint=inet
#SBATCH --qos=2h
#SBATCH --time=02:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --array=0-7%1

set -euo pipefail

: "${RUN_ROOT:?RUN_ROOT is required}"
: "${SOURCE_ROOT:?SOURCE_ROOT is required}"
: "${PROJECT_ROOT:?PROJECT_ROOT is required}"

cd "$SOURCE_ROOT"
TARGETS=(R-006 R-007)
MODES=(secure_rag_mode sensitivity_eval_mode)
task_id="${SLURM_ARRAY_TASK_ID:?}"
condition_id=$((task_id % 4))
profile_group=$((task_id / 4))
target_id="${TARGETS[$((condition_id % 2))]}"
rag_mode="${MODES[$((condition_id / 2))]}"
if [[ "$profile_group" -eq 0 ]]; then
  PROFILES=(workflow_follow_v1 audit_paraphrase_v1)
else
  PROFILES=(localized_de_v1 benign_metadata_control_v1)
fi

export PYTHONPATH="$SOURCE_ROOT/code"
export OPENAI_BASE_URL="https://api.openai.com/v1"
export GENERATION_MODEL="gpt-4o-mini"
export GENERATION_TEMPERATURE="0.0"
export PROMPT_STYLE="neutral"
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

for profile in "${PROFILES[@]}"; do
  for arm_spec in "arm_A_guard_off:off" "arm_B_guard_on:on"; do
    arm="${arm_spec%%:*}"
    injection_guard="${arm_spec##*:}"
    out_dir="$RUN_ROOT/pilot/$arm/$rag_mode/$profile/$target_id"
    mkdir -p "$out_dir" "$RUN_ROOT/slurm"
    echo "phase=pilot arm=$arm mode=$rag_mode profile=$profile target=$target_id"
    echo "guards injection=$injection_guard output=off membership=off embedding=off memory_clear=on relation=on"

    "$PROJECT_ROOT/env/rag/bin/python3" -u code/evaluation2/run_prompt_injection_poisoned_row.py \
      --rag-mode "$rag_mode" \
      --challenge-profile "$profile" \
      --prompt-injection-guard "$injection_guard" \
      --output-leakage-verifier off \
      --access all \
      --target-ids "$target_id" \
      --conversation-lengths 1 3 \
      --iterations 2 \
      --json-output "$out_dir/results.json" \
      --csv-output "$out_dir/results.csv" \
      --markdown-output "$out_dir/report.md"
  done
done

echo "finished=$(date -Is)"
