import json
import re

from dataclasses import dataclass
from datetime import (
    datetime,
    timezone,
)
from json import JSONDecodeError
from typing import Any


class IngestionEventError(
    RuntimeError
):
    """
    Base exception for invalid ingestion events.

    These exceptions represent permanent event
    contract failures. Retrying the same unchanged
    message will not make the event valid.
    """


class IngestionEventJsonError(
    IngestionEventError
):
    """
    The ingestion event body is not valid JSON or
    its top-level JSON value is not an object.
    """


class IngestionEventFieldError(
    IngestionEventError
):
    """
    A required ingestion-event field is missing,
    has an invalid type, or contains an invalid
    value.
    """


class UnsupportedIngestionEventError(
    IngestionEventError
):
    """
    The event type or event-contract version is not
    supported by this Ingestion worker.
    """


class IngestionEventIdentityError(
    IngestionEventError
):
    """
    Identity values in the event are inconsistent
    with the declared extraction manifest location.
    """


@dataclass(
    frozen=True,
    slots=True,
)
class ExtractionCompletedEvent:
    """
    Immutable contract published after Extraction
    completes a document successfully.

    The event identifies the exact Extraction
    success manifest that Ingestion must load and
    validate.

    manifest_version_id is optional so the contract
    remains usable with both versioned and
    unversioned Amazon S3 buckets. When supplied,
    Ingestion must load that exact object version.
    """

    event_type: str
    event_version: str

    document_id: str
    processing_schema_version: str

    manifest_bucket: str
    manifest_key: str
    manifest_version_id: str | None

    occurred_at: datetime


class IngestionEventParser:
    """
    Parse and validate Extraction-completed event
    messages.

    This parser validates:

    - JSON structure
    - required fields
    - supported event type and version
    - document identity format
    - Extraction processing schema
    - success-manifest S3 location
    - event timestamp timezone

    The Extraction success manifest remains the
    authoritative processing contract. This event
    only identifies where that manifest can be
    loaded.
    """

    SUPPORTED_EVENT_TYPE = (
        "EXTRACTION_COMPLETED"
    )

    SUPPORTED_EVENT_VERSION = "1"

    SUPPORTED_PROCESSING_SCHEMA = (
        "extraction-v1"
    )

    MANIFEST_PREFIX = (
        "canonical-documents"
    )

    MANIFEST_FILE_NAME = (
        "_SUCCESS.json"
    )

    DOCUMENT_ID_PATTERN = re.compile(
        r"^[0-9a-f]{64}$"
    )

    KNOWN_FIELDS = frozenset(
        {
            "event_type",
            "event_version",
            "document_id",
            "processing_schema_version",
            "manifest_bucket",
            "manifest_key",
            "manifest_version_id",
            "occurred_at",
        }
    )

    def parse(
        self,
        message_body: str,
    ) -> ExtractionCompletedEvent:
        """
        Parse one SQS message body into an immutable
        ExtractionCompletedEvent.
        """
        payload = self._parse_payload(
            message_body
        )

        event_type = (
            self._require_nonblank_string(
                payload=payload,
                field_name="event_type",
            )
        )

        event_version = (
            self._require_nonblank_string(
                payload=payload,
                field_name="event_version",
            )
        )

        self._validate_event_contract(
            event_type=event_type,
            event_version=event_version,
        )

        document_id = (
            self._require_nonblank_string(
                payload=payload,
                field_name="document_id",
            )
        )

        self._validate_document_id(
            document_id
        )

        processing_schema_version = (
            self._require_nonblank_string(
                payload=payload,
                field_name=(
                    "processing_schema_version"
                ),
            )
        )

        self._validate_processing_schema(
            processing_schema_version
        )

        manifest_bucket = (
            self._require_nonblank_string(
                payload=payload,
                field_name="manifest_bucket",
            )
        )

        self._validate_bucket_name(
            manifest_bucket
        )

        manifest_key = (
            self._require_nonblank_string(
                payload=payload,
                field_name="manifest_key",
            )
        )

        self._validate_manifest_key(
            manifest_key=manifest_key,
            document_id=document_id,
        )

        manifest_version_id = (
            self._read_optional_nonblank_string(
                payload=payload,
                field_name=(
                    "manifest_version_id"
                ),
            )
        )

        occurred_at_text = (
            self._require_nonblank_string(
                payload=payload,
                field_name="occurred_at",
            )
        )

        occurred_at = (
            self._parse_timestamp(
                occurred_at_text
            )
        )

        return ExtractionCompletedEvent(
            event_type=event_type,
            event_version=event_version,
            document_id=document_id,
            processing_schema_version=(
                processing_schema_version
            ),
            manifest_bucket=manifest_bucket,
            manifest_key=manifest_key,
            manifest_version_id=(
                manifest_version_id
            ),
            occurred_at=occurred_at,
        )

    def _parse_payload(
        self,
        message_body: str,
    ) -> dict[str, Any]:
        """
        Parse the top-level JSON object.
        """
        if not isinstance(
            message_body,
            str,
        ):
            raise IngestionEventJsonError(
                "Ingestion event body must be "
                "text."
            )

        if not message_body.strip():
            raise IngestionEventJsonError(
                "Ingestion event body must not "
                "be blank."
            )

        try:
            payload = json.loads(
                message_body
            )
        except JSONDecodeError as exception:
            raise IngestionEventJsonError(
                "Ingestion event body is not "
                "valid JSON."
            ) from exception

        if not isinstance(
            payload,
            dict,
        ):
            raise IngestionEventJsonError(
                "Ingestion event top-level JSON "
                "value must be an object."
            )

        return payload

    def _validate_event_contract(
        self,
        *,
        event_type: str,
        event_version: str,
    ) -> None:
        """
        Reject unsupported event types and contract
        versions.
        """
        if (
            event_type
            != self.SUPPORTED_EVENT_TYPE
        ):
            raise UnsupportedIngestionEventError(
                "Unsupported ingestion event_type "
                f"'{event_type}'. Expected "
                f"'{self.SUPPORTED_EVENT_TYPE}'."
            )

        if (
            event_version
            != self.SUPPORTED_EVENT_VERSION
        ):
            raise UnsupportedIngestionEventError(
                "Unsupported ingestion event_version "
                f"'{event_version}'. Expected "
                f"'{self.SUPPORTED_EVENT_VERSION}'."
            )

    def _validate_document_id(
        self,
        document_id: str,
    ) -> None:
        """
        Validate the deterministic Extraction
        document identifier.
        """
        if not self.DOCUMENT_ID_PATTERN.fullmatch(
            document_id
        ):
            raise IngestionEventFieldError(
                "Ingestion event document_id must "
                "be a 64-character lowercase "
                "SHA-256 hexadecimal value."
            )

    def _validate_processing_schema(
        self,
        processing_schema_version: str,
    ) -> None:
        """
        Accept only the Extraction schema currently
        supported by Ingestion.
        """
        if (
            processing_schema_version
            != self
            .SUPPORTED_PROCESSING_SCHEMA
        ):
            raise UnsupportedIngestionEventError(
                "Unsupported extraction processing "
                "schema "
                f"'{processing_schema_version}'. "
                "Expected "
                f"'{self.SUPPORTED_PROCESSING_SCHEMA}'."
            )

    def _validate_bucket_name(
        self,
        bucket_name: str,
    ) -> None:
        """
        Perform safe structural validation of the
        manifest bucket name.

        Full Amazon S3 naming validation remains the
        responsibility of infrastructure and S3.
        This check prevents malformed resource
        identifiers from entering the worker.
        """
        if any(
            character.isspace()
            for character
            in bucket_name
        ):
            raise IngestionEventFieldError(
                "Ingestion event manifest_bucket "
                "must not contain whitespace."
            )

        if (
            "/" in bucket_name
            or "\\" in bucket_name
        ):
            raise IngestionEventFieldError(
                "Ingestion event manifest_bucket "
                "must contain only the bucket name, "
                "not an object path."
            )

        if bucket_name.startswith(
            (
                "s3://",
                "http://",
                "https://",
            )
        ):
            raise IngestionEventFieldError(
                "Ingestion event manifest_bucket "
                "must not contain a URI scheme."
            )

    def _validate_manifest_key(
        self,
        *,
        manifest_key: str,
        document_id: str,
    ) -> None:
        """
        Require the authoritative Extraction success
        manifest location for the supplied document
        identity.
        """
        if manifest_key.startswith(
            "/"
        ):
            raise IngestionEventFieldError(
                "Ingestion event manifest_key "
                "must not begin with '/'."
            )

        if "\\" in manifest_key:
            raise IngestionEventFieldError(
                "Ingestion event manifest_key "
                "must use forward slashes."
            )

        key_parts = manifest_key.split(
            "/"
        )

        if (
            len(key_parts) != 3
            or key_parts[0]
            != self.MANIFEST_PREFIX
            or key_parts[1]
            != document_id
            or key_parts[2]
            != self.MANIFEST_FILE_NAME
        ):
            expected_key = (
                f"{self.MANIFEST_PREFIX}/"
                f"{document_id}/"
                f"{self.MANIFEST_FILE_NAME}"
            )

            raise IngestionEventIdentityError(
                "Ingestion event manifest_key must "
                "match the supplied document_id. "
                f"Expected '{expected_key}'."
            )

    def _parse_timestamp(
        self,
        value: str,
    ) -> datetime:
        """
        Parse one timezone-aware ISO 8601 timestamp
        and normalize it to UTC.
        """
        normalized_value = value

        if value.endswith(
            (
                "Z",
                "z",
            )
        ):
            normalized_value = (
                f"{value[:-1]}+00:00"
            )

        try:
            timestamp = datetime.fromisoformat(
                normalized_value
            )
        except ValueError as exception:
            raise IngestionEventFieldError(
                "Ingestion event occurred_at must "
                "be a valid ISO 8601 timestamp."
            ) from exception

        if (
            timestamp.tzinfo is None
            or timestamp.utcoffset()
            is None
        ):
            raise IngestionEventFieldError(
                "Ingestion event occurred_at must "
                "include timezone information."
            )

        return timestamp.astimezone(
            timezone.utc
        )

    def _require_nonblank_string(
        self,
        *,
        payload: dict[str, Any],
        field_name: str,
    ) -> str:
        """
        Read and normalize one required nonblank
        string field.
        """
        if field_name not in payload:
            raise IngestionEventFieldError(
                "Ingestion event is missing "
                f"required field '{field_name}'."
            )

        value = payload[
            field_name
        ]

        if not isinstance(
            value,
            str,
        ):
            raise IngestionEventFieldError(
                "Ingestion event field "
                f"'{field_name}' must be a string."
            )

        normalized_value = (
            value.strip()
        )

        if not normalized_value:
            raise IngestionEventFieldError(
                "Ingestion event field "
                f"'{field_name}' must not be blank."
            )

        return normalized_value

    def _read_optional_nonblank_string(
        self,
        *,
        payload: dict[str, Any],
        field_name: str,
    ) -> str | None:
        """
        Read an optional string that must be nonblank
        when supplied.

        A missing field and an explicit null both
        represent an unavailable object version.
        """
        value = payload.get(
            field_name
        )

        if value is None:
            return None

        if not isinstance(
            value,
            str,
        ):
            raise IngestionEventFieldError(
                "Ingestion event field "
                f"'{field_name}' must be a string "
                "or null."
            )

        normalized_value = (
            value.strip()
        )

        if not normalized_value:
            raise IngestionEventFieldError(
                "Ingestion event field "
                f"'{field_name}' must not be blank "
                "when supplied."
            )

        return normalized_value