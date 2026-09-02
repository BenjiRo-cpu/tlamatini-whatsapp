from __future__ import annotations

import json
import logging
import math
import re
import atexit
from pathlib import Path
from typing import Any


LOGGER = logging.getLogger(__name__)


class KnowledgeBase:
    """Índice semántico en Qdrant con respaldo léxico para entornos ligeros."""

    def __init__(self, data_path: str, embedding_model: str, qdrant_path: str, top_k: int = 3):
        self.documents = json.loads(Path(data_path).read_text(encoding="utf-8"))
        self.embedding_model_name = embedding_model
        self.qdrant_path = qdrant_path
        self.top_k = top_k
        self._encoder = None
        self._client = None
        self._semantic_ready = False
        self._close_registered = False

    def initialize_semantic_index(self) -> bool:
        if self._semantic_ready:
            return True
        try:
            from qdrant_client import QdrantClient, models
            from sentence_transformers import SentenceTransformer

            Path(self.qdrant_path).mkdir(parents=True, exist_ok=True)
            self._encoder = SentenceTransformer(self.embedding_model_name)
            vectors = self._encoder.encode(
                [doc["text"] for doc in self.documents], normalize_embeddings=True
            ).tolist()
            self._client = QdrantClient(path=self.qdrant_path)
            if not self._close_registered:
                atexit.register(self.close)
                self._close_registered = True
            collection = "historia_mexica"
            existing = {item.name for item in self._client.get_collections().collections}
            if collection not in existing:
                self._client.create_collection(
                    collection_name=collection,
                    vectors_config=models.VectorParams(
                        size=len(vectors[0]), distance=models.Distance.COSINE
                    ),
                )
            points = [
                models.PointStruct(id=index + 1, vector=vector, payload=doc)
                for index, (vector, doc) in enumerate(zip(vectors, self.documents))
            ]
            self._client.upsert(collection_name=collection, points=points, wait=True)
            self._semantic_ready = True
            LOGGER.info("Índice semántico listo con %s documentos", len(points))
            return True
        except Exception as exc:  # El respaldo mantiene vivo el webhook.
            LOGGER.warning("No se pudo iniciar el índice semántico; se usará búsqueda léxica: %s", exc)
            return False

    def close(self) -> None:
        client, self._client = self._client, None
        if client is not None:
            client.close()
        self._semantic_ready = False

    def search(self, query: str, limit: int | None = None) -> list[dict[str, Any]]:
        limit = min(max(limit or self.top_k, 1), 5)
        if not self._semantic_ready:
            self.initialize_semantic_index()
        if self._semantic_ready:
            vector = self._encoder.encode(query, normalize_embeddings=True).tolist()
            try:
                response = self._client.query_points(
                    collection_name="historia_mexica", query=vector, limit=limit
                )
                points = response.points
            except AttributeError:  # Compatibilidad con qdrant-client anterior.
                points = self._client.search(
                    collection_name="historia_mexica", query_vector=vector, limit=limit
                )
            return [
                {**point.payload, "score": round(float(point.score), 4)} for point in points
            ]
        return self._lexical_search(query, limit)

    def _lexical_search(self, query: str, limit: int) -> list[dict[str, Any]]:
        terms = set(re.findall(r"[a-záéíóúñü]+", query.lower()))
        scored = []
        for doc in self.documents:
            doc_terms = set(re.findall(r"[a-záéíóúñü]+", (doc["title"] + " " + doc["text"]).lower()))
            overlap = len(terms & doc_terms)
            score = overlap / math.sqrt(max(len(terms) * len(doc_terms), 1))
            scored.append({**doc, "score": round(score, 4)})
        return sorted(scored, key=lambda item: item["score"], reverse=True)[:limit]
