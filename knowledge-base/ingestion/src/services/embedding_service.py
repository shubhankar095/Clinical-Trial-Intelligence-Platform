import math

from embedders.base_embedder import BaseEmbedder
from models.document import DocumentChunk
from models.embedded_chunk import EmbeddedChunk
from models.ingestion_profile import IngestionProfile
from exceptions.processing import PermanentIngestionError
from services.provider_error_classifier import raise_classified_provider_error


class EmbeddingService:
    """Generate and validate embeddings through the selected managed provider."""

    def __init__(self, embedder: BaseEmbedder):
        if not isinstance(embedder, BaseEmbedder):
            raise TypeError("embedder must implement BaseEmbedder.")
        self.embedder = embedder

    def embed_chunks(
        self,
        chunks: tuple[DocumentChunk, ...],
        profile: IngestionProfile,
    ) -> tuple[EmbeddedChunk, ...]:
        if not isinstance(chunks, tuple) or not chunks:
            raise ValueError("chunks must be a non-empty tuple.")
        if not isinstance(profile, IngestionProfile):
            raise TypeError("profile must be an IngestionProfile.")
        try:
            results = tuple(
                self.embedder.embed(chunk)
                for chunk in chunks
            )
        except Exception as exception:
            raise_classified_provider_error(
                exception,
                operation="Embedding generation",
            )
        if len(results) != len(chunks):
            raise PermanentIngestionError("Embedding count does not match chunk count.")
        for chunk, result in zip(chunks, results, strict=True):
            if result.chunk != chunk:
                raise PermanentIngestionError("Embedding result does not reference the supplied chunk.")
            if result.embedding_provider != profile.embedding_provider:
                raise PermanentIngestionError("Embedding provider does not match the ingestion profile.")
            if result.embedding_model_id != profile.embedding_model_id:
                raise PermanentIngestionError("Embedding model does not match the ingestion profile.")
            if result.embedding_dimensions != profile.embedding_dimensions:
                raise PermanentIngestionError("Embedding dimensions do not match the ingestion profile.")
            if len(result.embedding) != profile.embedding_dimensions:
                raise PermanentIngestionError("Embedding vector length is invalid.")
            if result.embedding_normalized != profile.embedding_normalize:
                raise PermanentIngestionError("Embedding normalization flag does not match the profile.")
            if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in result.embedding):
                raise PermanentIngestionError("Embedding vector must contain only finite numeric values.")
        return results

    def close(self) -> None:
        close = getattr(self.embedder, "close", None)
        if callable(close):
            close()
