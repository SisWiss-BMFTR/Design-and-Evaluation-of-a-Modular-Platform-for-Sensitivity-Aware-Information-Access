#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/user/arash.hedayatzadeh/u26184/.project/dir.project/rag-master-thesis"
cd "$PROJECT_ROOT"

export PYTHONUNBUFFERED="1"
export PYTHONPATH="$PROJECT_ROOT/code:${PYTHONPATH:-}"
export OPENAI_BASE_URL="https://api.openai.com/v1"
export GENERATION_MODEL="gpt-4o-mini"
export GENERATION_TEMPERATURE="0.0"
export HF_HOME="/user/arash.hedayatzadeh/u26184/.cache/huggingface"
export TRANSFORMERS_CACHE="/user/arash.hedayatzadeh/u26184/.cache/huggingface/hub"
export HF_HUB_OFFLINE="1"
export TRANSFORMERS_OFFLINE="1"
export TOKENIZERS_PARALLELISM="false"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-4}"

echo "Started local Attack 1 at $(date -Is)"

for RAG_MODE in secure_rag_mode sensitivity_eval_mode; do
  OUT_DIR="outputs/experiments/gpt4o_mini/attack_01_direct_cell_extraction/${RAG_MODE}"
  mkdir -p "$OUT_DIR"

  echo "Running Attack 1 mode=${RAG_MODE} at $(date -Is)"

  env/rag/bin/python -u code/evaluation2/run_direct_cell_extraction.py \
    --rag-mode "$RAG_MODE" \
    --access all \
    --models gpt-4o-mini \
    --target-ids all \
    --conversation-lengths 1 3 5 \
    --iterations 5 \
    --json-output "$OUT_DIR/results.json" \
    --csv-output "$OUT_DIR/results.csv" \
    --markdown-output "$OUT_DIR/report.md"

  echo "Finished Attack 1 mode=${RAG_MODE} at $(date -Is)"
done

echo "Finished local Attack 1 at $(date -Is)"
