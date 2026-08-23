#!/usr/bin/env bash
#SBATCH --job-name=a07s-audit
#SBATCH --account=kisski_l3s_sis_wiss
#SBATCH --partition=kisski
#SBATCH --qos=2h
#SBATCH --time=00:20:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G

set -euo pipefail
: "${RUN_ROOT:?RUN_ROOT is required}"
: "${SOURCE_ROOT:?SOURCE_ROOT is required}"
: "${PROJECT_ROOT:?PROJECT_ROOT is required}"

cd "$SOURCE_ROOT"
export PYTHONPATH="$SOURCE_ROOT/code"
"$PROJECT_ROOT/env/rag/bin/python3" \
  "$SOURCE_ROOT/scripts/audit_matched_a07s.py" \
  --run-root "$RUN_ROOT" \
  --output "$RUN_ROOT/authoritative_a07s_evidence.json"

"$PROJECT_ROOT/env/rag/bin/python3" - "$RUN_ROOT" <<'PY'
from datetime import datetime, timezone
from pathlib import Path
import json, sys
run_root = Path(sys.argv[1])
evidence = json.loads((run_root / "authoritative_a07s_evidence.json").read_text())
(run_root / "AUDIT_COMPLETE.json").write_text(
    json.dumps(
        {
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": evidence["status"],
            "authoritative_evidence": "authoritative_a07s_evidence.json",
        },
        indent=2,
    ) + "\n",
    encoding="utf-8",
)
PY
