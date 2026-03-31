# GraphRAG Agent — Setup & Usage Guide

A locally-run GraphRAG agent that indexes PDF and PPTX documents, builds a knowledge graph, and answers natural language questions through a browser chat interface. Runs entirely on your laptop — no cloud or paid APIs required by default, with optional cloud provider support via a simple `.env` configuration.

---

## Table of Contents

1. [Hardware & Software Requirements](#1-hardware--software-requirements)
2. [First-Time Installation](#2-first-time-installation)
3. [Model & Provider Configuration](#3-model--provider-configuration)
4. [LM Studio Setup (Default)](#4-lm-studio-setup-default)
5. [Running the Pipeline Step by Step](#5-running-the-pipeline-step-by-step)
6. [Starting the Chat UI](#6-starting-the-chat-ui)
7. [Querying from the Command Line](#7-querying-from-the-command-line)
8. [Checking Ingestion Stats](#8-checking-ingestion-stats)
9. [Resetting for a New Domain](#9-resetting-for-a-new-domain)
10. [Full CLI Reference](#10-full-cli-reference)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Hardware & Software Requirements

### Hardware

| Resource | Minimum | Notes |
|----------|---------|-------|
| RAM | 16 GB | 32 GB recommended for large corpora |
| VRAM | 4 GB | For GPU-accelerated LLM inference |
| Storage | 10 GB free | For models, embeddings, and graph data |

### Software

- **Python 3.10 or later**
- **LM Studio** — local AI model server (free) — required for the default setup
- **PowerShell** (Windows) — use PowerShell, not Git Bash, for reliable Ctrl+C behaviour

---

## 2. First-Time Installation

Open PowerShell, navigate to the project folder, and run:

```powershell
cd C:\path\to\Knowledge_Graph_v2

# Create and activate a virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install all dependencies
pip install -r requirements.txt
```

> All dependencies install via pip — no conda, Docker, or admin rights required.

---

## 3. Model & Provider Configuration

The system uses two AI models at different stages of the pipeline:

| Role | What it does | Used at |
|------|-------------|---------|
| **Embedding model** | Converts text into vectors for semantic search | Embed step + every query |
| **LLM** | Extracts entities from documents and generates answers | Graph step + every query |

### Default setup — LM Studio (no configuration needed)

Out of the box, both models are served by LM Studio running on your laptop. No `.env` file is required. If no `.env` file is present, the system automatically uses:

| Role | Default model | Server |
|------|--------------|--------|
| Embedding | `nomic-embed-text-v1.5` | LM Studio at `http://localhost:1234` |
| LLM | `Qwen2.5-7B-Instruct` | LM Studio at `http://localhost:1234` |

### Using a different model within LM Studio

You can load any instruction-following model in LM Studio and pass its name at runtime — no code changes, no `.env` file:

```powershell
# Graph step with a different LLM
python src/main.py graph --model "Mistral-7B-Instruct"

# Query step with a different LLM
python src/main.py query --question "Your question" --llm-model "Llama-3.1-8B-Instruct"
```

In the Chat UI sidebar, clear the **LLM Model** field and type your model name — takes effect on the next question.

> LM Studio ignores the model name string in the API call — it always runs whichever model is currently loaded in the Developer tab. The name you pass just needs to match what you have loaded so logs stay consistent.

**Model selection notes:**

| Factor | Notes |
|--------|-------|
| VRAM | Target Q4_K_M quantised models. 7B–8B models typically need 3.5–4.5 GB VRAM. |
| Instruction following | Use instruction-tuned variants (`-Instruct`, `-Chat`, `-it` suffixes). Base models do not follow prompts reliably. |
| DeepSeek R1 models | R1 distil models output a `<think>...</think>` reasoning block before the answer — this will appear in the chat UI. Use a DeepSeek V2/V3 Chat model for clean output. |
| Re-running the graph step | Switching LLM mid-project does not invalidate existing graph data. Only re-run `graph` if you want the new model to re-extract entities from scratch. |

### Using a cloud provider (Gemini, OpenAI, Anthropic, Ollama)

To use a cloud or alternative provider instead of LM Studio, create a `.env` file in the project root. A template is provided:

```powershell
copy .env.example .env
```

Then edit `.env` and fill in your provider and API key. The system reads this file on startup — no code changes needed.

**LLM provider examples:**

```env
# Gemini
LLM_PROVIDER=gemini
LLM_MODEL=gemini/gemini-2.0-flash
GEMINI_API_KEY=your-key-here

# OpenAI
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=your-key-here

# Anthropic (Claude)
LLM_PROVIDER=anthropic
LLM_MODEL=anthropic/claude-sonnet-4-5
ANTHROPIC_API_KEY=your-key-here

# Ollama (local, no API key)
LLM_PROVIDER=ollama
LLM_MODEL=ollama/qwen2.5:7b
```

**Embedding provider examples:**

```env
# OpenAI embeddings
EMBED_PROVIDER=openai
EMBED_MODEL=text-embedding-3-small
OPENAI_API_KEY=your-key-here

# Gemini embeddings
EMBED_PROVIDER=gemini
EMBED_MODEL=gemini/text-embedding-004
GEMINI_API_KEY=your-key-here

# Ollama embeddings (local)
EMBED_PROVIDER=ollama
EMBED_MODEL=ollama/nomic-embed-text
```

> **Important — embedding model consistency:** The embedding model used during the embed step must be the same model used at query time. If you change `EMBED_MODEL` after already building a corpus, the system will detect the mismatch and warn you before proceeding. You will need to re-run `python src/main.py embed` to rebuild the vector database with the new model.

When a `.env` file is present, LM Studio is no longer required for the configured steps (though you can still use it for the steps not covered by the `.env`).

---

## 4. LM Studio Setup (Default)

Skip this section if you are using a cloud provider via `.env` for both LLM and embedding steps.

### Download the models (one-time)

1. Open LM Studio
2. Go to the **Search** tab and download both models:

| Model | Purpose | Search for |
|-------|---------|------------|
| `nomic-embed-text-v1.5` | Text embeddings | `nomic-embed-text` |
| `Qwen2.5-7B-Instruct` | Answer generation & entity extraction | `qwen2.5-7b-instruct` |

> Choose a quantised version — **Q4_K_M** is recommended to fit within 4 GB VRAM.

### Starting the LM Studio server

In LM Studio, go to the **Developer** tab (or Local Server tab) and click **Start Server**. The server runs at `http://localhost:1234`.

### Which model to load at each stage

| Pipeline Stage | Model to load in LM Studio |
|---------------|---------------------------|
| Step 1 — Ingest | None required |
| Step 2 — Embed | `nomic-embed-text-v1.5` |
| Step 3 — Graph | `Qwen2.5-7B-Instruct` |
| Step 4 — Query / Chat UI | Both models loaded |

> LM Studio runs one model at a time by default. For the query and chat UI stage, load the embedding model first, then also load the LLM. They run sequentially (embedding for the query, LLM for the answer) and do not compete for VRAM simultaneously.

---

## 5. Running the Pipeline Step by Step

Run all commands from the project root with the virtual environment activated.

### Step 1 — Ingest documents

**LM Studio:** Not required for this step.

Extracts text from all PDF and PPTX files in a folder and stores chunks in a local SQLite database. Already-indexed files are skipped automatically on re-runs (SHA-256 deduplication).

```powershell
# Ingest from the default folder (Ingest_Documents/)
python src/main.py ingest

# Ingest from a specific folder
python src/main.py ingest --path C:\path\to\your\documents

# Ingest a single file
python src/main.py ingest --path C:\path\to\report.pdf
```

Expected output:
```
Ingestion complete in 12.4s
  Documents ingested: 42
  Documents skipped (already indexed): 0
  Total chunks stored: 1,847
  Database: data/chunks.db
```

---

### Step 2 — Generate embeddings

**LM Studio (default):** Load `nomic-embed-text-v1.5` and start the server before running this step.
**Cloud provider:** Ensure `EMBED_PROVIDER` and the relevant API key are set in `.env`.

Converts every text chunk into a vector embedding stored in ChromaDB. These embeddings power the semantic search when you ask a question.

```powershell
python src/main.py embed
```

Expected output:
```
Embedding complete in 94.3s
  Chunks embedded: 1,847
  API batches: 37
  ChromaDB: data/chroma_db
```

> This step can take several minutes for large corpora. Progress is shown per batch.

---

### Step 3 — Build the knowledge graph

**LM Studio (default):** Switch to `Qwen2.5-7B-Instruct` and ensure the server is running.
**Cloud provider:** Ensure `LLM_PROVIDER` and the relevant API key are set in `.env`.

Uses the LLM to extract named entities (companies, technologies, products, people) and their relationships from each chunk. Stores them in a KuzuDB graph database, linked back to source documents for citations.

```powershell
python src/main.py graph
```

Expected output:
```
Knowledge graph complete in 648.2s
  Chunks processed: 1,847
  Entities extracted: 3,241
  LLM batches: 185
  Graph explosion alert: No
  KuzuDB: data/kuzu_db
  State: data/extraction_state.json
```

> This is the slowest step — the LLM processes every chunk. For 500 documents expect 30–90 minutes depending on hardware. The checkpoint file (`data/extraction_state.json`) lets you resume if the process is interrupted.

---

## 6. Starting the Chat UI

**LM Studio (default):** Both models must be loaded (`nomic-embed-text-v1.5` and `Qwen2.5-7B-Instruct`).
**Cloud provider:** Ensure your `.env` is configured with both `LLM_PROVIDER` and `EMBED_PROVIDER`.

```powershell
streamlit run app.py
```

Then open your browser at **http://localhost:8501**.

The first page load takes 20–60 seconds while Python loads the database libraries. Subsequent loads in the same session are instant.

### Using the chat interface

- Type your question in the input box at the bottom and press **Enter**
- A spinner shows while the system retrieves relevant documents (~2–5 seconds)
- The answer streams in token by token — you see it being written live
- Click **"Sources (N cited)"** below any answer to see the referenced documents with confidence ratings (HIGH = strong evidence, LOW = mentioned once or twice)

### Advanced settings (sidebar)

| Setting | Default | Effect |
|---------|---------|--------|
| LLM Model | `Qwen2.5-7B-Instruct` | Change if you load a different LLM in LM Studio (ignored when using a `.env` cloud provider) |
| Top-K retrieval results | 10 | Number of document chunks retrieved before graph expansion |
| Context token budget | 3000 | Tokens of retrieved text sent to the LLM. Higher = richer answers, slower generation. Safe range: 500–8000 |

### Stopping the server

Press **Ctrl+C** in the PowerShell window where Streamlit is running.

> If the process does not stop, run in a separate PowerShell window:
> ```powershell
> Get-Process python | Stop-Process -Force
> ```

---

## 7. Querying from the Command Line

**LM Studio (default):** Both models must be loaded.
**Cloud provider:** Ensure your `.env` is configured.

For quick one-off questions without opening the browser:

```powershell
python src/main.py query --question "What EV strategies did Toyota adopt?"
```

With optional parameters:

```powershell
python src/main.py query `
  --question "What supply chain risks did we identify for OEMs?" `
  --top-k 15 `
  --llm-model "Qwen2.5-7B-Instruct" `
  --embed-model "nomic-embed-text-v1.5"
```

---

## 8. Checking Ingestion Stats

View how many documents and chunks are in the database at any time — no LM Studio required:

```powershell
python src/main.py stats
```

Output:
```
Database: data/chunks.db
  Documents: 42
  Chunks total: 1,847
  Chunks pending embedding: 0
```

`Chunks pending embedding: 0` means the embed step is up to date. A non-zero number means you have ingested new documents but haven't run `embed` yet.

---

## 9. Resetting for a New Domain

To index a completely different set of documents (e.g., switching from automotive to another domain), clear the existing knowledge base first:

```powershell
# Interactive — shows what will be deleted and asks for confirmation
python src/main.py clear

# Non-interactive (for scripts)
python src/main.py clear --force
```

This deletes:
- `data/chunks.db` — document and chunk database
- `data/chroma_db/` — vector embeddings
- `data/kuzu_db/` — knowledge graph
- `data/extraction_state.json` — extraction checkpoint

Then run the full pipeline again from Step 1 with the new document folder.

---

## 10. Full CLI Reference

### Get help

```powershell
# List all available commands
python src/main.py --help

# Help for a specific command
python src/main.py ingest --help
python src/main.py embed --help
python src/main.py graph --help
python src/main.py query --help
python src/main.py stats --help
python src/main.py clear --help
```

### All commands

#### `ingest` — Extract and store document chunks
```
python src/main.py ingest [--path PATH] [--db DB]

  --path PATH    File or directory to ingest (default: Ingest_Documents/)
  --db DB        SQLite database path (default: data/chunks.db)
```

#### `embed` — Generate vector embeddings
```
python src/main.py embed [--db DB] [--chroma CHROMA] [--model MODEL]

  --db DB          SQLite database path (default: data/chunks.db)
  --chroma CHROMA  ChromaDB path (default: data/chroma_db)
  --model MODEL    Embedding model name (default: nomic-embed-text-v1.5)
                   Overridden by EMBED_MODEL in .env if set
```

#### `graph` — Build the knowledge graph
```
python src/main.py graph [--db DB] [--graph GRAPH] [--model MODEL] [--state STATE]

  --db DB        SQLite database path (default: data/chunks.db)
  --graph GRAPH  KuzuDB directory path (default: data/kuzu_db)
  --model MODEL  LLM model name (default: Qwen2.5-7B-Instruct)
                 Overridden by LLM_MODEL in .env if set
  --state STATE  Extraction checkpoint file (default: data/extraction_state.json)
```

#### `query` — Answer a question from the command line
```
python src/main.py query --question QUESTION [options]

  --question QUESTION      Natural language question (required)
  --db DB                  SQLite database path (default: data/chunks.db)
  --chroma CHROMA          ChromaDB path (default: data/chroma_db)
  --graph GRAPH            KuzuDB directory path (default: data/kuzu_db)
  --embed-model MODEL      Embedding model name (default: nomic-embed-text-v1.5)
  --llm-model MODEL        LLM model name (default: Qwen2.5-7B-Instruct)
  --top-k N                Vector results before graph expansion (default: 10)
```

#### `stats` — Show database statistics
```
python src/main.py stats [--db DB]

  --db DB    SQLite database path (default: data/chunks.db)
```

#### `clear` — Delete all indexed data
```
python src/main.py clear [--db DB] [--chroma CHROMA] [--graph GRAPH] [--state STATE] [--force]

  --db DB          SQLite database path (default: data/chunks.db)
  --chroma CHROMA  ChromaDB path (default: data/chroma_db)
  --graph GRAPH    KuzuDB directory path (default: data/kuzu_db)
  --state STATE    Extraction checkpoint file (default: data/extraction_state.json)
  --force          Skip confirmation prompt
```

---

## 11. Troubleshooting

### "LM Studio is not running or not reachable at localhost:1234"
- Open LM Studio and click **Start Server** in the Developer/Local Server tab
- Ensure the correct model is loaded for the current step (see [LM Studio Setup](#4-lm-studio-setup-default))
- Check LM Studio shows the server status as **Running**

### "No module named 'openai'" or similar import error
```powershell
pip install -r requirements.txt
```

### Graph step interrupted midway
The graph step saves progress to `data/extraction_state.json`. Simply re-run `python src/main.py graph` and it will resume from where it stopped — already-processed chunks are skipped.

### "Database path cannot be a directory" (KuzuDB error)
KuzuDB creates its own database folder. If you manually created `data/kuzu_db/` as an empty folder, delete it first:
```powershell
Remove-Item -Recurse -Force data\kuzu_db
python src/main.py graph
```

### Streamlit page blank for a long time on first load
Normal behaviour — Python is importing the database libraries (KuzuDB, ChromaDB) for the first time. Wait 20–60 seconds. Subsequent loads in the same session are fast.

### Ctrl+C not stopping Streamlit
Use PowerShell (not Git Bash). If still stuck:
```powershell
Get-Process python | Stop-Process -Force
```

### Query answers seem thin or low-confidence
- Increase **Top-K** (try 15–20) to retrieve more candidate chunks
- Increase **Context token budget** in the sidebar (try 4000–5000)
- Check `python src/main.py stats` — if "Chunks pending embedding" is non-zero, run `embed` again
- Ensure the graph step completed fully (check entity count in the `graph` output)

### "Embedding model mismatch" warning
This appears when the `EMBED_MODEL` in your `.env` differs from the model used to build the existing corpus. You must re-run the embed step to rebuild the vector database with the new model:
```powershell
python src/main.py embed
```
Type `yes` when prompted to confirm. This overwrites the existing embeddings.

### Adding more documents to an existing knowledge base
No need to clear. Just run ingest and embed again — new documents are added incrementally, already-indexed files are skipped:
```powershell
python src/main.py ingest --path C:\path\to\new\documents
python src/main.py embed
# Re-run graph to extract entities from new documents
python src/main.py graph
```
