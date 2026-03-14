# SYS FOLDER SETUP

This bundle is ready to drop into your project.

## Recommended active structure
```text
sys/
├── 00_core/
├── 10_task_playbooks/
└── 90_index/
```

## After copying
1. Move your old raw `.md` files out of active `sys/`.
2. Put this cleaned `sys/` folder in place.
3. Rebuild your sync / embeddings.
4. Test with prompts from debugging, coding, research, writing, and general chat.

## Why this structure
Your app indexes every `*.md` file under `sys/`, so the active folder should contain only high-signal playbooks.
