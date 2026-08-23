from pathlib import Path
from typing import Dict, List, Optional

from config.settings import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    DATA_DIR,
    EMBEDDING_MODEL,
    GENERATION_MODEL,
    MEMORY_RECENT_TURNS_WINDOW,
    MEMORY_RETRIEVAL_TOP_K,
    MEMORY_SUMMARY_BATCH_SIZE,
    TOP_K,
    EMBEDDING_PROBE_GUARD_ENABLED,
    MEMBERSHIP_GUARD_ENABLED,
    OUTPUT_LEAKAGE_VERIFIER_ENABLED,
    PROMPT_INJECTION_GUARD_ENABLED,
    RELATION_ACCESS_GUARD_ENABLED,
)
from generation.openai_generator import OpenAIGenerator
from ingestion.chunker import chunk_text
from ingestion.embedder import Embedder
from ingestion.loader import load_documents
from ingestion.xlsx_loader import load_xlsx_as_text
from ingestion.xlsx_multilevel_loader import load_xlsx_multilevel
from memory.conversation_memory import ConversationMemory
from pipeline.rag_pipeline import RAGPipeline
from security.field_access import SENSITIVITY_EVAL_MODE
from retrieval.faiss_retriever import FaissRetriever


DEFAULT_XLSX_FILE = Path("data/SiSWiss_Testdaten.xlsx")


def build_shared_components(
    use_xlsx: bool = True,
    use_multilevel: bool = True,
    xlsx_file: Path = DEFAULT_XLSX_FILE,
) -> Dict[str, object]:
    if use_xlsx:
        if use_multilevel:
            documents = load_xlsx_multilevel(xlsx_file)
            chunks: List[str] = [doc["text"] for doc in documents]
            metadatas: List[Dict] = [doc["metadata"] for doc in documents]
        else:
            chunks = load_xlsx_as_text(xlsx_file)
            metadatas = [{} for _ in chunks]
    else:
        documents = load_documents(DATA_DIR)
        chunks = []
        for doc in documents:
            chunks.extend(chunk_text(doc, CHUNK_SIZE, CHUNK_OVERLAP))
        metadatas = [{} for _ in chunks]

    embedder = Embedder(EMBEDDING_MODEL)
    embeddings = embedder.embed(chunks)

    retriever = FaissRetriever(
        embeddings=embeddings,
        documents=chunks,
        metadatas=metadatas,
    )
    generator = OpenAIGenerator(GENERATION_MODEL)

    return {
        "embedder": embedder,
        "retriever": retriever,
        "generator": generator,
        "chunks_count": len(chunks),
    }


def create_rag_pipeline(
    shared: Dict[str, object],
    user_role: Optional[str] = None,
    rag_mode: str = SENSITIVITY_EVAL_MODE,
    post_generation_verifier_enabled: Optional[bool] = None,
    output_leakage_verifier_enabled: Optional[bool] = None,
    membership_guard_enabled: Optional[bool] = None,
    embedding_probe_guard_enabled: Optional[bool] = None,
    prompt_injection_guard_enabled: Optional[bool] = None,
    access_change_memory_clear_enabled: Optional[bool] = None,
    relation_access_guard_enabled: Optional[bool] = None,
) -> RAGPipeline:
    embedder = shared["embedder"]
    retriever = shared["retriever"]
    generator = shared["generator"]

    memory = ConversationMemory(
        embedder=embedder,
        recent_turns_window=MEMORY_RECENT_TURNS_WINDOW,
        memory_top_k=MEMORY_RETRIEVAL_TOP_K,
        summary_batch_size=MEMORY_SUMMARY_BATCH_SIZE,
    )

    return RAGPipeline(
        embedder=embedder,
        retriever=retriever,
        generator=generator,
        top_k=TOP_K,
        memory=memory,
        user_role=user_role,
        rag_mode=rag_mode,
        post_generation_verifier_enabled=(
            OUTPUT_LEAKAGE_VERIFIER_ENABLED
            if post_generation_verifier_enabled is None
            else post_generation_verifier_enabled
        ),
        output_leakage_verifier_enabled=output_leakage_verifier_enabled,
        membership_guard_enabled=(
            MEMBERSHIP_GUARD_ENABLED if membership_guard_enabled is None else membership_guard_enabled
        ),
        embedding_probe_guard_enabled=(
            EMBEDDING_PROBE_GUARD_ENABLED
            if embedding_probe_guard_enabled is None
            else embedding_probe_guard_enabled
        ),
        prompt_injection_guard_enabled=(
            PROMPT_INJECTION_GUARD_ENABLED
            if prompt_injection_guard_enabled is None
            else prompt_injection_guard_enabled
        ),
        access_change_memory_clear_enabled=access_change_memory_clear_enabled,
        relation_access_guard_enabled=(
            RELATION_ACCESS_GUARD_ENABLED
            if relation_access_guard_enabled is None
            else relation_access_guard_enabled
        ),
    )
