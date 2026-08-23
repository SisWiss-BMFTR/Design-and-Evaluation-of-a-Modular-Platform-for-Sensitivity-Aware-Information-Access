import os
from pathlib import Path

from config.env_loader import load_env_file


load_env_file()

BASE_DIR = Path(__file__).resolve().parents[2]

DATA_DIR = BASE_DIR / "data"

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
GENERATION_MODEL = os.getenv("GENERATION_MODEL", "gpt-4o-mini")

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
TOP_K = 5

# Multi-turn memory configuration.
MEMORY_RECENT_TURNS_WINDOW = 6
MEMORY_RETRIEVAL_TOP_K = 4
MEMORY_SUMMARY_BATCH_SIZE = 4

def _env_bool(name: str, default: bool = True) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


# Independent experiment switches. The legacy variable remains an output-verifier
# fallback so existing deployments keep their previous behavior.
OUTPUT_LEAKAGE_VERIFIER_ENABLED = _env_bool(
    "OUTPUT_LEAKAGE_VERIFIER_ENABLED",
    _env_bool("POST_GENERATION_VERIFIER_ENABLED", True),
)
POST_GENERATION_VERIFIER_ENABLED = OUTPUT_LEAKAGE_VERIFIER_ENABLED
MEMBERSHIP_GUARD_ENABLED = _env_bool("MEMBERSHIP_GUARD_ENABLED")
EMBEDDING_PROBE_GUARD_ENABLED = _env_bool("EMBEDDING_PROBE_GUARD_ENABLED")
PROMPT_INJECTION_GUARD_ENABLED = _env_bool("PROMPT_INJECTION_GUARD_ENABLED")
ACCESS_CHANGE_MEMORY_CLEAR_ENABLED = _env_bool("ACCESS_CHANGE_MEMORY_CLEAR_ENABLED")
RELATION_ACCESS_GUARD_ENABLED = _env_bool("RELATION_ACCESS_GUARD_ENABLED")
