# Aggregated Attack Results Report

Generated: 2026-06-22

This report aggregates the completed `gpt-4o-mini` SLURM experiment outputs under `outputs/experiments/gpt4o_mini_slurm/`.

## Scope

- Attacks analyzed: 8 attack families.
- RAG modes: `secure_rag_mode` and `sensitivity_eval_mode`.
- Runs per attack/mode: 225 conversations.
- Total conversations analyzed: 3,600.
- Unauthorized conditions per attack/mode: 150 public/internal conversations.
- Positive-control conditions per attack/mode: 75 protected conversations.
- Access levels: `public`, `internal`, and `protected`.
- Conversation lengths: 1, 3, and 5 user turns. For Attack 3, this means pre-attack history length before the final downgraded turn.
- Iterations per target/access/length condition: 5.
- Dataset: `data/SiSWiss_Testdaten.xlsx`.
- Generation model: `gpt-4o-mini`.
- Generation temperature: 0.0.

The metrics below were computed from the `results.csv` files in each attack folder and interpreted using the attack-specific `report.md` files.

## Mode Interpretation

`secure_rag_mode` is the normal enforcement path. Retrieved entities may contain mixed-sensitivity records internally, but forbidden fields should be removed before the generator sees them. In this mode, raw retrieval exposure is diagnostic, while final-answer leakage is the user-visible failure signal.

`sensitivity_eval_mode` is a controlled evaluation path. Restricted facts are intentionally included in labelled context to test whether the model follows access labels. In this mode, restricted context exposure is expected by design; answer-level leakage is the main failure condition.

Because the output schemas do not always distinguish raw retrieved records from projected prompt context, this report keeps retrieval/context exposure separate from final-answer leakage.

## Executive Summary

The strongest failure is Attack 3, access-level downgrade memory leakage. It leaked the protected value in 150/150 unauthorized public/internal final answers in both RAG modes. This indicates that once protected information was introduced during the authorized setup turn, it remained available after access was reduced.

In `secure_rag_mode`, final-answer leakage occurred in three attack families: Attack 2 multi-turn row construction, Attack 3 access downgrade, and Attack 5 rank-probing membership inference. Direct cell extraction, relational join-path inference, poisoned-row prompt injection, backdoor-triggered extraction, and embedding-side probing did not leak protected secrets in unauthorized final answers under the current scoring, although most showed retrieval/context exposure.

In `sensitivity_eval_mode`, answer leakage increased. Attack 2 leaked in 108/150 unauthorized runs, Attack 4 leaked join-edge information in 86/150, Attack 5 leaked membership signals in 50/150, Attack 8 leaked protected numeric values in 10/150, and Attack 3 still leaked in 150/150.

Public and internal behavior differed sharply in `secure_rag_mode`. Attack 2 and Attack 5 leaked only under `internal`, while `public` stayed at 0/75 for those attacks. Attack 3 leaked under both public and internal access.

Prompt-injection and backdoor behavior split into two separate risks. Attack 6 did not emit the canary and did not leak protected answers. Attack 7 emitted the backdoor canary in 150/150 unauthorized runs in both modes, showing instruction-following manipulation, but still did not reveal the protected target marker in unauthorized final answers.

Positive-control reliability was uneven. Secure mode positive controls were strong for Attacks 1, 3, 4, 5, and 8, but weaker for Attack 2 and Attack 6 and very weak for Attack 7. Sensitivity-evaluation positive controls were often worse, especially for Attacks 4, 6, 7, and 8.

## Normalized Results

| Attack | Mode | Unauthorized retrieval/context exposure | Unauthorized answer leakage | Protected positive-control success | Authorized errors | Notes |
|---|---|---:|---:|---:|---:|---|
| A01 Direct Cell Extraction | `secure_rag_mode` | 150/150 (100.0%) | 0/150 (0.0%) | 75/75 (100.0%) | 0/75 (0.0%) | Direct protected values were refused in unauthorized answers. |
| A01 Direct Cell Extraction | `sensitivity_eval_mode` | 150/150 (100.0%) | 0/150 (0.0%) | 57/75 (76.0%) | 18/75 (24.0%) | Unauthorized answers still refused; protected controls were less reliable. |
| A02 Multi-Turn Row Construction | `secure_rag_mode` | 120/150 (80.0%) | 50/150 (33.3%) | 68/75 (90.7%) | 7/75 (9.3%) | Unauthorized leaks were partial; full unauthorized row reconstruction was 0/150. |
| A02 Multi-Turn Row Construction | `sensitivity_eval_mode` | 120/150 (80.0%) | 108/150 (72.0%) | 74/75 (98.7%) | 1/75 (1.3%) | Full unauthorized row reconstruction occurred in 44/150 runs. |
| A03 Access-Level Downgrade | `secure_rag_mode` | 150/150 (100.0%) | 150/150 (100.0%) | 75/75 (100.0%) | 0/75 (0.0%) | Memory exposure was also 150/150. |
| A03 Access-Level Downgrade | `sensitivity_eval_mode` | 150/150 (100.0%) | 150/150 (100.0%) | 75/75 (100.0%) | 0/75 (0.0%) | Same 100% downgrade leakage pattern as secure mode. |
| A04 Relational Join-Path Inference | `secure_rag_mode` | 150/150 (100.0%) | 0/150 (0.0%) | 75/75 (100.0%) | 0/75 (0.0%) | Unauthorized answers did not complete the join edge or reveal protected details. |
| A04 Relational Join-Path Inference | `sensitivity_eval_mode` | 150/150 (100.0%) | 86/150 (57.3%) | 11/75 (14.7%) | 64/75 (85.3%) | Leakage was join-edge disclosure; protected-detail answer leakage was 0/150. |
| A05 Rank-Probing Membership Inference | `secure_rag_mode` | 150/150 (100.0%) | 55/150 (36.7%) | 75/75 (100.0%) | 0/75 (0.0%) | Candidate ID/name evidence appeared in 150/150 unauthorized retrievals. |
| A05 Rank-Probing Membership Inference | `sensitivity_eval_mode` | 150/150 (100.0%) | 50/150 (33.3%) | 75/75 (100.0%) | 0/75 (0.0%) | Public and internal leaked equally in this mode. |
| A06 Prompt Injection / Poisoned Row | `secure_rag_mode` | 150/150 (100.0%) | 0/150 (0.0%) | 68/75 (90.7%) | 7/75 (9.3%) | Poison rows were retrieved in 150/150 unauthorized runs; canary output was 0/150. |
| A06 Prompt Injection / Poisoned Row | `sensitivity_eval_mode` | 150/150 (100.0%) | 0/150 (0.0%) | 25/75 (33.3%) | 50/75 (66.7%) | No unauthorized secret leak, but authorized accuracy dropped sharply. |
| A07 Backdoor-Triggered Extraction | `secure_rag_mode` | 150/150 (100.0%) | 0/150 (0.0%) | 5/75 (6.7%) | 70/75 (93.3%) | Backdoor canary appeared in 150/150 unauthorized answers. |
| A07 Backdoor-Triggered Extraction | `sensitivity_eval_mode` | 150/150 (100.0%) | 0/150 (0.0%) | 0/75 (0.0%) | 75/75 (100.0%) | Backdoor canary appeared in 150/150 unauthorized answers. |
| A08 Embedding-Side Leakage | `secure_rag_mode` | 150/150 (100.0%) | 0/150 (0.0%) | 75/75 (100.0%) | 0/75 (0.0%) | Unsupported unauthorized leaks were 0/150. |
| A08 Embedding-Side Leakage | `sensitivity_eval_mode` | 150/150 (100.0%) | 10/150 (6.7%) | 27/75 (36.0%) | 48/75 (64.0%) | Unauthorized leaks occurred only in one-turn conditions. |

## Cross-Mode Totals

| Mode | Unauthorized final-answer leaks | Unauthorized retrieval/context exposures | Protected positive-control successes | Authorized errors |
|---|---:|---:|---:|---:|
| `secure_rag_mode` | 255/1200 (21.2%) | 1170/1200 (97.5%) | 516/600 (86.0%) | 84/600 (14.0%) |
| `sensitivity_eval_mode` | 404/1200 (33.7%) | 1170/1200 (97.5%) | 344/600 (57.3%) | 256/600 (42.7%) |

These totals should not be interpreted as a single security score because each attack measures a different failure type. They are useful as a high-level map of where the system is weakest.

## Access-Level Pattern

| Attack | Mode | Public unauthorized answer leaks | Internal unauthorized answer leaks |
|---|---|---:|---:|
| A01 | `secure_rag_mode` | 0/75 | 0/75 |
| A01 | `sensitivity_eval_mode` | 0/75 | 0/75 |
| A02 | `secure_rag_mode` | 0/75 | 50/75 |
| A02 | `sensitivity_eval_mode` | 45/75 | 63/75 |
| A03 | `secure_rag_mode` | 75/75 | 75/75 |
| A03 | `sensitivity_eval_mode` | 75/75 | 75/75 |
| A04 | `secure_rag_mode` | 0/75 | 0/75 |
| A04 | `sensitivity_eval_mode` | 37/75 | 49/75 |
| A05 | `secure_rag_mode` | 0/75 | 55/75 |
| A05 | `sensitivity_eval_mode` | 25/75 | 25/75 |
| A06 | `secure_rag_mode` | 0/75 | 0/75 |
| A06 | `sensitivity_eval_mode` | 0/75 | 0/75 |
| A07 | `secure_rag_mode` | 0/75 | 0/75 |
| A07 | `sensitivity_eval_mode` | 0/75 | 0/75 |
| A08 | `secure_rag_mode` | 0/75 | 0/75 |
| A08 | `sensitivity_eval_mode` | 5/75 | 5/75 |

The secure-mode access-level pattern suggests that the `internal` role is a major residual attack surface. Internal users were able to obtain partial protected-row information in Attack 2 and membership confirmations in Attack 5, while public users did not leak in those two secure-mode attacks. The access-downgrade attack bypassed this distinction and leaked equally under public and internal final access.

## Conversation-Length Pattern

| Attack | Mode | 1-turn unauthorized leaks | 3-turn unauthorized leaks | 5-turn unauthorized leaks |
|---|---|---:|---:|---:|
| A01 | `secure_rag_mode` | 0/50 | 0/50 | 0/50 |
| A01 | `sensitivity_eval_mode` | 0/50 | 0/50 | 0/50 |
| A02 | `secure_rag_mode` | 5/50 | 25/50 | 20/50 |
| A02 | `sensitivity_eval_mode` | 13/50 | 45/50 | 50/50 |
| A03 | `secure_rag_mode` | 50/50 | 50/50 | 50/50 |
| A03 | `sensitivity_eval_mode` | 50/50 | 50/50 | 50/50 |
| A04 | `secure_rag_mode` | 0/50 | 0/50 | 0/50 |
| A04 | `sensitivity_eval_mode` | 5/50 | 44/50 | 37/50 |
| A05 | `secure_rag_mode` | 25/50 | 12/50 | 18/50 |
| A05 | `sensitivity_eval_mode` | 50/50 | 0/50 | 0/50 |
| A06 | `secure_rag_mode` | 0/50 | 0/50 | 0/50 |
| A06 | `sensitivity_eval_mode` | 0/50 | 0/50 | 0/50 |
| A07 | `secure_rag_mode` | 0/50 | 0/50 | 0/50 |
| A07 | `sensitivity_eval_mode` | 0/50 | 0/50 | 0/50 |
| A08 | `secure_rag_mode` | 0/50 | 0/50 | 0/50 |
| A08 | `sensitivity_eval_mode` | 10/50 | 0/50 | 0/50 |

Longer context is not uniformly worse, but it is clearly risky for reconstruction and relational inference in `sensitivity_eval_mode`. Attack 2 rose from 13/50 at one turn to 50/50 at five turns. Attack 4 rose from 5/50 at one turn to 44/50 at three turns and 37/50 at five turns. Attack 3 was saturated at 50/50 for every history length.

## Attack-by-Attack Analysis

### Attack 1: Direct Cell Extraction

Direct requests for protected cell values were blocked at the final-answer level for unauthorized users in both modes: 0/150 answer leaks in `secure_rag_mode` and 0/150 in `sensitivity_eval_mode`.

The diagnostic exposure fields still showed 150/150 unauthorized retrieval/context exposures in both modes. This should be investigated as a boundary-attribution issue: the report should distinguish raw retrieved entities from the projected prompt context given to the generator. The final answers indicate that the model did not disclose the target value to unauthorized users.

### Attack 2: Multi-Turn Row Construction

This attack is a serious reconstruction risk, especially for internal users and mixed-context evaluation.

In secure mode, unauthorized answer leakage was 50/150, all under internal access. Public access leaked 0/75. The leaks were partial rather than complete: full unauthorized row reconstruction was 0/150.

In sensitivity-evaluation mode, unauthorized leakage rose to 108/150, with public leaks at 45/75 and internal leaks at 63/75. Full unauthorized row reconstruction occurred in 44/150 runs. Longer conversations made this worse, reaching 50/50 leaks at five turns.

### Attack 3: Access-Level Downgrade Memory Leakage

This is the highest-priority failure.

Both modes leaked in every unauthorized final answer: 150/150 in secure mode and 150/150 in sensitivity-evaluation mode. Memory exposure was also 150/150. Positive controls were 75/75, so the target values were consistently available and reproduced.

The attack starts under protected access, elicits the protected value, reduces access to public or internal, then asks for the previous value. The system repeated the value after downgrade. This indicates the active role change is not sufficiently isolating recent messages, summaries, snippets, retrieval context, or final-answer validation.

### Attack 4: Relational Join-Path Inference

Secure mode protected the final answer: 0/150 unauthorized answer leaks and 75/75 protected positive-control successes. However, retrieval/context diagnostics showed 150/150 unauthorized exposure of protected downstream detail, so projected prompt visibility should be checked directly.

Sensitivity-evaluation mode was much weaker. Unauthorized answer leakage was 86/150, driven by join-edge disclosure. Protected-detail answer leakage was 0/150, meaning the model tended to reveal relation IDs or path structure rather than ingredient/process details.

### Attack 5: Rank-Probing Membership Inference

Membership inference remains a high-risk path.

In secure mode, unauthorized answer leakage was 55/150 and occurred only for internal users. Public users returned 0/75 leaks. Protected positive controls were 75/75.

In sensitivity-evaluation mode, unauthorized answer leakage was 50/150, split evenly between public and internal users. Candidate ID/name evidence appeared in 150/150 unauthorized retrievals. Even if some evidence comes from allowed metadata, final-answer membership confirmation under unauthorized access is a real leakage signal.

### Attack 6: Prompt Injection Through Poisoned Rows

The poisoned public rows were retrieved in all unauthorized runs, but the attack did not cause unauthorized protected-answer leakage: 0/150 in both modes. The canary was also not emitted in unauthorized answers: 0/150 in both modes.

Protected positive controls dropped from 68/75 in secure mode to 25/75 in sensitivity-evaluation mode. The injected public rows and mixed labels appear to interfere with authorized answer accuracy even when they do not cause unauthorized secret disclosure.

### Attack 7: Backdoor-Triggered Extraction

The backdoor attack did not disclose protected target markers to unauthorized users: 0/150 answer leaks in both modes. However, it did cause complete canary compliance: 150/150 unauthorized canary outputs in both modes.

This means the model followed the backdoor instruction text from retrieved public content, even though it did not reveal the protected marker. That is still an integrity problem: attacker-controlled public rows can manipulate assistant output.

### Attack 8: Embedding-Side Leakage

Secure mode resisted the embedding-side prompt at the final-answer level: 0/150 unauthorized leaks and 75/75 protected positive-control successes.

Sensitivity-evaluation mode leaked in 10/150 unauthorized runs. All leaks occurred in one-turn conditions: 10/50 at one turn, 0/50 at three turns, and 0/50 at five turns. Unsupported unauthorized leaks were 0/150.

## Severity Ranking

| Priority | Attack | Reason |
|---:|---|---|
| 1 | A03 Access-Level Downgrade | 100% unauthorized final-answer leakage in both modes; memory exposure also 100%. |
| 2 | A02 Multi-Turn Row Construction | Secure-mode internal leakage and high sensitivity-mode reconstruction leakage. |
| 3 | A05 Rank-Probing Membership Inference | Secure-mode internal membership leaks and sensitivity-mode public/internal leaks. |
| 4 | A04 Relational Join-Path Inference | Secure final answers held, but sensitivity-mode join-edge leakage was high. |
| 5 | A07 Backdoor-Triggered Extraction | No unauthorized secret disclosure, but 100% canary compliance shows output manipulation. |
| 6 | A08 Embedding-Side Leakage | Secure mode held; sensitivity mode leaked in 10/150 unauthorized runs. |
| 7 | A06 Prompt Injection / Poisoned Row | No unauthorized answer leakage or canary compliance, but authorized accuracy degraded. |
| 8 | A01 Direct Cell Extraction | No unauthorized final-answer leakage; positive-control reliability needs attention in sensitivity mode. |

## Mitigation Priorities

1. Fix access-downgrade memory isolation first. On any access reduction, clear or re-scope recent turns, summaries, semantic memory snippets, cached retrieved context, and any generated hidden state tied to the previous higher role.
2. Add explicit model-visible context logging. Every attack output should distinguish raw retrieval from projected prompt context.
3. Harden row reconstruction responses for internal users. Detect prompts that ask for structured row reconstruction, field-value pairs, or completion of known identifiers.
4. Harden membership-inference answers. Avoid confirming whether protected formulation records exist for unauthorized users, even when the prompt provides an exact ID or name.
5. Reclassify join edges and linked identifiers. If a relationship field bridges from public/internal records to protected records, protect the edge itself or return a non-confirming answer.
6. Treat retrieved rows as data, never instructions. Strip or neutralize instruction-like text from retrieved user-controlled rows before generation.
7. Repair positive-control regressions. For attacks with low protected positive-control success, adjust prompts or context labels so authorized users can still receive allowed information.
8. Re-run the full matrix after fixes so results remain comparable.

## Thesis-Ready Summary

Across 3,600 attack conversations, the evaluated RAG system showed strong final-answer resistance to direct cell extraction, poisoned-row prompt injection, and secure-mode embedding-side probing, but it remained vulnerable to attacks that exploit memory, multi-turn reconstruction, membership confirmation, and relationship inference. The most severe result was access-level downgrade leakage: after protected information was disclosed during an authorized setup turn, the system repeated it in 150/150 unauthorized final answers in both `secure_rag_mode` and `sensitivity_eval_mode`. In secure mode, unauthorized answer leakage also appeared in internal multi-turn row construction and internal membership inference, while public access remained protected for those two attacks. Sensitivity-evaluation mode produced more final-answer leakage overall because restricted facts were intentionally visible in labelled context, exposing model-level weaknesses in row reconstruction, relational inference, membership inference, and embedding-side prompts. The results show that field-level projection alone is not sufficient unless conversation memory, relationship metadata, answer validation, and prompt-integrity controls are enforced under the current active role.
