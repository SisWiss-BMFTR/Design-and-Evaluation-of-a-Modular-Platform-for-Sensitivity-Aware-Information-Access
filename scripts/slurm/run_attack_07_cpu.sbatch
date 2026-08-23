#!/usr/bin/env bash
#SBATCH --job-name=gpt4o-a07
#SBATCH --account=kisski_l3s_sis_wiss
#SBATCH --partition=kisski
#SBATCH --constraint=inet
#SBATCH --qos=2h
#SBATCH --time=02:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --array=0-1%1
#SBATCH --output=outputs/experiments/gpt4o_mini_slurm/slurm/attack_07_%A_%a.out
#SBATCH --error=outputs/experiments/gpt4o_mini_slurm/slurm/attack_07_%A_%a.err

set -euo pipefail

PROJECT_ROOT="/user/arash.hedayatzadeh/u26184/.project/dir.project/rag-master-thesis"
cd "$PROJECT_ROOT"

export PYTHONPATH="$PROJECT_ROOT/code:${PYTHONPATH:-}"

OUTPUT_ROOT="${OUTPUT_ROOT:-outputs/experiments/gpt4o_mini_slurm}"
mkdir -p "$OUTPUT_ROOT/slurm"

MODES=("secure_rag_mode" "sensitivity_eval_mode")
RAG_MODE="${MODES[$SLURM_ARRAY_TASK_ID]}"
ATTACK_STYLE="${ATTACK_STYLE:-natural}"
OUT_DIR="$OUTPUT_ROOT/attack_07_backdoor_triggered_extraction/${ATTACK_STYLE}/${RAG_MODE}"

mkdir -p "$OUT_DIR"

export OPENAI_BASE_URL="https://api.openai.com/v1"
export GENERATION_MODEL="gpt-4o-mini"
export GENERATION_TEMPERATURE="0.0"
export OPENAI_MAX_RETRIES="${OPENAI_MAX_RETRIES:-12}"
export OPENAI_RETRY_BASE_SECONDS="${OPENAI_RETRY_BASE_SECONDS:-1}"
export OPENAI_RETRY_MAX_SECONDS="${OPENAI_RETRY_MAX_SECONDS:-20}"
export http_proxy="http://www-cache.gwdg.de:3128"
export https_proxy="http://www-cache.gwdg.de:3128"
export ftp_proxy="http://www-cache.gwdg.de:3128"
export HTTP_PROXY="$http_proxy"
export HTTPS_PROXY="$https_proxy"
export FTP_PROXY="$ftp_proxy"
export HF_HOME="/user/arash.hedayatzadeh/u26184/.cache/huggingface"
export TRANSFORMERS_CACHE="/user/arash.hedayatzadeh/u26184/.cache/huggingface/hub"
export HF_HUB_OFFLINE="1"
export TRANSFORMERS_OFFLINE="1"
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}"
export TOKENIZERS_PARALLELISM="false"

echo "Started Attack 7 at $(date -Is)"
echo "SLURM_JOB_ID=${SLURM_JOB_ID:-unknown}"
echo "SLURM_ARRAY_TASK_ID=${SLURM_ARRAY_TASK_ID:-unknown}"
echo "RAG_MODE=${RAG_MODE}"
echo "OUT_DIR=${OUT_DIR}"
echo "ATTACK_STYLE=${ATTACK_STYLE}"
PROMPT_INJECTION_GUARD="${PROMPT_INJECTION_GUARD:-on}"
echo "PROMPT_INJECTION_GUARD=${PROMPT_INJECTION_GUARD}"

env/rag/bin/python code/evaluation2/run_backdoor_triggered_extraction.py \
  --rag-mode "$RAG_MODE" \
  --attack-style "$ATTACK_STYLE" \
  --access all \
  --target-ids all \
  --conversation-lengths 1 3 5 \
  --iterations 5 \
  --prompt-injection-guard "$PROMPT_INJECTION_GUARD" \
  --json-output "$OUT_DIR/results.json" \
  --csv-output "$OUT_DIR/results.csv" \
  --markdown-output "$OUT_DIR/report.md"

echo "Finished Attack 7 at $(date -Is)"
