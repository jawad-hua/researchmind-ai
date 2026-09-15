"""
Web Search — wraps the Tavily API.

Tavily is purpose-built for LLM agents: it returns cleaned content
snippets (not raw HTML), which saves us a scraping/parsing layer.
"""

import os
from tavily import TavilyClient
from dotenv import load_dotenv

load_dotenv()

_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))


def search_web(query: str, max_results: int = 5) -> tuple[list[dict], str | None]:
    """
    Run a web search and return (results, error_message).
    error_message is None on success, or a short diagnostic string on failure —
    the caller decides how to surface it (Streamlit warning, log, etc.).
    """
    if not os.getenv("TAVILY_API_KEY"):
        return [], "TAVILY_API_KEY not set. Add it to your .env file."

    try:
        response = _client.search(
            query=query,
            search_depth="advanced",
            max_results=max_results,
        )
    except Exception as e:
        # Surface the real error instead of failing silently
        return [], f"{type(e).__name__}: {e}"

    results = []
    for item in response.get("results", []):
        results.append({
            "title": item.get("title", "Untitled"),
            "url": item.get("url", ""),
            "content": item.get("content", ""),
        })
    return results, None
