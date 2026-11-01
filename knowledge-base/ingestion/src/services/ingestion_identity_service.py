import hashlib
import json

from dataclasses import asdict
from typing import Any

from models.canonical_document import (
    CanonicalDocument,
)
from models.extraction_manifest import (
    ExtractionSuccessManifest,
)
from models.ingestion_profile import (
    IngestionIdentity,
    IngestionProfile,
)


class IngestionIdentityService:
    """
    Produce deterministic ingestion profile and
    ingestion generation identities.

    Identity payloads are serialized using sorted
    JSON keys and compact separators so dictionary
    ordering and formatting cannot change the hash.
    """

    PROFILE_ID_PREFIX = (
        "ingestion-profile"
    )

    INGESTION_ID_PREFIX = (
        "ingestion"
    )

    def create_profile_id(
        self,
        profile: IngestionProfile,
    ) -> str:
        """
        Create a deterministic SHA-256 identifier
        for the supplied ingestion profile.
        """
        if not isinstance(
            profile,
            IngestionProfile,
        ):
            raise TypeError(
                "profile must be an "
                "IngestionProfile."
            )

        profile_payload = {
            "identity_type": (
                self.PROFILE_ID_PREFIX
            ),
            "profile": asdict(
                profile
            ),
        }

        return self._hash_payload(
            profile_payload
        )

    def create_ingestion_identity(
        self,
        document: CanonicalDocument,
        manifest: ExtractionSuccessManifest,
        profile: IngestionProfile,
    ) -> IngestionIdentity:
        """
        Create the deterministic identity for one
        canonical document and ingestion profile.
        """
        if not isinstance(
            document,
            CanonicalDocument,
        ):
            raise TypeError(
                "document must be a "
                "CanonicalDocument."
            )

        if not isinstance(
            manifest,
            ExtractionSuccessManifest,
        ):
            raise TypeError(
                "manifest must be an "
                "ExtractionSuccessManifest."
            )

        if not isinstance(
            profile,
            IngestionProfile,
        ):
            raise TypeError(
                "profile must be an "
                "IngestionProfile."
            )

        if (
            document.document_id
            != manifest.document_id
        ):
            raise ValueError(
                "Canonical document and "
                "extraction manifest must have "
                "the same document_id."
            )

        ingestion_profile_id = (
            self.create_profile_id(
                profile
            )
        )

        canonical_version_id = (
            self._optional_manifest_string(
                manifest=manifest,
                field_name=(
                    "canonical_version_id"
                ),
            )
        )

        canonical_sha256 = (
            self._optional_manifest_string(
                manifest=manifest,
                field_name=(
                    "canonical_sha256"
                ),
            )
        )

        identity_payload = {
            "identity_type": (
                self.INGESTION_ID_PREFIX
            ),
            "document_id": (
                document.document_id
            ),
            "source_bucket": (
                document.source_bucket
            ),
            "source_key": (
                document.source_key
            ),
            "source_version_id": (
                document.source_version_id
            ),
            "processing_schema_version": (
                document
                .processing_schema_version
            ),
            "canonical_bucket": (
                document.canonical_bucket
            ),
            "canonical_key": (
                document.canonical_key
            ),
            "canonical_version_id": (
                canonical_version_id
            ),
            "canonical_sha256": (
                canonical_sha256
            ),
            "ingestion_profile_id": (
                ingestion_profile_id
            ),
        }

        ingestion_id = self._hash_payload(
            identity_payload
        )

        return IngestionIdentity(
            document_id=(
                document.document_id
            ),
            ingestion_profile_id=(
                ingestion_profile_id
            ),
            ingestion_id=ingestion_id,
            canonical_bucket=(
                document.canonical_bucket
            ),
            canonical_key=(
                document.canonical_key
            ),
            canonical_version_id=(
                canonical_version_id
            ),
            canonical_sha256=(
                canonical_sha256
            ),
        )

    def _hash_payload(
        self,
        payload: dict[str, Any],
    ) -> str:
        """
        Serialize and hash one identity payload.
        """
        serialized_payload = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

        return hashlib.sha256(
            serialized_payload.encode(
                "utf-8"
            )
        ).hexdigest()

    def _optional_manifest_string(
        self,
        manifest: ExtractionSuccessManifest,
        field_name: str,
    ) -> str | None:
        """
        Return a normalized optional value from
        forward-compatible manifest fields.
        """
        value = (
            manifest.additional_fields.get(
                field_name
            )
        )

        if value is None:
            return None

        if not isinstance(
            value,
            str,
        ):
            raise ValueError(
                "Extraction manifest field "
                f"'{field_name}' must be a "
                "string when supplied."
            )

        normalized_value = (
            value.strip()
        )

        if not normalized_value:
            raise ValueError(
                "Extraction manifest field "
                f"'{field_name}' must not be "
                "blank when supplied."
            )

        return normalized_value