#!/usr/bin/env bash
#SBATCH --account=kisski_l3s_sis_wiss
#SBATCH --partition=kisski
#SBATCH --constraint=inet
#SBATCH --time=06:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --array=0-1%2

set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/user/arash.hedayatzadeh/u26184/.project/dir.project/rag-master-thesis}"
OUTPUT_ROOT="${OUTPUT_ROOT:-outputs/experiments/post hardened 1-8}"
: "${ATTACK_ID:?Submit with ATTACK_ID set to an integer from 03 through 08}"
cd "$PROJECT_ROOT"

MODES=(secure_rag_mode sensitivity_eval_mode)
RAG_MODE="${MODES[${SLURM_ARRAY_TASK_ID:?}]}"

case "$ATTACK_ID" in
  03) ATTACK_DIR=attack_03_access_level_downgrade_task ;;
  04) ATTACK_DIR=attack_04_relational_join_path_inference ;;
  05) ATTACK_DIR=attack_05_rank_probing_membership_inference ;;
  06) ATTACK_DIR=attack_06_prompt_injection_poisoned_row ;;
  07) ATTACK_DIR=attack_07_backdoor_triggered_extraction ;;
  08) ATTACK_DIR=attack_08_embedding_side_leakage ;;
  *) echo "Invalid ATTACK_ID: $ATTACK_ID" >&2; exit 2 ;;
esac

OUT_DIR="$OUTPUT_ROOT/$ATTACK_DIR/$RAG_MODE"
mkdir -p "$OUT_DIR" "$OUTPUT_ROOT/slurm"

export PYTHONPATH="$PROJECT_ROOT/code:${PYTHONPATH:-}"
export OPENAI_BASE_URL=https://api.openai.com/v1
export GENERATION_MODEL=gpt-4o-mini
export GENERATION_TEMPERATURE=0.0
export POST_GENERATION_VERIFIER_ENABLED=true
export PROMPT_INJECTION_GUARD_ENABLED=true
export ACCESS_CHANGE_MEMORY_CLEAR_ENABLED=true
export PROMPT_STYLE=neutral
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

echo "started=$(date -Is) attack=$ATTACK_ID mode=$RAG_MODE prompt_style=$PROMPT_STYLE output=$OUT_DIR"
COMMON=(--rag-mode "$RAG_MODE" --access all --conversation-lengths 1 3 5 --iterations 5)

case "$ATTACK_ID" in
  03) env/rag/bin/python -u code/evaluation2/run_access_level_downgrade_task.py "${COMMON[@]}" --target-ids all --json-output "$OUT_DIR/results.json" --csv-output "$OUT_DIR/results.csv" --markdown-output "$OUT_DIR/report.md" ;;
  04) env/rag/bin/python -u code/evaluation2/run_relational_join_path_inference_batch.py "${COMMON[@]}" --target-count 5 --post-generation-verifier on --json-output "$OUT_DIR/results.json" --csv-output "$OUT_DIR/results.csv" --markdown-output "$OUT_DIR/report.md" ;;
  05) env/rag/bin/python -u code/evaluation2/run_rank_probing_membership_inference_batch.py "${COMMON[@]}" --target-ids all --json-output "$OUT_DIR/results.json" --csv-output "$OUT_DIR/results.csv" --markdown-output "$OUT_DIR/report.md" ;;
  06) env/rag/bin/python -u code/evaluation2/run_prompt_injection_poisoned_row.py "${COMMON[@]}" --target-ids all --json-output "$OUT_DIR/results.json" --csv-output "$OUT_DIR/results.csv" --markdown-output "$OUT_DIR/report.md" ;;
  07) env/rag/bin/python -u code/evaluation2/run_backdoor_triggered_extraction.py "${COMMON[@]}" --attack-style natural --prompt-injection-guard on --target-ids all --json-output "$OUT_DIR/results.json" --csv-output "$OUT_DIR/results.csv" --markdown-output "$OUT_DIR/report.md" ;;
  08) env/rag/bin/python -u code/evaluation2/run_embedding_side_leakage.py "${COMMON[@]}" --prompt-style neutral --model gpt-4o-mini --target-ids all --json-output "$OUT_DIR/results.json" --csv-output "$OUT_DIR/results.csv" --markdown-output "$OUT_DIR/report.md" ;;
esac

echo "finished=$(date -Is)"
