#!/usr/bin/env bash
#SBATCH --job-name=a02-verifier-full
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
: "${RUN_ROOT:?}" "${SOURCE_ROOT:?}" "${PROJECT_ROOT:?}"
cd "$SOURCE_ROOT"
targets=(t1_r001_avocadoel t2_r002_sonnenblumenoel t3_r003_panthenol t4_r005_kamillenextrakt t5_r006_aloe_vera_gel)
target="${targets[$SLURM_ARRAY_TASK_ID]}"
export PYTHONPATH="$SOURCE_ROOT/code:$SOURCE_ROOT/scripts"
export OPENAI_BASE_URL=https://api.openai.com/v1 GENERATION_MODEL=gpt-4o-mini GENERATION_TEMPERATURE=0.0
export OPENAI_MAX_RETRIES=12 OPENAI_RETRY_BASE_SECONDS=1 OPENAI_RETRY_MAX_SECONDS=20
export http_proxy="${http_proxy:-http://www-cache.gwdg.de:3128}" https_proxy="${https_proxy:-http://www-cache.gwdg.de:3128}"
export HTTP_PROXY="$http_proxy" HTTPS_PROXY="$https_proxy" HF_HOME="${HF_HOME:-/user/arash.hedayatzadeh/u26184/.cache/huggingface}"
export TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE:-$HF_HOME/hub}" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=4
"$PROJECT_ROOT/env/rag/bin/python" scripts/run_full_a02_verifier_challenge.py --target-id "$target" --output-dir "$RUN_ROOT/raw_generation/$target"
