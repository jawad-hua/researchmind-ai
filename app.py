"""
ResearchMind AI — Streamlit frontend.

Phase 3: this is now a pure UI layer with no agent logic of its own —
every piece of work (planning, search, retrieval, synthesis, fact-check,
PDF export) happens through HTTP calls to the FastAPI backend
(backend/main.py). This mirrors a real production split between a
frontend and an API service, and means the backend could be swapped
for a mobile app, a CLI, or another UI without touching agent code.
"""

import json
import os
import tempfile

import requests
import streamlit as st

from utils.pdf_export import markdown_to_pdf

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="ResearchMind AI", layout="wide")

# ---------------------------------------------------------------------------
# Visual design: restrained, neutral, no default Streamlit chrome/colors.
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    #MainMenu, footer {visibility: hidden;}
    header {background-color: transparent;}

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


def ensure_session():
    """Create a backend session once per browser session and cache the id."""
    if "session_id" in st.session_state:
        return
    try:
        r = requests.post(f"{BACKEND_URL}/sessions", timeout=10)
        r.raise_for_status()
        st.session_state.session_id = r.json()["session_id"]
    except requests.exceptions.RequestException as e:
        st.session_state.session_id = None
        st.session_state.backend_error = str(e)


ensure_session()

if not st.session_state.get("session_id"):
    st.error(
        f"Can't reach the backend at {BACKEND_URL}. "
        f"Make sure it's running (`uvicorn backend.main:app`). "
        f"Details: {st.session_state.get('backend_error', 'unknown error')}"
    )
    st.stop()

session_id = st.session_state.session_id

with st.sidebar:
    st.markdown("**Settings**")
    run_fact_check = st.checkbox("Fact-check pass", value=True)
    results_per_subq = st.slider("Search results per sub-question", 2, 8, 5)
    st.markdown("---")

    st.markdown("**Documents**")
    uploaded_files = st.file_uploader(
        "Upload PDFs to research alongside the web",
        type=["pdf"],
        accept_multiple_files=True,
    )

    if "indexed_files" not in st.session_state:
        # local mirror of the backend's session document list:
        # {(name, size): {"source_key": ..., "name": ...}}
        st.session_state.indexed_files = {}

    current_keys = {(f.name, f.size): f for f in (uploaded_files or [])}

    # A file removed from the widget gets removed on the backend too.
    removed = [k for k in st.session_state.indexed_files if k not in current_keys]
    for k in removed:
        entry = st.session_state.indexed_files[k]
        try:
            requests.delete(
                f"{BACKEND_URL}/sessions/{session_id}/documents/{entry['source_key']}",
                timeout=10,
            )
        except requests.exceptions.RequestException:
            pass  # best-effort cleanup; stale backend doc is harmless if this fails
        del st.session_state.indexed_files[k]

    # New files in the widget get uploaded to the backend.
    new = [k for k in current_keys if k not in st.session_state.indexed_files]
    if new:
        with st.spinner(f"Indexing {len(new)} document(s)..."):
            files_payload = [
                ("files", (current_keys[k].name, current_keys[k].getvalue(), "application/pdf"))
                for k in new
            ]
            try:
                r = requests.post(
                    f"{BACKEND_URL}/sessions/{session_id}/documents",
                    files=files_payload,
                    timeout=120,
                )
                r.raise_for_status()
                # Backend returns the full current list; rebuild our local mirror from it.
                indexed = r.json()["indexed"]
                st.session_state.indexed_files = {}
                for k in current_keys:
                    f = current_keys[k]
                    match = next((e for e in indexed if e["name"] == f.name), None)
                    if match:
                        st.session_state.indexed_files[k] = match
            except requests.exceptions.RequestException as e:
                st.error(f"Upload failed: {e}")

    if st.session_state.indexed_files:
        st.caption(f"{len(st.session_state.indexed_files)} document(s) indexed:")
        for entry in st.session_state.indexed_files.values():
            st.caption(f"\u2014 {entry['name']}")

    st.markdown("---")
    with st.expander("How it works"):
        st.markdown(
            "Query, planner, web search plus document retrieval, extractor, "
            "synthesizer, fact-checker, final report with sources. "
            "All of it runs in the backend API; this page is just the UI."
        )

if "messages" not in st.session_state:
    st.session_state.messages = []

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
        status_box = st.empty()
        report_box = st.empty()
        accumulated_text = ""
        final_report = None
        error_text = None

        try:
            with requests.post(
                f"{BACKEND_URL}/sessions/{session_id}/research/stream",
                json={
                    "topic": topic,
                    "results_per_subquestion": results_per_subq,
                    "run_fact_check": run_fact_check,
                },
                stream=True,
                timeout=300,
            ) as resp:
                resp.raise_for_status()
                event_type = None

                for line in resp.iter_lines(decode_unicode=True):
                    if line is None or line == "":
                        continue
                    if line.startswith("event: "):
                        event_type = line[len("event: "):]
                        continue
                    if not line.startswith("data: "):
                        continue

                    payload = json.loads(line[len("data: "):])

                    if event_type == "status":
                        status_box.markdown(
                            f'<span class="status-line">{payload}</span>',
                            unsafe_allow_html=True,
                        )
                    elif event_type == "token":
                        status_box.empty()
                        accumulated_text += payload
                        report_box.markdown(accumulated_text)
                    elif event_type == "done":
                        status_box.empty()
                        final_report = payload["report_markdown"]
                        report_box.markdown(final_report)
                    elif event_type == "error":
                        status_box.empty()
                        error_text = f"Research failed: {payload}"
                        report_box.markdown(error_text)

        except requests.exceptions.RequestException as e:
            status_box.empty()
            error_text = f"Can't reach the backend: {e}"
            report_box.markdown(error_text)

        if final_report:
            st.session_state.messages.append({
                "role": "assistant",
                "content": final_report,
                "report_markdown": final_report,
                "topic": topic,
            })
            st.rerun()
        elif error_text:
            st.session_state.messages.append({"role": "assistant", "content": error_text})
