# Final thesis evidence bundle

This directory is the machine-readable bridge between the stored experiment
records and Chapters 5--9.

- `metrics.json` contains counts extracted from the original baseline, original
  hardened-package, policy-aware A02 rescore, and matched guard-ablation JSON.
- `provenance.json` and `provenance.csv` classify every comparison and record
  source stage, prompt status, guard configuration, hashes, denominators, and
  unavailable metadata.
- `checksums.json` hashes the main input summaries and generated evidence files.
- `consistency_check.json` records the final numerical, figure, and layout
  checks.

The correction folders' `pre_hardening` arms are hardened-code guards-off
ablations. They are not the original pre-hardening implementation.

Rebuild and validate from the repository root:

```bash
env/rag/bin/python scripts/build_final_thesis_evidence.py
env/rag/bin/python scripts/plot_final_thesis_figures.py
cd thesis
../env/rag/bin/tectonic --keep-logs --outdir build-final-clean main.tex
cd ..
env/rag/bin/python scripts/check_final_thesis_consistency.py
```

The plotting script requires Matplotlib. The compile command used Tectonic
0.16.9.
