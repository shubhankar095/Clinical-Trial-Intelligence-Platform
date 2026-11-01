from dataclasses import (
    dataclass,
    field,
)
from types import MappingProxyType
from typing import (
    Any,
    Mapping,
)


def _immutable_mapping(
    value: Mapping[str, Any],
) -> Mapping[str, Any]:
    """
    Return a shallow immutable copy of a mapping.
    """
    if not isinstance(
        value,
        Mapping,
    ):
        raise TypeError(
            "Expected a mapping."
        )

    return MappingProxyType(
        dict(value)
    )


@dataclass(
    frozen=True,
    slots=True,
)
class CanonicalDocumentMetadata:
    """
    Clinical metadata produced by extraction.

    Individual values remain optional because some
    shared or historical documents may not contain
    every clinical metadata field.
    """

    study_id: str | None = None
    document_type: str | None = None
    version: str | None = None
    sponsor: str | None = None
    phase: str | None = None

    additional_fields: Mapping[
        str,
        Any,
    ] = field(
        default_factory=dict,
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "additional_fields",
            _immutable_mapping(
                self.additional_fields
            ),
        )


@dataclass(
    frozen=True,
    slots=True,
)
class CanonicalDocumentPage:
    """
    Page-level extracted text and source offsets.

    Offset semantics:

    - start_offset is inclusive
    - end_offset is exclusive
    - raw_text[start_offset:end_offset] must equal
      the page text
    """

    page_number: int
    text: str

    start_offset: int
    end_offset: int

    word_count: int
    quality_score: float

    requires_ocr: bool
    ocr_applied: bool

    extraction_method: str

    additional_fields: Mapping[
        str,
        Any,
    ] = field(
        default_factory=dict,
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "additional_fields",
            _immutable_mapping(
                self.additional_fields
            ),
        )


@dataclass(
    frozen=True,
    slots=True,
)
class CanonicalDocumentImage:
    """
    Metadata for an image extracted from a canonical
    source document.
    """

    image_id: str
    page_number: int
    extension: str
    s3_key: str
    width: int
    height: int

    additional_fields: Mapping[
        str,
        Any,
    ] = field(
        default_factory=dict,
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "additional_fields",
            _immutable_mapping(
                self.additional_fields
            ),
        )


@dataclass(
    frozen=True,
    slots=True,
)
class CanonicalDocumentTable:
    """
    Metadata for a table extracted from a canonical
    source document.
    """

    table_id: str
    page_number: int
    s3_key: str
    row_count: int
    column_count: int
    title: str | None = None

    additional_fields: Mapping[
        str,
        Any,
    ] = field(
        default_factory=dict,
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "additional_fields",
            _immutable_mapping(
                self.additional_fields
            ),
        )


@dataclass(
    frozen=True,
    slots=True,
)
class CanonicalDocument:
    """
    Typed representation of an extraction-v1
    canonical document.

    Structural parsing creates this object.
    CanonicalDocumentValidator will enforce the
    extraction-to-ingestion business contract.
    """

    document_id: str
    file_name: str
    file_format: str

    source_bucket: str
    source_key: str
    source_version_id: str

    canonical_bucket: str
    canonical_key: str

    processing_schema_version: str
    processing_status: str

    metadata: CanonicalDocumentMetadata

    raw_text: str

    pages: tuple[
        CanonicalDocumentPage,
        ...,
    ]

    page_count: int
    ocr_page_count: int

    images: tuple[
        CanonicalDocumentImage,
        ...,
    ]

    image_count: int

    tables: tuple[
        CanonicalDocumentTable,
        ...,
    ]

    table_count: int

    warnings: tuple[
        str,
        ...,
    ]

    already_processed: bool
    error_message: str | None

    additional_fields: Mapping[
        str,
        Any,
    ] = field(
        default_factory=dict,
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "pages",
            tuple(self.pages),
        )

        object.__setattr__(
            self,
            "images",
            tuple(self.images),
        )

        object.__setattr__(
            self,
            "tables",
            tuple(self.tables),
        )

        object.__setattr__(
            self,
            "warnings",
            tuple(self.warnings),
        )

        object.__setattr__(
            self,
            "additional_fields",
            _immutable_mapping(
                self.additional_fields
            ),
        )