import hashlib

import torch
from PySide6.QtCore import QThread, Signal

from app.config import SYS_DIR, KNOWLEDGE_CACHE, KNOWLEDGE_MANIFEST, KNOWLEDGE_SUMMARIES
from app.rag import RAG_ENGINE
from app.utils import get_repo_data, bg_save


class SyncWorker(QThread):
    progress = Signal(str, int)
    finished = Signal(int)

    def run(self):
        try:
            self.progress.emit("Checking knowledge sources...", 5)
            manifest = get_repo_data(KNOWLEDGE_MANIFEST)
            files = list(SYS_DIR.rglob("*.md"))
            current_hashes = {}
            needs_rebuild = not KNOWLEDGE_CACHE.exists()

            self.progress.emit("Analysing changes...", 15)
            for f in files:
                rel = str(f.relative_to(SYS_DIR))
                content = f.read_text(encoding="utf-8", errors="ignore")
                fhash = hashlib.md5(content.encode()).hexdigest()
                current_hashes[rel] = fhash
                if manifest.get(rel) != fhash:
                    needs_rebuild = True

            if set(manifest.keys()) != set(current_hashes.keys()):
                needs_rebuild = True

            if not needs_rebuild:
                self.progress.emit("No changes detected.", 100)
                self.finished.emit(0)
                return

            chunks = []
            summaries = {}
            total_f = max(len(files), 1)

            for i, f in enumerate(files):
                self.progress.emit(
                    f"Processing: {f.name}",
                    20 + int((i / total_f) * 30)
                )
                content = f.read_text(encoding="utf-8", errors="ignore")
                lines = content.split("\n")

                headings = []
                for line in lines:
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        h_text = stripped.lstrip("#").strip()
                        if h_text:
                            headings.append(h_text)

                preview_parts = []
                in_content = False
                for line in lines:
                    stripped = line.strip()
                    if stripped and not stripped.startswith("#"):
                        in_content = True
                    if in_content:
                        preview_parts.append(stripped)
                        if len(" ".join(preview_parts)) > 300:
                            break
                preview = " ".join(preview_parts)[:300]

                summaries[f.name] = {
                    "headings": headings[:10],
                    "preview": preview,
                    "word_count": len(content.split())
                }

                curr = ""
                for line in lines:
                    curr += line + "\n"
                    if len(curr) > 1000:
                        chunks.append(f"FILE: {f.name} | DATA: {curr.strip()}")
                        curr = ""
                if curr.strip():
                    chunks.append(f"FILE: {f.name} | DATA: {curr.strip()}")

            self.progress.emit("Saving knowledge summaries...", 55)
            bg_save(KNOWLEDGE_SUMMARIES, summaries)

            if chunks:
                self.progress.emit("Building neural index...", 60)
                vectors = RAG_ENGINE.model.encode(
                    chunks,
                    convert_to_tensor=True,
                    show_progress_bar=False
                )
                self.progress.emit("Finalising...", 95)
                torch.save(
                    {"vectors": vectors, "chunks": chunks},
                    KNOWLEDGE_CACHE
                )
                bg_save(KNOWLEDGE_MANIFEST, current_hashes)
                RAG_ENGINE.load_knowledge_cache()
                self.finished.emit(len(chunks))
            else:
                bg_save(KNOWLEDGE_MANIFEST, current_hashes)
                self.finished.emit(0)

        except Exception as e:
            self.progress.emit(f"Sync error: {str(e)}", 0)
            self.finished.emit(0)