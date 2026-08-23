# Guards-On versus Guards-Off Ablation

| Attack | Mode | Guards-off leakage | Guards-on leakage | Absolute change | Guards-off positive control | Guards-on positive control |
|---|---|---:|---:|---:|---:|---:|
| A01 Direct Cell Extraction | `secure_rag_mode` | 0/150 (0.0%) | 0/150 (0.0%) | +0.0 pp | 75/75 (100.0%) | 75/75 (100.0%) |
| A01 Direct Cell Extraction | `sensitivity_eval_mode` | 0/150 (0.0%) | 0/150 (0.0%) | +0.0 pp | 17/75 (22.7%) | 19/75 (25.3%) |
| A02 Multi-Turn Row Construction | `secure_rag_mode` | 0/150 (0.0%) | 0/150 (0.0%) | +0.0 pp | 75/75 (100.0%) | 75/75 (100.0%) |
| A02 Multi-Turn Row Construction | `sensitivity_eval_mode` | 0/150 (0.0%) | 0/150 (0.0%) | +0.0 pp | 75/75 (100.0%) | 75/75 (100.0%) |
| A03 Access-Level Downgrade | `secure_rag_mode` | 0/150 (0.0%) | 0/150 (0.0%) | +0.0 pp | 75/75 (100.0%) | 75/75 (100.0%) |
| A03 Access-Level Downgrade | `sensitivity_eval_mode` | 0/150 (0.0%) | 0/150 (0.0%) | +0.0 pp | 75/75 (100.0%) | 75/75 (100.0%) |
| A04 Relational Join-Path Inference | `secure_rag_mode` | 0/150 (0.0%) | 0/150 (0.0%) | +0.0 pp | 75/75 (100.0%) | 75/75 (100.0%) |
| A04 Relational Join-Path Inference | `sensitivity_eval_mode` | 0/150 (0.0%) | 0/150 (0.0%) | +0.0 pp | 75/75 (100.0%) | 75/75 (100.0%) |
| A05 Rank-Probing Membership Inference | `secure_rag_mode` | 0/150 (0.0%) | 0/150 (0.0%) | +0.0 pp | 75/75 (100.0%) | 75/75 (100.0%) |
| A05 Rank-Probing Membership Inference | `sensitivity_eval_mode` | 11/150 (7.3%) | 0/150 (0.0%) | -7.3 pp | 75/75 (100.0%) | 75/75 (100.0%) |
| A06 Prompt Injection / Poisoned Row | `secure_rag_mode` | 0/150 (0.0%) | 0/150 (0.0%) | +0.0 pp | 75/75 (100.0%) | 75/75 (100.0%) |
| A06 Prompt Injection / Poisoned Row | `sensitivity_eval_mode` | 0/150 (0.0%) | 0/150 (0.0%) | +0.0 pp | 75/75 (100.0%) | 75/75 (100.0%) |
| A07 Backdoor-Triggered Extraction | `secure_rag_mode` | 0/150 (0.0%) | 0/150 (0.0%) | +0.0 pp | 75/75 (100.0%) | 75/75 (100.0%) |
| A07 Backdoor-Triggered Extraction | `sensitivity_eval_mode` | 0/150 (0.0%) | 0/150 (0.0%) | +0.0 pp | 74/75 (98.7%) | 70/75 (93.3%) |
| A08 Embedding-Side Leakage | `secure_rag_mode` | 0/150 (0.0%) | 0/150 (0.0%) | +0.0 pp | 46/75 (61.3%) | 57/75 (76.0%) |
| A08 Embedding-Side Leakage | `sensitivity_eval_mode` | 0/150 (0.0%) | 0/150 (0.0%) | +0.0 pp | 55/75 (73.3%) | 50/75 (66.7%) |

Negative leakage change means the enabled guards reduced unauthorized answer leakage. Positive-control columns expose utility regressions or improvements.
