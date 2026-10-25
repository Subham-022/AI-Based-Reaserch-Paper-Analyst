# AI-Based Research Paper Analyst

Local research workspace for ingesting research-paper PDFs, searching their
content, asking cited questions, comparing papers, and exporting Markdown or
PDF reports.

## Requirements

- Python 3.11
- Node.js 20.19+ or 22.12+
- Ollama for the default local language model (`llama3.2:3b`)

The first PDF ingestion or chat request may take longer while the embedding
model is downloaded and initialized. If Ollama is unavailable or times out,
Chat returns retrieved source passages with page citations instead of an
unsupported generated answer.

## Run locally on Windows

Open two PowerShell terminals from the repository root.

### 1. Backend

Create the virtual environment and install dependencies once:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

Ensure the default model is downloaded:

```powershell
ollama pull llama3.2:3b
```

Ollama usually runs as a background app on Windows. If it is not running,
start it in a separate terminal and leave that terminal open:

```powershell
ollama serve
```

Start FastAPI:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The API health endpoint is <http://127.0.0.1:8000/health>; interactive API docs
are at <http://127.0.0.1:8000/docs>.

### 2. Frontend

In the second terminal:

```powershell
Set-Location frontend
npm ci
npm run dev
```

Open <http://127.0.0.1:4174/library>. The Vite config binds to loopback and uses
a strict, fixed port so it cannot silently switch to another URL.

## Configuration

Defaults are defined in `backend/app/config.py` and can be overridden with
environment variables:

- `LLM_PROVIDER`: `ollama` (default), `anthropic`, or `openai-compatible`
- `LLM_MODEL`: defaults to `llama3.2:3b`
- `OLLAMA_BASE_URL`: defaults to `http://127.0.0.1:11434`
- `LLM_API_KEY` and `LLM_BASE_URL`: for remote LLM providers
- `DATA_DIR`: SQLite database, uploaded PDFs, reports, and Chroma index
- `CORS_ORIGINS`: comma-separated browser origins when using a custom frontend
  URL

Do not commit API keys or other secrets. Local research data is stored under
`backend/data` by default and is ignored by Git.

## Validate changes

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
.\.venv\Scripts\python.exe -m ruff check backend\app
Set-Location frontend
npm run build
npm run lint
```

Reports and comparisons use retrieved passages and page citations. Multi-paper
reports include a comparison table, and chat/comparison citations open their
exact stored passage with its page and section. Chat validates model answers
against retrieval and falls back to relevant excerpts when generation fails.
