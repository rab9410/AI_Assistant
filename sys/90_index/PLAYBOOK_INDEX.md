# PLAYBOOK INDEX

This folder is the cleaned active knowledge set for your AI.

## Folder Layout

### `00_core/`
Core behavior and reliability rules that should apply broadly across most requests.

Files:
- `assistant_core_playbook.md`
- `trust_playbook.md`
- `tool_use_playbook.md`
- `rag_knowledge_playbook.md`
- `formatting_output_playbook.md`
- `safety_boundaries_playbook.md`

### `10_task_playbooks/`
Task-specific operating playbooks.

Files:
- `coding_playbook.md`
- `debugging_playbook.md`
- `research_playbook.md`
- `writing_playbook.md`
- `system_design_playbook.md`
- `memory_personalization_playbook.md`

## Recommended Use
- Keep only these distilled files inside active `/sys`.
- Move raw vendor prompts and large reference dumps into `/sys_archive/`.
- Rebuild your embeddings or sync index after replacing the folder.
- Keep filenames unique to avoid summary collisions.

## Suggested Archive Structure
```text
sys_archive/
├── Anthropic/
├── Google/
├── vendor_prompts/
└── raw_reference/
```
