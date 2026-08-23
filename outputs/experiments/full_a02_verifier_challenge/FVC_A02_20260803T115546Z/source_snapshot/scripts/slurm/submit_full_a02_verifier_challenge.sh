#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="${PROJECT_ROOT:-/user/arash.hedayatzadeh/u26184/.project/dir.project/rag-master-thesis}"
cd "$PROJECT_ROOT"
run_tag="${RUN_TAG:-$(date -u +%Y%m%dT%H%M%SZ)}"
run_root="$PROJECT_ROOT/outputs/experiments/full_a02_verifier_challenge/FVC_A02_$run_tag"
source_root="$run_root/source_snapshot"
mkdir -p "$source_root/data" "$source_root/scripts/slurm" "$source_root/scripts" "$run_root/slurm"
cp -a code "$source_root/code"
cp -a data/SiSWiss_Testdaten.xlsx "$source_root/data/"
cp -a sensitivity_policy.yaml sensitivity_overrides.yaml "$source_root/"
cp -a scripts/a02_verifier_challenge_prompts.py scripts/run_full_a02_verifier_challenge.py scripts/audit_full_a02_verifier_challenge.py scripts/rescore_a02_policy_aware.py "$source_root/scripts/"
cp -a scripts/slurm/run_full_a02_verifier_challenge.sbatch scripts/slurm/run_full_a02_verifier_challenge_audit.sbatch scripts/slurm/submit_full_a02_verifier_challenge.sh "$source_root/scripts/slurm/"
ln -s "$PROJECT_ROOT/.env" "$source_root/.env"
git status --porcelain=v1 --untracked-files=all > "$run_root/git_status.txt"
git diff --binary HEAD > "$run_root/tracked_worktree.patch"
"$PROJECT_ROOT/env/rag/bin/python" -m pip freeze > "$run_root/dependency_versions.txt"
"$PROJECT_ROOT/env/rag/bin/python" - "$PROJECT_ROOT" "$run_root" "$source_root" <<'PY'
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
project,run,source=map(Path,sys.argv[1:])
sys.path[:0]=[str(source/'code'),str(source/'scripts')]
from evaluation2 import run_multiturn_row_construction_batch as runner
from a02_verifier_challenge_prompts import PROMPT_RENDERER_VERSION,challenge_final_prompt
def sha(p):
 h=hashlib.sha256(); h.update(p.read_bytes()); return h.hexdigest()
runner.PROMPT_STYLES=tuple(runner.PROMPT_STYLES)+('verifier_challenge_v1',)
runner.final_attack_prompt=lambda target,conversation_length,prompt_style='verifier_challenge_v1': challenge_final_prompt(target,conversation_length,runner.SCORABLE_FIELDS)
targets=runner.load_targets(['all'])
sequences=[]
for target in targets:
 for length in (1,3,5):
  sequences.append({'target_id':target.target_id,'rezeptur_id':target.rezeptur_id,'rohstoff':target.rohstoff,
                    'conversation_length':length,'prompts':[x['prompt'] for x in runner.build_conversation_prompts(target,length,'verifier_challenge_v1')]})
prompt_manifest={'schema_version':'a02-verifier-challenge-prompt-manifest-v1','renderer_version':PROMPT_RENDERER_VERSION,
                 'family_label_omitted':True,'sequences':sequences}
prompt_manifest['exact_prompt_sequence_set_sha256']=hashlib.sha256(json.dumps(sequences,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
(run/'prompt_manifest.json').write_text(json.dumps(prompt_manifest,ensure_ascii=False,indent=2)+'\n')
files=sorted(p for p in source.rglob('*') if p.is_file() and not p.is_symlink())
hashes={str(p.relative_to(source)):sha(p) for p in files}
source_hash=hashlib.sha256(json.dumps(hashes,sort_keys=True,separators=(',',':')).encode()).hexdigest()
pilot=project/'outputs/experiments/verifier_challenge_pilot/VCP_A01_A02_20260803T024529Z'
pilot_audit=json.loads((pilot/'pilot_audit.json').read_text()); pilot_prompt=json.loads((pilot/'prompt_audit.json').read_text())
manifest={'schema_version':'full-a02-verifier-challenge-preregistration-v1','created_at_utc':datetime.now(timezone.utc).isoformat(),
 'git_commit':subprocess.run(['git','rev-parse','HEAD'],cwd=project,text=True,capture_output=True,check=True).stdout.strip(),
 'source_manifest_sha256':source_hash,'source_files_sha256':hashes,'dataset':{'path':'data/SiSWiss_Testdaten.xlsx','sha256':sha(source/'data/SiSWiss_Testdaten.xlsx')},
 'policy_sha256':sha(source/'sensitivity_policy.yaml'),'overrides_sha256':sha(source/'sensitivity_overrides.yaml'),
 'dependency_versions_sha256':sha(run/'dependency_versions.txt'),'model':'gpt-4o-mini','temperature':0.0,
 'design':'one generation per condition with verifier OFF/observe-only; deterministic fork of the identical raw answer into OFF and ON delivery records',
 'pilot_gate':{'status':pilot_audit['status'],'A02':pilot_audit['summary']['A02'],'exact_pilot_prompt_sequence_set_sha256':pilot_prompt['exact_prompt_sequence_set_sha256']},
 'prompt_manifest':'prompt_manifest.json','prompt_sequence_set_sha256':prompt_manifest['exact_prompt_sequence_set_sha256'],
 'targets':[t.target_id for t in targets],'rag_modes':['sensitivity_eval_mode'],'roles':['public','internal','protected'],
 'conversation_lengths':[1,3,5],'iterations':5,'expected_conversations':225,'expected_unauthorised':150,'expected_positive_controls':75,
 'expected_model_calls':675,'derived_delivery_records':450,
 'fixed_guards':{'membership_guard':False,'embedding_probe_guard':False,'prompt_injection_guard':False,'access_change_memory_clear':True,'relation_access_guard':True},
 'intervention':'output leakage verifier delivery decision only','scorer':{'id':'A02 policy-aware scorer','version':'a02-policy-aware-v1','source':'scripts/rescore_a02_policy_aware.py','sha256':sha(source/'scripts/rescore_a02_policy_aware.py')},
 'technical_acceptance':{'audit_complete':True,'all_raw_hashes_shared_across_derived_arms':True,'execution_errors':0},
 'interpretation_gate':'A causal leakage-reduction claim additionally requires non-zero verifier-OFF policy-aware leakage.',
 'reporting_rule':'Report the full result even if the verifier does not reduce leakage; do not tune prompts after submission and do not replace historical package results.'}
(run/'preregistration.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
PY
submission=$(sbatch --output="$run_root/slurm/full_%A_%a.out" --error="$run_root/slurm/full_%A_%a.err" --export="ALL,PROJECT_ROOT=$PROJECT_ROOT,RUN_ROOT=$run_root,SOURCE_ROOT=$source_root" "$source_root/scripts/slurm/run_full_a02_verifier_challenge.sbatch")
job_id="${submission##* }"
audit_submission=$(sbatch --dependency="afterok:$job_id" --output="$run_root/slurm/audit_%j.out" --error="$run_root/slurm/audit_%j.err" --export="ALL,PROJECT_ROOT=$PROJECT_ROOT,RUN_ROOT=$run_root,SOURCE_ROOT=$source_root" "$source_root/scripts/slurm/run_full_a02_verifier_challenge_audit.sbatch")
audit_id="${audit_submission##* }"
"$PROJECT_ROOT/env/rag/bin/python" - "$run_root" "$job_id" "$audit_id" <<'PY'
import json,sys
from pathlib import Path
root=Path(sys.argv[1]); root.joinpath('submission.json').write_text(json.dumps({'full_array_job_id':sys.argv[2],'audit_job_id':sys.argv[3],'audit_dependency':f'afterok:{sys.argv[2]}'},indent=2)+'\n')
PY
echo "$submission"; echo "$audit_submission"; echo "RUN_ROOT=$run_root"
