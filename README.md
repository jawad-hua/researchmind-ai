# ResearchMind AI

An AI research agent that takes a topic (or question) and autonomously
plans, searches the web, and writes a structured, cited report — no
manual research required.

## How it works

```
User Query
   |
Planner        -> LLM breaks the topic into focused sub-questions
   |
Web Search     -> Tavily API searches the web for each sub-question
   |
Extractor      -> cleans results into a citable evidence bundle
   |
Synthesizer    -> LLM writes a structured report with inline [S1][S2] citations
   |
Fact-Checker   -> LLM reviews its own report against the evidence
   |
Report + Sources + PDF export
```

## Features

- Multi-step research agent (query decomposition, not a single search call)
- Retrieval-augmented research: upload PDFs and the agent researches from
  them alongside the live web, in the same cited report
- Automatic source citation, deduplicated across sub-questions and documents
- Self fact-checking pass
- One-click PDF export with full Unicode support and rendered tables
- Minimal, chat-style Streamlit interface, adapts to system light/dark theme

## Roadmap

- **Phase 3:** FastAPI backend, Docker deployment, streaming responses,
  conversation memory
- **Phase 4:** persistent (disk-backed) vector store, smarter chunking

## Tech Stack

Python, Groq (LLM inference), Tavily Search API, ChromaDB (vector store),
Streamlit, pypdf, fpdf2

## Setup

```bash
git clone <your-repo-url>
cd researchmind-ai
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env      # then fill in your API keys
streamlit run app.py
```

Get free API keys:
- Groq: https://console.groq.com
- Tavily: https://tavily.com

## Example

**Input:** "Explain the latest trends in Generative AI and make a 5-page report."

**Output:** A structured markdown report with sections, inline citations
`[S1]`, `[S2]`, a sources list, a fact-check verdict, and a downloadable PDF.

## License

MIT
