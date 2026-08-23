from typing import Any, Dict, List, Optional, Sequence

import faiss
import numpy as np

from ingestion.embedder import Embedder
from security.field_access import (
    least_sensitive_label,
    load_sensitivity_policy,
    normalize_sensitivity,
    sensitivity_rank,
)


class ConversationMemory:
    def __init__(
        self,
        embedder: Embedder,
        recent_turns_window: int = 6,
        memory_top_k: int = 4,
        summary_batch_size: int = 4,
        sensitivity_policy: Optional[Dict[str, Any]] = None,
    ):
        self.embedder = embedder
        self.recent_turns_window = max(1, recent_turns_window)
        self.memory_top_k = max(1, memory_top_k)
        self.summary_batch_size = max(1, summary_batch_size)
        self.sensitivity_policy = sensitivity_policy or load_sensitivity_policy()

        self.turns: List[Dict[str, str]] = []
        self.summary: str = ""
        self.summary_sensitivity: str = least_sensitive_label(self.sensitivity_policy)
        self._turn_sensitivities: List[str] = []

        self._summary_cursor = 0

        self._memory_index: Optional[faiss.IndexFlatIP] = None
        self._memory_texts: List[str] = []
        self._memory_sensitivities: List[str] = []

    def _normalize_sensitivity(self, sensitivity: Optional[str]) -> str:
        return normalize_sensitivity(sensitivity, self.sensitivity_policy)

    def _max_label(self, labels: Sequence[str]) -> str:
        highest = least_sensitive_label(self.sensitivity_policy)
        for label in labels:
            normalized = self._normalize_sensitivity(label)
            if sensitivity_rank(normalized, self.sensitivity_policy) > sensitivity_rank(highest, self.sensitivity_policy):
                highest = normalized
        return highest

    def _result_sensitivity(self, result: Dict) -> str:
        meta = result.get("metadata", {}) if isinstance(result, dict) else {}
        labels: List[str] = []

        max_label = meta.get("retrieval_sensitivity") or meta.get("max_sensitivity")
        if max_label:
            labels.append(str(max_label))

        field_sensitivities = meta.get("field_sensitivities") or []
        if isinstance(field_sensitivities, (list, tuple, set)):
            labels.extend(str(label) for label in field_sensitivities)

        fields = meta.get("entity_fields") or (meta.get("entity") or {}).get("fields") or []
        if isinstance(fields, list):
            labels.extend(str(field.get("sensitivity")) for field in fields if field.get("sensitivity"))

        doc_sensitivity = meta.get("sensitivity")
        if doc_sensitivity and str(doc_sensitivity).strip().lower() != "mixed":
            labels.append(str(doc_sensitivity))

        return self._max_label(labels)

    def _turn_sensitivity(
        self,
        retrieval_results: List[Dict],
        sensitivity: Optional[str],
    ) -> str:
        labels = [sensitivity] if sensitivity else []
        labels.extend(self._result_sensitivity(result) for result in retrieval_results)
        return self._max_label([label for label in labels if label])

    def _is_allowed(self, sensitivity: str, allowed_sensitivities: Optional[Sequence[str]]) -> bool:
        if allowed_sensitivities is None:
            return True
        allowed = [self._normalize_sensitivity(label) for label in allowed_sensitivities]
        if not allowed:
            return False
        max_allowed = max(sensitivity_rank(label, self.sensitivity_policy) for label in allowed)
        return sensitivity_rank(self._normalize_sensitivity(sensitivity), self.sensitivity_policy) <= max_allowed

    def _id_allowed_for_memory(
        self,
        metadata_key: str,
        allowed_sensitivities: Optional[Sequence[str]],
    ) -> bool:
        if metadata_key == "rezept_id":
            return True
        if allowed_sensitivities is None:
            return True
        return self._is_allowed("protected", allowed_sensitivities)

    def _extract_ids(
        self,
        retrieval_results: List[Dict],
        allowed_sensitivities: Optional[Sequence[str]] = None,
    ) -> List[str]:
        keys = ("rezeptur_id", "rezept_id", "verfahren_id")
        out: List[str] = []
        seen = set()
        for item in retrieval_results:
            meta = item.get("metadata", {})
            for key in keys:
                if not self._id_allowed_for_memory(key, allowed_sensitivities):
                    continue
                value = meta.get(key)
                if value and value not in seen:
                    out.append(str(value))
                    seen.add(value)
        return out

    def _to_memory_text(
        self,
        user_text: str,
        assistant_text: str,
        retrieval_results: List[Dict],
        allowed_sensitivities: Optional[Sequence[str]] = None,
    ) -> str:
        ids = self._extract_ids(retrieval_results, allowed_sensitivities=allowed_sensitivities)
        ids_part = f" IDs: {', '.join(ids)}." if ids else ""
        return f"User asked: {user_text}\nAssistant answered: {assistant_text}{ids_part}"

    def _ensure_index(self, dim: int) -> None:
        if self._memory_index is None:
            self._memory_index = faiss.IndexFlatIP(dim)

    def add_turn(
        self,
        user_text: str,
        assistant_text: str,
        retrieval_results: Optional[List[Dict]] = None,
        sensitivity: Optional[str] = None,
        allowed_sensitivities: Optional[Sequence[str]] = None,
    ) -> None:
        retrieval_results = retrieval_results or []
        turn_sensitivity = self._turn_sensitivity(retrieval_results, sensitivity)
        self.turns.append({"user": user_text, "assistant": assistant_text})
        self._turn_sensitivities.append(turn_sensitivity)

        memory_text = self._to_memory_text(
            user_text,
            assistant_text,
            retrieval_results,
            allowed_sensitivities=allowed_sensitivities,
        )
        emb = self.embedder.embed([memory_text]).astype(np.float32)
        faiss.normalize_L2(emb)

        self._ensure_index(emb.shape[1])
        self._memory_index.add(emb)
        self._memory_texts.append(memory_text)
        self._memory_sensitivities.append(turn_sensitivity)

    def clear(self) -> None:
        self.turns = []
        self.summary = ""
        self.summary_sensitivity = least_sensitive_label(self.sensitivity_policy)
        self._turn_sensitivities = []
        self._summary_cursor = 0
        self._memory_index = None
        self._memory_texts = []
        self._memory_sensitivities = []

    def recent_messages(
        self,
        allowed_sensitivities: Optional[Sequence[str]] = None,
    ) -> List[Dict[str, str]]:
        start = max(0, len(self.turns) - self.recent_turns_window)
        messages: List[Dict[str, str]] = []
        for idx, turn in enumerate(self.turns[start:], start=start):
            sensitivity = (
                self._turn_sensitivities[idx]
                if idx < len(self._turn_sensitivities)
                else least_sensitive_label(self.sensitivity_policy)
            )
            if not self._is_allowed(sensitivity, allowed_sensitivities):
                continue
            messages.append({"role": "user", "content": turn["user"]})
            messages.append({"role": "assistant", "content": turn["assistant"]})
        return messages

    def relevant_memories(
        self,
        query: str,
        allowed_sensitivities: Optional[Sequence[str]] = None,
    ) -> List[str]:
        if self._memory_index is None or not self._memory_texts:
            return []

        q = self.embedder.embed([query]).astype(np.float32)
        faiss.normalize_L2(q)

        _, indices = self._memory_index.search(q, len(self._memory_texts))

        out: List[str] = []
        seen = set()
        for i in indices[0]:
            if i < 0:
                continue
            sensitivity = (
                self._memory_sensitivities[i]
                if i < len(self._memory_sensitivities)
                else least_sensitive_label(self.sensitivity_policy)
            )
            if not self._is_allowed(sensitivity, allowed_sensitivities):
                continue
            text = self._memory_texts[i]
            if text in seen:
                continue
            out.append(text)
            seen.add(text)
            if len(out) >= self.memory_top_k:
                break
        return out

    def summary_for_allowed(self, allowed_sensitivities: Optional[Sequence[str]] = None) -> str:
        if self._is_allowed(self.summary_sensitivity, allowed_sensitivities):
            return self.summary
        return ""

    def should_update_summary(self) -> bool:
        return len(self.turns) - self._summary_cursor >= self.summary_batch_size

    def unsummarized_turns(
        self,
        allowed_sensitivities: Optional[Sequence[str]] = None,
    ) -> List[Dict[str, str]]:
        out: List[Dict[str, str]] = []
        for idx, turn in enumerate(self.turns[self._summary_cursor :], start=self._summary_cursor):
            sensitivity = (
                self._turn_sensitivities[idx]
                if idx < len(self._turn_sensitivities)
                else least_sensitive_label(self.sensitivity_policy)
            )
            if self._is_allowed(sensitivity, allowed_sensitivities):
                out.append(turn)
        return out

    def update_summary(
        self,
        new_summary: str,
        consumed_turns: int,
        sensitivity: Optional[str] = None,
    ) -> None:
        self.summary = new_summary.strip()
        consumed = max(0, consumed_turns)
        consumed_sensitivities = self._turn_sensitivities[
            self._summary_cursor : self._summary_cursor + consumed
        ]
        labels = [self.summary_sensitivity]
        labels.extend(consumed_sensitivities)
        if sensitivity:
            labels.append(sensitivity)
        self.summary_sensitivity = self._max_label(labels)
        self._summary_cursor += consumed
