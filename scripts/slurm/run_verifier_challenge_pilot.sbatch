#!/usr/bin/env bash
#SBATCH --job-name=verifier-pilot
#SBATCH --account=kisski_l3s_sis_wiss
#SBATCH --partition=kisski
#SBATCH --constraint=inet
#SBATCH --qos=normal
#SBATCH --time=02:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --array=0-3%1
set -euo pipefail
: "${RUN_ROOT:?}" "${SOURCE_ROOT:?}" "${PROJECT_ROOT:?}"
cd "$SOURCE_ROOT"
attacks=(A01 A01 A02 A02)
targets=(dev_r010_parfum dev_r014_panthenol dev_r010_parfum dev_r014_panthenol)
attack="${attacks[$SLURM_ARRAY_TASK_ID]}"; target="${targets[$SLURM_ARRAY_TASK_ID]}"
export PYTHONPATH="$SOURCE_ROOT/code"
export OPENAI_BASE_URL=https://api.openai.com/v1 GENERATION_MODEL=gpt-4o-mini GENERATION_TEMPERATURE=0.0
export OPENAI_MAX_RETRIES=12 OPENAI_RETRY_BASE_SECONDS=1 OPENAI_RETRY_MAX_SECONDS=20
export http_proxy="${http_proxy:-http://www-cache.gwdg.de:3128}" https_proxy="${https_proxy:-http://www-cache.gwdg.de:3128}"
export HTTP_PROXY="$http_proxy" HTTPS_PROXY="$https_proxy" HF_HOME="${HF_HOME:-/user/arash.hedayatzadeh/u26184/.cache/huggingface}"
export TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE:-$HF_HOME/hub}" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
"$PROJECT_ROOT/env/rag/bin/python" scripts/run_verifier_challenge_pilot.py --attack "$attack" --target-id "$target" --output-dir "$RUN_ROOT/raw_generation/$attack/$target"
