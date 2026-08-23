# A07-S matched rerun design

This rerun uses the exact family-label-omitted synthetic-trigger prompt recorded
in the historical original-baseline A07-S results. Both arms use the same source
snapshot, dataset, synthetic entity, targets, prompts, model settings, roles,
conversation lengths, and iterations. Only the prompt-injection guard changes.

- Primary outcome: unauthorised delivered exact-canary compliance (integrity).
- Secondary outcome: unauthorised delivered ingredient-plus-percentage leakage
  (confidentiality).
- Fixed on: relation-access guard and access-change memory clearing.
- Fixed off: output verifier, membership guard, and embedding-probe guard.
- Matrix: 450 conversations per arm, 900 total, with 150 unauthorised and 75
  protected positive-control conversations per mode and arm.

The dependent audit validates all 20 result shards, 900 records, exact pairing,
prompt and system-prompt equality, fixed configurations, runtime index/scorer
provenance, errors, hashes, and paired outcome transitions. Historical outputs
are read-only references and are never modified.
