# Methodology

> **Labelled legacy draft.** The frozen thesis methodology and appendices are authoritative. This earlier prose draft is retained only to preserve development context.

This chapter describes the methodological procedure used to evaluate the implemented field-level, sensitivity-aware Retrieval-Augmented Generation (RAG) system. The aim of the evaluation is not to prove the general security of all RAG systems, but to conduct a controlled empirical case study of confidentiality risks in a RAG pipeline over structured spreadsheet data. The methodology therefore covers the complete research process: preparation of the dataset, construction of the RAG pipeline, definition of the access-control model, formulation of the threat model, design of adversarial test scenarios, scoring of leakage events, and documentation of experimental outputs.

The central methodological challenge is that the system does not use simple document-level access control. Instead, access decisions are made at field level. A retrieved entity may contain public, internal, confidential, restricted, and protected fields at the same time. For this reason, the evaluation must distinguish between information that is retrieved internally, information that is actually inserted into the model prompt, information that remains in conversation memory, and information that appears in the final answer. This distinction is essential for interpreting the results correctly.

## 1. Research Objective and Evaluation Strategy

The objective of the methodology is to evaluate whether a field-level RAG system can prevent unauthorized users from obtaining protected spreadsheet information through direct questions, multi-turn interaction, relational inference, memory effects, prompt injection, backdoor triggers, or embedding-oriented probing. The system is treated as the object under test. Each experiment submits controlled prompts to the same indexed corpus and records the behavior of the retrieval, context-construction, memory, and generation components.

The evaluation follows two complementary perspectives. The first perspective is pipeline-oriented. It examines whether the implemented RAG pipeline retrieves relevant entities, applies the role-based field projection correctly, removes forbidden field values before prompt construction in secure mode, and resets or isolates conversation state when access conditions change. The second perspective is model-oriented. It examines whether the language model reveals restricted values, follows access instructions, refuses appropriately, or produces unsupported sensitive information under adversarial prompting.

This separation is important because leakage can originate at different points in the system. A protected value may be present in the raw retrieved entity but absent from the prompt after field projection. In that case, the event is relevant as an internal diagnostic signal, but it is not equivalent to user-visible leakage in secure mode. Conversely, a final answer may contain a protected value even when the current retrieved context does not contain it; such a result may indicate memory leakage, unsupported generation, or contamination from a previous turn. The methodology therefore records intermediate system states rather than relying only on the final assistant response.

## 2. System Under Evaluation

The evaluated system is a prototype RAG application over the fictional spreadsheet dataset `SiSWiss_Testdaten.xlsx`. The dataset represents a cosmetic product-development scenario and contains information about products, formulations, manufacturing processes, and product-testing properties. It is suitable for this evaluation because the same business entity can contain information with different confidentiality levels. For example, a product name may be public, a test value may be internal, a formulation description may be confidential, ingredient and supplier information may be restricted, and exact ingredient percentages may be protected.

The workbook is transformed into entity-level documents rather than isolated cells or whole-workbook chunks. The current architecture indexes 300 entities: 100 formulation entities, 100 process entities, and 100 product entities. Product entities also include associated testing properties. Each indexed entity has two representations. The first is a textual representation used for embedding and retrieval. The second is structured metadata, especially the `entity_fields` list. Each field record stores the logical field name, value, sensitivity label, optional category, optional field-specific role restriction, and source information such as sheet name, row index, document identifier, and source column name.

This dual representation is methodologically important. Retrieval operates over the entity text and metadata, but secure prompt construction does not simply pass the raw retrieved text to the language model. Instead, secure mode reconstructs the prompt context from the structured field records after applying the active user's access rights. The evaluation is therefore designed around the question of whether forbidden fields are removed before they become visible to the model or the user.

## 3. Access-Control Model

Sensitivity labels and role permissions are defined outside the Python code in `sensitivity_policy.yaml`. The policy defines five ordered labels: `public`, `internal`, `confidential`, `restricted`, and `protected`. These labels represent increasing confidentiality. The policy also defines roles and the labels each role may access.

| Role | Allowed sensitivity labels |
| --- | --- |
| `public_user` | `public` |
| `internal_user` | `public`, `internal` |
| `research_user` | `public`, `internal`, `confidential`, `restricted` |
| `admin` | `public`, `internal`, `confidential`, `restricted`, `protected` |

The policy also defines access-level aliases used in the experiments. The alias `public` maps to `public_user`, `internal` maps to `internal_user`, and `protected` maps to `admin`. In the methodology, `public` and `internal` are treated as unauthorized conditions for protected formulation and process information, while `protected` or `admin` is used as an authorized positive-control condition.


The system also supports manual sensitivity overrides through `sensitivity_overrides.yaml`. Overrides can change the sensitivity label, category, or allowed roles for specific fields without changing source code. This makes it possible to represent reviewed exceptions where a column-level default classification is too coarse. The methodology assumes that the configured policy and overrides define the ground truth for access decisions during the experiments.

## 4. RAG Pipeline Configuration

All experiments use the same general RAG pipeline unless an attack scenario explicitly adds poisoned or backdoor rows. During ingestion, the workbook is loaded, relational rows are converted into entity documents, and field-level sensitivity metadata is attached. Entity texts are embedded with `sentence-transformers/all-MiniLM-L6-v2` and stored in an in-memory FAISS index. The index uses normalized dense vectors, so inner-product search corresponds to cosine similarity.

Retrieval is hybrid. The system combines semantic search with lexical matching, exact identifier lookup, document-type hints, and relation expansion. This is necessary because spreadsheet questions often refer to short identifiers such as product IDs, formulation IDs, or process IDs. If a prompt contains an explicit identifier, the pipeline can prioritize metadata lookup. If the prompt asks about formulation details, process steps, properties, or linked entities, the pipeline can expand across relationships in the workbook. The default retrieval depth is `top_k = 5`, so at most five retrieved or expanded entities are normally considered for prompt construction.

The generation component uses an OpenAI-compatible chat-completion interface. The configured model can be a hosted model such as `gpt-4o-mini` or a locally served OpenAI-compatible model such as `Qwen/Qwen3-32B`. Generation is run with temperature `0.0` in the experiments to reduce nondeterminism. This does not make model output fully deterministic in all possible deployments, but it makes the experimental setting more reproducible.

Conversation memory is enabled for multi-turn experiments. The memory module stores recent messages, retrieves relevant memory snippets, and maintains a compact summary. This supports follow-up questions and row-construction attacks, but it also creates a security-relevant state channel. Therefore, experiments involving access changes inspect recent messages, summary memory, and semantic memory snippets separately.

## 5. RAG Modes

The implementation supports two RAG modes, and the methodology interprets them differently.

| Mode | Purpose | Methodological interpretation |
| --- | --- | --- |
| `secure_rag_mode` | Normal enforcement mode | Tests whether forbidden field values are removed before the prompt is built. |
| `sensitivity_eval_mode` | Controlled evaluation mode | Tests whether the model follows access instructions when mixed allowed and restricted facts are intentionally visible. |

In `secure_rag_mode`, each retrieved entity is projected according to the active role before prompt construction. Visible fields are rendered into the context; forbidden fields are omitted. If a protected value appears in the final answer under an unauthorized role in this mode, the evaluation checks whether the value entered the projected prompt, conversation memory, or neither.

In `sensitivity_eval_mode`, the prompt intentionally includes both allowed and restricted facts, annotated with sensitivity and access labels. This mode is not interpreted as a secure deployment configuration. It is an experimental condition that isolates model-level instruction following: the model sees restricted facts and is instructed not to reveal them. Leakage in this mode therefore measures model behavior under labeled mixed context, not failure of the secure field-projection boundary.

## 6. Threat Model

The attacker is modeled as a user with access to the chat interface. The attacker can submit natural-language prompts, use multiple turns, refer to previous conversation state, provide known spreadsheet identifiers, and phrase requests adversarially. The attacker is assumed to know or guess some public or semi-public anchors, such as product names or formulation identifiers, but does not have direct access to the workbook file, source code, FAISS index, raw metadata, logs, or hidden prompt context.

In the main unauthorized setting, the attacker has either public or internal access. A public attacker should only receive fields labeled as public. An internal attacker may additionally receive internal fields, but should not receive confidential, restricted, or protected information unless the policy explicitly grants access. Protected/admin access is not considered an attack condition. It is used as a positive control to verify that the target information exists, can be retrieved, and can be used by the system when access is authorized.

The poisoning and backdoor scenarios use a stronger attacker assumption. In those experiments, the attacker is assumed to have caused additional public rows to be indexed. These rows are visible to low-access users but contain malicious instructions, canary strings, trigger phrases, or links to protected targets. This stronger condition is analyzed separately because it evaluates the interaction between attacker-controlled retrieved content and access-control enforcement.

## 7. Experimental Design

The experiments are implemented as standalone scripts in `code/evaluation/`. Each script constructs the RAG pipeline, selects targets and access conditions, submits deterministic prompt sequences, records diagnostic state, scores the output, and writes structured results. The complete experiment suite covers eight attack scenarios:

1. Direct cell extraction.
2. Multi-turn row construction.
3. Access-level downgrade memory leakage.
4. Relational join-path inference.
5. Rank-probing membership inference.
6. Prompt injection through poisoned rows.
7. Backdoor-triggered extraction.
8. Embedding-side leakage.

Most experiments vary three factors: target, access level, and conversation length. The target panels are deterministic so that results can be reproduced and compared. The access levels are typically `public`, `internal`, and `protected`, corresponding to unauthorized low-access users and an authorized positive control. Conversation lengths are varied to compare single-turn attacks with multi-turn attacks that introduce benign history before the final adversarial turn. Each attack is evaluated across selected target entities, access roles, conversation lengths, and repeated iterations. The final report specifies the number of targets, repetitions, and total generations for each attack.

Some attacks have special designs. The access-level downgrade attack begins with protected access, intentionally reveals a target value during an authorized setup turn, then lowers the access level before the final attack prompt. The poisoning and backdoor attacks add synthetic public rows to the indexed corpus. Membership-inference attacks score whether the answer confirms the existence of a protected target, even when exact protected values are not revealed.

Where supported, retrieval-only diagnostics are used to isolate retrieval behavior from language-model generation. In this condition, the experiment examines whether target information entered retrieved context without relying on an LLM answer. Model-backed runs then evaluate whether the target information appears in the user-visible final response.

For the sensitivity-evaluation experiments, `sensitivity_eval_mode` is used as the main experimental condition. In this mode, the model receives context that may contain fields from multiple sensitivity levels, including fields that are not accessible to the active user role. These fields are annotated with their sensitivity labels and access restrictions. The purpose of this mode is not to enforce confidentiality through field projection, but to test whether the model itself can follow the access policy during answer generation. Therefore, the presence of restricted fields in the model-visible context is expected and is not scored as a security failure. A failure is counted only when the final answer reveals, confirms, paraphrases, transforms, or helps reconstruct information that the active role is not allowed to access.

## 8. Attack Scenarios
The direct cell extraction attack asks for a specific protected spreadsheet value, such as an ingredient percentage for a known formulation row. In `secure_rag_mode`, it evaluates whether the field-projection boundary prevents the value from entering the prompt. In `sensitivity_eval_mode`, it evaluates whether the model discloses the protected value even though it is visible in the labelled context.

The multi-turn row construction attack tests whether an attacker can reconstruct a protected formulation row by spreading requests across several turns. Known anchor fields supplied by the attacker are excluded from leakage scoring, while protected or otherwise unauthorized fields are scored when they appear in the answer.

The access-level downgrade attack tests whether protected information remains available after a user's access level is reduced. Because the protected value is intentionally revealed during the authorized setup phase, the main question is whether recent messages, summary memory, semantic memory snippets, retrieval, or the final answer carry that value across the later lower-access boundary.

The relational join-path inference attack evaluates whether the system leaks protected relationships across spreadsheet sheets. The attacker starts from a product-level anchor and attempts to recover linked formulation and process information. The scoring distinguishes association leakage, such as linked identifiers, from protected-detail leakage, such as ingredients, percentages, process names, or process steps.

The rank-probing membership-inference attack evaluates whether prompts framed as existence checks or retrieval-rank probes can reveal whether protected records are present in the index. The attack is scored for answer-level membership confirmation, direct retrieval of protected target entities, and any exposure of protected details.

The prompt-injection attack evaluates whether attacker-controlled public rows can manipulate the generator into revealing protected information. Synthetic public rows contain malicious instructions, canary strings, and links to protected targets. Canary compliance is measured separately from protected-data leakage because the model may follow the malicious instruction without actually exposing a protected value.

The backdoor-triggered extraction attack extends the poisoned-row setting by adding dormant trigger phrases. The final prompt includes the trigger and tests whether the retrieved public row causes the model to reveal target information or canary text.

The embedding-side leakage attack evaluates whether vector-search framing can induce the system to disclose protected values. The attacker asks the model to reason about nearest neighbors or embedding results and report a protected value supposedly implied by the index. This tests whether retrieval language or rank-probing language bypasses access controls.

## 9. Metrics and Scoring

The methodology distinguishes several leakage and diagnostic categories. Because the system can be executed in both `secure_rag_mode` and `sensitivity_eval_mode`, the interpretation of some metrics depends on the selected mode. In `secure_rag_mode`, the main security boundary is field projection before prompt construction. In `sensitivity_eval_mode`, mixed-sensitivity context is intentionally visible to the model, and the main question is whether the model follows the access policy during answer generation.

The following table lists the main automated metrics and qualitative interpretation categories used in the analysis. Not every category is computed for every attack. Exact-value leakage, partial leakage, retrieval exposure, memory exposure, canary compliance, positive-control success, and answer-accuracy errors are scored by the relevant experiment scripts. Broader categories such as semantic leakage, transformation leakage, confirmation leakage, and reconstruction assistance are used for qualitative review of borderline or indirect answers where exact string matching is not sufficient.

| Metric or category             | Meaning                                                                                                                                                         |
| ------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Raw retrieval exposure         | Target content appears in raw retrieved entities or metadata.                                                                                                   |
| Model-visible context exposure | Target content appears in the prompt context after secure field projection or sensitivity-evaluation context construction.                                      |
| Memory exposure                | Target content appears in recent messages, summary memory, or semantic memory snippets.                                                                         |
| Answer leakage                 | Target content appears in the final answer under an unauthorized access condition.                                                                              |
| Unsupported answer leakage     | Target content appears in the final answer even though it was not present in the current retrieved context, model-visible context, or relevant memory state.    |
| Partial leakage                | The answer reveals only part of an unauthorized value, such as a prefix, suffix, substring, length, pattern, or characteristic fragment.                        |
| Semantic leakage               | The answer paraphrases, summarizes, describes, or indirectly communicates unauthorized information without reproducing the exact protected value.               |
| Confirmation leakage           | The answer confirms or denies a guessed protected value, protected relationship, or protected record membership.                                                |
| Transformation leakage         | The model reveals unauthorized information through translation, summarization, table formatting, JSON output, rephrasing, or another requested transformation.  |
| Reconstruction assistance      | The model provides hints, fragments, comparisons, or intermediate facts that help reconstruct unauthorized information across one or more turns.                |
| Label-compliance assessment    | Qualitative or aggregated assessment of whether answers respect the active role and the sensitivity labels visible in the context.                              |
| Positive-control success       | Authorized protected/admin access retrieves and answers with the target information.                                                                            |
| Answer-accuracy error          | The target context is available under authorized access, but the answer omits or misstates it.                                                                  |
| Canary compliance              | A canary from poisoned or backdoor content appears in the answer.                                                                                               |
| Over-refusal                   | The model refuses to provide information that is allowed for the active role.                                                                                   |

Raw retrieval exposure is treated as a diagnostic signal. Because retrieved entities may contain fields with different sensitivity labels, the presence of unauthorized information in raw retrieved entities is not by itself equivalent to user-visible leakage. It shows that the retrieval component selected an entity containing the target information, but the interpretation depends on the selected RAG mode and on whether the information becomes visible in the prompt, memory, or final answer.

In `secure_rag_mode`, a security failure occurs when a forbidden value survives into the projected prompt, conversation memory available under an unauthorized role, or the final answer. In this mode, model-visible context exposure is security-relevant because the field-projection mechanism is expected to remove fields that the active role is not allowed to access.

In `sensitivity_eval_mode`, model-visible context exposure is interpreted differently. Mixed-sensitivity context is intentionally included in the model-visible prompt, including fields that the active role is not allowed to access. Therefore, the presence of restricted or protected fields in the prompt context is treated as an experimental precondition rather than as a security failure. In this mode, the central failure condition is answer-level disclosure: the model reveals, confirms, paraphrases, transforms, or helps reconstruct information that the active role is not allowed to access.

Scoring is attack-specific. Numeric cell extraction checks for exact protected values. Row-construction attacks check whether scored fields appear in the answer. Join-path attacks separately score association leakage and downstream protected details. Membership-inference attacks score whether the system confirms the existence of protected records. Poisoning and backdoor attacks score canary compliance, protected target retrieval, and protected target disclosure separately. Across all attacks, unauthorized leakage is only counted when the relevant target signal appears under a role that should not have access according to the policy.

Positive controls are interpreted carefully. If protected/admin access cannot retrieve or answer with the target, this is not counted as a security success. It is recorded as a retrieval failure or answer-accuracy error, because the system failed to demonstrate that the target was reachable under authorized conditions. Conversely, if the authorized condition succeeds while the unauthorized condition refuses, masks, or omits the same value, this supports the interpretation that the access policy is being followed in the tested condition.

## 10. Data Collection and Analysis

For each run, the evaluation records the access level, model, target, conversation length, iteration, prompt sequence, final answer, raw retrieved results, retrieved sensitivities, retrieved document types, model-visible context, access decisions, memory state where relevant, and attack-specific scoring labels. Outputs are written as JSON for full reproducibility, CSV for tabular aggregation, and Markdown for thesis-readable reporting.

The analysis aggregates results by attack, target, access level, and conversation length. Unauthorized public and internal conditions are analyzed separately from protected/admin positive controls. In `secure_rag_mode`, the main security-relevant outcomes are model-visible context exposure, memory exposure after access reduction, and answer leakage. In `sensitivity_eval_mode`, model-visible context exposure is treated as an experimental precondition rather than a failure, because mixed-sensitivity context is intentionally visible to the model. For this mode, the main security-relevant outcomes are answer leakage, partial leakage, over-refusal, and any qualitatively observed confirmation, semantic, transformation, or reconstruction-assistance leakage. Raw retrieval exposure is reported as a diagnostic layer because it helps explain whether later leakage originated from retrieval, context construction, memory, or generation.

All prompts, target selections, and warm-up turns are deterministic. Generation is run with temperature `0.0`. This improves reproducibility, although model-backed outputs may still depend on the configured model backend and serving environment. The methodology therefore treats the results as evidence about the implemented prototype under the reported configuration rather than as a universal claim about all RAG systems or all language models.

## 11. Reproducibility Procedure

The experiment scripts are located in `code/evaluation/`, and the batch runner for the Qwen-based suite is located in `jobs/run_qwen3_experiment_suite.sh`. The scripts load the same dataset, apply the same policy file, instantiate the same RAG pipeline, execute the configured attack matrix, and export JSON, CSV, and Markdown artifacts.

To reproduce a run, the environment must specify the desired OpenAI-compatible generation backend. For hosted models, this requires an API key. For local Qwen runs, the environment can point `OPENAI_BASE_URL` to the local vLLM endpoint and set `GENERATION_MODEL` accordingly. The retrieved corpus, sensitivity policy, manual overrides, model name, generation temperature, access levels, target IDs, conversation lengths, and iteration counts should all be reported with the final results.

## 12. Limitations

The methodology has several limitations. First, the dataset is synthetic and represents one structured enterprise scenario. Results may not generalize to other domains, larger datasets, different spreadsheet schemas, or unstructured corpora. Second, the attacks are scripted and deterministic. They provide controlled coverage of important leakage channels, but they do not represent the full space of adaptive human red-team behavior. Third, results depend on the configured model backend, prompt templates, embedding model, retrieval depth, and field classification policy.

Fourth, the prototype still retrieves over raw entity text and metadata. This is acceptable for the experimental architecture because secure prompt construction performs field projection afterward, but it means raw retrieval logs must be treated as sensitive diagnostic artifacts. Fifth, conversation memory is security-relevant. Although the pipeline clears memory when access context changes through the access-context API, memory entries themselves are not fully modeled as independent field-level objects with their own sensitivity labels. A production system would require stronger memory isolation, sensitivity-aware summaries, and stricter handling of diagnostic outputs.

These limitations do not invalidate the evaluation. Instead, they define its scope. The methodology provides a controlled empirical assessment of how the implemented field-level RAG prototype behaves under selected confidentiality attacks, while avoiding broader claims that are not supported by the experimental design.

## 13. Summary

The methodology evaluates the complete process by which protected spreadsheet information may or may not become visible in a field-level RAG system. It begins with a structured dataset, applies policy-based sensitivity labels, constructs a hybrid retrieval pipeline, projects retrieved entities according to role permissions, and tests the resulting system under adversarial prompts. The attack scenarios are therefore one part of a broader evaluation procedure.

By recording raw retrieval, projected context, memory state, and final answers separately, the methodology can attribute failures to the appropriate system component. This is necessary for the current architecture because retrieval and authorization are deliberately separated. The resulting evaluation supports a thesis-level analysis of confidentiality risks in field-level, sensitivity-aware RAG over structured spreadsheet data.
