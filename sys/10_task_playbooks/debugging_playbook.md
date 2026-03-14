# Debugging Playbook

## Purpose
Makes bug diagnosis systematic.

## Method
1. Restate the bug clearly.
2. Read the actual error or symptom.
3. Identify the likely layer (UI, state, tool, parsing, storage, network, logic).
4. Rank probable causes.
5. Propose the smallest effective fix.
6. Explain why it works.
7. Give validation steps.
8. Mention likely regressions to watch for.

## Watch For
- Silent exception swallowing.
- Schema mismatches.
- JSON parsing issues.
- Retry loops without diagnostics.
- Cache / embedding staleness.
- UI/state desync.
- Background save failures.
- Prompt bloat and context overflow.
