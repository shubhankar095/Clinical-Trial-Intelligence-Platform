from dataclasses import (
    asdict,
    dataclass,
)
from datetime import (
    datetime,
    timezone,
)
from typing import Any


def _normalize_required_string(
    value: str,
    field_name: str,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            f"{field_name} must be a string."
        )

    normalized_value = value.strip()

    if not normalized_value:
        raise ValueError(
            f"{field_name} must not be blank."
        )

    return normalized_value


def _normalize_optional_string(
    value: str | None,
    field_name: str,
) -> str | None:
    if value is None:
        return None

    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            f"{field_name} must be a string or "
            "None."
        )

    normalized_value = value.strip()

    if not normalized_value:
        raise ValueError(
            f"{field_name} must not be blank when "
            "supplied."
        )

    return normalized_value


def _validate_nonnegative_integer(
    value: int,
    field_name: str,
) -> None:
    if (
        not isinstance(
            value,
            int,
        )
        or isinstance(
            value,
            bool,
        )
    ):
        raise TypeError(
            f"{field_name} must be an integer."
        )

    if value < 0:
        raise ValueError(
            f"{field_name} must be zero or "
            "greater."
        )


def _normalize_timestamp(
    value: datetime,
    field_name: str,
) -> datetime:
    if not isinstance(
        value,
        datetime,
    ):
        raise TypeError(
            f"{field_name} must be a datetime."
        )

    if (
        value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(
            f"{field_name} must include timezone "
            "information."
        )

    return value.astimezone(
        timezone.utc
    )


@dataclass(
    frozen=True,
    slots=True,
)
class IngestionSuccessManifest:
    """
    Immutable ingestion-success-v1 contract.

    The manifest records the exact document,
    ingestion profile, embedding configuration, and
    OpenSearch destination produced by one completed
    ingestion generation.
    """

    event_type: str
    manifest_schema_version: str
    processing_status: str

    document_id: str
    ingestion_id: str
    ingestion_profile_id: str

    processing_schema_version: str
    ingestion_schema_version: str
    index_schema_version: str

    source_bucket: str
    source_key: str
    source_version_id: str

    canonical_bucket: str
    canonical_key: str
    canonical_version_id: str | None
    canonical_sha256: str | None

    index_destination: str
    index_record_count: int
    chunk_count: int

    embedding_provider: str
    embedding_model_id: str
    embedding_dimensions: int
    embedding_normalized: bool

    completed_at: datetime

    def __post_init__(
        self,
    ) -> None:
        required_string_fields = (
            "event_type",
            "manifest_schema_version",
            "processing_status",
            "document_id",
            "ingestion_id",
            "ingestion_profile_id",
            "processing_schema_version",
            "ingestion_schema_version",
            "index_schema_version",
            "source_bucket",
            "source_key",
            "source_version_id",
            "canonical_bucket",
            "canonical_key",
            "index_destination",
            "embedding_provider",
            "embedding_model_id",
        )

        for field_name in required_string_fields:
            object.__setattr__(
                self,
                field_name,
                _normalize_required_string(
                    getattr(
                        self,
                        field_name,
                    ),
                    field_name,
                ),
            )

        object.__setattr__(
            self,
            "canonical_version_id",
            _normalize_optional_string(
                self.canonical_version_id,
                "canonical_version_id",
            ),
        )

        object.__setattr__(
            self,
            "canonical_sha256",
            _normalize_optional_string(
                self.canonical_sha256,
                "canonical_sha256",
            ),
        )

        _validate_nonnegative_integer(
            self.index_record_count,
            "index_record_count",
        )

        _validate_nonnegative_integer(
            self.chunk_count,
            "chunk_count",
        )

        if (
            not isinstance(
                self.embedding_dimensions,
                int,
            )
            or isinstance(
                self.embedding_dimensions,
                bool,
            )
        ):
            raise TypeError(
                "embedding_dimensions must be an "
                "integer."
            )

        if self.embedding_dimensions <= 0:
            raise ValueError(
                "embedding_dimensions must be "
                "greater than zero."
            )

        if not isinstance(
            self.embedding_normalized,
            bool,
        ):
            raise TypeError(
                "embedding_normalized must be a "
                "boolean."
            )

        object.__setattr__(
            self,
            "completed_at",
            _normalize_timestamp(
                self.completed_at,
                "completed_at",
            ),
        )

        if self.event_type != "INGESTION_COMPLETED":
            raise ValueError(
                "event_type must be exactly "
                "'INGESTION_COMPLETED'."
            )

        if (
            self.manifest_schema_version
            != "ingestion-success-v1"
        ):
            raise ValueError(
                "manifest_schema_version must be "
                "exactly 'ingestion-success-v1'."
            )

        if self.processing_status != "SUCCESS":
            raise ValueError(
                "processing_status must be exactly "
                "'SUCCESS'."
            )

        if (
            self.index_record_count
            != self.chunk_count
        ):
            raise ValueError(
                "index_record_count must match "
                "chunk_count."
            )

    def to_payload(
        self,
    ) -> dict[str, Any]:
        """
        Return a JSON-serializable manifest payload.
        """
        payload = asdict(
            self
        )

        payload["completed_at"] = (
            self.completed_at
            .isoformat()
        )

        return payload


@dataclass(
    frozen=True,
    slots=True,
)
class IngestionFailureManifest:
    """
    Immutable ingestion-failure-v1 contract.

    This artifact is written only for a permanent
    processing failure when an ingestion identity is
    available. Retryable infrastructure failures do
    not produce a final failure manifest.
    """

    event_type: str
    manifest_schema_version: str
    processing_status: str

    document_id: str
    ingestion_id: str
    ingestion_profile_id: str

    processing_schema_version: str
    ingestion_schema_version: str

    manifest_bucket: str
    manifest_key: str
    manifest_version_id: str | None

    error_type: str
    error_message: str

    failed_at: datetime

    def __post_init__(
        self,
    ) -> None:
        required_string_fields = (
            "event_type",
            "manifest_schema_version",
            "processing_status",
            "document_id",
            "ingestion_id",
            "ingestion_profile_id",
            "processing_schema_version",
            "ingestion_schema_version",
            "manifest_bucket",
            "manifest_key",
            "error_type",
            "error_message",
        )

        for field_name in required_string_fields:
            object.__setattr__(
                self,
                field_name,
                _normalize_required_string(
                    getattr(
                        self,
                        field_name,
                    ),
                    field_name,
                ),
            )

        object.__setattr__(
            self,
            "manifest_version_id",
            _normalize_optional_string(
                self.manifest_version_id,
                "manifest_version_id",
            ),
        )

        object.__setattr__(
            self,
            "failed_at",
            _normalize_timestamp(
                self.failed_at,
                "failed_at",
            ),
        )

        if self.event_type != "INGESTION_FAILED":
            raise ValueError(
                "event_type must be exactly "
                "'INGESTION_FAILED'."
            )

        if (
            self.manifest_schema_version
            != "ingestion-failure-v1"
        ):
            raise ValueError(
                "manifest_schema_version must be "
                "exactly 'ingestion-failure-v1'."
            )

        if self.processing_status != "FAILED":
            raise ValueError(
                "processing_status must be exactly "
                "'FAILED'."
            )

    def to_payload(
        self,
    ) -> dict[str, Any]:
        """
        Return a JSON-serializable manifest payload.
        """
        payload = asdict(
            self
        )

        payload["failed_at"] = (
            self.failed_at
            .isoformat()
        )

        return payload