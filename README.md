# AI-Based Research Paper Analyst

Local research workspace for ingesting research-paper PDFs, searching their
content, asking cited questions, comparing papers, and exporting Markdown or
PDF reports.

## Requirements

- Python 3.11
- Node.js 20.19+ or 22.12+
- [Ollama](https://ollama.com/) with the configured model available locally

The first PDF ingestion may take longer while the embedding model is downloaded
and initialized. Research-paper analysis and chat use the local Ollama model.
The analysis includes a detailed findings-oriented summary and extracts
detectable PDF figures, tables, equations, and numerical calculations for
display in the paper workspace.

## Run locally on Windows

Open two PowerShell terminals from the repository root.

### 1. Backend

Create the virtual environment and install dependencies once:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

Set up the Ollama model before starting the backend:

```powershell
ollama pull llama3.2:3b
Copy-Item .env.example .env
```

Make sure Ollama is running. The Ollama desktop app normally starts it
automatically; otherwise run `ollama serve` in a separate terminal. The `.env`
file is ignored by Git and can be used to change the model or Ollama URL.

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

- `LLM_MODEL`: defaults to `llama3.2:3b`; must be pulled with `ollama pull`
- `OLLAMA_BASE_URL`: defaults to `http://127.0.0.1:11434`
- `DATA_DIR`: SQLite database, uploaded PDFs, reports, and Chroma index
- `CORS_ORIGINS`: comma-separated browser origins when using a custom frontend
  URL

Do not commit API keys or other secrets. Local research data is stored under
`backend/data` by default and is ignored by Git.

Existing papers can be processed again with **Re-analyze PDF** after fixing
configuration or correcting a failed analysis. Re-analyze papers already in
the library once to generate the expanded findings and refresh their extracted
figures, tables, and calculations.

## Validate changes

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
.\.venv\Scripts\python.exe -m ruff check backend\app
Set-Location frontend
npm run build
npm run lint
```

Comparisons use retrieved passages and page citations. PDF reports include the
saved analysis details and embed extracted figures and table previews. Multi-
paper reports include a comparison table, and chat/comparison citations open
their exact stored passage with its page and section. Chat validates model
answers against retrieval and falls back to relevant excerpts when generation
fails.
