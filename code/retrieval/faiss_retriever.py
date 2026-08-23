import faiss
import numpy as np
import re
from collections.abc import Iterable as IterableABC
from typing import Any, Dict, Iterable, List, Optional

from security.field_access import (
    least_sensitive_label,
    load_sensitivity_policy,
    normalize_sensitivity,
    sensitivity_rank,
)
from .base import BaseRetriever

class FaissRetriever(BaseRetriever):
    ACCESS_FILTER_KEY = "__allowed_sensitivities__"

    def __init__(
        self,
        embeddings: np.ndarray,
        documents: List[str],
        metadatas: Optional[List[Dict]] = None,
    ):
        self.documents = documents
        self.metadatas = metadatas if metadatas is not None else [{} for _ in documents]
        self.sensitivity_policy = load_sensitivity_policy()

        dim = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dim)

        # Cosine search with normalized vectors.
        faiss.normalize_L2(embeddings)
        self.index.add(embeddings)

        self._search_blobs = [self._build_search_blob(text, meta) for text, meta in zip(self.documents, self.metadatas)]

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return re.findall(r"[a-zA-Z0-9\-]+", str(text).lower())

    @staticmethod
    def _content_terms(query: str) -> List[str]:
        stop_words = {
            "the", "is", "are", "all", "of", "for", "to", "which", "what", "who", "has", "with",
            "tell", "me", "explain", "linked", "link", "id", "ids", "and", "or", "by",
            "wer", "hat", "diese", "dieser", "diesen", "welche", "wurde", "wird",
            "gepruft", "geprüft", "pruefer", "prüfer", "tester", "tested",
            "rezeptur", "rezepture", "rezept", "verfahren", "prozess", "process",
            "parameter", "properties", "eigenschaften",
        }
        return [t for t in FaissRetriever._tokenize(query) if len(t) >= 3 and t not in stop_words]

    def _flatten_values(self, value) -> Iterable[str]:
        if value is None:
            return []
        if isinstance(value, dict):
            out = []
            for k, v in value.items():
                out.extend(self._flatten_values(k))
                out.extend(self._flatten_values(v))
            return out
        if isinstance(value, (list, tuple, set)):
            out = []
            for item in value:
                out.extend(self._flatten_values(item))
            return out
        return [str(value)]

    def _build_search_blob(self, text: str, meta: Dict) -> str:
        parts = [str(text)]
        for v in meta.values():
            parts.extend(self._flatten_values(v))
        return "\n".join(parts).lower()

    @staticmethod
    def _normalize_identifier(key: str, value) -> str:
        raw = str(value).strip().upper()
        compact = re.sub(r"\s+", "", raw)

        prefix_map = {
            "rezeptur_id": "R",
            "rezept_id": "P",
            "verfahren_id": "V",
        }
        prefix = prefix_map.get(str(key))
        if not prefix:
            return compact

        probe = compact.replace("-", "")
        if probe.startswith(prefix):
            probe = probe[1:]

        m = re.search(r"(\d+)", probe)
        if not m:
            return compact

        return f"{prefix}-{m.group(1).zfill(3)}"

    @staticmethod
    def _equals(key: str, a, b) -> bool:
        return FaissRetriever._normalize_identifier(key, a) == FaissRetriever._normalize_identifier(key, b)

    def _value_matches(self, key: str, value: Any, expected: Any) -> bool:
        if isinstance(expected, IterableABC) and not isinstance(expected, (str, bytes, dict)):
            return any(self._value_matches(key, value, item) for item in expected)

        if isinstance(value, (list, tuple, set)):
            return any(self._equals(key, item, expected) for item in value)

        return self._equals(key, value, expected)

    def _max_label(self, labels: Iterable[str]) -> str:
        highest = least_sensitive_label(self.sensitivity_policy)
        for label in labels:
            normalized = normalize_sensitivity(label, self.sensitivity_policy)
            if sensitivity_rank(normalized, self.sensitivity_policy) > sensitivity_rank(highest, self.sensitivity_policy):
                highest = normalized
        return highest

    def _metadata_retrieval_sensitivity(self, meta: Dict) -> Optional[str]:
        explicit = meta.get("retrieval_sensitivity")
        if explicit:
            return normalize_sensitivity(explicit, self.sensitivity_policy)

        labels: List[str] = []
        max_label = meta.get("max_sensitivity")
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

        if not labels:
            return None
        return self._max_label(labels)

    def _metadata_allowed_for_sensitivities(self, meta: Dict, expected: Any) -> bool:
        if isinstance(expected, IterableABC) and not isinstance(expected, (str, bytes, dict)):
            allowed = [normalize_sensitivity(label, self.sensitivity_policy) for label in expected]
        else:
            allowed = [normalize_sensitivity(expected, self.sensitivity_policy)]
        if not allowed:
            return False

        sensitivity = self._metadata_retrieval_sensitivity(meta)
        if sensitivity is None:
            return True

        max_allowed_rank = max(sensitivity_rank(label, self.sensitivity_policy) for label in allowed)
        return sensitivity_rank(sensitivity, self.sensitivity_policy) <= max_allowed_rank

    def _metadata_matches(self, meta: Dict, filters: Dict[str, Any]) -> bool:
        for key, expected in filters.items():
            if key == self.ACCESS_FILTER_KEY:
                if not self._metadata_allowed_for_sensitivities(meta, expected):
                    return False
                continue

            value = meta.get(key)
            if value is None:
                return False
            if not self._value_matches(key, value, expected):
                return False
        return True



    def retrieve(self, query_embedding: np.ndarray, top_k: int) -> List[Dict]:
        faiss.normalize_L2(query_embedding)
        _, indices = self.index.search(query_embedding, top_k)

        return [
            {"text": self.documents[i], "metadata": self.metadatas[i]}
            for i in indices[0]
        ]

    def retrieve_with_doc_type_filter(
        self,
        query_embedding: np.ndarray,
        top_k: int,
        doc_types: List[str],
    ) -> List[Dict]:
        if not doc_types:
            return self.retrieve(query_embedding, top_k)

        normalized = {str(d).strip().lower() for d in doc_types}
        faiss.normalize_L2(query_embedding)
        _, indices = self.index.search(query_embedding, len(self.documents))

        results = []
        for i in indices[0]:
            meta = self.metadatas[i]
            if str(meta.get("doc_type", "")).strip().lower() in normalized:
                results.append({"text": self.documents[i], "metadata": meta})
            if len(results) >= top_k:
                break
        return results

    def retrieve_by_metadata(
        self,
        filters: Dict[str, Any],
        top_k: int,
        prefer_doc_types: Optional[List[str]] = None,
    ) -> List[Dict]:
        if not filters:
            return []

        candidates = []
        for text, meta in zip(self.documents, self.metadatas):
            if self._metadata_matches(meta, filters):
                candidates.append({"text": text, "metadata": meta})

        if prefer_doc_types:
            priority = {doc_type: idx for idx, doc_type in enumerate(prefer_doc_types)}
            candidates.sort(
                key=lambda item: priority.get(
                    str(item["metadata"].get("doc_type", "")),
                    len(priority),
                )
            )

        return candidates[:top_k]

    def retrieve_by_text_query(
        self,
        query: str,
        top_k: int,
        prefer_doc_types: Optional[List[str]] = None,
    ) -> List[Dict]:
        terms = self._content_terms(query)
        if not terms:
            return []

        scored = []
        doc_type_pref = set(prefer_doc_types or [])
        phrase = " ".join(terms)

        for text, meta, blob in zip(self.documents, self.metadatas, self._search_blobs):
            hits = sum(1 for term in terms if term in blob)
            if hits == 0:
                continue

            score = hits / max(len(terms), 1)
            if phrase and phrase in blob:
                score += 1.0
            if doc_type_pref and str(meta.get("doc_type", "")) in doc_type_pref:
                score += 0.5

            scored.append((score, {"text": text, "metadata": meta}))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:top_k]]

    def retrieve_hybrid(
        self,
        query: str,
        query_embedding: np.ndarray,
        top_k: int,
        doc_type_hints: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict]:
        filters = filters or {}
        terms = self._content_terms(query)
        hinted_doc_types = {str(d).strip().lower() for d in (doc_type_hints or [])}

        faiss.normalize_L2(query_embedding)
        semantic_k = min(len(self.documents), max(top_k * 10, 30))
        semantic_scores, semantic_indices = self.index.search(query_embedding, semantic_k)
        semantic_map = {
            idx: float(score) for idx, score in zip(semantic_indices[0], semantic_scores[0]) if idx >= 0
        }

        scored = []
        for idx, (text, meta, blob) in enumerate(zip(self.documents, self.metadatas, self._search_blobs)):
            if filters and not self._metadata_matches(meta, filters):
                continue

            sem_score = semantic_map.get(idx, 0.0)

            lex_hits = 0
            if terms:
                lex_hits = sum(1 for term in terms if term in blob)
            lex_score = lex_hits / max(len(terms), 1) if terms else 0.0

            score = (1.2 * sem_score) + (2.2 * lex_score)

            doc_type = str(meta.get("doc_type", "")).strip().lower()
            if hinted_doc_types and doc_type in hinted_doc_types:
                score += 0.4

            # Small boost for exact ID mention anywhere in query.
            for key in ("rezeptur_id", "rezept_id", "verfahren_id"):
                val = str(meta.get(key, "")).strip()
                if val and val.lower() in query.lower():
                    score += 0.8

            # Stronger boost for exact multi-token phrase in product/formulation names.
            if len(terms) >= 2:
                phrase = " ".join(terms)
                product_name = str(meta.get("product_name", "")).lower()
                formulation_name = str(meta.get("formulation_name", "")).lower()
                if phrase and (phrase in product_name or phrase in formulation_name):
                    score += 1.2

            scored.append((score, idx))

        if not scored:
            return []

        scored.sort(key=lambda x: x[0], reverse=True)
        out = []
        for _, idx in scored[:top_k]:
            out.append({"text": self.documents[idx], "metadata": self.metadatas[idx]})
        return out
