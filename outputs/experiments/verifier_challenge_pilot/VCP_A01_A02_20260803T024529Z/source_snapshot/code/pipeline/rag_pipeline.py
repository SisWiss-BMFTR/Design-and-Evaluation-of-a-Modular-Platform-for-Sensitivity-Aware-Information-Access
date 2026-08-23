import logging
import re
from typing import Dict, List, Optional, Sequence

from config.settings import (
    ACCESS_CHANGE_MEMORY_CLEAR_ENABLED,
    EMBEDDING_PROBE_GUARD_ENABLED,
    MEMBERSHIP_GUARD_ENABLED,
    OUTPUT_LEAKAGE_VERIFIER_ENABLED,
    PROMPT_INJECTION_GUARD_ENABLED,
    RELATION_ACCESS_GUARD_ENABLED,
)

from generation.base import BaseGenerator
from ingestion.embedder import Embedder
from memory.conversation_memory import ConversationMemory
from retrieval.base import BaseRetriever
from security.field_access import (
    SECURE_RAG_MODE,
    SENSITIVITY_EVAL_MODE,
    allowed_labels_for_role,
    build_secure_context_chunks,
    build_sensitivity_eval_context_chunks,
    collect_fields_by_visibility,
    default_user_role,
    infer_role_from_allowed_sensitivities,
    load_sensitivity_policy,
    normalize_sensitivity,
    normalize_user_role,
    sensitivity_rank,
)
from security.membership_inference_guard import (
    MEMBERSHIP_REFUSAL,
    answer_is_membership_refusal,
    build_authorized_membership_answer,
    build_pre_retrieval_refusal_result,
    detect_membership_probe,
    empty_membership_guard_result,
    enrich_probe_from_metadata,
    is_unauthorized_membership_probe,
    validate_membership_answer,
)
from security.output_leakage_verifier import verify_answer_against_restricted_fields
from security.relation_access import (
    collect_relation_fields_by_visibility,
    id_key_allowed_for_role,
    matching_relation_edge,
    relation_visibility_for_role,
)
from security.prompt_injection_guard import (
    answer_contains_injection_artifact,
    build_injection_resistant_context_chunks,
    empty_prompt_injection_guard_result,
    redact_answer_injection_artifacts,
)


logger = logging.getLogger("rag.retrieval")


EMBEDDING_EVIDENCE_TERMS = [
    "nearest indexed chunk",
    "nearest chunk",
    "indexed chunk",
    "retrieved chunk",
    "retrieval result",
    "retrieved result",
    "embedding probe",
    "embedding-side",
    "vector-search probe",
    "vector search probe",
    "vector-search",
    "vector search",
    "nearest neighbor",
    "nearest-neighbor",
    "similarity score",
    "similarity rank",
    "ranked result",
]

PROTECTED_DETAIL_TERMS = [
    "menge",
    "percentage",
    "percent",
    "supplier",
    "ingredient",
    "inci",
    "formulation",
    "rezeptur",
    "protected",
    "restricted",
    "hidden",
    "secret",
    "record",
    "row",
    "chunk",
    "entity",
]

EMBEDDING_PROBE_POLICY_CHUNK = (
    "[RETRIEVAL EVIDENCE POLICY]\n"
    "For this role, do not reveal nearest-neighbor evidence about protected records. "
    "Do not disclose or confirm retrieved chunk IDs, ranks, similarity scores, protected "
    "formulation IDs, protected record membership, protected ingredient presence, or "
    "protected field values. General technical explanations of retrieval are allowed, "
    "but requests for retrieval evidence about protected records must be answered without "
    "confirming whether the protected record or value exists."
)


class RAGPipeline:
    def __init__(
        self,
        embedder: Embedder,
        retriever: BaseRetriever,
        generator: BaseGenerator,
        top_k: int,
        memory: Optional[ConversationMemory] = None,
        allowed_sensitivities: Optional[Sequence[str]] = None,
        user_role: Optional[str] = None,
        rag_mode: str = SENSITIVITY_EVAL_MODE,
        post_generation_verifier_enabled: Optional[bool] = None,
        output_leakage_verifier_enabled: Optional[bool] = None,
        membership_guard_enabled: Optional[bool] = None,
        embedding_probe_guard_enabled: Optional[bool] = None,
        prompt_injection_guard_enabled: Optional[bool] = None,
        access_change_memory_clear_enabled: Optional[bool] = None,
        relation_access_guard_enabled: Optional[bool] = None,
    ):
        self.embedder = embedder
        self.retriever = retriever
        self.generator = generator
        self.top_k = top_k
        self.memory = memory
        self.sensitivity_policy = load_sensitivity_policy()
        self._user_role: Optional[str] = None
        self._allowed_sensitivities: List[str] = []
        self.rag_mode = rag_mode
        output_switch = (
            output_leakage_verifier_enabled
            if output_leakage_verifier_enabled is not None
            else post_generation_verifier_enabled
        )
        self.output_leakage_verifier_enabled = (
            OUTPUT_LEAKAGE_VERIFIER_ENABLED if output_switch is None else bool(output_switch)
        )
        # Compatibility attribute for existing runners and result schemas.
        self.post_generation_verifier_enabled = self.output_leakage_verifier_enabled
        self.membership_guard_enabled = (
            MEMBERSHIP_GUARD_ENABLED if membership_guard_enabled is None else bool(membership_guard_enabled)
        )
        self.embedding_probe_guard_enabled = (
            EMBEDDING_PROBE_GUARD_ENABLED
            if embedding_probe_guard_enabled is None
            else bool(embedding_probe_guard_enabled)
        )
        self.prompt_injection_guard_enabled = (
            PROMPT_INJECTION_GUARD_ENABLED
            if prompt_injection_guard_enabled is None
            else bool(prompt_injection_guard_enabled)
        )
        self.access_change_memory_clear_enabled = (
            ACCESS_CHANGE_MEMORY_CLEAR_ENABLED
            if access_change_memory_clear_enabled is None
            else bool(access_change_memory_clear_enabled)
        )
        self.relation_access_guard_enabled = (
            RELATION_ACCESS_GUARD_ENABLED
            if relation_access_guard_enabled is None
            else bool(relation_access_guard_enabled)
        )
        self.last_raw_answer = ""
        self.last_output_guard: Dict = self._empty_output_guard_result()
        self.last_prompt_injection_guard: Dict = empty_prompt_injection_guard_result(
            enabled=self.prompt_injection_guard_enabled
        )
        self.last_membership_guard: Dict = empty_membership_guard_result(
            enabled=self.membership_guard_enabled
        )
        self.last_embedding_probe_guard: Dict = self._empty_embedding_probe_guard_result()
        self.last_access_decisions: List[Dict] = []
        self.last_visible_context_chunks: List[str] = []
        # Retrieval-local diagnostics. Generator input must use last_visible_context_chunks.
        self.last_results: List[Dict] = []

        # Conversation focus history (clean user-entity tracking used for pronouns like "es/it"
        # and phrases such as "last/previous product").
        self.focus_history: List[Dict[str, List[str]]] = []

        self.set_access_context(
            user_role=user_role,
            allowed_sensitivities=allowed_sensitivities,
            clear_memory_on_role_change=False,
        )

    @property
    def user_role(self) -> Optional[str]:
        return self._user_role

    @user_role.setter
    def user_role(self, value: Optional[str]) -> None:
        self.set_access_context(user_role=value)

    @property
    def allowed_sensitivities(self) -> List[str]:
        return list(self._allowed_sensitivities)

    @allowed_sensitivities.setter
    def allowed_sensitivities(self, value: Optional[Sequence[str]]) -> None:
        self.set_access_context(allowed_sensitivities=value)

    def _active_retrieval_filters(self, force_secure: bool = False) -> Dict[str, List[str]]:
        if self.rag_mode == SENSITIVITY_EVAL_MODE and not force_secure:
            return {}
        # Secure retrieval can be narrowed by role before field projection.
        return {"__allowed_sensitivities__": list(self._allowed_sensitivities)}

    def _normalize_allowed_sensitivities(self, allowed_sensitivities: Optional[Sequence[str]]) -> List[str]:
        labels: List[str] = []
        seen = set()
        for level in allowed_sensitivities or []:
            label = normalize_sensitivity(level, self.sensitivity_policy)
            if label not in seen:
                labels.append(label)
                seen.add(label)
        return labels or allowed_labels_for_role(default_user_role(self.sensitivity_policy), self.sensitivity_policy)

    def _clear_memory_after_role_change(self) -> None:
        # Access changes are session boundaries: discard all state produced under
        # a different authorization context.
        if self.memory and hasattr(self.memory, "clear") and callable(self.memory.clear):
            self.memory.clear()
        elif self.memory:
            self.memory.turns = []
            self.memory.summary = ""
        self.last_results = []
        self.last_visible_context_chunks = []
        self.last_access_decisions = []
        self.focus_history = []
        self.last_raw_answer = ""
        self.last_output_guard = self._empty_output_guard_result()
        self.last_prompt_injection_guard = empty_prompt_injection_guard_result(
            enabled=self.prompt_injection_guard_enabled
        )
        self.last_membership_guard = empty_membership_guard_result(
            enabled=self.membership_guard_enabled
        )
        self.last_embedding_probe_guard = self._empty_embedding_probe_guard_result()

    def set_post_generation_verifier(self, enabled: bool) -> None:
        self.set_output_leakage_verifier(enabled)

    def set_output_leakage_verifier(self, enabled: bool) -> None:
        self.output_leakage_verifier_enabled = bool(enabled)
        self.post_generation_verifier_enabled = self.output_leakage_verifier_enabled
        self.last_output_guard = self._empty_output_guard_result()

    def set_membership_guard(self, enabled: bool) -> None:
        self.membership_guard_enabled = bool(enabled)
        self.last_membership_guard = empty_membership_guard_result(
            enabled=self.membership_guard_enabled
        )

    def set_embedding_probe_guard(self, enabled: bool) -> None:
        self.embedding_probe_guard_enabled = bool(enabled)
        self.last_embedding_probe_guard = self._empty_embedding_probe_guard_result()

    def set_prompt_injection_guard(self, enabled: bool) -> None:
        self.prompt_injection_guard_enabled = bool(enabled)
        self.last_prompt_injection_guard = empty_prompt_injection_guard_result(
            enabled=self.prompt_injection_guard_enabled
        )

    def set_access_change_memory_clear(self, enabled: bool) -> None:
        self.access_change_memory_clear_enabled = bool(enabled)

    def set_relation_access_guard(self, enabled: bool) -> None:
        self.relation_access_guard_enabled = bool(enabled)


    def set_access_context(
        self,
        user_role: Optional[str] = None,
        allowed_sensitivities: Optional[Sequence[str]] = None,
        clear_memory_on_role_change: bool = True,
    ) -> None:
        previous_role = self._active_user_role() if (self._user_role or self._allowed_sensitivities) else None
        previous_allowed = list(self._allowed_sensitivities)

        if allowed_sensitivities is not None:
            new_allowed = self._normalize_allowed_sensitivities(allowed_sensitivities)
        elif user_role is not None:
            normalized_role = normalize_user_role(user_role, self.sensitivity_policy)
            new_allowed = allowed_labels_for_role(normalized_role, self.sensitivity_policy)
        elif self._allowed_sensitivities:
            new_allowed = list(self._allowed_sensitivities)
        else:
            new_allowed = allowed_labels_for_role(default_user_role(self.sensitivity_policy), self.sensitivity_policy)

        if user_role is not None:
            new_role = normalize_user_role(user_role, self.sensitivity_policy)
        elif allowed_sensitivities is not None:
            new_role = infer_role_from_allowed_sensitivities(new_allowed, self.sensitivity_policy)
        elif self._user_role:
            new_role = normalize_user_role(self._user_role, self.sensitivity_policy)
        else:
            new_role = infer_role_from_allowed_sensitivities(new_allowed, self.sensitivity_policy)

        self._user_role = new_role
        self._allowed_sensitivities = new_allowed

        access_changed = previous_role != new_role or previous_allowed != new_allowed
        if (
            self.access_change_memory_clear_enabled
            and clear_memory_on_role_change
            and previous_role
            and access_changed
        ):
            self._clear_memory_after_role_change()

    def _active_user_role(self) -> str:
        if self._user_role:
            return normalize_user_role(self._user_role, self.sensitivity_policy)
        return infer_role_from_allowed_sensitivities(self._allowed_sensitivities, self.sensitivity_policy)

    def _with_active_filters(self, filters: Dict[str, str], force_secure: bool = False) -> Dict:
        out = dict(filters)
        out.update(self._active_retrieval_filters(force_secure=force_secure))
        return out

    def _empty_embedding_probe_guard_result(self) -> Dict:
        return {
            "checked": False,
            "triggered": False,
            "strict_retrieval_access": False,
            "force_secure_projection": False,
            "side_channel_policy_added": False,
            "evidence_terms": [],
            "sensitive_signals": [],
            "action": "not_checked",
        }

    def _protected_access_authorized(self) -> bool:
        protected_label = normalize_sensitivity("protected", self.sensitivity_policy)
        return protected_label in set(self._allowed_sensitivities)

    def _detect_embedding_probe_guard(
        self,
        question: str,
        explicit_ids: Dict[str, List[str]],
        membership_probe: Dict,
    ) -> Dict:
        result = self._empty_embedding_probe_guard_result()
        if not self.embedding_probe_guard_enabled:
            result["action"] = "disabled"
            return result
        result["checked"] = True

        text = str(question or "").casefold()
        evidence_terms = [term for term in EMBEDDING_EVIDENCE_TERMS if term in text]
        sensitive_signals: List[str] = []

        if explicit_ids.get("rezeptur_id"):
            sensitive_signals.append("explicit_protected_formulation_id")
        if membership_probe.get("is_membership_probe"):
            sensitive_signals.append("membership_probe")
        if any(term in text for term in PROTECTED_DETAIL_TERMS):
            sensitive_signals.append("protected_detail_language")
        if ("formulation" in text or "rezeptur" in text) and any(
            term in text for term in ("value", "numeric", "field", "menge", "percentage", "supplier", "ingredient", "inci")
        ):
            sensitive_signals.append("formulation_field_request")

        unauthorized = not self._protected_access_authorized()
        triggered = bool(evidence_terms and sensitive_signals and unauthorized)
        result.update({
            "triggered": triggered,
            "strict_retrieval_access": triggered,
            "force_secure_projection": triggered,
            "side_channel_policy_added": triggered,
            "evidence_terms": evidence_terms,
            "sensitive_signals": sorted(set(sensitive_signals)),
            "action": "strict_role_filtered_retrieval" if triggered else "allow_normal_retrieval",
        })
        return result

    def _sensitivity_allowed_for_active_role(self, sensitivity: str) -> bool:
        if not sensitivity:
            return True
        allowed = [normalize_sensitivity(label, self.sensitivity_policy) for label in self._allowed_sensitivities]
        if not allowed:
            return False
        normalized = normalize_sensitivity(sensitivity, self.sensitivity_policy)
        max_allowed_rank = max(sensitivity_rank(label, self.sensitivity_policy) for label in allowed)
        return sensitivity_rank(normalized, self.sensitivity_policy) <= max_allowed_rank

    def _result_allowed_for_active_retrieval(self, item: Dict) -> bool:
        meta = item.get("metadata", {}) if isinstance(item, dict) else {}
        retrieval_sensitivity = meta.get("retrieval_sensitivity")
        if retrieval_sensitivity:
            return self._sensitivity_allowed_for_active_role(str(retrieval_sensitivity))

        doc_sensitivity = str(meta.get("sensitivity") or "").strip()
        if doc_sensitivity and doc_sensitivity.casefold() != "mixed":
            return self._sensitivity_allowed_for_active_role(doc_sensitivity)

        # Mixed chunks without an explicit retrieval sensitivity are kept so field-level
        # projection can remove only the restricted fields.
        return True

    def _filter_results_for_active_access(self, results: List[Dict]) -> List[Dict]:
        filtered = [item for item in results if self._result_allowed_for_active_retrieval(item)]
        removed = len(results) - len(filtered)
        if removed:
            logger.info(
                "embedding_probe_retrieval_filter_removed %s",
                {"removed_count": removed, "role": self._active_user_role()},
            )
        return filtered

    def _restricted_inventory_fields(self) -> List[Dict]:
        if self._protected_access_authorized():
            return []

        restricted: List[Dict] = []
        role = self._active_user_role()
        for meta in self._retriever_metadatas():
            item = {"metadata": meta, "text": ""}
            fields = collect_fields_by_visibility([item], user_role=role, policy=self.sensitivity_policy)
            restricted.extend(fields.get("restricted", []))
            if self.relation_access_guard_enabled:
                relation_fields = collect_relation_fields_by_visibility(
                    [item],
                    user_role=role,
                    policy=self.sensitivity_policy,
                )
                restricted.extend(relation_fields.get("restricted", []))

            membership_sensitivity = (
                meta.get("membership_sensitivity")
                or meta.get("existence_sensitivity")
                or meta.get("retrieval_sensitivity")
            )
            if membership_sensitivity and not self._sensitivity_allowed_for_active_role(str(membership_sensitivity)):
                for key, field_name in (
                    ("entity_id", "protected_entity_id"),
                    ("rezeptur_id", "protected_rezeptur_id"),
                    ("formulation_name", "protected_formulation_name"),
                ):
                    value = str(meta.get(key) or "").strip()
                    if value:
                        restricted.append({
                            "field_name": field_name,
                            "value": value,
                            "sensitivity": str(membership_sensitivity),
                            "entity_id": str(meta.get("entity_id") or ""),
                            "doc_type": str(meta.get("doc_type") or ""),
                        })

        return restricted

    def _format_context_chunks(
        self,
        results: List[Dict],
        force_secure_projection: bool = False,
        include_embedding_policy: bool = False,
    ) -> List[str]:
        user_role = self._active_user_role()
        if self.prompt_injection_guard_enabled:
            guard_mode = SECURE_RAG_MODE if force_secure_projection else self.rag_mode
            chunks, decisions, guard_result = build_injection_resistant_context_chunks(
                results=results,
                user_role=user_role,
                rag_mode=guard_mode,
                policy=self.sensitivity_policy,
                relation_access_guard_enabled=self.relation_access_guard_enabled,
            )
            if include_embedding_policy:
                chunks = [EMBEDDING_PROBE_POLICY_CHUNK, *chunks]
            self.last_access_decisions = decisions
            self.last_visible_context_chunks = chunks
            self.last_prompt_injection_guard = guard_result
            return chunks

        if self.rag_mode == SENSITIVITY_EVAL_MODE and not force_secure_projection:
            chunks = build_sensitivity_eval_context_chunks(
                results,
                user_role=user_role,
                policy=self.sensitivity_policy,
                relation_access_guard_enabled=self.relation_access_guard_enabled,
            )
            self.last_access_decisions = []
        else:
            chunks, decisions = build_secure_context_chunks(
                results,
                user_role=user_role,
                policy=self.sensitivity_policy,
                relation_access_guard_enabled=self.relation_access_guard_enabled,
            )
            self.last_access_decisions = decisions

        if include_embedding_policy:
            chunks = [EMBEDDING_PROBE_POLICY_CHUNK, *chunks]
        self.last_visible_context_chunks = chunks
        return chunks

    @staticmethod
    def _empty_id_map() -> Dict[str, List[str]]:
        return {
            "rezeptur_id": [],
            "rezept_id": [],
            "verfahren_id": [],
        }

    @staticmethod
    def _has_any_ids(id_map: Dict[str, List[str]]) -> bool:
        return any(bool(id_map.get(k)) for k in ("rezeptur_id", "rezept_id", "verfahren_id"))

    @staticmethod
    def _contains_any(text: str, words: List[str]) -> bool:
        lowered = text.lower()
        return any(word in lowered for word in words)

    @staticmethod
    def _normalize_id(prefix: str, raw: str) -> str:
        number = raw.strip()
        if number.isdigit():
            number = number.zfill(3)
        return f"{prefix}-{number}"

    def _extract_ids(self, question: str) -> Dict[str, List[str]]:
        ids = self._empty_id_map()

        patterns = {
            "rezeptur_id": ("R", r"\bR-?(\d+)\b"),
            "rezept_id": ("P", r"\bP-?(\d+)\b"),
            "verfahren_id": ("V", r"\bV-?(\d+)\b"),
        }

        for key, (prefix, pattern) in patterns.items():
            matches = re.findall(pattern, question, flags=re.IGNORECASE)
            seen = set()
            for m in matches:
                norm = self._normalize_id(prefix, m)
                if norm not in seen:
                    ids[key].append(norm)
                    seen.add(norm)

        return ids

    def _infer_doc_type_hints(self, question: str) -> List[str]:
        hints = []

        if self._contains_any(question, ["process", "verfahren", "steps", "schritt"]):
            hints.extend(["process", "product"])
        if self._contains_any(question, ["ingredient", "ingredients", "claim", "claims", "rezeptur", "formulation", "phase", "inci"]):
            hints.extend(["formulation", "product"])
        if self._contains_any(question, ["parameter", "properties", "eigenschaften", "geprüft", "gepruft", "tester", "prüfer", "pruefer"]):
            hints.extend(["product"])
        if self._contains_any(question, ["rezept-id", "product", "produkt", "target market", "zielmarkt", "market"]):
            hints.extend(["product"])

        deduped = []
        seen = set()
        for hint in hints:
            if hint not in seen:
                deduped.append(hint)
                seen.add(hint)
        return deduped

    @staticmethod
    def _dedupe_results(results: List[Dict]) -> List[Dict]:
        seen = set()
        deduped = []
        for item in results:
            key = (item.get("text", ""), repr(sorted(item.get("metadata", {}).items())))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    def _metadata_id_allowed_for_focus(self, item: Dict, key: str) -> bool:
        if not self.relation_access_guard_enabled:
            return True
        if key == "rezept_id":
            return True
        edge = matching_relation_edge(
            item,
            self.sensitivity_policy,
            metadata_key=key,
        )
        if edge:
            allowed, _ = relation_visibility_for_role(
                edge,
                self._active_user_role(),
                self.sensitivity_policy,
                action="disclose",
            )
            return allowed
        return id_key_allowed_for_role(key, self._active_user_role(), self.sensitivity_policy)

    def _get_from_last_results(self, key: str) -> List[str]:
        values = []
        seen = set()
        for item in self.last_results:
            if not self._metadata_id_allowed_for_focus(item, key):
                continue
            value = item.get("metadata", {}).get(key)
            if value and value not in seen:
                values.append(str(value))
                seen.add(value)
        return values

    def _sanitize_id_map_for_focus(self, id_map: Dict[str, List[str]]) -> Dict[str, List[str]]:
        if not self.relation_access_guard_enabled:
            return {
                key: self._merge_unique([], id_map.get(key, []))
                for key in self._empty_id_map()
            }
        sanitized = self._empty_id_map()
        sanitized["rezept_id"] = self._merge_unique([], id_map.get("rezept_id", []))
        for key in ("rezeptur_id", "verfahren_id"):
            if id_key_allowed_for_role(key, self._active_user_role(), self.sensitivity_policy):
                sanitized[key] = self._merge_unique([], id_map.get(key, []))
        return sanitized

    @staticmethod
    def _merge_unique(values_a: List[str], values_b: List[str]) -> List[str]:
        out: List[str] = []
        seen = set()
        for value in values_a + values_b:
            if value and value not in seen:
                out.append(value)
                seen.add(value)
        return out

    def _merge_id_maps(self, left: Dict[str, List[str]], right: Dict[str, List[str]]) -> Dict[str, List[str]]:
        return {
            "rezeptur_id": self._merge_unique(left.get("rezeptur_id", []), right.get("rezeptur_id", [])),
            "rezept_id": self._merge_unique(left.get("rezept_id", []), right.get("rezept_id", [])),
            "verfahren_id": self._merge_unique(left.get("verfahren_id", []), right.get("verfahren_id", [])),
        }

    def _ids_from_focus_history(self, offset: int = 1) -> Dict[str, List[str]]:
        if offset <= 0 or len(self.focus_history) < offset:
            return self._empty_id_map()

        source = self.focus_history[-offset]
        return {
            "rezeptur_id": list(source.get("rezeptur_id", [])),
            "rezept_id": list(source.get("rezept_id", [])),
            "verfahren_id": list(source.get("verfahren_id", [])),
        }

    def _ids_from_recent_memory(self) -> Dict[str, List[str]]:
        if not self.memory or not getattr(self.memory, "turns", None):
            return self._empty_id_map()

        try:
            recent_messages = self.memory.recent_messages(allowed_sensitivities=self._allowed_sensitivities)
        except TypeError:
            recent_messages = self.memory.recent_messages()

        # Only parse user turns to avoid assistant-generated IDs polluting scope.
        merged_text = "\n".join(
            message.get("content", "")
            for message in recent_messages
            if message.get("role") == "user"
        )
        return self._extract_ids(merged_text)

    def _should_reuse_topic_context(self, question: str, id_map: Dict[str, List[str]]) -> bool:
        if self._has_any_ids(id_map):
            return False

        followup_signals = [
            "target market",
            "market",
            "zielmarkt",
            "inci",
            "ingredients",
            "claims",
            "properties",
            "parameter",
            "process",
            "verfahren",
            "steps",
            "compare",
            "vergleich",
            "vergleiche",
            "difference",
            "what about",
            "tell me about",
            "warum",
            "wieso",
            "wozu",
            "welche",
            "welcher",
            "welches",
        ]
        return self._contains_any(question, followup_signals)

    def _asks_previous_entity(self, question: str) -> bool:
        signals = [
            "last product",
            "previous product",
            "last one",
            "previous one",
            "letzte produkt",
            "letztes produkt",
            "vorherige produkt",
            "voriges produkt",
            "letzte",
            "vorherige",
        ]
        return self._contains_any(question, signals)

    def _asks_formulation_details(self, question: str) -> bool:
        return self._contains_any(
            question,
            [
                "rezeptur",
                "formulation",
                "composition",
                "ingredient",
                "ingredients",
                "percentage",
                "percentages",
                "supplier",
                "suppliers",
                "inci",
                "claim",
                "phase",
            ],
        )

    def _is_explicit_product_formulation_query(self, question: str, explicit_ids: Dict[str, List[str]]) -> bool:
        return bool(explicit_ids.get("rezept_id")) and self._asks_formulation_details(question)

    def _fetch_by_id(self, key: str, values: List[str], doc_type: str, force_secure: bool = False) -> List[Dict]:
        retrieve_by_metadata = getattr(self.retriever, "retrieve_by_metadata", None)
        if not callable(retrieve_by_metadata):
            return []

        out = []
        for value in values:
            out.extend(
                retrieve_by_metadata(
                    filters=self._with_active_filters({key: value}, force_secure=force_secure),
                    top_k=3,
                    prefer_doc_types=[doc_type],
                )
            )
        return out

    def _focus_product_formulation_results(
        self,
        results: List[Dict],
        explicit_ids: Dict[str, List[str]],
        include_processes: bool = False,
    ) -> List[Dict]:
        requested_products = set(explicit_ids.get("rezept_id") or [])
        requested_formulations = set(explicit_ids.get("rezeptur_id") or [])
        requested_processes = set(explicit_ids.get("verfahren_id") or [])

        for item in results:
            meta = item.get("metadata", {})
            if meta.get("doc_type") == "product" and str(meta.get("rezept_id")) in requested_products:
                linked_formulation = meta.get("rezeptur_id")
                linked_process = meta.get("verfahren_id")
                if linked_formulation:
                    requested_formulations.add(str(linked_formulation))
                if linked_process:
                    requested_processes.add(str(linked_process))

        focused: List[Dict] = []
        for item in results:
            meta = item.get("metadata", {})
            doc_type = str(meta.get("doc_type") or "")
            if doc_type == "product" and str(meta.get("rezept_id")) in requested_products:
                focused.append(item)
            elif doc_type == "formulation" and str(meta.get("rezeptur_id")) in requested_formulations:
                focused.append(item)
            elif (
                include_processes
                and doc_type == "process"
                and str(meta.get("verfahren_id")) in requested_processes
            ):
                focused.append(item)

        return focused or results

    def _can_traverse_relation(
        self,
        item: Dict,
        metadata_key: str,
        target_type: str,
        value: str,
        force_secure: bool = False,
    ) -> bool:
        if not self.relation_access_guard_enabled:
            return True
        if self.rag_mode == SENSITIVITY_EVAL_MODE and not force_secure:
            return True
        edge = matching_relation_edge(
            item,
            self.sensitivity_policy,
            metadata_key=metadata_key,
            target_type=target_type,
            value=value,
        )
        if not edge:
            return True
        allowed, reason = relation_visibility_for_role(
            edge,
            self._active_user_role(),
            self.sensitivity_policy,
            action="traverse",
        )
        if not allowed:
            logger.info(
                "relation_traversal_denied %s",
                {
                    "source_entity": edge.get("source_entity"),
                    "target_entity": edge.get("target_entity"),
                    "relation_type": edge.get("relation_type"),
                    "role": self._active_user_role(),
                    "reason": reason,
                },
            )
        return allowed

    def _expand_relations(self, question: str, seed_results: List[Dict], force_secure: bool = False) -> List[Dict]:
        retrieve_by_metadata = getattr(self.retriever, "retrieve_by_metadata", None)
        if not callable(retrieve_by_metadata):
            return seed_results

        asks_process = self._contains_any(question, ["process", "verfahren", "steps", "schritt"])
        asks_formulation = self._asks_formulation_details(question)
        asks_testing = self._contains_any(question, ["geprüft", "gepruft", "tester", "prüfer", "pruefer", "parameter", "properties", "eigenschaften"])
        asks_market = self._contains_any(question, ["target market", "zielmarkt", "market", "verwendung"])

        expanded = list(seed_results)

        for item in seed_results:
            meta = item.get("metadata", {})
            doc_type = meta.get("doc_type")

            if doc_type == "product":
                if (
                    asks_process
                    and meta.get("verfahren_id")
                    and self._can_traverse_relation(item, "verfahren_id", "process", str(meta["verfahren_id"]), force_secure=force_secure)
                ):
                    expanded.extend(
                        retrieve_by_metadata(
                            filters=self._with_active_filters({"verfahren_id": str(meta["verfahren_id"])}, force_secure=force_secure),
                            top_k=1,
                            prefer_doc_types=["process"],
                        )
                    )
                if (
                    asks_formulation
                    and meta.get("rezeptur_id")
                    and self._can_traverse_relation(item, "rezeptur_id", "formulation", str(meta["rezeptur_id"]), force_secure=force_secure)
                ):
                    expanded.extend(
                        retrieve_by_metadata(
                            filters=self._with_active_filters({"rezeptur_id": str(meta["rezeptur_id"])}, force_secure=force_secure),
                            top_k=1,
                            prefer_doc_types=["formulation"],
                        )
                    )

            if doc_type == "formulation" and asks_market and meta.get("rezeptur_id"):
                expanded.extend(
                    retrieve_by_metadata(
                        filters=self._with_active_filters({"rezeptur_id": str(meta["rezeptur_id"])}, force_secure=force_secure),
                        top_k=3,
                        prefer_doc_types=["product"],
                    )
                )

            if doc_type == "process" and asks_market and meta.get("rezeptur_id"):
                expanded.extend(
                    retrieve_by_metadata(
                        filters=self._with_active_filters({"rezeptur_id": str(meta["rezeptur_id"])}, force_secure=force_secure),
                        top_k=3,
                        prefer_doc_types=["product"],
                    )
                )

            if doc_type == "formulation" and asks_testing and meta.get("rezeptur_id"):
                expanded.extend(
                    retrieve_by_metadata(
                        filters=self._with_active_filters({"rezeptur_id": str(meta["rezeptur_id"])}, force_secure=force_secure),
                        top_k=3,
                        prefer_doc_types=["product"],
                    )
                )

            if doc_type == "process" and asks_testing and meta.get("rezeptur_id"):
                expanded.extend(
                    retrieve_by_metadata(
                        filters=self._with_active_filters({"rezeptur_id": str(meta["rezeptur_id"])}, force_secure=force_secure),
                        top_k=3,
                        prefer_doc_types=["product"],
                    )
                )

        return self._dedupe_results(expanded)

    def _prepare_memory_inputs(
        self,
        question: str,
        suppress_memory_snippets: bool = False,
        suppress_conversation_messages: bool = False,
    ) -> Dict[str, List[Dict]]:
        if not self.memory:
            return {
                "conversation_messages": [],
                "memory_snippets": [],
            }

        if suppress_conversation_messages:
            conversation_messages = []
        else:
            try:
                conversation_messages = self.memory.recent_messages(
                    allowed_sensitivities=self._allowed_sensitivities,
                )
            except TypeError:
                conversation_messages = self.memory.recent_messages()

        if suppress_memory_snippets:
            memory_snippets = []
        else:
            try:
                memory_snippets = self.memory.relevant_memories(
                    question,
                    allowed_sensitivities=self._allowed_sensitivities,
                )
            except TypeError:
                memory_snippets = self.memory.relevant_memories(question)

        return {
            "conversation_messages": conversation_messages,
            "memory_snippets": memory_snippets,
        }

    def _maybe_update_summary(self) -> str:
        if not self.memory:
            return ""

        if hasattr(self.memory, "summary_for_allowed"):
            visible_summary = self.memory.summary_for_allowed(self._allowed_sensitivities)
        else:
            visible_summary = self.memory.summary

        if not self.memory.should_update_summary():
            return visible_summary

        try:
            pending_turns = self.memory.unsummarized_turns(
                allowed_sensitivities=self._allowed_sensitivities,
            )
        except TypeError:
            pending_turns = self.memory.unsummarized_turns()

        if not pending_turns:
            return visible_summary

        new_summary = self.generator.summarize_conversation(
            existing_summary=visible_summary,
            turns=pending_turns,
        )
        try:
            self.memory.update_summary(
                new_summary,
                consumed_turns=len(pending_turns),
                sensitivity=self._current_memory_sensitivity(),
            )
        except TypeError:
            self.memory.update_summary(new_summary, consumed_turns=len(pending_turns))
        return self.memory.summary_for_allowed(self._allowed_sensitivities) if hasattr(self.memory, "summary_for_allowed") else self.memory.summary

    def _infer_focus_ids_from_results(self, results: List[Dict]) -> Dict[str, List[str]]:
        out = self._empty_id_map()
        keys = ("rezeptur_id", "rezept_id", "verfahren_id")

        for item in results:
            meta = item.get("metadata", {})
            for key in keys:
                if out[key]:
                    continue
                if not self._metadata_id_allowed_for_focus(item, key):
                    continue
                value = meta.get(key)
                if value:
                    out[key] = [str(value)]
            if self._has_any_ids(out):
                break

        return out

    def _update_focus_history(self, id_map: Dict[str, List[str]]) -> None:
        id_map = self._sanitize_id_map_for_focus(id_map)
        if not self._has_any_ids(id_map):
            return

        normalized = {
            "rezeptur_id": self._merge_unique([], id_map.get("rezeptur_id", [])),
            "rezept_id": self._merge_unique([], id_map.get("rezept_id", [])),
            "verfahren_id": self._merge_unique([], id_map.get("verfahren_id", [])),
        }

        if self.focus_history and self.focus_history[-1] == normalized:
            return

        self.focus_history.append(normalized)
        if len(self.focus_history) > 30:
            self.focus_history = self.focus_history[-30:]

    def _current_memory_sensitivity(self) -> str:
        if not self._allowed_sensitivities:
            return normalize_sensitivity(None, self.sensitivity_policy)
        return max(
            self._allowed_sensitivities,
            key=lambda label: sensitivity_rank(label, self.sensitivity_policy),
        )

    @staticmethod
    def _value_is_specific(value: str) -> bool:
        text = str(value or "").strip()
        if not text or text.casefold() in {"n/a", "none", "nan", "unknown"}:
            return False
        return len(text) >= 3

    def _empty_output_guard_result(self) -> Dict:
        return {
            "enabled": self.output_leakage_verifier_enabled if hasattr(self, "output_leakage_verifier_enabled") else True,
            "checked": False,
            "leakage_detected": False,
            "matched_fields": [],
            "matched_count": 0,
            "action": "not_checked",
        }

    def _verify_answer_for_leakage(self, answer: str, results: List[Dict]) -> Dict:
        fields = collect_fields_by_visibility(
            results,
            user_role=self._active_user_role(),
            policy=self.sensitivity_policy,
        )
        relation_fields = (
            collect_relation_fields_by_visibility(
                results,
                user_role=self._active_user_role(),
                policy=self.sensitivity_policy,
            )
            if self.relation_access_guard_enabled
            else {"allowed": [], "restricted": []}
        )
        fields["allowed"].extend(relation_fields.get("allowed", []))
        fields["restricted"].extend(relation_fields.get("restricted", []))
        fields["restricted"].extend(self._restricted_inventory_fields())
        verification = verify_answer_against_restricted_fields(
            answer=answer,
            restricted_fields=fields.get("restricted", []),
            allowed_fields=fields.get("allowed", []),
        )
        action = "allow"
        if verification.leakage_detected:
            action = "replace_with_refusal" if self.output_leakage_verifier_enabled else "observe_only"
        return {
            "enabled": self.output_leakage_verifier_enabled,
            "checked": True,
            "leakage_detected": verification.leakage_detected,
            "matched_fields": verification.matched_fields,
            "matched_count": verification.matched_count,
            "action": action,
        }

    def _guard_answer(self, answer: str, results: List[Dict]) -> str:
        self.last_output_guard = self._verify_answer_for_leakage(answer, results)
        if self.last_output_guard["action"] == "replace_with_refusal":
            return (
                "I cannot provide restricted values for your current role. "
                "I can answer using only fields marked allowed for your role."
            )

        if self.prompt_injection_guard_enabled:
            detected, artifacts = answer_contains_injection_artifact(answer)
            self.last_prompt_injection_guard.update({
                "checked": True,
                "answer_checked": True,
                "answer_artifact_detected": detected,
                "answer_matched_artifacts": artifacts,
            })
            if detected:
                redacted = redact_answer_injection_artifacts(answer)
                self.last_prompt_injection_guard["action"] = "redact_artifact" if redacted else "replace_with_refusal"
                return redacted or (
                    "I cannot follow instructions embedded in retrieved data. "
                    "I can answer using only trusted task instructions and fields allowed for your role."
                )
            self.last_prompt_injection_guard["action"] = self.last_prompt_injection_guard.get("action") or "allow"

        return answer

    def _retriever_metadatas(self) -> List[Dict]:
        metadatas = getattr(self.retriever, "metadatas", None)
        return list(metadatas) if metadatas else []

    def _guard_answer_for_membership(self, question: str, answer: str) -> str:
        self.last_membership_guard = validate_membership_answer(
            query=question,
            answer=answer,
            user_role=self._active_user_role(),
            policy=self.sensitivity_policy,
            metadatas=self._retriever_metadatas(),
            enabled=self.membership_guard_enabled,
            probe=self.last_membership_guard,
        )
        if self.last_membership_guard["action"] == "replace_with_refusal":
            return MEMBERSHIP_REFUSAL
        if (
            self.last_membership_guard.get("is_membership_probe")
            and not self.last_membership_guard.get("unauthorized_user")
            and answer_is_membership_refusal(answer)
        ):
            authorized_answer = build_authorized_membership_answer(
                self.last_membership_guard,
                self._retriever_metadatas(),
            )
            if authorized_answer:
                self.last_membership_guard["triggered"] = True
                self.last_membership_guard["action"] = "replace_authorized_refusal"
                return authorized_answer
        return answer

    def query(self, question: str) -> str:
        self.last_raw_answer = ""
        self.last_output_guard = self._empty_output_guard_result()
        self.last_prompt_injection_guard = empty_prompt_injection_guard_result(
            enabled=self.prompt_injection_guard_enabled
        )
        self.last_membership_guard = empty_membership_guard_result(
            enabled=self.membership_guard_enabled
        )
        self.last_embedding_probe_guard = self._empty_embedding_probe_guard_result()

        explicit_ids = self._extract_ids(question)
        membership_probe = enrich_probe_from_metadata(
            detect_membership_probe(question),
            metadatas=self._retriever_metadatas(),
            policy=self.sensitivity_policy,
        )
        if (
            self.membership_guard_enabled
            and self.rag_mode != SENSITIVITY_EVAL_MODE
            and is_unauthorized_membership_probe(
                membership_probe,
                user_role=self._active_user_role(),
                policy=self.sensitivity_policy,
            )
        ):
            self.last_membership_guard = build_pre_retrieval_refusal_result(
                membership_probe,
                enabled=self.membership_guard_enabled,
            )
            self.last_raw_answer = MEMBERSHIP_REFUSAL
            self.last_results = []
            self.last_visible_context_chunks = []
            self.last_access_decisions = []
            if self.memory:
                try:
                    self.memory.add_turn(
                        question,
                        MEMBERSHIP_REFUSAL,
                        retrieval_results=[],
                        sensitivity=self._current_memory_sensitivity(),
                    )
                except TypeError:
                    self.memory.add_turn(question, MEMBERSHIP_REFUSAL, retrieval_results=[])
            return MEMBERSHIP_REFUSAL

        self.last_embedding_probe_guard = self._detect_embedding_probe_guard(
            question=question,
            explicit_ids=explicit_ids,
            membership_probe=membership_probe,
        )
        strict_retrieval_access = bool(self.last_embedding_probe_guard.get("strict_retrieval_access"))

        id_map = self._merge_id_maps(self._empty_id_map(), explicit_ids)
        reused_context = False
        focus_explicit_product_formulation = self._is_explicit_product_formulation_query(question, explicit_ids)

        has_reference = self._contains_any(
            question,
            ["diese", "dieser", "diesen", "these", "those", "that", "es", "it", "ihn", "ihm", "sie"],
        )
        asks_previous_entity = self._asks_previous_entity(question)
        asks_testing = self._contains_any(
            question, ["geprüft", "gepruft", "tester", "prüfer", "pruefer", "tested"]
        )
        asks_process_details = self._contains_any(question, ["process", "verfahren", "steps", "schritt"])

        # Resolve pronouns using clean focus history first (not last_results).
        if has_reference:
            id_map_from_focus = self._ids_from_focus_history(1)
            if self._has_any_ids(id_map_from_focus):
                id_map = self._merge_id_maps(id_map, id_map_from_focus)
                reused_context = True
            elif self.last_results:
                # Fallback only if focus history is empty.
                id_map_from_last = {
                    "rezeptur_id": self._get_from_last_results("rezeptur_id"),
                    "rezept_id": self._get_from_last_results("rezept_id"),
                    "verfahren_id": self._get_from_last_results("verfahren_id"),
                }
                if self._has_any_ids(id_map_from_last):
                    id_map = self._merge_id_maps(id_map, id_map_from_last)
                    reused_context = True

        # "last/previous product" -> add previous focus entity.
        if asks_previous_entity:
            id_map_previous_focus = self._ids_from_focus_history(2)
            if self._has_any_ids(id_map_previous_focus):
                id_map = self._merge_id_maps(id_map, id_map_previous_focus)
                reused_context = True

        # Generic follow-up without explicit IDs.
        if self._should_reuse_topic_context(question, id_map):
            id_map_from_focus = self._ids_from_focus_history(1)
            if self._has_any_ids(id_map_from_focus):
                id_map = self._merge_id_maps(id_map, id_map_from_focus)
                reused_context = True
            elif self.last_results:
                id_map_from_last = {
                    "rezeptur_id": self._get_from_last_results("rezeptur_id"),
                    "rezept_id": self._get_from_last_results("rezept_id"),
                    "verfahren_id": self._get_from_last_results("verfahren_id"),
                }
                if self._has_any_ids(id_map_from_last):
                    id_map = self._merge_id_maps(id_map, id_map_from_last)
                    reused_context = True
                else:
                    id_map_from_memory = self._ids_from_recent_memory()
                    if self._has_any_ids(id_map_from_memory):
                        id_map = self._merge_id_maps(id_map, id_map_from_memory)
                        reused_context = True

        doc_type_hints = self._infer_doc_type_hints(question)

        seed_results = []
        seed_results.extend(self._fetch_by_id("rezeptur_id", id_map["rezeptur_id"], "formulation", force_secure=strict_retrieval_access))
        seed_results.extend(self._fetch_by_id("rezept_id", id_map["rezept_id"], "product", force_secure=strict_retrieval_access))
        seed_results.extend(self._fetch_by_id("verfahren_id", id_map["verfahren_id"], "process", force_secure=strict_retrieval_access))
        seed_results = self._dedupe_results(seed_results)

        if seed_results:
            results = self._expand_relations(question, seed_results, force_secure=strict_retrieval_access)
            if len(results) < self.top_k and not reused_context and not focus_explicit_product_formulation:
                query_embedding = self.embedder.embed([question])
                retrieve_hybrid = getattr(self.retriever, "retrieve_hybrid", None)
                if callable(retrieve_hybrid):
                    fallback = retrieve_hybrid(
                        query=question,
                        query_embedding=query_embedding,
                        top_k=self.top_k,
                        doc_type_hints=doc_type_hints,
                        filters=self._active_retrieval_filters(force_secure=strict_retrieval_access),
                    )
                    results = self._dedupe_results(results + fallback)
            if focus_explicit_product_formulation:
                results = self._focus_product_formulation_results(
                    results,
                    explicit_ids,
                    include_processes=asks_process_details,
                )
            results = results[: self.top_k]
        else:
            query_embedding = self.embedder.embed([question])
            retrieve_hybrid = getattr(self.retriever, "retrieve_hybrid", None)
            if callable(retrieve_hybrid):
                results = retrieve_hybrid(
                    query=question,
                    query_embedding=query_embedding,
                    top_k=self.top_k,
                    doc_type_hints=doc_type_hints,
                    filters=self._active_retrieval_filters(force_secure=strict_retrieval_access),
                )
            else:
                results = self.retriever.retrieve(query_embedding, self.top_k)

        if strict_retrieval_access:
            results = self._filter_results_for_active_access(results)

        if asks_testing:
            product_results = [r for r in results if r.get("metadata", {}).get("doc_type") == "product"]
            if product_results:
                non_products = [r for r in results if r.get("metadata", {}).get("doc_type") != "product"]
                results = (product_results + non_products)[: self.top_k]

        for r in results:
            meta = r.get("metadata", {})
            logger.info(
                "retrieved_entity %s",
                {
                    "entity_id": meta.get("entity_id"),
                    "doc_type": meta.get("doc_type"),
                    "field_sensitivities": meta.get("field_sensitivities"),
                    "max_sensitivity": meta.get("max_sensitivity"),
                },
            )

        context_chunks = self._format_context_chunks(
            results,
            force_secure_projection=bool(self.last_embedding_probe_guard.get("force_secure_projection")),
            include_embedding_policy=bool(self.last_embedding_probe_guard.get("side_channel_policy_added")),
        )
        suppress_memory_for_query = focus_explicit_product_formulation or strict_retrieval_access
        memory_inputs = self._prepare_memory_inputs(
            question,
            suppress_memory_snippets=suppress_memory_for_query,
            suppress_conversation_messages=suppress_memory_for_query,
        )
        memory_summary = "" if suppress_memory_for_query else self._maybe_update_summary()

        raw_answer = self.generator.generate(
            query=question,
            context_chunks=context_chunks,
            conversation_messages=memory_inputs["conversation_messages"],
            memory_summary=memory_summary,
            memory_snippets=memory_inputs["memory_snippets"],
        )
        self.last_raw_answer = raw_answer
        answer = self._guard_answer_for_membership(question, raw_answer)
        answer = self._guard_answer(answer, results)

        self.last_results = results

        # Update focus history with user-centric entity scope.
        if asks_previous_entity:
            focus_ids = id_map
        elif self._has_any_ids(explicit_ids):
            focus_ids = explicit_ids
        elif has_reference or self._should_reuse_topic_context(question, explicit_ids):
            focus_ids = id_map
        else:
            focus_ids = self._infer_focus_ids_from_results(results)

        self._update_focus_history(focus_ids)

        if self.memory:
            try:
                self.memory.add_turn(
                    question,
                    answer,
                    retrieval_results=results,
                    sensitivity=self._current_memory_sensitivity(),
                    allowed_sensitivities=self._allowed_sensitivities,
                )
            except TypeError:
                self.memory.add_turn(question, answer, retrieval_results=results)

        return answer
