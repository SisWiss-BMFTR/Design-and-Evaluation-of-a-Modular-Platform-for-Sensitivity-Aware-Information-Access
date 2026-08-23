#!/usr/bin/env bash
#SBATCH --job-name=matched-a05-a07
#SBATCH --account=kisski_l3s_sis_wiss
#SBATCH --partition=kisski
#SBATCH --constraint=inet
#SBATCH --time=12:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --array=0-11%2

set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/user/arash.hedayatzadeh/u26184/.project/dir.project/rag-master-thesis}"
: "${OUTPUT_ROOT:?Submit with OUTPUT_ROOT set to a new timestamped directory}"
cd "$PROJECT_ROOT"

case "${SLURM_ARRAY_TASK_ID:?}" in
  0) ATTACK=A05; STAGE=pre_hardening;  RAG_MODE=secure_rag_mode ;;
  1) ATTACK=A05; STAGE=pre_hardening;  RAG_MODE=sensitivity_eval_mode ;;
  2) ATTACK=A05; STAGE=post_hardening; RAG_MODE=secure_rag_mode ;;
  3) ATTACK=A05; STAGE=post_hardening; RAG_MODE=sensitivity_eval_mode ;;
  4) ATTACK=A07-S; STAGE=pre_hardening;  RAG_MODE=secure_rag_mode ;;
  5) ATTACK=A07-S; STAGE=pre_hardening;  RAG_MODE=sensitivity_eval_mode ;;
  6) ATTACK=A07-S; STAGE=post_hardening; RAG_MODE=secure_rag_mode ;;
  7) ATTACK=A07-S; STAGE=post_hardening; RAG_MODE=sensitivity_eval_mode ;;
  8) ATTACK=A07-N; STAGE=pre_hardening;  RAG_MODE=secure_rag_mode ;;
  9) ATTACK=A07-N; STAGE=pre_hardening;  RAG_MODE=sensitivity_eval_mode ;;
 10) ATTACK=A07-N; STAGE=post_hardening; RAG_MODE=secure_rag_mode ;;
 11) ATTACK=A07-N; STAGE=post_hardening; RAG_MODE=sensitivity_eval_mode ;;
  *) echo "Unexpected task ${SLURM_ARRAY_TASK_ID}" >&2; exit 2 ;;
esac

if [[ "$STAGE" == post_hardening ]]; then
  GUARD_BOOL=true
  GUARD_SWITCH=on
else
  GUARD_BOOL=false
  GUARD_SWITCH=off
fi

OUT_DIR="$OUTPUT_ROOT/$ATTACK/$STAGE/$RAG_MODE"
LOG_DIR="$OUTPUT_ROOT/slurm"
if [[ -e "$OUT_DIR/results.json" ]]; then
  echo "Refusing to overwrite completed output: $OUT_DIR/results.json" >&2
  exit 3
fi
mkdir -p "$OUT_DIR" "$LOG_DIR"
exec > >(tee -a "$LOG_DIR/${SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID}.out")
exec 2> >(tee -a "$LOG_DIR/${SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID}.err" >&2)

export PYTHONPATH="$PROJECT_ROOT/code:${PYTHONPATH:-}"
export OPENAI_BASE_URL=https://api.openai.com/v1
export GENERATION_MODEL=gpt-4o-mini
export GENERATION_TEMPERATURE=0.0
export POST_GENERATION_VERIFIER_ENABLED="$GUARD_BOOL"
export PROMPT_INJECTION_GUARD_ENABLED="$GUARD_BOOL"
export ACCESS_CHANGE_MEMORY_CLEAR_ENABLED="$GUARD_BOOL"
export OPENAI_MAX_RETRIES="${OPENAI_MAX_RETRIES:-20}"
export OPENAI_RETRY_BASE_SECONDS="${OPENAI_RETRY_BASE_SECONDS:-2}"
export OPENAI_RETRY_MAX_SECONDS="${OPENAI_RETRY_MAX_SECONDS:-60}"
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

echo "started=$(date -Is) attack=$ATTACK stage=$STAGE mode=$RAG_MODE guards=$GUARD_BOOL output=$OUT_DIR"
COMMON=(--rag-mode "$RAG_MODE" --access all --conversation-lengths 1 3 5 --iterations 5)

if [[ "$ATTACK" == A05 ]]; then
  env/rag/bin/python -u code/evaluation2/run_rank_probing_membership_inference_batch.py \
    "${COMMON[@]}" --target-ids all \
    --json-output "$OUT_DIR/results.json" --csv-output "$OUT_DIR/results.csv" \
    --markdown-output "$OUT_DIR/report.md"
else
  if [[ "$ATTACK" == A07-S ]]; then ATTACK_STYLE=synthetic; else ATTACK_STYLE=natural; fi
  env/rag/bin/python -u code/evaluation2/run_backdoor_triggered_extraction.py \
    "${COMMON[@]}" --attack-style "$ATTACK_STYLE" --prompt-injection-guard "$GUARD_SWITCH" \
    --target-ids all --json-output "$OUT_DIR/results.json" --csv-output "$OUT_DIR/results.csv" \
    --markdown-output "$OUT_DIR/report.md"
fi

echo "finished=$(date -Is)"
