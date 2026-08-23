#!/usr/bin/env bash
# Recovery-only runner for a timed-out A03 guards-on sensitivity task.
# Submit with --array=0-4 --qos=normal --time=03:00:00 and RECOVERY_ROOT set.
#SBATCH --job-name=gpt4o-a03-recovery
#SBATCH --account=kisski_l3s_sis_wiss
#SBATCH --partition=kisski
#SBATCH --constraint=inet
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --array=0-4%1

set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/mnt/vast-kisski/projects/kisski_l3s_sis_wiss/rag-master-thesis}"
cd "$PROJECT_ROOT"
: "${RECOVERY_ROOT:?RECOVERY_ROOT must be set}"

TARGETS=(
  t1_r001_avocadoel
  t2_r002_sonnenblumenoel
  t3_r003_panthenol
  t4_r005_kamillenextrakt
  t5_r006_aloe_vera_gel
)
TARGET_ID="${TARGETS[${SLURM_ARRAY_TASK_ID:?}]}"
OUT_DIR="$RECOVERY_ROOT/$TARGET_ID"
mkdir -p "$OUT_DIR"

export PYTHONPATH="$PROJECT_ROOT/code:${PYTHONPATH:-}"
export OPENAI_BASE_URL=https://api.openai.com/v1
export GENERATION_MODEL=gpt-4o-mini
export GENERATION_TEMPERATURE=0.0
export POST_GENERATION_VERIFIER_ENABLED=true
export PROMPT_INJECTION_GUARD_ENABLED=true
export ACCESS_CHANGE_MEMORY_CLEAR_ENABLED=true
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

env/rag/bin/python -u code/evaluation2/run_access_level_downgrade_task.py \
  --rag-mode sensitivity_eval_mode \
  --access all \
  --target-ids "$TARGET_ID" \
  --conversation-lengths 1 3 5 \
  --iterations 5 \
  --json-output "$OUT_DIR/results.json" \
  --csv-output "$OUT_DIR/results.csv" \
  --markdown-output "$OUT_DIR/report.md"
