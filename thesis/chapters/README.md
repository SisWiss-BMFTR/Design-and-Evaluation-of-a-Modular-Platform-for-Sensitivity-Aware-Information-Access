# Generated thesis chapters

The five `.tex` files in this directory are standalone chapter includes for Chapters 5--9. They follow a discovery--analysis--hardening--re-evaluation narrative and do not modify the completed System Architecture or Methodology chapters.

The repository now provides `thesis/main.tex`, which loads the required packages and includes these files in numeric order. Chapters 1--4 remain commented include points until their existing thesis sources are available in LaTeX form.

Evidence precedence used during drafting:

1. Neutral-prompt pre-hardening JSON/CSV outputs under `outputs/experiments/gpt4o_mini_slurm_attacks01_07_08_neutral_prehardened_20260719` for all baseline measurements.
2. Neutral-prompt post-hardening JSON/CSV outputs under `outputs/experiments/post hardened 1-8` for post-hardening measurements.
3. Attack-specific Markdown reports beside those outputs, when consistent with the underlying records.
4. Matched guard-ablation JSON/CSV outputs under `outputs/experiments/matched_single_guard_ablations` for A01--A08 component-level evidence.
5. Aggregated reports and the supervisor report only for experiment history and supporting interpretation.

The earlier attack-labelled pre-hardening and post-hardening outputs are not used as the primary package-level evidence. Attack-family labels are absent in both authoritative package stages. The A01--A08 component experiments are kept separate: their guards-off arm is not the historical original implementation. Exact off/on prompts match within each ablation. The authoritative A04 and A06 component results use the later complete family-label-omitted executions; their earlier complete labelled runs are superseded, and the incomplete first A06 family-label-omitted attempt is excluded. Family-label omission does not imply semantic prompt neutrality. The A07 ablation covers only the natural A07-N family, not the historical synthetic A07-S trigger. The first A08 attempt failed before producing usable result records and is excluded; the complete rerun is authoritative. At package level, A05 retains a wording difference and A07 compares synthetic-trigger and natural-style variants, which the chapters qualify explicitly.
