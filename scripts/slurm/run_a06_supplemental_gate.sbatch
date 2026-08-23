#!/usr/bin/env bash
#SBATCH --job-name=a06-supp-gate
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
  "$RUN_ROOT" --phase pilot

decision=$("$PROJECT_ROOT/env/rag/bin/python3" - "$RUN_ROOT/PILOT_AUDIT_COMPLETE.json" <<'PY'
import json, sys
print(json.load(open(sys.argv[1], encoding="utf-8"))["interpretation_decision"])
PY
)

if [[ "$decision" != "PASS_AND_CONTINUE" ]]; then
  "$PROJECT_ROOT/env/rag/bin/python3" - "$RUN_ROOT" "$decision" <<'PY'
import json, sys
from datetime import datetime, timezone
from pathlib import Path
root = Path(sys.argv[1])
root.joinpath("continuation.json").write_text(json.dumps({
    "decision": sys.argv[2],
    "full_run_submitted": False,
    "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
    "reason": "The prospectively frozen pilot continuation gate did not pass.",
}, indent=2) + "\n", encoding="utf-8")
PY
  echo "Pilot audited successfully; continuation decision=$decision. Full run not submitted."
  exit 0
fi

full_submission=$(sbatch \
  --output="$RUN_ROOT/slurm/full_%A_%a.out" \
  --error="$RUN_ROOT/slurm/full_%A_%a.err" \
  --export="ALL,PROJECT_ROOT=$PROJECT_ROOT,RUN_ROOT=$RUN_ROOT,SOURCE_ROOT=$SOURCE_ROOT" \
  "$SOURCE_ROOT/scripts/slurm/run_a06_supplemental_full.sbatch")
full_job_id="${full_submission##* }"
audit_submission=$(sbatch \
  --dependency="afterany:$full_job_id" \
  --output="$RUN_ROOT/slurm/full_audit_%j.out" \
  --error="$RUN_ROOT/slurm/full_audit_%j.err" \
  --export="ALL,PROJECT_ROOT=$PROJECT_ROOT,RUN_ROOT=$RUN_ROOT,SOURCE_ROOT=$SOURCE_ROOT" \
  "$SOURCE_ROOT/scripts/slurm/run_a06_supplemental_full_audit.sbatch")
audit_job_id="${audit_submission##* }"

"$PROJECT_ROOT/env/rag/bin/python3" - "$RUN_ROOT" "$decision" "$full_job_id" "$audit_job_id" <<'PY'
import json, sys
from datetime import datetime, timezone
from pathlib import Path
root = Path(sys.argv[1])
root.joinpath("continuation.json").write_text(json.dumps({
    "decision": sys.argv[2],
    "full_run_submitted": True,
    "full_array_job_id": sys.argv[3],
    "full_audit_job_id": sys.argv[4],
    "full_audit_dependency": f"afterany:{sys.argv[3]}",
    "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
}, indent=2) + "\n", encoding="utf-8")
PY

echo "$full_submission"
echo "$audit_submission"
