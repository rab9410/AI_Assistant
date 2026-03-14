# Tool Use Playbook

## Purpose
Makes tool usage disciplined, fast, and reliable.

## Use Tools When
- The request needs live or current information.
- The answer depends on external state.
- A lookup, search, market price, weather check, time lookup, or current news check is required.
- Verification matters more than general background knowledge.

## Do Not Use Tools When
- The task is conceptual, explanatory, or creative.
- Stable knowledge is enough.
- The tool would add noise without improving the answer.

## Decision Rules
1. Decide whether the question is current or stable.
2. If current, emit the tool call immediately.
3. If multiple steps are required, chain tools in the minimum useful order.
4. After results return, summarize what matters instead of dumping raw output.
5. If a tool fails, say so and fall back gracefully where possible.

## Priority Order
1. Live tool results
2. User-provided facts and files
3. Retrieved knowledge base playbooks
4. General model knowledge

## Output Discipline
- Return tool requests in the exact required schema.
- Do not say “let me check” when a tool call is required.
- Do not invent live data.
