# Provenance limitations

## Repository-history boundary

This clean internal archival repository intentionally begins with a single final snapshot. The original development Git history is not included because historical revisions contained actual-looking OpenAI credentials. No commits, objects, refs, tags, reflogs, bundles, or remote configuration were imported. Revocation or rotation of the affected credentials is a separate mandatory action before delivery.

Development chronology is therefore not part of this archive. Scientific provenance is instead carried by the vetted captured source snapshots, patches, status captures, manifests, checksums, evidence ledgers, prompt records, scheduler receipts, and the limitations documented here. The manifest-controlled transfer did not require omission of any listed provenance artifact for containing an authentication credential. `manifests/SECRET_PRIVACY_SCAN.json` records the earlier development-project audit; `manifests/ARCHIVAL_WORKSPACE_SECURITY_SCAN.json` records the value-free scan of this isolated archival workspace.

## Historical package evidence

The historical baseline and hardened package result files do not retain a complete source manifest, exact system/API payload, run-time dataset hash, formal scorer source hash/version, or index-content hash. Current code must not be presented as a byte-identical reconstruction of either package stage.

Prompt equivalence is also incomplete:

- A01 baseline prompts are stored at target level; hardened final prompts are reconstructed rather than preserved as complete payloads.
- A02 warm-up prompts match, but all 450 final package prompts differ.
- A03 protected seed prompts differ.
- A04 and A08 exact original prompts are unavailable.
- A05 formulations/prompt setup differ and the original package ledger omitted the hardened post-source binding.
- A06 stored attack and warm-up prompts match, but several implementation controls changed together.
- A07 compares different variants at package level.

Package comparisons are therefore descriptive, not component-level causal estimates.

## Matched ablations

The matched A01--A08 experiments preserve exact within-run prompts, conditions, pair identifiers, dataset/policy hashes, and executed source snapshots. The working trees were dirty; the snapshots and patches, rather than a clean commit alone, define the executed state.

Most earlier matched runs did not capture formal scorer source hashes or index-content hashes. A04 and A06 have stronger runtime scorer/index provenance. A03 did not materialize every unrelated inherited guard value, and A07 evaluates the natural A07-N variant rather than the historical synthetic-trigger A07-S variant.

The guards-off arms use captured hardened-stage source with one declared component switched. They are not the historical original implementation.

Captured source manifests include historical Python bytecode. The proposed Git tree retains manifest-bound bytecode as an explicit exception to normal cache rules. Unmanifested `.env` symlinks are excluded because they are not scientific inputs and point to a private live-credential location.

## Supplemental evidence

The supplemental A02 verifier challenge branches the final raw answer through verifier-off/on delivery; it does not create independent warm-up generations. The scorer is versioned and stored-output rescoring is deterministic, but exact hosted generation is not.

The A07-S study preserves exact historical prompts and strong source/scorer/index provenance. It remains a finite target/prompt panel and does not establish general trigger robustness.

The frozen A06 study preserves exact prompts, request settings, source, scorer, index hashes, pair identifiers, audit markers, and scheduler evidence. Its guard-off and guard-on generations were separate fixed-order API calls. The protected positive-control prerequisite failed structurally, so the study supports the bounded exact-canary delivery claim but not utility preservation or confidentiality reduction.

The verifier replay corpus combines evidence strata with different inventories and synthetic controls. Its confusion matrix diagnoses the frozen detector on that corpus; it is not a deployment prevalence estimate.

## Hosted-model reproducibility

Temperature `0.0` does not make a hosted API service byte-deterministic. Service-side model revisions, batching, infrastructure, and undocumented changes prevent an exact historical-generation guarantee. Stored outputs can be hashed and rescored; new API calls are new observations.

## Paths and portability

Immutable ledgers and run records retain absolute `/mnt/vast/...`, `/user/...`, and `file://` paths from the execution environment. They are preserved rather than rewritten. `manifests/PATH_MAPPINGS.json` provides additive repo-relative/internal-archive mappings.

## Archive durability

The original raw trees and newly created compressed archives currently reside on the same HPC-backed filesystem. They are separate logical copies but not independent durable copies. `pending_internal_archival` remains the correct status until an authorized university storage destination contains a checksum-verified copy and a restoration test has passed there.

## Dependency portability

Run-specific dependency captures contain Conda build paths and machine-specific origins. `requirements.txt` provides a clean functional environment, not a bit-for-bit recreation. Source snapshots and dependency captures remain the evidence of later executed runs.
