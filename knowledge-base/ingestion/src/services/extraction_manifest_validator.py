import re

from models.extraction_manifest import (
    ExtractionSuccessManifest,
)
from models.storage_location import (
    StorageLocation,
)
from exceptions.extraction_manifest import (
    ManifestFieldError,
    ManifestIdentityMismatchError,
    ManifestLocationError,
    UnsupportedExtractionSchemaError,
)


class ExtractionManifestValidator:
    """
    Validate the extraction-success-v1 business
    contract required by ingestion.
    """

    SUPPORTED_PROCESSING_SCHEMA = (
        "extraction-v1"
    )

    SUCCESS_STATUS = "SUCCESS"

    DOCUMENT_ID_PATTERN = re.compile(
        r"^[0-9a-f]{64}$"
    )

    MANIFEST_PREFIX = (
        "canonical-documents"
    )

    MANIFEST_FILE_NAME = (
        "_SUCCESS.json"
    )

    CANONICAL_FILE_NAME = (
        "extracted-document.json"
    )

    def __init__(
        self,
        expected_canonical_bucket: (
            str | None
        ) = None,
    ):
        if (
            expected_canonical_bucket
            is not None
            and not expected_canonical_bucket
            .strip()
        ):
            raise ValueError(
                "expected_canonical_bucket "
                "must not be blank when "
                "supplied."
            )

        self.expected_canonical_bucket = (
            expected_canonical_bucket
        )

    def validate(
        self,
        manifest: ExtractionSuccessManifest,
        location: StorageLocation,
    ) -> ExtractionSuccessManifest:
        """
        Validate and return the supplied manifest.

        Returning the manifest allows the validator
        to be used fluently by orchestration services.
        """

        if not isinstance(manifest, ExtractionSuccessManifest):
            raise TypeError("manifest must be an ExtractionSuccessManifest.")
        
        if not isinstance(location, StorageLocation):
            raise TypeError("location must be a StorageLocation.")

        path_document_id = (
            self._validate_location(
                location
            )
        )

        self._validate_document_id(
            manifest.document_id
        )

        if (
            path_document_id
            != manifest.document_id
        ):
            raise (
                ManifestIdentityMismatchError(
                    "Manifest document_id does "
                    "not match the document ID "
                    "in the manifest key."
                )
            )

        self._validate_status(
            manifest.processing_status
        )

        self._validate_schema(
            manifest
            .processing_schema_version
        )

        self._validate_canonical_bucket(
            manifest.canonical_bucket
        )

        self._validate_canonical_key(
            manifest
        )

        self._validate_completed_at(
            manifest
        )

        return manifest

    def _validate_location(
        self,
        location: StorageLocation,
    ) -> str:
        normalized_key = (
            location.key.strip("/")
        )

        key_parts = normalized_key.split(
            "/"
        )

        if (
            len(key_parts) != 3
            or key_parts[0]
            != self.MANIFEST_PREFIX
            or key_parts[2]
            != self.MANIFEST_FILE_NAME
            or not key_parts[1]
        ):
            raise ManifestLocationError(
                "Extraction success manifest "
                "key must match "
                "'canonical-documents/"
                " document-id>/_SUCCESS.json'."
            )

        return key_parts[1]

    def _validate_document_id(
        self,
        document_id: str,
    ) -> None:
        if not self.DOCUMENT_ID_PATTERN.fullmatch(
            document_id
        ):
            raise ManifestFieldError(
                "Extraction manifest document_id "
                "must be a 64-character lowercase "
                "SHA-256 hexadecimal value."
            )

    def _validate_status(
        self,
        processing_status: str,
    ) -> None:
        if (
            processing_status
            != self.SUCCESS_STATUS
        ):
            raise ManifestFieldError(
                "Extraction manifest "
                "processing_status must be "
                "exactly 'SUCCESS'."
            )

    def _validate_schema(
        self,
        processing_schema_version: str,
    ) -> None:
        if (
            processing_schema_version
            != self
            .SUPPORTED_PROCESSING_SCHEMA
        ):
            raise (
                UnsupportedExtractionSchemaError(
                    "Unsupported extraction "
                    "processing schema "
                    f"'{processing_schema_version}'."
                )
            )

    def _validate_canonical_bucket(
        self,
        canonical_bucket: str,
    ) -> None:
        if (
            self.expected_canonical_bucket
            is None
        ):
            return

        if (
            canonical_bucket
            != self.expected_canonical_bucket
        ):
            raise (
                ManifestIdentityMismatchError(
                    "Manifest canonical_bucket "
                    "does not match the expected "
                    "canonical bucket."
                )
            )

    def _validate_canonical_key(
        self,
        manifest: ExtractionSuccessManifest,
    ) -> None:
        expected_key = (
            f"{self.MANIFEST_PREFIX}/"
            f"{manifest.document_id}/"
            f"{self.CANONICAL_FILE_NAME}"
        )

        if (
            manifest.canonical_key
            != expected_key
        ):
            raise (
                ManifestIdentityMismatchError(
                    "Manifest canonical_key does "
                    "not match the canonical "
                    "document location required "
                    "for its document_id."
                )
            )

    def _validate_completed_at(
        self,
        manifest: ExtractionSuccessManifest,
    ) -> None:
        if (
            manifest.completed_at.tzinfo
            is None
            or manifest.completed_at
            .utcoffset()
            is None
        ):
            raise ManifestFieldError(
                "Extraction manifest "
                "completed_at must contain "
                "timezone information."
            )