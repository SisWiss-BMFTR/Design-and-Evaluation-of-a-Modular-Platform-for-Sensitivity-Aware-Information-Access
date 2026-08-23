"""Deterministic runtime provenance for evaluation indexes and scorers."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
from pathlib import Path
from typing import Any, Sequence

import faiss


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _stable_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")


def package_version(distribution: str) -> str:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return "unavailable"


def build_runtime_provenance(
    *,
    documents: Sequence[dict[str, Any]],
    faiss_index: Any,
    scorer_id: str,
    scorer_version: str,
    scorer_source: Path,
    embedding_model: str,
) -> dict[str, Any]:
    canonical_documents = [
        {
            "position": position,
            "text": str(document.get("text") or ""),
            "metadata": document.get("metadata") or {},
        }
        for position, document in enumerate(documents)
    ]
    scorer_bytes = scorer_source.read_bytes()
    serialized_index = faiss.serialize_index(faiss_index).tobytes()
    return {
        "schema_version": "runtime-provenance-v1",
        "index": {
            "canonical_chunk_content_sha256": _sha256_bytes(
                _stable_json(canonical_documents)
            ),
            "faiss_serialized_index_sha256": _sha256_bytes(serialized_index),
            "chunk_count": len(canonical_documents),
            "embedding_model": embedding_model,
            "embedding_model_distribution_version": package_version(
                "sentence-transformers"
            ),
            "faiss_distribution_version": package_version("faiss-cpu"),
        },
        "scorer": {
            "scorer_id": scorer_id,
            "scorer_version": scorer_version,
            "scorer_source_path": str(scorer_source),
            "scorer_source_sha256": _sha256_bytes(scorer_bytes),
            "scoring_implementation_scope": "attack runner source file",
        },
    }
