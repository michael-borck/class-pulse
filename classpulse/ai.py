"""AI question generation: provider config, HTTP adapters, prompts, parsing.

One provider serves the whole deployment (configured via environment, not
per-user). Two adapter families cover essentially every model:
  openai    -> POST {AI_BASE_URL}/chat/completions, "Authorization: Bearer"
               (OpenAI, Ollama's /v1, Groq, Together, vLLM, OpenRouter, ...).
               Leave AI_API_KEY blank for a local/keyless Ollama.
  anthropic -> POST {AI_BASE_URL}/messages, "x-api-key" + "anthropic-version"
               (api.anthropic.com direct).
Both AI_BASE_URL values are the "/v1" root; the adapter appends the endpoint.
"""

import json
import os
import re
from typing import Any, Dict

import requests

AI_PROVIDER = os.environ.get("AI_PROVIDER", "").strip().lower()
AI_BASE_URL = os.environ.get("AI_BASE_URL", "").strip().rstrip("/")
AI_API_KEY = os.environ.get("AI_API_KEY", "").strip()
AI_MODEL = os.environ.get("AI_MODEL", "").strip()

AI_CONFIGURED = AI_PROVIDER in ("openai", "anthropic") and bool(AI_BASE_URL and AI_MODEL)
_ai_enabled_raw = os.environ.get("AI_ENABLED", "").strip().lower()
AI_ENABLED = (_ai_enabled_raw in ("1", "true", "yes")) if _ai_enabled_raw else AI_CONFIGURED

_SYSTEM_PROMPT = ("You are a helpful assistant that generates educational questions. "
                  "Always respond with valid JSON.")


def call_openai_compatible_api(base_url: str, api_key: str, model: str, prompt: str) -> Dict[str, Any]:
    """Call an OpenAI-compatible /chat/completions endpoint."""
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        response = requests.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.7,
                "max_tokens": 500,
            },
            timeout=30,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return {"success": True, "response": content}
    except Exception as e:
        return {"success": False, "error": str(e)}


def call_anthropic_api(base_url: str, api_key: str, model: str, prompt: str) -> Dict[str, Any]:
    """Call an Anthropic-native /messages endpoint (api.anthropic.com direct)."""
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    try:
        response = requests.post(
            f"{base_url}/messages",
            headers=headers,
            json={
                "model": model,
                "max_tokens": 500,
                "system": _SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        response.raise_for_status()
        content = response.json()["content"][0]["text"]
        return {"success": True, "response": content}
    except Exception as e:
        return {"success": False, "error": str(e)}


_AI_ADAPTERS = {
    "openai": call_openai_compatible_api,
    "anthropic": call_anthropic_api,
}


def call_ai(prompt: str) -> Dict[str, Any]:
    """Generate a raw completion from the globally-configured AI provider."""
    adapter = _AI_ADAPTERS.get(AI_PROVIDER)
    if adapter is None:
        return {"success": False, "error": f"Unknown AI provider: {AI_PROVIDER!r}"}
    return adapter(AI_BASE_URL, AI_API_KEY, AI_MODEL, prompt)


def parse_ai_response(response_text: str) -> Dict[str, Any]:
    """Parse the AI's JSON response into a question dict."""
    from .questions import VALID_QUESTION_TYPES
    try:
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            if "question_type" in data and "title" in data:
                question_type = data["question_type"].lower().replace(" ", "_")
                if question_type in VALID_QUESTION_TYPES:
                    return {
                        "success": True,
                        "question_type": question_type,
                        "title": data["title"][:255],
                        "options": data.get("options", []),
                        "change_summary": (data.get("change_summary") or "")[:120],
                        "confidence": data.get("confidence", 0.8),
                    }
        return {"success": False, "error": "Could not parse valid question format from AI response"}
    except Exception as e:
        return {"success": False, "error": f"Error parsing AI response: {str(e)}"}


def build_ai_prompt(*, mode: str, instruction: str = None, title: str = None,
                    options: Any = None, hint: str = None, qtype: str = None) -> str:
    """Build the LLM prompt for generating a fresh question or refining an existing one."""
    if mode == "refine":
        if isinstance(options, list):
            opts_str = ", ".join(str(o) for o in options) or "none"
        elif isinstance(options, dict):
            opts_str = ", ".join(f"{k}={v}" for k, v in options.items()) or "none"
        else:
            opts_str = options or "none"
        steer = (hint or "").strip() or "Improve clarity and quality."
        return f"""You are refining an existing educational question. Apply the requested change and return the improved question.

Current question:
- Type: {qtype or 'unspecified'}
- Title: "{title or ''}"
- Options: {opts_str}

Requested change: "{steer}"

Respond in JSON format only:
{{
  "question_type": one of multiple_choice | word_cloud | rating | multi_select | short_answer | ranking | numeric | image_choice | multiple_choice_other,
  "title": "the improved question text (clear and concise)",
  "options": a list of strings for multiple_choice/multi_select/ranking/multiple_choice_other; [{{"label":"..","url":".."}},..] for image_choice; {{"max_rating":5}} for rating; {{"min":0,"max":100}} for numeric; [] for word_cloud/short_answer,
  "change_summary": "2-6 words describing what you changed (e.g. 'raised difficulty', 'added a 5th option')",
  "confidence": 0.0-1.0
}}

Guidelines:
- Keep the same question_type unless the change explicitly asks to switch.
- For multiple_choice: keep about 4 realistic options (add or remove as the change asks).
- Keep questions educational and appropriate."""

    # generate mode (default)
    instruction = (instruction or "").strip()
    return f"""Analyze this prompt and generate an educational question: '{instruction}'

Respond in JSON format only:
{{
  "question_type": one of multiple_choice | word_cloud | rating | multi_select | short_answer | ranking | numeric | image_choice | multiple_choice_other,
  "title": "the question text (clear and concise)",
  "options": a list of strings for multiple_choice/multi_select/ranking/multiple_choice_other; [{{"label":"..","url":".."}},..] for image_choice; {{"max_rating":5}} for rating; {{"min":0,"max":100}} for numeric; [] for word_cloud/short_answer,
  "confidence": 0.0-1.0
}}

Guidelines:
- For multiple_choice: Include 4 realistic options in the "options" array
- For word_cloud: Use a single prompt word/phrase that will generate interesting responses
- For rating: Include max_rating in options object (typically 5 or 10)
- Set confidence < 0.5 if the question type is unclear from the prompt
- Keep questions educational and appropriate"""


def generate_question_with_ai(*, mode: str = "generate", instruction: str = None,
                              title: str = None, options: Any = None, hint: str = None,
                              qtype: str = None) -> Dict[str, Any]:
    """Generate a fresh question or refine an existing one via the configured AI provider."""
    if not AI_ENABLED:
        return {"success": False, "error": "AI question generation is not configured."}
    prompt = build_ai_prompt(mode=mode, instruction=instruction, title=title,
                             options=options, hint=hint, qtype=qtype)
    result = call_ai(prompt)
    if result["success"]:
        return parse_ai_response(result["response"])
    return {"success": False, "error": result.get("error", "AI request failed.")}
