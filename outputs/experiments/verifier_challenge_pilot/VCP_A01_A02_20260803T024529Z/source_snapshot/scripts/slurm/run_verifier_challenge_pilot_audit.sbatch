#!/usr/bin/env bash
#SBATCH --job-name=verifier-pilot-audit
#SBATCH --account=kisski_l3s_sis_wiss
#SBATCH --partition=kisski
#SBATCH --qos=normal
#SBATCH --time=00:30:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
set -euo pipefail
: "${RUN_ROOT:?}" "${SOURCE_ROOT:?}" "${PROJECT_ROOT:?}"
cd "$SOURCE_ROOT"
"$PROJECT_ROOT/env/rag/bin/python" scripts/audit_verifier_challenge_pilot.py "$RUN_ROOT"
