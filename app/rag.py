import torch
from sentence_transformers import SentenceTransformer, util

from app.config import KNOWLEDGE_CACHE, KNOWLEDGE_SUMMARIES

from app.utils import get_repo_data

class NeuralRAG:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = SentenceTransformer(
            "all-MiniLM-L6-v2", device=self.device
        )
        self.knowledge_vectors = None
        self.knowledge_chunks = []
        self.load_knowledge_cache()

    def load_knowledge_cache(self):
        if KNOWLEDGE_CACHE.exists():
            try:
                data = torch.load(
                    KNOWLEDGE_CACHE,
                    map_location=self.device,
                    weights_only=False
                )
                self.knowledge_vectors = data.get("vectors")
                self.knowledge_chunks = data.get("chunks", [])
            except Exception:
                self.knowledge_vectors = None
                self.knowledge_chunks = []

    def get_knowledge(self, query, top_k=3):
        if self.knowledge_vectors is None or not self.knowledge_chunks:
            return "None available."
        try:
            with torch.no_grad():
                q_emb = self.model.encode(
                    query, convert_to_tensor=True
                )
                scores = util.cos_sim(q_emb, self.knowledge_vectors)[0]
                k = min(top_k, len(self.knowledge_chunks))
                top = torch.topk(scores, k=k)
            return "\n".join(
                [self.knowledge_chunks[idx] for idx in top.indices]
            )
        except Exception:
            return "None available."

    def get_knowledge_overview(self):
        data = get_repo_data(KNOWLEDGE_SUMMARIES)
        if not data:
            return "  No knowledge base loaded yet. Use Sync to index."
        lines = []
        for fname, info in data.items():
            headings = ", ".join(info.get("headings", [])[:5])
            words = info.get("word_count", 0)
            preview = info.get("preview", "")[:80]
            entry = f"  • {fname} ({words:,} words)"
            if headings:
                entry += f": {headings}"
            if preview:
                entry += f" — {preview}..."
            lines.append(entry)
        return "\n".join(lines)


RAG_ENGINE = NeuralRAG()