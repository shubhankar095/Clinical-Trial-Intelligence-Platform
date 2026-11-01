from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class ExtractionSuccessManifest:
    """
    Typed representation of an extraction-success-v1
    manifest.

    The model represents structurally valid manifest
    data. Business-contract validation is performed
    separately by ExtractionManifestValidator.
    """

    document_id: str

    source_bucket: str
    source_key: str
    source_version_id: str

    processing_schema_version: str

    canonical_bucket: str
    canonical_key: str

    completed_at: datetime
    processing_status: str

    additional_fields: Mapping[str, Any] = field(
        default_factory=dict,
    )

    def __post_init__(self) -> None:
        if not isinstance(
            self.additional_fields,
            Mapping,
        ):
            raise TypeError(
                "additional_fields must be "
                "a mapping."
            )

        immutable_fields = MappingProxyType(
            dict(
                self.additional_fields
            )
        )

        object.__setattr__(
            self,
            "additional_fields",
            immutable_fields,
        )