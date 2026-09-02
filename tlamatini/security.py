from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass

import requests

from .config import Config


def verify_meta_signature(raw_body: bytes, signature_header: str | None, app_secret: str) -> bool:
    if not app_secret or not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    supplied = signature_header.removeprefix("sha256=")
    return hmac.compare_digest(expected, supplied)


@dataclass
class GuardResult:
    allowed: bool
    reason: str = ""


class SecurityPipeline:
    INJECTION_PATTERNS = [
        r"ignora (todas )?(las )?instrucciones",
        r"ignore (all )?(previous|prior) instructions",
        r"revela (tu|el) (prompt|mensaje) (del )?sistema",
        r"show me (your|the) system prompt",
        r"act[uú]a como (desarrollador|developer|administrador|admin)",
        r"sobrescribe (tus|las) instrucciones",
        r"jailbreak",
    ]
    HARMFUL_PATTERNS = [
        r"c[oó]mo fabricar (una )?(bomba|arma)",
        r"instrucciones para (matar|envenenar|hackear)",
    ]

    def __init__(self, config: Config):
        self.config = config

    def check_input(self, text: str) -> GuardResult:
        if self.config.prompt_guard_mode == "off":
            return GuardResult(True)
        if self.config.prompt_guard_mode == "groq":
            return self._groq_prompt_guard(text)
        return self._rules_input(text)

    def _rules_input(self, text: str) -> GuardResult:
        normalized = text.lower()
        for pattern in self.INJECTION_PATTERNS:
            if re.search(pattern, normalized):
                return GuardResult(False, "posible_inyeccion_de_prompt")
        for pattern in self.HARMFUL_PATTERNS:
            if re.search(pattern, normalized):
                return GuardResult(False, "contenido_peligroso")
        return GuardResult(True)

    def check_output(self, text: str) -> GuardResult:
        if self.config.content_guard_mode == "off":
            return GuardResult(True)
        if self.config.content_guard_mode == "ollama":
            return self._ollama_content_guard(text)
        lowered = text.lower()
        if any(re.search(pattern, lowered) for pattern in self.HARMFUL_PATTERNS):
            return GuardResult(False, "salida_peligrosa")
        return GuardResult(True)

    def _groq_prompt_guard(self, text: str) -> GuardResult:
        try:
            from groq import Groq

            client = Groq(api_key=self.config.groq_api_key)
            response = client.chat.completions.create(
                model=self.config.prompt_guard_model,
                messages=[{"role": "user", "content": text}],
                temperature=0,
            )
            label = (response.choices[0].message.content or "").lower()
            unsafe = any(word in label for word in ("injection", "jailbreak", "unsafe"))
            return GuardResult(not unsafe, "prompt_guard" if unsafe else "")
        except Exception:
            # En caso de caída del clasificador, conserva la barrera local.
            return self._rules_input(text)

    def _ollama_content_guard(self, text: str) -> GuardResult:
        try:
            response = requests.post(
                f"{self.config.ollama_base_url.rstrip('/')}/api/chat",
                json={
                    "model": self.config.llama_guard_model,
                    "messages": [{"role": "user", "content": text}],
                    "stream": False,
                },
                timeout=min(self.config.llm_timeout_seconds, 20),
            )
            response.raise_for_status()
            label = response.json()["message"]["content"].strip().lower()
            return GuardResult(label.startswith("safe"), "llama_guard" if not label.startswith("safe") else "")
        except Exception:
            return GuardResult(False, "content_guard_unavailable")
