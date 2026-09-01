# Internal reproducibility and evidence verification

## Reproducibility levels

The archive distinguishes four operations:

1. **Hash/provenance verification** checks that a stored artifact is the artifact bound by a manifest.
2. **Metric recomputation** applies deterministic scoring or aggregation to preserved raw outputs.
3. **Comparable rerun** executes the maintained runner under documented settings and produces a new hosted-model sample.
4. **Exact historical reproduction** would recreate the original source state, payloads, service state, and model outputs byte-for-byte.

Levels 1 and 2 are supported where the required evidence is retained. Level 3 is supported for maintained runners when an authorized reviewer supplies an API credential and dependencies. Level 4 is not claimed: hosted-model calls are nondeterministic in practice, and historical package provenance is incomplete.

## Setup

Use Python 3.10:

```bash
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The portable requirements are functional bounds, not an exact reconstruction of the HPC environment. Exact dependency captures for later supplemental runs remain in their run roots.

## Verification that needs no OpenAI call

```bash
sha256sum --ignore-missing -c manifests/RELEASE_SHA256SUMS
PYTHONPATH=code python -m unittest discover -s tests
python scripts/check_thesis_with_matched_ablations.py \
  --evidence-dir outputs/final_thesis_evidence_20260803_prompt_provenance_v3 \
  --build-log thesis/build/main.log \
  --pdf thesis/build/main.pdf \
  --report manifests/THESIS_SOURCE_CONSISTENCY.json \
  --skip-external-raw-rehash
```

The checksum file intentionally covers the frozen thesis, dataset, policy, ledgers, archive manifest, source manifests, compact evidence, and the externally stored evidence archive payloads and verification sidecars. `--ignore-missing` verifies the Git-resident subset in a Git-only checkout. A complete local check without that option requires all 24 non-Git paths at their documented repo-relative locations: twelve `.tar.zst` payloads and twelve `.verification.json` sidecars. The payload hashes remain bound to the canonical `archive_sha256` values in `manifests/ARCHIVED_EVIDENCE.json`; the absent sidecar checksum bindings are retained from the prior release manifest and were not independently revalidated during this final Git-only update. No API credential is required.

## Large raw evidence

Normal Git does not contain the multi-gigabyte uncompressed raw arms. Internal archive metadata is in:

```text
manifests/ARCHIVED_EVIDENCE.json
manifests/evidence_inventories/*.json
```

The local archive payloads are under:

```text
internal_archive/thesis_evidence_20260823/archives/
```

An independent external copy of all twelve payloads is recorded at the [Google Drive raw-evidence archive](https://drive.google.com/drive/folders/1BWu5604Fmyo3qZHEO3OjKPpgqGYT4Cs5?usp=drive_link). After upload, the archives were downloaded to a local machine and SHA-256 was recomputed on all twelve downloaded `.tar.zst` files. The result was 12/12 matches against the canonical `archive_sha256` fields in `manifests/ARCHIVED_EVIDENCE.json`. This verifies the archive bytes after a storage round trip; it is distinct from the existing source-inventory/stream verification recorded by each archive's `restoration_test` field.

For each archive:

```bash
sha256sum internal_archive/thesis_evidence_20260823/archives/<archive>.tar.zst
zstd -t internal_archive/thesis_evidence_20260823/archives/<archive>.tar.zst
tar --use-compress-program=zstd -tf internal_archive/thesis_evidence_20260823/archives/<archive>.tar.zst
```

`scripts/internal_archive_tools.py` generated and stream-verified each archive against its source inventory. It can be used by an authorized reviewer to repeat verification while the original tree is available.

The previous same-HPC-filesystem-only limitation no longer describes the current storage state because the independently downloaded Drive copies passed the 12/12 canonical-hash comparison. The original raw trees and prepared HPC archive copies remain retained. Access to the Drive folder is intended to remain restricted to authorized university reviewers; because no Google API or remote inspection was used in this metadata update, confirm the sharing configuration administratively before granting reviewer access. Fresh-clone simulation directories and other local readiness scratch material under `internal_archive/` are not part of the twelve-archive delivery set.

## Restoring an archive

Restore into a new empty directory; never extract over the working repository:

```bash
mkdir restored-evidence
tar --use-compress-program=zstd -xf <archive>.tar.zst -C restored-evidence
```

Recompute the restored file inventory using the canonicalization documented in the corresponding JSON inventory. The expected member count, byte count, and canonical inventory SHA-256 are also present in `manifests/ARCHIVED_EVIDENCE.json`.

Unmanifested `.env` symlinks found in source-snapshot directories are intentionally absent from internal archives and the proposed Git tree. They point to private local paths and are not part of any captured scientific source manifest.

## Evidence classes

- Historical baseline and hardened package: stored counts can be recomputed, but exact historical source/payload reproduction is unavailable.
- Matched A01--A08: exact within-run prompts, conditions, captured source states, and pair identifiers are preserved; raw arms are internally archived.
- Supplemental A02/A06/A07-S: stronger prompt, scorer, source, dependency, and index provenance is retained.
- Verifier replay: deterministic decisions can be recomputed from the frozen corpus without API calls.

See `docs/EVIDENCE_MAP.md` for authoritative paths and `docs/PROVENANCE_LIMITATIONS.md` for boundaries.

## Comparable new experiments

New A01--A08 runs use `code/evaluation2/` and the Slurm or local wrappers under `scripts/`. A new run must record its source state, prompts, model, temperature, policy/dataset hashes, dependency versions, guard configuration, scorer identity, and result hashes. It is a new observation; it does not replace any thesis evidence.

OpenAI credentials are required only for new hosted-model generations. Deterministic retrieval-only modes, stored-output scoring, audits, tests, hash verification, and thesis compilation do not require an API call.

## Thesis build

```bash
mkdir -p thesis/build
(cd thesis && tectonic --keep-logs --outdir build main.tex)
```

The build consumes frozen source, generated tables, and figures. It does not rerun experiments and must not overwrite `thesis/final_thesis.pdf`.
