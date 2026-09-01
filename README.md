# Design and Evaluation of a Modular Platform for Sensitivity-Aware Information Access

## Repository status

This repository is an internal archival snapshot corresponding to the final Master's thesis submission. It intentionally does not include the original development Git history. Scientific provenance relevant to the reported experiments is preserved through captured source snapshots, manifests, checksums, evidence ledgers, prompt records, audit artifacts, and documented provenance limitations.

The archive is intended only for supervisors, examiners, and authorized university reviewers. It is not a public release or a reconstructed development-history repository.

The retained material has four distinct roles:

1. `code/`, `scripts/`, `tests/`, and the synchronized thesis source represent the final archival implementation and source state;
2. labelled historical and hardened outputs are descriptive experimental evidence, not component-level causal reruns;
3. matched and supplemental run roots retain the captured source snapshots, prompts, manifests, patches, and receipts that define their executed states;
4. executions made from the final archival implementation are new comparable reruns and must not be represented as exact recreation of historical hosted-model calls.

The implementation is a research prototype. Its recorded findings are limited to the workbook, prompts, roles, modes, scorers, source states, and hosted-model calls described in the thesis.

## Frozen thesis authority

The canonical thesis PDF is:

```text
thesis/final_thesis.pdf
```

The human-readable submission copy is:

```text
thesis/Design and Evaluation of a Modular Platform for Sensitivity-Aware Information Access.pdf
```

Both frozen PDFs are byte-identical, contain 192 physical pages, and have SHA-256:

```text
15ed795d0753c70b88b80e6b652845c3f6c9bd7ba54aba23e2464d1dd2d452d8
```

These two files are the authoritative final thesis artefacts. Rebuilding the LaTeX source is a content/buildability check; it does not replace either frozen PDF.

## Architecture

The system loads a fictional structured workbook, creates entity documents with field-level metadata, embeds them with `sentence-transformers/all-MiniLM-L6-v2`, and retrieves through a FAISS-based hybrid retriever. The pipeline then applies role, field, relation, memory, prompt-injection, membership, embedding-probe, and output-delivery controls before returning an answer.

Primary implementation areas:

- `code/ingestion/`: XLSX loading and entity construction;
- `code/retrieval/`: FAISS and hybrid retrieval;
- `code/memory/`: conversation state;
- `code/security/`: the six evaluated guards and access projection;
- `code/pipeline/rag_pipeline.py`: orchestration;
- `code/generation/`: OpenAI-compatible generation;
- `code/evaluation2/`: maintained A01--A08 runners and runtime provenance.

`code/evaluation/` is retained as labelled legacy/reference code. It is not a recovered byte-identical historical source tree.

## Repository structure

```text
data/                 fictional thesis workbook
code/                 RAG implementation and evaluation runners
scripts/              scoring, audits, evidence builders, plots, Slurm jobs
tests/                deterministic access/verifier tests
thesis/               frozen PDF and synchronized LaTeX source
outputs/              historical, hardened, matched, and supplemental evidence
manifests/            archive inventories, path mappings, provenance and checksums
docs/                 internal reproducibility and evidence documentation
external raw archive  twelve checksum-bound packages; not inside this Git tree
```

## Dataset and policy

The fictional workbook is committed at the case-sensitive runtime path:

```text
data/SiSWiss_Testdaten.xlsx
```

Expected SHA-256:

```text
bbeaf08104ae59a1d3cdc035c03c7509dccb09b643854ae42136ddffc843e236
```

Field labels, ranks, roles, permissions, and aliases are defined in `sensitivity_policy.yaml`. Reviewed field/cell exceptions are recorded in `sensitivity_overrides.yaml`. See `data/README.md` and the thesis methodology for scope and interpretation.

## Installation

Use Python 3.10. The current source uses Python 3.10 type syntax.

```bash
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

`requirements.txt` is a portable functional specification, not a byte-identical reconstruction of an HPC environment. Run-specific dependency captures remain with the supplemental evidence.

## API configuration

Copy `.env.example` to `.env` and insert credentials only for a new hosted-model run:

```bash
cp .env.example .env
chmod 600 .env
```

Never commit `.env`. Inspecting stored evidence, verifying hashes, deterministic rescoring, and building the thesis do not require an OpenAI credential.

## Running the RAG system

```bash
streamlit run code/streamlit_app.py
```

`secure_rag_mode` applies role-based projection before generation. `sensitivity_eval_mode` deliberately retains labelled mixed-sensitivity evidence in model-visible context for controlled diagnosis; it is not the secure deployment setting.

The independent evaluated switches are:

- `OUTPUT_LEAKAGE_VERIFIER_ENABLED`;
- `MEMBERSHIP_GUARD_ENABLED`;
- `EMBEDDING_PROBE_GUARD_ENABLED`;
- `PROMPT_INJECTION_GUARD_ENABLED`;
- `ACCESS_CHANGE_MEMORY_CLEAR_ENABLED`;
- `RELATION_ACCESS_GUARD_ENABLED`.

Record every override when running a new experiment.

## A01--A08 and matched ablations

The maintained runners under `code/evaluation2/` implement:

1. A01 direct cell extraction;
2. A02 multi-turn row construction;
3. A03 access downgrade and memory leakage;
4. A04 relational join-path inference;
5. A05 rank-probing membership inference;
6. A06 poisoned-row prompt injection;
7. A07 backdoor-triggered extraction;
8. A08 embedding-side leakage.

Matched single-guard job definitions and submission scripts are under `scripts/slurm/`. The authoritative run-specific source snapshots and prompt manifests remain under the corresponding experiment roots. Current code can be used for a comparable new experiment but must not be substituted for a captured executed snapshot.

## Supplemental studies

- Full A02 verifier challenge: `outputs/experiments/full_a02_verifier_challenge/FVC_A02_20260803T115546Z`;
- frozen A06 challenge: `outputs/experiments/supplemental_a06_poisoned_row/SA06_A06_prompt_injection_guard_20260805T220542Z`;
- matched A07-S: `outputs/experiments/matched_a07s_prompt_injection_guard/E07S_A07S_prompt_injection_guard_family_label_omitted_20260803T021408Z`;
- deterministic replay: `outputs/verifier_validation/a01_a02_replay_v1_20260803`.

The scoring and audit implementations are retained in `scripts/`, and their run-specific copies/hashes are preserved where captured.

## Evidence verification

Four different operations must remain separate:

1. verify file hashes and provenance;
2. recompute deterministic metrics from stored raw outputs;
3. run a new comparable experiment;
4. exactly regenerate a historical hosted-model run.

Stored outputs and deterministic scoring can be verified where the raw evidence is retained. Comparable new experiments can be run from the current source, but hosted-model outputs and historically incomplete source states cannot be exactly regenerated.

Canonical evidence sources include:

- historical and hardened result trees under `outputs/experiments/`;
- `outputs/rescoring/a02_policy_aware_20260722T155853Z/`;
- `outputs/final_thesis_evidence_20260803_prompt_provenance_v3/`;
- `outputs/final_thesis_supplemental_evidence_20260806/`;
- `manifests/HARDENED_A05_PROVENANCE.json`;
- `manifests/ARCHIVED_EVIDENCE.json`.

See `docs/EVIDENCE_MAP.md` and `docs/PROVENANCE_LIMITATIONS.md` before interpreting comparisons.

## Internal raw archives

The twelve large matched and supplemental raw packages are not stored in this Git working tree. Their original prepared deterministic `tar.zst` copies remain at the separate development-project archive location:

```text
internal_archive/thesis_evidence_20260823/archives/
```

An independent external copy of all twelve archives is retained in the [Google Drive raw-evidence archive](https://drive.google.com/drive/folders/1BWu5604Fmyo3qZHEO3OjKPpgqGYT4Cs5?usp=drive_link). After upload, all twelve archives were downloaded to a local machine and SHA-256 was recomputed; 12/12 downloaded hashes matched the canonical `archive_sha256` values in `manifests/ARCHIVED_EVIDENCE.json`. The original HPC copies remain retained.

The Drive archive is intended only for restricted, authorized university review and is not presented as public evidence. This metadata update did not call Google APIs, so the current Google sharing configuration was not independently inspected from the repository. Per-member inventories are retained under `manifests/evidence_inventories/`, and archive-level bindings and structured round-trip verification metadata are in `manifests/ARCHIVED_EVIDENCE.json` and `manifests/RELEASE_SHA256SUMS`.

## Tests and deterministic checks

```bash
PYTHONPATH=code python -m unittest discover -s tests
python scripts/check_thesis_with_matched_ablations.py \
  --evidence-dir outputs/final_thesis_evidence_20260803_prompt_provenance_v3 \
  --build-log thesis/build/main.log \
  --pdf thesis/build/main.pdf \
  --report manifests/THESIS_SOURCE_CONSISTENCY.json \
  --skip-external-raw-rehash
```

No OpenAI call is needed for these checks.

## Tables and figures

Final generated tables are under `thesis/generated/`; final plots are under `thesis/figures/results/`. Plotting, evidence-building, and table-generation scripts are under `scripts/`. `manifests/FIGURE_TABLE_PROVENANCE.json` binds frozen outputs to known scripts and principal inputs without rerunning experiments.

## Building the thesis

With Tectonic installed:

```bash
mkdir -p thesis/build
(cd thesis && tectonic --keep-logs --outdir build main.tex)
```

The review build may differ in PDF metadata or pagination across TeX environments. It must not overwrite `thesis/final_thesis.pdf`.

## Documentation

- `docs/REPRODUCIBILITY.md`: verification and restoration procedures;
- `docs/EVIDENCE_MAP.md`: claim-to-evidence map;
- `docs/PROVENANCE_LIMITATIONS.md`: unavailable or bounded provenance;
- `manifests/PATH_MAPPINGS.json`: additive portable mappings for historical absolute paths.
- `manifests/ARCHIVAL_WORKSPACE_SECURITY_SCAN.json`: value-free security and history-isolation scan of the clean workspace;
- `manifests/PROVENANCE_ARTIFACT_CLASSIFICATION.json`: per-artifact provenance security classification.

Older prose documents in `docs/` are labelled legacy where retained. The frozen thesis source is authoritative for scientific wording.
