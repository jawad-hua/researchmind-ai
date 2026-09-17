# ResearchMind AI

An AI research agent that takes a topic (or question) and autonomously
plans, searches the web, and writes a structured, cited report — no
manual research required. Upload PDFs and it researches from them
alongside the live web, in the same cited report.

## Architecture

```
Streamlit Frontend (UI)  --HTTP-->  FastAPI Backend (API)
                                            |
                                    Planner -> Web Search + Document
                                    Retrieval (ChromaDB) -> Synthesizer
                                    -> Fact-Checker -> Report
                                            |
                                    Groq (LLM) + Tavily (Search)
```

The frontend is a pure UI layer with no research logic of its own —
every step of the pipeline runs in the backend API. This means the
backend could serve a mobile app, a CLI, or another frontend without
any changes to the agent code.

## Features

- Multi-step research agent (query decomposition, not a single search call)
- Retrieval-augmented research: upload PDFs and the agent researches from
  them alongside the live web, in the same cited report
- Automatic source citation, deduplicated across sub-questions and documents
- Self fact-checking pass, including citation-accuracy checks
- Streaming responses: the report renders token-by-token as it's generated
- One-click PDF export with full Unicode support and rendered tables
- Minimal, chat-style Streamlit interface, adapts to system light/dark theme
- FastAPI backend with a documented REST API (`/docs` for interactive Swagger UI)
- Dockerized: backend and frontend run as separate containers via Docker Compose
- Automated test suite (pytest) covering the agent pipeline, vector store,
  and every backend endpoint, run automatically in CI on every push (GitHub Actions)

## Roadmap

- Persistent (disk-backed) vector store, smarter chunking
- Conversation memory across research sessions
- Structured logging and centralized config

## Tech Stack

Python, FastAPI, Groq (LLM inference), Tavily Search API, ChromaDB
(vector store), Streamlit, pypdf, fpdf2, Docker, pytest, GitHub Actions

## Running locally (without Docker)

Needs two terminals — one for the backend, one for the frontend.

```bash
git clone <your-repo-url>
cd researchmind-ai
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env      # then fill in your API keys
```

Terminal 1 — backend:
```bash
uvicorn backend.main:app --reload --port 8000
```

Terminal 2 — frontend:
```bash
streamlit run app.py
```

Get free API keys:
- Groq: https://console.groq.com
- Tavily: https://tavily.com

## Running with Docker

```bash
cp .env.example .env      # fill in GROQ_API_KEY and TAVILY_API_KEY
docker compose up --build
```

- Frontend: http://localhost:8501
- Backend API docs (Swagger UI): http://localhost:8000/docs

## API Overview

- `POST /sessions` — start a research session, returns a `session_id`
- `POST /sessions/{id}/documents` — upload PDF(s) to research alongside the web
- `GET /sessions/{id}/documents` — list documents indexed in this session
- `DELETE /sessions/{id}/documents/{source_key}` — remove an indexed document
- `POST /sessions/{id}/research` — run the full pipeline, returns the cited report
- `POST /sessions/{id}/research/stream` — same pipeline, streamed as Server-Sent Events
  (`status`, `token`, `done`, `error`)
- `GET /health` — service + API key status

Full interactive documentation is auto-generated at `/docs` when the backend is running.

## Running the tests

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest -v
```

The suite mocks every LLM call, web search, and the embedding model, so it
runs fully offline in a couple of seconds. It also runs automatically on
every push via GitHub Actions (see `.github/workflows/tests.yml`).

## Example

**Input:** "Explain the latest trends in Generative AI and make a 5-page report."

**Output:** A structured markdown report with sections, inline citations
`[S1]`, `[S2]`, a sources list, a fact-check verdict, and a downloadable PDF.

## License

MIT
