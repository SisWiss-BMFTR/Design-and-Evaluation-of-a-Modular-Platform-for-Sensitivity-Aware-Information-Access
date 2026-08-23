# Matched guard-ablation evidence used by the thesis

This directory is generated from the completed experiments under
`outputs/experiments/matched_single_guard_ablations`.

- `provenance_with_ablations.json` records source selection, implementation and
  prompt matching, fixed and switched guard settings, dataset metadata, and
  experiment limitations.
- `matched_ablation_metric_summary.json` and
  `matched_ablation_summary.csv` contain the attack-specific measurements used
  in the thesis tables and figures.
- `matched_ablation_pair_validation.csv` and
  `matched_ablation_completeness.csv` document the record-level pairing audit.
- `consistency_check.json` records the automated audit outcome.
- `figure_generation_manifest.json` connects generated thesis figures to this
  evidence package.

The guards-off arms use the captured hardened implementation with one control
disabled. They are not the historical original baseline.

A06 is limited to its matched attack-labelled prompt. A07 covers the natural
A07-N family only; it does not test the historical synthetic-trigger A07-S
family. The incomplete A08 attempt
`E08_A08_embedding_probe_guard_20260729T084534Z` produced no usable result
records and is excluded. The complete rerun
`E08_A08_embedding_probe_guard_20260729T092151Z` is the sole authoritative A08
matched source.
