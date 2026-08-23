#!/usr/bin/env bash
#SBATCH --job-name=gpt4o-ablation
#SBATCH --account=kisski_l3s_sis_wiss
#SBATCH --partition=kisski
#SBATCH --constraint=inet
#SBATCH --qos=2h
#SBATCH --time=02:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --array=0-3%1
#SBATCH --output=logs/full_ablation_%A_%a.out
#SBATCH --error=logs/full_ablation_%A_%a.err

set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/user/arash.hedayatzadeh/u26184/.project/dir.project/rag-master-thesis}"
cd "$PROJECT_ROOT"

: "${ATTACK_ID:?Submit with --export=ALL,ATTACK_ID=01,OUTPUT_ROOT=...}"
: "${OUTPUT_ROOT:?Submit with --export=ALL,ATTACK_ID=01,OUTPUT_ROOT=...}"

case "${SLURM_ARRAY_TASK_ID:?}" in
  0) GUARD_PROFILE=guards_on;  RAG_MODE=secure_rag_mode ;;
  1) GUARD_PROFILE=guards_on;  RAG_MODE=sensitivity_eval_mode ;;
  2) GUARD_PROFILE=guards_off; RAG_MODE=secure_rag_mode ;;
  3) GUARD_PROFILE=guards_off; RAG_MODE=sensitivity_eval_mode ;;
  *) echo "Invalid array index: $SLURM_ARRAY_TASK_ID" >&2; exit 2 ;;
esac

if [[ "$GUARD_PROFILE" == guards_on ]]; then
  GUARD_BOOL=true
  GUARD_SWITCH=on
  A2_VERIFIER=(--post-generation-verifier)
else
  GUARD_BOOL=false
  GUARD_SWITCH=off
  A2_VERIFIER=(--no-post-generation-verifier)
fi

export PYTHONPATH="$PROJECT_ROOT/code:${PYTHONPATH:-}"
export OPENAI_BASE_URL="https://api.openai.com/v1"
export GENERATION_MODEL="gpt-4o-mini"
export GENERATION_TEMPERATURE="0.0"
export POST_GENERATION_VERIFIER_ENABLED="$GUARD_BOOL"
export PROMPT_INJECTION_GUARD_ENABLED="$GUARD_BOOL"
export ACCESS_CHANGE_MEMORY_CLEAR_ENABLED="$GUARD_BOOL"
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

case "$ATTACK_ID" in
  01) ATTACK_DIR=attack_01_direct_cell_extraction ;;
  02) ATTACK_DIR=attack_02_multiturn_row_construction ;;
  03) ATTACK_DIR=attack_03_access_level_downgrade_task ;;
  04) ATTACK_DIR=attack_04_relational_join_path_inference ;;
  05) ATTACK_DIR=attack_05_rank_probing_membership_inference ;;
  06) ATTACK_DIR=attack_06_prompt_injection_poisoned_row ;;
  07) ATTACK_DIR=attack_07_backdoor_triggered_extraction ;;
  08) ATTACK_DIR=attack_08_embedding_side_leakage ;;
  *) echo "Invalid ATTACK_ID: $ATTACK_ID" >&2; exit 2 ;;
esac

OUT_DIR="$OUTPUT_ROOT/$GUARD_PROFILE/$ATTACK_DIR/$RAG_MODE"
mkdir -p "$OUT_DIR" "$OUTPUT_ROOT/slurm"

echo "attack=$ATTACK_ID profile=$GUARD_PROFILE mode=$RAG_MODE output=$OUT_DIR"
echo "post_generation=$POST_GENERATION_VERIFIER_ENABLED prompt_injection=$PROMPT_INJECTION_GUARD_ENABLED memory_clear=$ACCESS_CHANGE_MEMORY_CLEAR_ENABLED"
echo "prompt_style=${PROMPT_STYLE:-labeled}"

COMMON=(--rag-mode "$RAG_MODE" --access all --conversation-lengths 1 3 5 --iterations 5)

case "$ATTACK_ID" in
  01)
    env/rag/bin/python -u code/evaluation2/run_direct_cell_extraction.py "${COMMON[@]}" \
      --models gpt-4o-mini --target-ids all --json-output "$OUT_DIR/results.json" \
      --csv-output "$OUT_DIR/results.csv" --markdown-output "$OUT_DIR/report.md"
    ;;
  02)
    env/rag/bin/python -u code/evaluation2/run_multiturn_row_construction_batch.py "${COMMON[@]}" \
      "${A2_VERIFIER[@]}" --target-ids all --json-output "$OUT_DIR/results.json" \
      --csv-output "$OUT_DIR/results.csv" --report-output "$OUT_DIR/report.md"
    ;;
  03)
    env/rag/bin/python -u code/evaluation2/run_access_level_downgrade_task.py "${COMMON[@]}" \
      --target-ids all --json-output "$OUT_DIR/results.json" --csv-output "$OUT_DIR/results.csv" \
      --markdown-output "$OUT_DIR/report.md"
    ;;
  04)
    env/rag/bin/python -u code/evaluation2/run_relational_join_path_inference_batch.py "${COMMON[@]}" \
      --target-count 5 --post-generation-verifier "$GUARD_SWITCH" \
      --json-output "$OUT_DIR/results.json" --csv-output "$OUT_DIR/results.csv" \
      --markdown-output "$OUT_DIR/report.md"
    ;;
  05)
    env/rag/bin/python -u code/evaluation2/run_rank_probing_membership_inference_batch.py "${COMMON[@]}" \
      --target-ids all --json-output "$OUT_DIR/results.json" --csv-output "$OUT_DIR/results.csv" \
      --markdown-output "$OUT_DIR/report.md"
    ;;
  06)
    env/rag/bin/python -u code/evaluation2/run_prompt_injection_poisoned_row.py "${COMMON[@]}" \
      --target-ids all --json-output "$OUT_DIR/results.json" --csv-output "$OUT_DIR/results.csv" \
      --markdown-output "$OUT_DIR/report.md"
    ;;
  07)
    env/rag/bin/python -u code/evaluation2/run_backdoor_triggered_extraction.py "${COMMON[@]}" \
      --attack-style natural --prompt-injection-guard "$GUARD_SWITCH" --target-ids all \
      --json-output "$OUT_DIR/results.json" --csv-output "$OUT_DIR/results.csv" \
      --markdown-output "$OUT_DIR/report.md"
    ;;
  08)
    env/rag/bin/python -u code/evaluation2/run_embedding_side_leakage.py "${COMMON[@]}" \
      --prompt-style "${PROMPT_STYLE:-labeled}" \
      --model gpt-4o-mini --target-ids all --json-output "$OUT_DIR/results.json" \
      --csv-output "$OUT_DIR/results.csv" --markdown-output "$OUT_DIR/report.md"
    ;;
esac

echo "finished=$(date -Is)"
