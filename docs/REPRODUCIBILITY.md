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

The checksum file intentionally covers the frozen thesis, dataset, policy, ledgers, archive manifest, source manifests, compact evidence, and locally available evidence archives. `--ignore-missing` verifies the Git-resident subset in a Git-only checkout. After the twelve archive payloads have been restored at their documented repo-relative paths, run `sha256sum -c manifests/RELEASE_SHA256SUMS` without that option for the complete internal archive. No API credential is required.

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

For each archive:

```bash
sha256sum internal_archive/thesis_evidence_20260823/archives/<archive>.tar.zst
zstd -t internal_archive/thesis_evidence_20260823/archives/<archive>.tar.zst
tar --use-compress-program=zstd -tf internal_archive/thesis_evidence_20260823/archives/<archive>.tar.zst
```

`scripts/internal_archive_tools.py` generated and stream-verified each archive against its source inventory. It can be used by an authorized reviewer to repeat verification while the original tree is available.

Before delivery, copy `internal_archive/thesis_evidence_20260823/archives/` together with `manifests/ARCHIVED_EVIDENCE.json`, `manifests/evidence_inventories/`, and `manifests/RELEASE_SHA256SUMS` to an independent authorized university destination. The existing archives and original trees are on the same HPC-backed filesystem and are not independent durable copies. Fresh-clone simulation directories and other local readiness scratch material under `internal_archive/` are not part of the twelve-archive delivery set.

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
