from dataclasses import dataclass


@dataclass(
    frozen=True,
    slots=True,
)
class DocumentChunk:
    """
    Deterministic text chunk produced from a
    canonical document.

    The chunk contains only chunking-stage data.
    Embeddings and OpenSearch-specific fields belong
    to later pipeline stages.
    """

    chunk_id: str

    ingestion_id: str
    ingestion_profile_id: str
    document_id: str

    chunk_index: int

    text: str

    start_offset: int
    end_offset: int

    start_page: int | None
    end_page: int | None

    character_count: int