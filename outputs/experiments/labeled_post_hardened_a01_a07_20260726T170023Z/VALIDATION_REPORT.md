# Labeled Post-Hardened A01/A07 Validation Report

Validated: 2026-07-26T19:57:20.830317+00:00

Overall valid: `True`

Records: `1350/1350`; duplicates: `0`; validation errors: `0`.

## Results

### A01 / secure_rag_mode

- unauthorized delivered leaks: `0`
- unauthorized runs: `150`
- protected delivered disclosures: `75`
- protected runs: `75`
- output guard blocks: `0`

### A01 / sensitivity_eval_mode

- unauthorized delivered leaks: `0`
- unauthorized runs: `150`
- protected delivered disclosures: `19`
- protected runs: `75`
- output guard blocks: `0`

### A07-S / secure_rag_mode

- unauthorized answer leaks: `0`
- unauthorized runs: `150`
- protected positive control successes: `30`
- protected runs: `75`
- prompt context quarantines: `75`
- canary outputs: `0`

### A07-S / sensitivity_eval_mode

- unauthorized answer leaks: `0`
- unauthorized runs: `150`
- protected positive control successes: `75`
- protected runs: `75`
- prompt context quarantines: `0`
- canary outputs: `0`

### A07-N / secure_rag_mode

- unauthorized answer leaks: `0`
- unauthorized runs: `150`
- protected positive control successes: `35`
- protected runs: `75`
- prompt context quarantines: `75`
- canary outputs: `0`

### A07-N / sensitivity_eval_mode

- unauthorized answer leaks: `0`
- unauthorized runs: `150`
- protected positive control successes: `66`
- protected runs: `75`
- prompt context quarantines: `0`
- canary outputs: `0`

## Coverage

- Every unit contains five targets, public/internal/protected roles, conversation lengths 1/3/5, iterations 1–5, and 225 unique records.
- All prompts explicitly name the attack.
- A01 output verification and A07 prompt-injection guarding are enabled in every record.
- The submission environment also enabled post-generation verification, prompt-injection guarding, and access-change memory clearing globally.
