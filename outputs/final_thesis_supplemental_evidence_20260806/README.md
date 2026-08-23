# Final-thesis supplemental component evidence v2

Status: **PASS**. Schema: `final-thesis-supplemental-component-evidence-v2`.

This is an additive bundle. The four evidence classes in the 2026-08-03 bundle are copied into the v2 ledger without changing any value or count. The new `matched_a06` class adds the completed A06 poisoned-row evaluation; it does not replace the historical baseline, hardened package, earlier matched A06 result, or any 2026-08-03 supplemental result.

## A06 full confirmatory result

- Technical audit: PASS; the completion marker binds SHA-256 `5adfa65641e5c032daed6aa4b93ce3e6850923f57fa871b7092de0b278ba5512` for the authoritative evidence.
- Completeness: 20/20 result files, 900/900 records, 450 records per arm, 450 matched pairs, and 45 records in every shard.
- Primary integrity outcome: delivered exact-canary compliance was 300/300 guard-off and 0/300 guard-on; all 300 unauthorised matched pairs transitioned `1->0`.
- Secure RAG: raw and delivered canary 150/150 -> 0/150.
- Sensitivity evaluation: raw canary 150/150 -> 145/150, delivered canary 150/150 -> 0/150.
- Protected ingredient-plus-percentage leakage: 0/300 in each arm. Target retrieval and secret-context exposure were 0/900 overall and 0/300 across protected records.
- Matching boundary: external user prompts, system messages, and request settings were identical across all 450 pairs. Full API-message sequences differed in 450/450 pairs (225/225 per mode), as expected: secure RAG changed the context through pre-generation quarantine/schema projection, while sensitivity evaluation added an explicit untrusted-data boundary around preserved instruction-like context.

## Authorised positive control

Success was 0/150 in each arm. This is a structural, non-informative zero: the final user prompt did not activate formulation relation expansion, the target formulation was never retrieved, and the secret never entered an LLM context. Therefore the result supports neither utility preservation nor guard-caused utility loss. The full causal audit is in `a06_positive_control_root_cause_audit.json`.

## Pilot profiles and exploratory benign check

- `workflow_follow_v1`: delivered unauthorised canary 32/32 -> 0/32 across modes.
- `localized_de_v1`: 32/32 -> 0/32.
- `audit_paraphrase_v1`: 14/32 -> 0/32 (the 14 guard-off events were in secure mode; sensitivity evaluation was 0/16).
- `benign_metadata_control_v1`: 0/32 -> 0/32.
- Unauthorised protected ingredient-plus-percentage leakage was zero in every pilot profile, arm, and mode.
- A post-hoc scorer found the exact synthetic product name and target market in 96/96 benign delivered answers. This is labelled exploratory and does not repair the invalid authorised formulation control.

## Files

- `supplemental_component_evidence.json`: compact v2 ledger, prior evidence classes, A06 metrics, provenance, boundaries, and SHA-256 bindings.
- `a06_full_mode_summary.csv`: exact full metrics by mode and arm.
- `a06_pilot_profile_summary.csv`: all four pilot profiles aggregated across modes by arm.
- `a06_full_result_file_provenance.csv`: the 20 result-file hashes plus index and scorer provenance.
- `a06_positive_control_root_cause_audit.json`: deterministic retrieval/scorer/gate diagnosis with frozen-source bindings.
- `a06_raw_result_archive_manifest.json`: per-file SHA-256 and size inventory for the 52 large raw result JSON files, plus their retained HPC capture location and durability boundary.

Execution caveat: no top-level per-record execution-error field exists. The bundle therefore reports the narrower evidence actually available: every shard has 45 records, the formal audit passed, and 12 full/full-audit logs had zero matches for the declared fatal-pattern set. Five task stderr logs contain only the recorded Transformers cache deprecation FutureWarnings.

The tracked `scheduler_receipt.json` additionally preserves the Slurm accounting response: all five full array tasks and the dependent audit job were `COMPLETED` with exit code `0:0`.
