# RottenPoodles AI 🧠🐩
RottenPoodles AI is a modular desktop AI assistant built in Python with a modern UI, tool execution engine, knowledge retrieval system (RAG), and autonomous reasoning loop.

It combines:

* AI chat
* real-time tools
* knowledge retrieval
* persistent memory
* chart generation
* modular architecture
* The goal of the project is to create a personal AI operating system style assistant that can be extended with tools, knowledge playbooks, and automation.

## Features
* AI Assistant
* Structured AI agent with a strict JSON output contract
* Supports multiple model providers
* Autonomous tool execution loop
* Persistent memory
* Markdown responses
* Chart generation
* Real-Time Tools
* The assistant can call tools for live data.

## Tool	Function
* Weather	Current weather + forecast
* Search	Web search
* Market	Stock prices
* Crypto	Cryptocurrency prices
* Currency	Exchange rate conversion
* News	Current news
* Time	Local time lookup
* The AI emits structured JSON tool calls which the system executes automatically.

## Knowledge System (RAG)
RottenPoodles AI uses Retrieval Augmented Generation (RAG).

Knowledge files placed in: _/sys_

are automatically:
* scanned
* chunked
* embedded
* indexed
* retrieved during queries

__This allows the assistant to reason using custom playbooks and documents.__

## Memory System
The assistant supports persistent memory using:

_[LEARN: KEY | VALUE]_

__Example:__ _[LEARN: USER_PREFERRED_LANGUAGE | Python]_

Memory is stored in: _data/memory_store.json_

## Chart Generation
The assistant can generate charts directly inside the chat UI.

Supported chart types:

* Line
* Bar
* Pie
* Scatter
* Histogram
* Charts are rendered and displayed automatically.

## Modern UI
Built with PySide6 (Qt).

__Features:__

* ChatGPT-style chat interface
* AI / User avatars
* animated buttons
* auto-growing input box
* thread switching
* markdown rendering
* chart lightbox viewer

## Architecture
User > GUI > AI Worker (Agent Loop) > Tool Execution > Knowledge Retrieval (RAG) > Model API

## Project Structure
app/ 
  ai_worker.py 
  config.py 
  markdown_renderer.py 
  prompts.py 
  rag.py 
  sync_worker.py 
  tools.py 
  ui_components.py 
  utils.py 
  playbook_router.py

data/ 
knowledge_base/ 
logs/ 
threads/ 
memory_store.json 
threads_meta.json

sys/ 
playbooks 
knowledge files

sys_archive/ 
archived knowledge

GUI.py

## Installation
1. Clone the repository
_bash git clone https://github.com/rab9410/AI_Assistant.git_
_cd AI_Assistant_

_pip install PySide6 requests torch sentence-transformers matplotlib openai beautifulsoup4_

## API Keys Setup

RottenPoodles AI supports two model providers.
__You must add API keys as environment variables.__

* Groq API (Recommended)
Groq provides fast inference for models like Llama.

Create a key here: https://console.groq.com/keys

Environment variable name: __groq_api__

Example:
Windows _setx groq_api YOUR_API_KEY_
Mac / Linux _export groq_api=YOUR_API_KEY_

* HuggingFace Router API
Used for accessing hosted models.

Create a key here: https://huggingface.co/settings/tokens

Environment variable name: __HF_TOKEN__

Example:
* Windows _setx HF_TOKEN YOUR_API_KEY_
* Mac / Linux _export HF_TOKEN=YOUR_API_KEY_

## Run the Assistant

Start the application with:

__python GUI.py__
__Knowledge Sync__

When you add or modify files inside the _/sys_ folder, run: __Sync Knowledge__
The system will: scan /sys chunk documents generate embeddings rebuild the vector index

## Security

The assistant includes safety guardrails:

* strict JSON output contract
* tool whitelist validation
* prompt injection resistance
* no system prompt disclosure
* sensitive topic handling

## Future Improvements

Planned upgrades:

* reasoning planner stage
* autonomous agents
* plugin tool system
* local model support
* workflow automation
* improved playbook routing
* streaming responses

## License
MIT License

## Author
R.A.B

GitHub: https://github.com/rab9410
