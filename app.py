"""
ResearchMind AI — Phase 1 MVP entrypoint.

Pipeline: Query -> Planner -> Web Search -> Extractor -> Synthesizer
          -> (optional) Fact-Checker -> Report + Sources -> PDF export
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

st.set_page_config(page_title="ResearchMind AI", page_icon="🤖", layout="wide")

st.title("🤖 ResearchMind AI")
st.caption("Give it a topic — it plans, searches the web, and writes a cited report.")

with st.sidebar:
    st.header("Settings")
    run_fact_check = st.checkbox("Run fact-check pass", value=True)
    results_per_subq = st.slider("Search results per sub-question", 2, 8, 5)
    st.markdown("---")
    st.markdown(
        "**Pipeline:**\n\n"
        "Query → Planner → Web Search → Extractor → "
        "Synthesizer → Fact-Check → Report"
    )

topic = st.text_area(
    "What should I research?",
    placeholder='e.g. "Explain the latest trends in Generative AI and make a 5-page report."',
    height=100,
)

generate_clicked = st.button("🔎 Generate Report", type="primary")

if generate_clicked:
    if not topic.strip():
        st.warning("Enter a topic first.")
        st.stop()

    if not os.getenv("GROQ_API_KEY") or not os.getenv("TAVILY_API_KEY"):
        st.error(
            "Missing API keys. Add GROQ_API_KEY and TAVILY_API_KEY to your .env file."
        )
        st.stop()

    with st.status("Running research pipeline...", expanded=True) as status:
        st.write("Step 1/5 — Planning sub-questions...")
        subquestions = plan_subquestions(topic)
        for sq in subquestions:
            st.write(f"  • {sq}")

        st.write("Step 2/5 — Searching the web...")
        evidence_bundles = collect_all_evidence(
            subquestions,
            search_fn=lambda q: search_web(q, max_results=results_per_subq),
        )
        for bundle in evidence_bundles:
            if bundle.get("error"):
                st.error(f"Search failed for '{bundle['subquestion']}': {bundle['error']}")
        total_sources = sum(len(b["sources"]) for b in evidence_bundles)
        st.write(f"  • Found {total_sources} source snippets")

        if total_sources == 0:
            st.warning(
                "No search results at all — check the error(s) above. "
                "Common causes: invalid/expired Tavily API key, or the "
                "Tavily free-tier quota being exhausted."
            )
            status.update(label="Failed — no evidence found", state="error")
            st.stop()


        st.write("Step 3/5 — Synthesizing report...")
        result = build_report(topic, evidence_bundles)
        report_md = result["report_markdown"]
        sources = result["sources"]

        fact_check_notes = ""
        if run_fact_check:
            st.write("Step 4/5 — Fact-checking...")
            evidence_blob = "\n\n".join(b["evidence_text"] for b in evidence_bundles)
            fact_check_notes = fact_check_report(report_md, evidence_blob)

        st.write("Step 5/5 — Finalizing report...")
        final_report = append_sources_section(report_md, sources)
        if fact_check_notes:
            final_report += f"\n\n{fact_check_notes}"

        status.update(label="Done!", state="complete")

    st.session_state["final_report"] = final_report
    st.session_state["topic"] = topic

if "final_report" in st.session_state:
    st.markdown("---")
    st.markdown(st.session_state["final_report"])

    # PDF export
    if st.button("📄 Prepare PDF"):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            pdf_path = markdown_to_pdf(
                st.session_state["final_report"],
                title=st.session_state["topic"][:60],
                output_path=tmp.name,
            )
        with open(pdf_path, "rb") as f:
            st.download_button(
                "⬇️ Download Report as PDF",
                data=f.read(),
                file_name="research_report.pdf",
                mime="application/pdf",
            )
