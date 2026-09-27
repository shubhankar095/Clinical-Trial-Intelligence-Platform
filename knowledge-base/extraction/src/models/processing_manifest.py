from dataclasses import dataclass


@dataclass
class ProcessingManifest:
    document_id: str

    source_bucket: str
    source_key: str
    source_version_id: str

    processing_schema_version: str

    canonical_bucket: str
    canonical_key: str

    completed_at: str

    processing_status: str = "SUCCESS"