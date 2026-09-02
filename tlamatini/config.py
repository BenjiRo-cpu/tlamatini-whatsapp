from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "si", "sí"}


@dataclass(frozen=True)
class Config:
    host: str = "0.0.0.0"
    port: int = 5000
    log_level: str = "INFO"
    database_path: str = "data/tlamatini.db"
    process_messages_async: bool = True

    whatsapp_verify_token: str = ""
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_app_secret: str = ""
    whatsapp_api_version: str = "v25.0"
    verify_webhook_signature: bool = True
    whatsapp_dry_run: bool = False

    llm_provider: str = "ollama"
    llm_timeout_seconds: int = 45
    max_tool_rounds: int = 3
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.2:3b"
    groq_api_key: str = ""
    groq_model: str = ""

    knowledge_path: str = "data/historia_mexica.json"
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    qdrant_path: str = "data/qdrant"
    rag_top_k: int = 3

    prompt_guard_mode: str = "rules"
    prompt_guard_model: str = "meta-llama/llama-prompt-guard-2-86m"
    content_guard_mode: str = "rules"
    llama_guard_model: str = "llama-guard3:1b"

    @classmethod
    def from_env(cls) -> "Config":
        load_dotenv()
        return cls(
            host=os.getenv("HOST", "0.0.0.0"),
            port=int(os.getenv("PORT", "5000")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            database_path=os.getenv("DATABASE_PATH", "data/tlamatini.db"),
            process_messages_async=_bool("PROCESS_MESSAGES_ASYNC", True),
            whatsapp_verify_token=os.getenv("WHATSAPP_VERIFY_TOKEN", ""),
            whatsapp_access_token=os.getenv("WHATSAPP_ACCESS_TOKEN", ""),
            whatsapp_phone_number_id=os.getenv("WHATSAPP_PHONE_NUMBER_ID", ""),
            whatsapp_app_secret=os.getenv("WHATSAPP_APP_SECRET", ""),
            whatsapp_api_version=os.getenv("WHATSAPP_API_VERSION", "v25.0"),
            verify_webhook_signature=_bool("VERIFY_WEBHOOK_SIGNATURE", True),
            whatsapp_dry_run=_bool("WHATSAPP_DRY_RUN", False),
            llm_provider=os.getenv("LLM_PROVIDER", "ollama").lower(),
            llm_timeout_seconds=int(os.getenv("LLM_TIMEOUT_SECONDS", "45")),
            max_tool_rounds=int(os.getenv("MAX_TOOL_ROUNDS", "3")),
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
            ollama_model=os.getenv("OLLAMA_MODEL", "llama3.2:3b"),
            groq_api_key=os.getenv("GROQ_API_KEY", ""),
            groq_model=os.getenv("GROQ_MODEL", ""),
            knowledge_path=os.getenv("KNOWLEDGE_PATH", "data/historia_mexica.json"),
            embedding_model=os.getenv("EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"),
            qdrant_path=os.getenv("QDRANT_PATH", "data/qdrant"),
            rag_top_k=int(os.getenv("RAG_TOP_K", "3")),
            prompt_guard_mode=os.getenv("PROMPT_GUARD_MODE", "rules").lower(),
            prompt_guard_model=os.getenv("PROMPT_GUARD_MODEL", "meta-llama/llama-prompt-guard-2-86m"),
            content_guard_mode=os.getenv("CONTENT_GUARD_MODE", "rules").lower(),
            llama_guard_model=os.getenv("LLAMA_GUARD_MODEL", "llama-guard3:1b"),
        )

    def ensure_directories(self) -> None:
        for path in (self.database_path, self.qdrant_path):
            target = Path(path)
            directory = target if not target.suffix else target.parent
            directory.mkdir(parents=True, exist_ok=True)

    def whatsapp_ready(self) -> bool:
        return self.whatsapp_dry_run or bool(self.whatsapp_access_token and self.whatsapp_phone_number_id)

    def validate_runtime(self) -> list[str]:
        warnings: list[str] = []
        if not self.whatsapp_verify_token:
            warnings.append("WHATSAPP_VERIFY_TOKEN no está configurado")
        if not self.whatsapp_ready():
            warnings.append("Faltan credenciales para enviar mensajes por WhatsApp")
        if self.verify_webhook_signature and not self.whatsapp_app_secret:
            warnings.append("WHATSAPP_APP_SECRET falta; la firma del webhook no podrá validarse")
        if self.llm_provider == "groq" and not (self.groq_api_key and self.groq_model):
            warnings.append("GROQ_API_KEY y GROQ_MODEL son obligatorios cuando LLM_PROVIDER=groq")
        return warnings
