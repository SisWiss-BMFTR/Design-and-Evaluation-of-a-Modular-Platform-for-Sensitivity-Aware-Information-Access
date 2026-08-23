#!/usr/bin/env bash
#SBATCH --job-name=a06-supp-audit
#SBATCH --account=kisski_l3s_sis_wiss
#SBATCH --partition=kisski
#SBATCH --qos=normal
#SBATCH --time=00:30:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G

set -euo pipefail
: "${RUN_ROOT:?RUN_ROOT is required}"
: "${SOURCE_ROOT:?SOURCE_ROOT is required}"
: "${PROJECT_ROOT:?PROJECT_ROOT is required}"
cd "$SOURCE_ROOT"
"$PROJECT_ROOT/env/rag/bin/python3" scripts/audit_a06_supplemental_challenge.py \
  "$RUN_ROOT" --phase full
