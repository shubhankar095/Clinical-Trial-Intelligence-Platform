from dataclasses import dataclass

from models.document import (
    DocumentChunk,
)


@dataclass(
    frozen=True,
    slots=True,
)
class EmbeddedChunk:
    """
    Immutable embedding result for one deterministic
    document chunk.
    """

    chunk: DocumentChunk

    embedding: tuple[
        float,
        ...,
    ]

    embedding_provider: str
    embedding_model_id: str
    embedding_dimensions: int
    embedding_normalized: bool

    input_token_count: int | None = None