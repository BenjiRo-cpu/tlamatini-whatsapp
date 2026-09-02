from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from flask import Flask, Response, jsonify, request

from .agent import TlamatiniAgent
from .config import Config
from .knowledge import KnowledgeBase
from .llm import build_llm
from .security import SecurityPipeline, verify_meta_signature
from .store import SQLiteStore
from .tools import ToolRegistry
from .whatsapp import WhatsAppClient, extract_messages


LOGGER = logging.getLogger(__name__)


@dataclass
class Services:
    store: SQLiteStore
    agent: TlamatiniAgent
    whatsapp: WhatsAppClient


def build_services(config: Config) -> Services:
    store = SQLiteStore(config.database_path)
    knowledge = KnowledgeBase(
        config.knowledge_path, config.embedding_model, config.qdrant_path, config.rag_top_k
    )
    tools = ToolRegistry(knowledge, store)
    security = SecurityPipeline(config)
    llm = build_llm(config)
    agent = TlamatiniAgent(config, llm, store, tools, security)
    whatsapp = WhatsAppClient(
        config.whatsapp_access_token,
        config.whatsapp_phone_number_id,
        config.whatsapp_api_version,
        dry_run=config.whatsapp_dry_run,
    )
    return Services(store, agent, whatsapp)


def create_app(config: Config | None = None, services: Services | None = None) -> Flask:
    config = config or Config.from_env()
    config.ensure_directories()
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    services = services or build_services(config)

    app = Flask(__name__)
    app.config["TLAMATINI_CONFIG"] = config
    app.config["TLAMATINI_SERVICES"] = services

    @app.get("/")
    def index():
        return jsonify({"name": "Tlamatini WhatsApp", "status": "running", "version": "2.0.0"})

    @app.get("/health")
    def health():
        return jsonify({
            "status": "ok",
            "llm_provider": config.llm_provider,
            "whatsapp_configured": config.whatsapp_ready(),
            "whatsapp_dry_run": config.whatsapp_dry_run,
            "warnings": config.validate_runtime(),
        })

    @app.get("/metrics")
    def metrics():
        return jsonify(services.store.metrics_summary())

    @app.get("/webhook")
    def verify_webhook():
        mode = request.args.get("hub.mode", "")
        token = request.args.get("hub.verify_token", "")
        challenge = request.args.get("hub.challenge", "")
        if mode == "subscribe" and token and token == config.whatsapp_verify_token:
            return Response(challenge, status=200, mimetype="text/plain")
        return jsonify({"error": "verification_failed"}), 403

    @app.post("/webhook")
    def receive_webhook():
        raw_body = request.get_data(cache=True)
        signature = request.headers.get("X-Hub-Signature-256")
        if config.verify_webhook_signature:
            if not verify_meta_signature(raw_body, signature, config.whatsapp_app_secret):
                services.store.record_metric("webhook", "invalid_signature")
                return jsonify({"error": "invalid_signature"}), 403

        payload = request.get_json(silent=True) or {}
        messages = extract_messages(payload)
        for message in messages:
            if not services.store.claim_message(message["id"]):
                services.store.record_metric("webhook", "duplicate", detail=message["id"])
                continue
            if config.process_messages_async:
                threading.Thread(
                    target=_process_message,
                    args=(services, message),
                    daemon=True,
                    name=f"wa-{message['id'][-8:]}",
                ).start()
            else:
                _process_message(services, message)
        return jsonify({"status": "accepted", "messages": len(messages)}), 200

    return app


def _process_message(services: Services, message: dict[str, str]) -> None:
    started = perf_counter()
    try:
        if message["type"] != "text":
            answer = "Por ahora puedo leer mensajes de texto. Escríbeme tu pregunta sobre historia mexica."
        elif not message["text"]:
            answer = "Recibí un mensaje vacío. ¿Qué te gustaría aprender sobre los mexicas?"
        else:
            answer = services.agent.respond(message["from"], message["text"])
        services.whatsapp.send_text(message["from"], answer)
        services.store.complete_message(message["id"])
        services.store.record_metric("webhook", "ok", (perf_counter() - started) * 1000)
    except Exception as exc:
        LOGGER.exception("Error al procesar mensaje %s", message["id"])
        services.store.fail_message(message["id"], str(exc))
        services.store.record_metric("webhook", "error", (perf_counter() - started) * 1000, str(exc))
