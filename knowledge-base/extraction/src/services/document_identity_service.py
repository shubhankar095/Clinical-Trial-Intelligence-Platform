import hashlib
import json


class DocumentIdentityService:
    """
    Generate deterministic document identities from
    immutable source and processing information.
    """

    def create_document_id(
        self,
        source_bucket: str,
        source_key: str,
        source_version_id: str,
        processing_schema_version: str,
    ) -> str:
        source_bucket = (
            source_bucket.strip()
        )

        source_key = (
            source_key.strip()
        )

        source_version_id = (
            source_version_id.strip()
        )

        processing_schema_version = (
            processing_schema_version.strip()
        )

        if not source_bucket:
            raise ValueError(
                "source_bucket must not be empty."
            )

        if not source_key:
            raise ValueError(
                "source_key must not be empty."
            )

        if not source_version_id:
            raise ValueError(
                "source_version_id must not "
                "be empty."
            )

        if not processing_schema_version:
            raise ValueError(
                "processing_schema_version "
                "must not be empty."
            )

        identity_payload = {
            "processing_schema_version": (
                processing_schema_version
            ),
            "source_bucket": source_bucket,
            "source_key": source_key,
            "source_version_id": (
                source_version_id
            ),
        }

        serialized_identity = json.dumps(
            identity_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

        return hashlib.sha256(
            serialized_identity.encode(
                "utf-8"
            )
        ).hexdigest()