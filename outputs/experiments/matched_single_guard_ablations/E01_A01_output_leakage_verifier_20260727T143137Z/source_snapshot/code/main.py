from pathlib import Path

from config.env_loader import load_env_file

# Load local .env values early so API keys are available to all components.
load_env_file()

# ===============================
# Configuration
# ===============================

USE_XLSX = True
USE_MULTILEVEL = True   # toggle row vs multilevel here

XLSX_FILE = Path("data/SiSWiss_Testdaten.xlsx")

from config.settings import *
from generation.openai_generator import OpenAIGenerator
from ingestion.chunker import chunk_text
from ingestion.embedder import Embedder
from ingestion.loader import load_documents
from ingestion.xlsx_loader import load_xlsx_as_text
from ingestion.xlsx_multilevel_loader import load_xlsx_multilevel
from memory.conversation_memory import ConversationMemory
from pipeline.rag_pipeline import RAGPipeline
from retrieval.faiss_retriever import FaissRetriever


# ===============================
# 1. Load Data
# ===============================

if USE_XLSX:
    print("Loading XLSX dataset...")

    if USE_MULTILEVEL:
        documents = load_xlsx_multilevel(XLSX_FILE)

        chunks = [doc["text"] for doc in documents]
        metadatas = [doc["metadata"] for doc in documents]

    else:
        chunks = load_xlsx_as_text(XLSX_FILE)
        metadatas = [{} for _ in chunks]

else:
    print("Loading TXT documents...")
    documents = load_documents(DATA_DIR)

    chunks = []
    for doc in documents:
        chunks.extend(
            chunk_text(doc, CHUNK_SIZE, CHUNK_OVERLAP)
        )

    metadatas = [{} for _ in chunks]

print(f"Total chunks: {len(chunks)}")


# ===============================
# 2. Embed Chunks
# ===============================

print("Embedding chunks...")
embedder = Embedder(EMBEDDING_MODEL)
embeddings = embedder.embed(chunks)


# ===============================
# 3. Initialize Retriever + Generator + Memory
# ===============================

retriever = FaissRetriever(
    embeddings=embeddings,
    documents=chunks,
    metadatas=metadatas
)

generator = OpenAIGenerator(GENERATION_MODEL)

memory = ConversationMemory(
    embedder=embedder,
    recent_turns_window=MEMORY_RECENT_TURNS_WINDOW,
    memory_top_k=MEMORY_RETRIEVAL_TOP_K,
    summary_batch_size=MEMORY_SUMMARY_BATCH_SIZE,
)

rag = RAGPipeline(
    embedder=embedder,
    retriever=retriever,
    generator=generator,
    top_k=TOP_K,
    memory=memory,
)


# ===============================
# 4. Interactive Query Loop
# ===============================

print("\nRAG system ready. Type 'exit' to quit.")

while True:
    query = input("\nQuery: ")

    if query.lower() in {"exit", "quit"}:
        break

    answer = rag.query(query)
    print("\nAnswer:\n", answer)
