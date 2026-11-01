import json

from dataclasses import dataclass


@dataclass(
    frozen=True,
    slots=True,
)
class IngestionProfile:
    """
    Versioned configuration that determines how a
    canonical document becomes a searchable
    knowledge representation.

    Every setting that can change chunks,
    embeddings, or indexed records must be included
    in this model.
    """

    ingestion_schema_version: str

    chunker_type: str
    chunker_version: str
    chunk_size: int
    chunk_overlap: int

    embedding_provider: str
    embedding_model_id: str
    embedding_dimensions: int
    embedding_normalize: bool
    embedding_model_options_json: str

    index_schema_version: str

    def __post_init__(
        self,
    ) -> None:
        object.__setattr__(
            self,
            "ingestion_schema_version",
            self._normalize_required_string(
                self.ingestion_schema_version,
                "ingestion_schema_version",
            ),
        )

        object.__setattr__(
            self,
            "chunker_type",
            self._normalize_required_string(
                self.chunker_type,
                "chunker_type",
            ),
        )

        object.__setattr__(
            self,
            "chunker_version",
            self._normalize_required_string(
                self.chunker_version,
                "chunker_version",
            ),
        )

        object.__setattr__(
            self,
            "embedding_provider",
            self._normalize_required_string(
                self.embedding_provider,
                "embedding_provider",
            ).lower(),
        )

        object.__setattr__(
            self,
            "embedding_model_id",
            self._normalize_required_string(
                self.embedding_model_id,
                "embedding_model_id",
            ),
        )

        normalized_model_options_json = (
            self._normalize_required_string(
                self
                .embedding_model_options_json,
                "embedding_model_options_json",
            )
        )

        try:
            model_options = json.loads(
                normalized_model_options_json
            )
        except json.JSONDecodeError as exception:
            raise ValueError(
                "embedding_model_options_json "
                "must contain valid JSON."
            ) from exception

        if not isinstance(
            model_options,
            dict,
        ):
            raise ValueError(
                "embedding_model_options_json "
                "must contain a JSON object."
            )

        canonical_model_options_json = (
            json.dumps(
                model_options,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            )
        )

        object.__setattr__(
            self,
            "embedding_model_options_json",
            canonical_model_options_json,
        )

        object.__setattr__(
            self,
            "index_schema_version",
            self._normalize_required_string(
                self.index_schema_version,
                "index_schema_version",
            ),
        )

        if (
            not isinstance(
                self.chunk_size,
                int,
            )
            or isinstance(
                self.chunk_size,
                bool,
            )
        ):
            raise TypeError(
                "chunk_size must be an integer."
            )

        if self.chunk_size <= 0:
            raise ValueError(
                "chunk_size must be greater "
                "than zero."
            )

        if (
            not isinstance(
                self.chunk_overlap,
                int,
            )
            or isinstance(
                self.chunk_overlap,
                bool,
            )
        ):
            raise TypeError(
                "chunk_overlap must be an integer."
            )

        if self.chunk_overlap < 0:
            raise ValueError(
                "chunk_overlap must be zero "
                "or greater."
            )

        if (
            self.chunk_overlap
            >= self.chunk_size
        ):
            raise ValueError(
                "chunk_overlap must be less "
                "than chunk_size."
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
                "embedding_dimensions must be "
                "an integer."
            )

        if self.embedding_dimensions <= 0:
            raise ValueError(
                "embedding_dimensions must be "
                "greater than zero."
            )

        if not isinstance(
            self.embedding_normalize,
            bool,
        ):
            raise TypeError(
                "embedding_normalize must be "
                "a boolean."
            )

    @staticmethod
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

        normalized_value = (
            value.strip()
        )

        if not normalized_value:
            raise ValueError(
                f"{field_name} must not be blank."
            )

        return normalized_value


@dataclass(
    frozen=True,
    slots=True,
)
class IngestionIdentity:
    """
    Deterministic identity for one canonical
    document processed with one ingestion profile.
    """

    document_id: str
    ingestion_profile_id: str
    ingestion_id: str

    canonical_bucket: str
    canonical_key: str
    canonical_version_id: str | None
    canonical_sha256: str | None