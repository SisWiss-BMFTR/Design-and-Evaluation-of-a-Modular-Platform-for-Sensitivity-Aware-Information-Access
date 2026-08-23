#!/usr/bin/env bash
#SBATCH --job-name=matched-a01
#SBATCH --account=kisski_l3s_sis_wiss
#SBATCH --partition=kisski
#SBATCH --constraint=inet
#SBATCH --time=12:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --array=0-3%2

set -euo pipefail
PROJECT_ROOT="${PROJECT_ROOT:-/user/arash.hedayatzadeh/u26184/.project/dir.project/rag-master-thesis}"
: "${OUTPUT_ROOT:?OUTPUT_ROOT must name a new timestamped directory}"
cd "$PROJECT_ROOT"
case "${SLURM_ARRAY_TASK_ID:?}" in
  0) STAGE=pre_hardening; RAG_MODE=secure_rag_mode; GUARD=off ;;
  1) STAGE=pre_hardening; RAG_MODE=sensitivity_eval_mode; GUARD=off ;;
  2) STAGE=post_hardening; RAG_MODE=secure_rag_mode; GUARD=on ;;
  3) STAGE=post_hardening; RAG_MODE=sensitivity_eval_mode; GUARD=on ;;
esac
OUT_DIR="$OUTPUT_ROOT/A01/$STAGE/$RAG_MODE"
mkdir -p "$OUT_DIR" "$OUTPUT_ROOT/slurm"
[[ ! -e "$OUT_DIR/results.json" ]] || { echo "Refusing overwrite" >&2; exit 3; }
export PYTHONPATH="$PROJECT_ROOT/code:${PYTHONPATH:-}"
export GENERATION_MODEL=gpt-4o-mini GENERATION_TEMPERATURE=0.0
export OPENAI_MAX_RETRIES=20 OPENAI_RETRY_BASE_SECONDS=2 OPENAI_RETRY_MAX_SECONDS=60
export http_proxy="${http_proxy:-http://www-cache.gwdg.de:3128}" https_proxy="${https_proxy:-http://www-cache.gwdg.de:3128}"
export HTTP_PROXY="$http_proxy" HTTPS_PROXY="$https_proxy"
export HF_HOME="${HF_HOME:-/user/arash.hedayatzadeh/u26184/.cache/huggingface}"
export TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE:-$HF_HOME/hub}"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=4
env/rag/bin/python -u code/evaluation2/run_direct_cell_extraction.py \
  --rag-mode "$RAG_MODE" --prompt-style neutral --post-generation-verifier "$GUARD" \
  --access all --models gpt-4o-mini --target-ids all --conversation-lengths 1 3 5 --iterations 5 \
  --json-output "$OUT_DIR/results.json" --csv-output "$OUT_DIR/results.csv" --markdown-output "$OUT_DIR/report.md"
