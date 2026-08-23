# Final matched-ablation evidence with neutral A04 and A06 prompts

This package is the authoritative matched guard-ablation evidence for the
current thesis. It selects the complete neutral-prompt reruns for A04 and A06
and retains the previously audited authoritative runs for A01--A03, A05,
A07-N, and A08.

The selected A04 experiment is
`E04_A04_relation_access_guard_neutral_20260801T163000Z`. The selected A06
experiment is
`E06_A06_prompt_injection_guard_neutral_20260801T163000Z`. Both contain 450
matched off/on pairs and use commit `8afb07d5d0dc09299e9fcab127703d0e97c1cd58`.

The earlier complete attack-labelled A04 and A06 experiments are superseded.
The initial A06 neutral attempt at `20260801T160000Z` produced no result shards
and is excluded. The earlier incomplete A08 attempt also remains excluded.

`provenance_with_ablations.json` records source selection and exclusions.
`matched_ablation_metric_summary.json` and the CSV files contain the values
used to regenerate the thesis tables and figures.

As in the earlier evidence package, a guards-off arm is a single-control
ablation of the captured hardened codebase. It is not the historical original
implementation.
