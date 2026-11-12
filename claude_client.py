"""Thin wrapper around the Anthropic SDK for Supplier Rescue AI.

The API key is read from the .env file (ANTHROPIC_API_KEY). All AI calls in the
app should go through this module so the model and settings live in one place.
"""

import os

import anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5-5")


def has_api_key() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY", "").strip())


def get_client() -> anthropic.Anthropic:
    # Reads ANTHROPIC_API_KEY from the environment (loaded from .env above).
    return anthropic.Anthropic()


def ask_claude(prompt: str, system: str = "", max_tokens: int = 4000) -> str:
    """Send a single prompt to Claude and return the text reply."""
    client = get_client()
    kwargs = {
        "model": MODEL,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = system

    response = client.messages.create(**kwargs)

    if response.stop_reason == "refusal":
        return "Claude declined this request."

    return "".join(block.text for block in response.content if block.type == "text")


def test_connection() -> str:
    """Quick check that the API key works. Raises on failure."""
    return ask_claude("Reply with exactly: Connection OK", max_tokens=1000)
