import json

from datetime import datetime
from json import JSONDecodeError
from typing import Any

from exceptions.extraction_manifest import (
    ManifestFieldError,
    ManifestJsonError,
)
from models.extraction_manifest import (
    ExtractionSuccessManifest,
)


class ExtractionManifestParser:
    """
    Parse extraction-success-v1 JSON into a typed
    ExtractionSuccessManifest.

    This class validates JSON structure and field
    types only. Business-contract rules belong in
    ExtractionManifestValidator.
    """

    REQUIRED_STRING_FIELDS = (
        "document_id",
        "source_bucket",
        "source_key",
        "source_version_id",
        "processing_schema_version",
        "canonical_bucket",
        "canonical_key",
        "completed_at",
        "processing_status",
    )

    KNOWN_FIELDS = frozenset(
        REQUIRED_STRING_FIELDS
    )

    def parse(
        self,
        manifest_text: str,
    ) -> ExtractionSuccessManifest:
        if not isinstance(
            manifest_text,
            str,
        ):
            raise ManifestJsonError(
                "Extraction manifest content "
                "must be text."
            )

        try:
            payload = json.loads(
                manifest_text
            )
        except JSONDecodeError as exception:
            raise ManifestJsonError(
                "Extraction manifest is not "
                "valid JSON."
            ) from exception

        if not isinstance(
            payload,
            dict,
        ):
            raise ManifestJsonError(
                "Extraction manifest top-level "
                "JSON value must be an object."
            )

        parsed_fields = {
            field_name: (
                self._require_string_field(
                    payload=payload,
                    field_name=field_name,
                )
            )
            for field_name
            in self.REQUIRED_STRING_FIELDS
        }

        completed_at = (
            self._parse_completed_at(
                parsed_fields[
                    "completed_at"
                ]
            )
        )

        additional_fields = {
            key: value
            for key, value in payload.items()
            if key not in self.KNOWN_FIELDS
        }

        return ExtractionSuccessManifest(
            document_id=(
                parsed_fields[
                    "document_id"
                ]
            ),
            source_bucket=(
                parsed_fields[
                    "source_bucket"
                ]
            ),
            source_key=(
                parsed_fields[
                    "source_key"
                ]
            ),
            source_version_id=(
                parsed_fields[
                    "source_version_id"
                ]
            ),
            processing_schema_version=(
                parsed_fields[
                    "processing_schema_version"
                ]
            ),
            canonical_bucket=(
                parsed_fields[
                    "canonical_bucket"
                ]
            ),
            canonical_key=(
                parsed_fields[
                    "canonical_key"
                ]
            ),
            completed_at=completed_at,
            processing_status=(
                parsed_fields[
                    "processing_status"
                ]
            ),
            additional_fields=(
                additional_fields
            ),
        )

    def _require_string_field(
        self,
        payload: dict[str, Any],
        field_name: str,
    ) -> str:
        if field_name not in payload:
            raise ManifestFieldError(
                "Extraction manifest is missing "
                f"required field '{field_name}'."
            )

        value = payload[
            field_name
        ]

        if not isinstance(
            value,
            str,
        ):
            raise ManifestFieldError(
                "Extraction manifest field "
                f"'{field_name}' must be "
                "a string."
            )

        normalized_value = (
            value.strip()
        )

        if not normalized_value:
            raise ManifestFieldError(
                "Extraction manifest field "
                f"'{field_name}' must not "
                "be blank."
            )

        return normalized_value

    def _parse_completed_at(
        self,
        value: str,
    ) -> datetime:
        normalized_value = value

        if value.endswith(
            ("Z", "z")
        ):
            normalized_value = (
                f"{value[:-1]}+00:00"
            )

        try:
            completed_at = (
                datetime.fromisoformat(
                    normalized_value
                )
            )
        except ValueError as exception:
            raise ManifestFieldError(
                "Extraction manifest field "
                "'completed_at' must be a valid "
                "ISO 8601 timestamp."
            ) from exception

        if (
            completed_at.tzinfo is None
            or completed_at.utcoffset()
            is None
        ):
            raise ManifestFieldError(
                "Extraction manifest field "
                "'completed_at' must include "
                "timezone information."
            )

        return completed_at