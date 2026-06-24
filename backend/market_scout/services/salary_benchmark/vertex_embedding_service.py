from __future__ import annotations

import os
from typing import Protocol


DEFAULT_VERTEX_LOCATION = "us-central1"
DEFAULT_EMBEDDING_MODEL = "text-multilingual-embedding-002"


class EmbeddingService(Protocol):
    model_name: str

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        ...

    def embed_query(self, text: str) -> list[float]:
        ...


class VertexTextEmbeddingService:
    """Generate document embeddings with Vertex AI."""

    def __init__(
        self,
        *,
        model_name: str | None = None,
        project: str | None = None,
        location: str | None = None,
        task_type: str = "RETRIEVAL_DOCUMENT",
    ) -> None:
        self.model_name = model_name or os.getenv("MARKET_SCOUT_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
        self.project = project or os.getenv("GOOGLE_CLOUD_PROJECT")
        self.location = location or os.getenv("MARKET_SCOUT_VERTEX_LOCATION", DEFAULT_VERTEX_LOCATION)
        self.task_type = task_type
        self._model = None

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        model = self._get_model()
        try:
            from vertexai.language_models import TextEmbeddingInput

            inputs = [TextEmbeddingInput(text, self.task_type) for text in texts]
            embeddings = model.get_embeddings(inputs)
        except TypeError:
            embeddings = model.get_embeddings(texts)

        return [list(embedding.values) for embedding in embeddings]

    def embed_query(self, text: str) -> list[float]:
        query_service = VertexTextEmbeddingService(
            model_name=self.model_name,
            project=self.project,
            location=self.location,
            task_type="RETRIEVAL_QUERY",
        )
        return query_service.embed_documents([text])[0]

    def _get_model(self):
        if self._model is not None:
            return self._model

        try:
            import vertexai
            from vertexai.language_models import TextEmbeddingModel
        except ImportError as exc:
            raise RuntimeError(
                "Missing dependency google-cloud-aiplatform. Install backend/market_scout/requirements.txt first."
            ) from exc

        vertexai.init(project=self.project, location=self.location)
        self._model = TextEmbeddingModel.from_pretrained(self.model_name)
        return self._model
