# Post-Generation Leakage Verifier

> **Labelled legacy implementation note.** Use the frozen thesis guard reference, current source, and run-specific source/scorer manifests for authoritative interpretation.

This defense is designed for `sensitivity_eval_mode`, where restricted values must remain visible to the language model. It does not filter retrieval and it does not remove sensitive fields from the prompt.

The pipeline is:

```text
user question
-> retrieval
-> sensitivity-eval context with metadata-rich field labels
-> LLM generation
-> post-generation leakage verifier
-> delivered answer
```

The verifier compares the raw generated answer against restricted field values from the retrieved records for the active role. If a restricted value appears in the raw answer and the verifier is enabled, the delivered answer is replaced with a refusal. The pipeline stores both `last_raw_answer` and `last_output_guard`, so experiments can report raw leakage and delivered leakage separately.

This keeps the sensitivity-evaluation condition intact: the LLM still sees allowed and restricted values, but the system can measure and reduce final-answer leakage.

For Attack 2, use:

```bash
env/rag/bin/python code/evaluation2/run_multiturn_row_construction_batch.py \
  --rag-mode sensitivity_eval_mode \
  --post-generation-verifier \
  --access all
```

For an ablation where the LLM still sees metadata-rich context but the final verifier does not redact the answer, use `--no-post-generation-verifier`.
