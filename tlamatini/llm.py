from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any, Protocol

import requests

from .config import Config


class LLMClient(Protocol):
    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]: ...


@dataclass
class OllamaClient:
    base_url: str
    model: str
    timeout: int = 45

    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        ollama_messages = []
        for original in messages:
            message = dict(original)
            if message.get("role") == "assistant" and message.get("tool_calls"):
                converted_calls = []
                for call in message["tool_calls"]:
                    function = dict(call.get("function", {}))
                    if isinstance(function.get("arguments"), str):
                        function["arguments"] = json.loads(function["arguments"] or "{}")
                    converted_calls.append({"function": function})
                message["tool_calls"] = converted_calls
            if message.get("role") == "tool":
                message = {
                    "role": "tool",
                    "tool_name": message.get("name", ""),
                    "content": message.get("content", ""),
                }
            ollama_messages.append(message)
        response = requests.post(
            f"{self.base_url.rstrip('/')}/api/chat",
            json={
                "model": self.model,
                "messages": ollama_messages,
                "tools": tools,
                "stream": False,
                "options": {"temperature": 0.2},
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        message = response.json()["message"]
        if message.get("tool_calls"):
            message["tool_calls"] = [
                {
                    "id": f"ollama_{uuid.uuid4().hex}",
                    "type": "function",
                    "function": {
                        "name": call.get("function", {}).get("name", ""),
                        "arguments": json.dumps(
                            call.get("function", {}).get("arguments", {}), ensure_ascii=False
                        ),
                    },
                }
                for call in message["tool_calls"]
            ]
        return message


class GroqClient:
    def __init__(self, api_key: str, model: str, timeout: int = 45):
        if not api_key or not model:
            raise ValueError("GROQ_API_KEY y GROQ_MODEL son obligatorios")
        from groq import Groq

        self.client = Groq(api_key=api_key, timeout=timeout)
        self.model = model

    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.2,
        )
        message = response.choices[0].message
        result: dict[str, Any] = {"role": "assistant", "content": message.content or ""}
        if message.tool_calls:
            result["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.function.name,
                        "arguments": call.function.arguments or "{}",
                    }
                }
                for call in message.tool_calls
            ]
        return result


def build_llm(config: Config) -> LLMClient:
    if config.llm_provider == "groq":
        return GroqClient(config.groq_api_key, config.groq_model, config.llm_timeout_seconds)
    if config.llm_provider == "ollama":
        return OllamaClient(config.ollama_base_url, config.ollama_model, config.llm_timeout_seconds)
    raise ValueError(f"LLM_PROVIDER no soportado: {config.llm_provider}")
