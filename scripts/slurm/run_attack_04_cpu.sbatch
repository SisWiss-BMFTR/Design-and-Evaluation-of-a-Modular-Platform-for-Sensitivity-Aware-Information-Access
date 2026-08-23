#!/usr/bin/env bash
#SBATCH --job-name=gpt4o-a04
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
#SBATCH --output=outputs/experiments/gpt4o_mini_slurm/slurm/attack_04_%A_%a.out
#SBATCH --error=outputs/experiments/gpt4o_mini_slurm/slurm/attack_04_%A_%a.err

set -euo pipefail

PROJECT_ROOT="/mnt/vast-kisski/projects/kisski_l3s_sis_wiss/rag-master-thesis"
cd "$PROJECT_ROOT"

export PYTHONPATH="$PROJECT_ROOT/code:${PYTHONPATH:-}"

OUTPUT_ROOT="${OUTPUT_ROOT:-outputs/experiments/gpt4o_mini_slurm}"
mkdir -p "$OUTPUT_ROOT/slurm"

MODES=("secure_rag_mode" "sensitivity_eval_mode")
RAG_MODE="${MODES[$SLURM_ARRAY_TASK_ID]}"
RUN_TAG="${RUN_TAG:-job_${SLURM_ARRAY_JOB_ID:-${SLURM_JOB_ID:-manual}}}"
OUT_DIR="$OUTPUT_ROOT/attack_04_relational_join_path_inference_runs/${RUN_TAG}/${RAG_MODE}"

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

echo "Started Attack 4 at $(date -Is)"
echo "SLURM_JOB_ID=${SLURM_JOB_ID:-unknown}"
echo "SLURM_ARRAY_TASK_ID=${SLURM_ARRAY_TASK_ID:-unknown}"
echo "RAG_MODE=${RAG_MODE}"
echo "OUT_DIR=${OUT_DIR}"

env/rag/bin/python code/evaluation2/run_relational_join_path_inference_batch.py \
  --rag-mode "$RAG_MODE" \
  --access all \
  --conversation-lengths 1 3 5 \
  --iterations 5 \
  --target-count 5 \
  --json-output "$OUT_DIR/results.json" \
  --csv-output "$OUT_DIR/results.csv" \
  --markdown-output "$OUT_DIR/report.md"

echo "Finished Attack 4 at $(date -Is)"
