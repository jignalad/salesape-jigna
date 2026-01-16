from __future__ import annotations

import os


class GeminiServiceError(RuntimeError):
    pass


def _get_model_name() -> str:
    return os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


def generate_reply(history: list[dict[str, str]], prompt: str, timeout_s: int = 10) -> str:
    """
    Minimal wrapper around google.genai.
    - history: list of {"role": "user"|"ai", "text": "..."}
    - prompt: the latest user input
    Returns plain text reply or raises GeminiServiceError on failure.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise GeminiServiceError("Gemini API key is missing; set GEMINI_API_KEY in .env")

    try:
        from google import genai
    except Exception as e:  # pragma: no cover - import error path
        raise GeminiServiceError(f"Gemini client not available: {e}")

    try:
        client = genai.Client(api_key=api_key)
        model_name = _get_model_name()

        # Synchronous call
        resp = client.models.generate_content(
            model=model_name,
            contents=prompt)
        text = getattr(resp, "text", None) or ""
        text = text.strip()
        if not text:
            raise GeminiServiceError("Empty response from Gemini")
        return text
    except Exception as e:
        raise GeminiServiceError(f"Gemini request failed: {e}")

