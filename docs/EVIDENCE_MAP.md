# Claim-to-evidence map

This map identifies repository artifacts used to verify the thesis. It does not upgrade descriptive evidence into causal evidence and does not substitute current source for a captured executed state.

## Package evidence

| Evidence | Authoritative path | Interpretation |
|---|---|---|
| Historical A01--A08 | `outputs/experiments/gpt4o_mini_slurm_attacks01_07_08_neutral_prehardened_20260719/` | Descriptive original-package outcomes |
| Hardened A01--A08 | `outputs/experiments/post hardened 1-8/` | Descriptive final-package outcomes |
| A02 policy-aware rescore | `outputs/rescoring/a02_policy_aware_20260722T155853Z/` | Deterministic policy-aware reconstruction scoring |
| Package prompt audit | `outputs/audits/package_prompt_provenance_a01_a02_20260803/` | Stored/reconstructed A01 prompts and complete stored A02 user-turn comparison |
| Package provenance | `outputs/final_thesis_evidence_20260803_prompt_provenance_v3/package_comparison_provenance.json` | Immutable package-stage ledger |
| A05 additive binding | `manifests/HARDENED_A05_PROVENANCE.json` | Corrects only the omitted hardened A05 post-source binding |

The original package ledger's A05 `post_source: N/A` field is preserved. The additive mapping binds existing hardened A05 files and states: “This corrects a provenance binding omission only; no reported A05 result was changed.”

## Authoritative matched ablations

| ID | Run root | Captured source manifest SHA-256 | Large archive ID |
|---|---|---|---|
| A01 | `outputs/experiments/matched_single_guard_ablations/E01_A01_output_leakage_verifier_20260727T143137Z` | `120d4914ca78d13315db3dd29e0d13ffecfadb823c00f2f29d0215c13a08071c` | `matched_A01` |
| A02 | `outputs/experiments/matched_single_guard_ablations/E02_A02_output_leakage_verifier_20260727T185707Z` | `31ab63db2b920328c147ef3409df181b994e7e51c0374884db3e17884afd53b3` | `matched_A02` |
| A03 | `outputs/experiments/matched_single_guard_ablations/E03_A03_access_change_memory_clear_20260727T231454Z` | `f8cb447e157c991b3eebb31d01c6380f1f06c648506a862d447994e0c49bdce9` | `matched_A03` |
| A04 | `outputs/experiments/matched_single_guard_ablations/E04_A04_relation_access_guard_neutral_20260801T163000Z` | `b226ca70311453064f1caa2ce022b107a42571cfd4527a69afae8f473189e354` | `matched_A04` |
| A05 | `outputs/experiments/matched_single_guard_ablations/E05_A05_membership_guard_20260728T121108Z` | `7814eacec05cf3426233a5fee60ff46ae37dc9598f62ca3b5f977d6433ceb396` | `matched_A05` |
| A06 | `outputs/experiments/matched_single_guard_ablations/E06_A06_prompt_injection_guard_neutral_20260801T163000Z` | `eac2eee7243a0b4aedeee39f306124fc657075fcdece54ccb8d7b50c23c1434d` | `matched_A06` |
| A07 | `outputs/experiments/matched_single_guard_ablations/E07_A07_relation_access_guard_20260728T231214Z` | `a01a602d1133e30f1777d50a907c50706a9cb69a550f39b341b54d6c377de6dc` | `matched_A07` |
| A08 | `outputs/experiments/matched_single_guard_ablations/E08_A08_embedding_probe_guard_20260729T092151Z` | `81ba73bd3a3c9a3bf0ea8340f45251b8d85789f7513743e407f16affc1d71680` | `matched_A08` |

The authoritative combined ledger is:

```text
outputs/final_thesis_evidence_20260803_prompt_provenance_v3/provenance_with_ablations.json
```

Each run contains its experiment and prompt manifests, captured Git state/patches, complete source snapshot, and selected runtime evidence. The large arms are bound by `manifests/evidence_inventories/` and `manifests/ARCHIVED_EVIDENCE.json`.

## Supplemental evidence

| Study | Run/evidence root | Primary audit/scorer binding | Archive ID |
|---|---|---|---|
| Full A02 verifier challenge | `outputs/experiments/full_a02_verifier_challenge/FVC_A02_20260803T115546Z` | `AUDIT_COMPLETE.json`; scorer SHA `c406e2908ee4bb3deb27a20cf25d96e153c0a1151f66511af5f5d8ee5bc5c6ac` | `supplemental_A02` |
| Frozen A06 challenge | `outputs/experiments/supplemental_a06_poisoned_row/SA06_A06_prompt_injection_guard_20260805T220542Z` | `AUDIT_COMPLETE.json`; scorer SHA `090d7b1a4742e01005a1390b7554b8f73fd8e59d5b923c9e8a4ba68fda15a171` | `supplemental_A06` |
| Matched A07-S | `outputs/experiments/matched_a07s_prompt_injection_guard/E07S_A07S_prompt_injection_guard_family_label_omitted_20260803T021408Z` | `AUDIT_COMPLETE.json`; scorer SHA `86001a391b1e1183684121e18ae03eeb219272b8e49abfa283bd77a10f4ccd30` | `supplemental_A07S` |
| A01/A02 verifier replay | `outputs/verifier_validation/a01_a02_replay_v1_20260803` | `freeze_manifest.json`, `audit.json`, `decision_log.json` | `verifier_replay` |

The compact supplemental ledger is:

```text
outputs/final_thesis_supplemental_evidence_20260806/supplemental_component_evidence.json
```

The original A06 52-file raw manifest is:

```text
outputs/final_thesis_supplemental_evidence_20260806/a06_raw_result_archive_manifest.json
```

It binds 1,284 records, 529,797,217 bytes, and canonical inventory SHA-256 `59f4d8272e88eadaaeff02df645708138f3abf72c435ee859cf94e258ad77131`.

## Evidence classifications

- **AUTHORITATIVE:** the roots listed above and their canonical ledgers.
- **DESCRIPTIVE HISTORICAL:** original baseline and hardened-package result trees.
- **SUPPLEMENTAL:** A02, A06, A07-S and verifier replay evidence.
- **PILOT:** pilot evidence retained inside supplemental designs, not pooled into confirmatory denominators.
- **SUPERSEDED:** earlier A04/A06 matched runs and earlier evidence bundles.
- **FAILED:** incomplete A08 and A06 attempts without usable denominators.

Superseded and failed attempts may remain in private archival storage for disclosure, but they are not authoritative thesis inputs.
