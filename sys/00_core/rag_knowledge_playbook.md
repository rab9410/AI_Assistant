# Knowledge and RAG Playbook

## Purpose
Controls how retrieved knowledge should be used.

## Retrieval Rules
- Retrieved knowledge is evidence, not gospel.
- Prefer the most relevant chunk, not the longest chunk.
- If retrieved content is irrelevant, ignore it.
- If retrieved content conflicts internally, acknowledge uncertainty.
- Distinguish operating doctrine from domain facts.
- Summarize and synthesize; do not parrot giant chunks.

## RAG Hygiene
- Keep indexed files compact and reusable.
- Distill giant prompts into slim playbooks.
- Archive raw vendor prompts outside the active indexed path once distilled.
- Favor 8–15 high-quality playbooks over 100+ noisy prompt dumps.
