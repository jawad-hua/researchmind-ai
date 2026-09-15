"""
ResearchMind AI — Phase 1 MVP entrypoint.

Pipeline: Query -> Planner -> Web Search -> Extractor -> Synthesizer
          -> (optional) Fact-Checker -> Report + Sources -> PDF export

UI: a minimal, chat-style interface (native Streamlit chat components)
with a restrained, neutral visual design — no emoji, no decoration.
"""

import os
import tempfile
import streamlit as st

from agent.planner import plan_subquestions
from agent.search import search_web
from agent.extractor import collect_all_evidence
from agent.synthesizer import build_report, append_sources_section
from agent.fact_checker import fact_check_report
from utils.pdf_export import markdown_to_pdf

st.set_page_config(page_title="ResearchMind AI", layout="wide")

# ---------------------------------------------------------------------------
# Visual design: restrained, neutral, no default Streamlit chrome/colors.
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    #MainMenu, footer, header {visibility: hidden;}

    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                     "Helvetica Neue", Arial, sans-serif;
    }

    :root {
        --bg: #ffffff;
        --bg-secondary: #f7f7f8;
        --text-primary: #0d0d0d;
        --text-secondary: #6e6e80;
        --border: #e5e5e5;
        --accent: #202123;
        --accent-contrast: #ffffff;
    }

    @media (prefers-color-scheme: dark) {
        :root {
            --bg: #212121;
            --bg-secondary: #171717;
            --text-primary: #ececec;
            --text-secondary: #9b9b9b;
            --border: #2f2f2f;
            --accent: #ececec;
            --accent-contrast: #0d0d0d;
        }
    }

    .stApp {
        background-color: var(--bg);
    }

    [data-testid="stSidebar"] {
        background-color: var(--bg-secondary);
        border-right: 1px solid var(--border);
    }

    [data-testid="stSidebar"] * {
        color: var(--text-primary);
    }

    .block-container {
        max-width: 48rem;
        padding-top: 2.5rem;
        padding-bottom: 6rem;
    }

    h1 {
        font-size: 1.5rem;
        font-weight: 600;
        color: var(--text-primary);
        letter-spacing: -0.01em;
    }

    .subtitle {
        color: var(--text-secondary);
        font-size: 0.95rem;
        margin-top: -0.5rem;
        margin-bottom: 2rem;
    }

    [data-testid="stChatMessage"] {
        background-color: transparent;
        border-bottom: 1px solid var(--border);
        padding: 1.25rem 0;
    }

    [data-testid="stChatMessageContent"],
    .stMarkdown, .stMarkdown p, .stMarkdown li,
    .stMarkdown h1, .stMarkdown h2, .stMarkdown h3,
    .stMarkdown table, .stMarkdown td, .stMarkdown th {
        color: var(--text-primary) !important;
    }

    .stMarkdown a {
        color: var(--accent) !important;
    }

    [data-testid="stChatInput"] textarea {
        color: var(--text-primary);
        background-color: var(--bg);
    }

    .stButton > button {
        border-radius: 6px;
        border: 1px solid var(--border);
        background-color: var(--bg);
        color: var(--text-primary);
        font-weight: 500;
        padding: 0.4rem 1rem;
    }

    .stButton > button:hover {
        border-color: var(--accent);
        color: var(--accent);
    }

    .stDownloadButton > button {
        border-radius: 6px;
        background-color: var(--accent);
        color: var(--accent-contrast);
        border: none;
        font-weight: 500;
    }

    [data-testid="stChatInput"] {
        border-color: var(--border);
    }

    .status-line {
        color: var(--text-secondary);
        font-size: 0.85rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("ResearchMind AI")
st.markdown(
    '<div class="subtitle">Give it a topic. It researches the web and writes a cited report.</div>',
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("**Settings**")
    run_fact_check = st.checkbox("Fact-check pass", value=True)
    results_per_subq = st.slider("Search results per sub-question", 2, 8, 5)
    st.markdown("---")
    with st.expander("How it works"):
        st.markdown(
            "Query, planner, web search, extractor, synthesizer, "
            "fact-checker, final report with sources."
        )

if "messages" not in st.session_state:
    st.session_state.messages = []  # list of {role, content, pdf_ready?}

# Render conversation history
for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"], avatar=None):
        st.markdown(msg["content"])
        if msg["role"] == "assistant" and msg.get("report_markdown"):
            if st.button("Prepare PDF", key=f"prep_pdf_{i}"):
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                    pdf_path = markdown_to_pdf(
                        msg["report_markdown"],
                        title=msg.get("topic", "Research Report")[:60],
                        output_path=tmp.name,
                    )
                st.session_state[f"pdf_path_{i}"] = pdf_path

            pdf_path = st.session_state.get(f"pdf_path_{i}")
            if pdf_path and os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f:
                    st.download_button(
                        "Download PDF",
                        data=f.read(),
                        file_name="research_report.pdf",
                        mime="application/pdf",
                        key=f"dl_pdf_{i}",
                    )

topic = st.chat_input("Ask ResearchMind AI to research something...")

if topic:
    st.session_state.messages.append({"role": "user", "content": topic})
    with st.chat_message("user", avatar=None):
        st.markdown(topic)

    with st.chat_message("assistant", avatar=None):
        if not os.getenv("GROQ_API_KEY") or not os.getenv("TAVILY_API_KEY"):
            error_text = "Missing API keys. Add GROQ_API_KEY and TAVILY_API_KEY to your .env file."
            st.markdown(error_text)
            st.session_state.messages.append({"role": "assistant", "content": error_text})
            st.stop()

        status_box = st.empty()

        status_box.markdown('<span class="status-line">Planning sub-questions...</span>', unsafe_allow_html=True)
        subquestions = plan_subquestions(topic)

        status_box.markdown('<span class="status-line">Searching the web...</span>', unsafe_allow_html=True)
        evidence_bundles = collect_all_evidence(
            subquestions,
            search_fn=lambda q: search_web(q, max_results=results_per_subq),
        )

        errors = [b["error"] for b in evidence_bundles if b.get("error")]
        total_sources = sum(len(b["sources"]) for b in evidence_bundles)

        if total_sources == 0:
            status_box.empty()
            error_text = "No search results found."
            if errors:
                error_text += f" Error: {errors[0]}"
            error_text += " Check your Tavily API key and quota."
            st.markdown(error_text)
            st.session_state.messages.append({"role": "assistant", "content": error_text})
            st.stop()

        status_box.markdown('<span class="status-line">Writing the report...</span>', unsafe_allow_html=True)
        result = build_report(topic, evidence_bundles)
        report_md = result["report_markdown"]
        sources = result["sources"]

        fact_check_notes = ""
        if run_fact_check:
            status_box.markdown('<span class="status-line">Fact-checking...</span>', unsafe_allow_html=True)
            evidence_blob = "\n\n".join(b["evidence_text"] for b in evidence_bundles)
            fact_check_notes = fact_check_report(report_md, evidence_blob)

        status_box.empty()

        final_report = append_sources_section(report_md, sources)
        if fact_check_notes:
            final_report += f"\n\n{fact_check_notes}"

        st.markdown(final_report)
        st.session_state.messages.append({
            "role": "assistant",
            "content": final_report,
            "report_markdown": final_report,
            "topic": topic,
        })
        st.rerun()
