"""
LLM Client — thin wrapper around the Groq API.

Design note: kept provider-agnostic on purpose. If tomorrow you swap
Groq for OpenAI/Anthropic, only this file changes — nothing else in
the codebase should import `groq` directly.
"""

import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
_MODEL = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")


def chat(
    prompt: str,
    system: str = "You are a precise, factual research assistant.",
    temperature: float = 0.3,
    max_tokens: int = 2048,
) -> str:
    """
    Send a single-turn prompt to the LLM and return the text response.

    Kept synchronous and simple for Phase 1. Streaming + multi-turn
    memory come in later phases.
    """
    if not os.getenv("GROQ_API_KEY"):
        raise RuntimeError(
            "GROQ_API_KEY not set. Add it to your .env file."
        )

    response = _client.chat.completions.create(
        model=_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content.strip()
