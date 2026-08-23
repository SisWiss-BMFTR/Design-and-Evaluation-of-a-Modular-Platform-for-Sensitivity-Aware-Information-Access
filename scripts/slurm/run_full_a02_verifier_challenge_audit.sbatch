#!/usr/bin/env bash
#SBATCH --job-name=a02-verifier-audit
#SBATCH --account=kisski_l3s_sis_wiss
#SBATCH --partition=kisski
#SBATCH --qos=normal
#SBATCH --time=00:30:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
set -euo pipefail
: "${RUN_ROOT:?}" "${SOURCE_ROOT:?}" "${PROJECT_ROOT:?}"
cd "$SOURCE_ROOT"
"$PROJECT_ROOT/env/rag/bin/python" scripts/audit_full_a02_verifier_challenge.py "$RUN_ROOT"
