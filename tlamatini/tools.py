from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from .knowledge import KnowledgeBase
from .store import SQLiteStore


class ToolRegistry:
    def __init__(self, knowledge: KnowledgeBase, store: SQLiteStore, quiz_path: str = "data/quiz_mexica.json"):
        self.knowledge = knowledge
        self.store = store
        self.quiz_bank = json.loads(Path(quiz_path).read_text(encoding="utf-8"))

    @property
    def schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "buscar_informacion_historica",
                    "description": "Busca datos verificables sobre historia mexica en la base documental. Úsala antes de responder cualquier pregunta histórica factual.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "consulta": {"type": "string", "description": "Pregunta o tema histórico concreto."},
                            "limite": {"type": "integer", "minimum": 1, "maximum": 5, "default": 3},
                        },
                        "required": ["consulta"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "iniciar_quiz",
                    "description": "Inicia una pregunta de opción múltiple sobre historia mexica y guarda el turno pendiente del estudiante.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "tema": {"type": "string", "description": "Tema solicitado por el estudiante."},
                            "dificultad": {"type": "string", "enum": ["básico", "intermedio", "avanzado"]},
                        },
                        "required": ["tema"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "consultar_progreso",
                    "description": "Consulta el progreso acumulado del usuario actual en los cuestionarios.",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
        ]

    def execute(self, name: str, arguments: dict[str, Any], user_id: str) -> dict[str, Any]:
        if name == "buscar_informacion_historica":
            query = str(arguments.get("consulta", "")).strip()
            if len(query) < 3:
                raise ValueError("La consulta debe contener al menos 3 caracteres")
            limit = int(arguments.get("limite", 3))
            return {"resultados": self.knowledge.search(query, limit)}

        if name == "iniciar_quiz":
            topic = str(arguments.get("tema", "general")).strip()[:80]
            difficulty = str(arguments.get("dificultad", "intermedio")).lower()
            allowed = {"básico", "intermedio", "avanzado"}
            if difficulty not in allowed:
                difficulty = "intermedio"
            candidates = [q for q in self.quiz_bank if q["difficulty"] == difficulty]
            if not candidates:
                candidates = self.quiz_bank
            question = random.choice(candidates)
            pending = {**question, "topic_requested": topic}
            self.store.update_state(user_id, mode="quiz_waiting", pending_quiz=pending)
            return {
                "tema": topic,
                "dificultad": difficulty,
                "pregunta": question["question"],
                "opciones": question["options"],
                "instruccion": "Pide al usuario responder con A, B, C o D.",
            }

        if name == "consultar_progreso":
            return self.progress(user_id)

        raise ValueError(f"Herramienta no autorizada: {name}")

    def answer_pending_quiz(self, user_id: str, text: str) -> str | None:
        state = self.store.get_state(user_id)
        pending = state.get("pending_quiz")
        if state.get("mode") != "quiz_waiting" or not pending:
            return None
        answer = text.strip().upper().replace("OPCIÓN", "").strip()
        if answer not in {"A", "B", "C", "D"}:
            return "Tenemos un quiz en curso. Respóndeme solamente con A, B, C o D."
        correct = answer == pending["answer"]
        topic = pending.get("topic_requested", pending.get("topic", "Historia mexica"))
        self.store.save_quiz_result(user_id, topic, int(correct), 1)
        self.store.update_state(user_id, mode="normal", pending_quiz=None, current_topic=topic)
        verdict = "¡Correcto!" if correct else f"Casi. La respuesta correcta era {pending['answer']}."
        return f"{verdict} {pending['explanation']}\n\nEscribe “otro quiz” si quieres continuar."

    def progress(self, user_id: str) -> dict[str, Any]:
        return self.store.quiz_progress(user_id)
