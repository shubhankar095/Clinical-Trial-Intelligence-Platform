from dataclasses import dataclass


@dataclass(
    frozen=True,
    slots=True,
)
class IndexRecord:
    """
    Provider-independent searchable record for one
    embedded document chunk.

    This model contains the content, vector,
    provenance, ingestion lineage, and clinical
    metadata required by an indexing adapter.
    """

    index_record_id: str
    index_schema_version: str

    document_id: str
    ingestion_id: str
    ingestion_profile_id: str

    chunk_id: str
    chunk_index: int

    text: str
    character_count: int

    start_offset: int
    end_offset: int

    start_page: int | None
    end_page: int | None

    embedding: tuple[
        float,
        ...,
    ]

    embedding_provider: str
    embedding_model_id: str
    embedding_dimensions: int
    embedding_normalized: bool

    input_token_count: int | None

    file_name: str
    file_format: str

    source_bucket: str
    source_key: str
    source_version_id: str

    canonical_bucket: str
    canonical_key: str

    study_id: str | None
    document_type: str | None
    document_version: str | None
    sponsor: str | None
    phase: str | None