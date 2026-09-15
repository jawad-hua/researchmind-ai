# 🤖 ResearchMind AI

An AI research agent that takes a topic (or question) and autonomously
plans, searches the web, and writes a structured, cited report — no
manual research required.

## How it works

```
User Query
   ↓
Planner        → LLM breaks the topic into focused sub-questions
   ↓
Web Search     → Tavily API searches the web for each sub-question
   ↓
Extractor      → cleans results into a citable evidence bundle
   ↓
Synthesizer    → LLM writes a structured report with inline [S1][S2] citations
   ↓
Fact-Checker   → LLM reviews its own report against the evidence
   ↓
Report + Sources + PDF export
```

## Features (Phase 1)

- 🔎 Multi-step research agent (query decomposition, not a single search call)
- 📚 Automatic source citation, deduplicated across sub-questions
- ✅ Self fact-checking pass
- 📄 One-click PDF export of the final report
- 🎨 Streamlit dashboard with live pipeline status

## Roadmap

- **Phase 2:** PDF/document upload + RAG (vector DB) so the agent can
  research from user-provided documents alongside the web
- **Phase 3:** FastAPI backend, Docker deployment, streaming responses,
  conversation memory

## Tech Stack

Python · Groq (Llama 3.3 70B) · Tavily Search API · Streamlit · fpdf2

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
