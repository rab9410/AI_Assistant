from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════════════
#  PATHS & CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════
DATA_DIR = Path("data")
THREAD_DIR = DATA_DIR / "threads"
SYS_DIR = Path("sys")
KNOWLEDGE_DIR = DATA_DIR / "knowledge_base"

for _p in [THREAD_DIR, KNOWLEDGE_DIR, SYS_DIR]:
    _p.mkdir(parents=True, exist_ok=True)

MEMORY_FILE = DATA_DIR / "memory_store.json"
THREADS_META = DATA_DIR / "threads_meta.json"
KNOWLEDGE_CACHE = KNOWLEDGE_DIR / "neural_vector_cache.pt"
KNOWLEDGE_MANIFEST = KNOWLEDGE_DIR / "knowledge_manifest.json"
KNOWLEDGE_SUMMARIES = KNOWLEDGE_DIR / "knowledge_summaries.json"

GROQ_API_MODEL = "llama-3.3-70b-versatile"
HF_MODEL_ID = "meta-llama/Llama-3.1-8B-Instruct"

MAX_THREAD_NAME_LEN = 28