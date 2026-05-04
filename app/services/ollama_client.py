import json
import re
from collections.abc import Iterator
from typing import Any

import httpx


THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


class OllamaError(Exception):
    pass


def chat_with_ollama(
    *,
    base_url: str,
    model: str,
    system_prompt: str = "",
    user_prompt: str = "",
    messages: list[dict[str, str]] | None = None,
    timeout_seconds: float = 120.0,
) -> str:
    if messages is None:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    payload = {
        "model": model,
        "stream": False,
        "messages": messages,
    }
    try:
        response = httpx.post(
            f"{base_url.rstrip('/')}/api/chat",
            json=payload,
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise OllamaError(f"Ollama chat request failed: {exc}") from exc

    content = data.get("message", {}).get("content")
    if not isinstance(content, str) or not content.strip():
        raise OllamaError("Ollama returned an empty response.")
    return strip_think_blocks(content).strip()


def stream_chat_with_ollama(
    *,
    base_url: str,
    model: str,
    system_prompt: str = "",
    user_prompt: str = "",
    messages: list[dict[str, str]] | None = None,
    thinking_enabled: bool,
    timeout_seconds: float = 120.0,
) -> Iterator[dict[str, Any]]:
    if messages is None:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    payload = {
        "model": model,
        "stream": True,
        "think": thinking_enabled,
        "messages": messages,
    }
    try:
        with httpx.stream(
            "POST",
            f"{base_url.rstrip('/')}/api/chat",
            json=payload,
            timeout=timeout_seconds,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except ValueError as exc:
                    raise OllamaError(f"Ollama returned invalid streaming JSON: {exc}") from exc
                message = data.get("message", {})
                thinking = message.get("thinking")
                content = message.get("content")
                if isinstance(thinking, str) and thinking:
                    yield {"type": "thinking_delta", "delta": thinking}
                if isinstance(content, str) and content:
                    yield {"type": "content_delta", "delta": content}
                if data.get("done"):
                    yield {
                        "type": "done",
                        "input_token_count": int(data.get("prompt_eval_count") or 0),
                        "output_token_count": int(data.get("eval_count") or 0),
                    }
    except httpx.HTTPError as exc:
        raise OllamaError(f"Ollama streaming chat request failed: {exc}") from exc


def get_ollama_health(*, base_url: str, model: str, timeout_seconds: float = 5.0) -> dict[str, Any]:
    try:
        response = httpx.get(f"{base_url.rstrip('/')}/api/tags", timeout=timeout_seconds)
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        return {"ok": False, "error": f"Ollama health check failed: {exc}"}

    models = data.get("models", [])
    available = [
        item.get("name") or item.get("model")
        for item in models
        if isinstance(item, dict) and (item.get("name") or item.get("model"))
    ]
    if model not in available:
        return {"ok": False, "error": f"Model {model} is not installed.", "available_models": available}
    return {"ok": True, "error": None, "available_models": available}


def strip_think_blocks(content: str) -> str:
    return THINK_BLOCK_RE.sub("", content)
