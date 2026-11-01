import hashlib
import json

from dataclasses import dataclass
from typing import Any

from botocore.exceptions import (
    BotoCoreError,
    ClientError,
)

from aws_utils.s3 import S3Service
from models.ingestion_manifest import (
    IngestionFailureManifest,
    IngestionSuccessManifest,
)


class IngestionManifestStoreError(
    RuntimeError
):
    """
    Base exception for Ingestion manifest
    persistence.
    """


class IngestionManifestWriteError(
    IngestionManifestStoreError
):
    """
    An Ingestion manifest could not be written to
    Amazon S3.
    """


@dataclass(
    frozen=True,
    slots=True,
)
class StoredIngestionManifest:
    """
    Metadata returned after writing one Ingestion
    manifest.
    """

    bucket: str
    key: str

    version_id: str | None
    etag: str | None
    checksum_sha256: str

    content_length: int


class S3IngestionManifestStore:
    """
    Serialize and store completed or failed
    Ingestion manifests in Amazon S3.

    Output structure:

        <prefix>/<ingestion_id>/_SUCCESS.json
        <prefix>/<ingestion_id>/_FAILED.json
    """

    SUCCESS_FILE_NAME = "_SUCCESS.json"
    FAILURE_FILE_NAME = "_FAILED.json"

    def __init__(
        self,
        *,
        bucket: str,
        prefix: str = "ingestion-results",
        s3_service: S3Service | None = None,
    ):
        self.bucket = (
            self._normalize_required_string(
                value=bucket,
                field_name="bucket",
            )
        )

        self.prefix = (
            self._normalize_prefix(
                prefix
            )
        )

        if (
            s3_service is not None
            and not isinstance(
                s3_service,
                S3Service,
            )
        ):
            raise TypeError(
                "s3_service must be an S3Service "
                "or None."
            )

        self.s3_service = (
            s3_service
            or S3Service()
        )

    def write_success(
        self,
        manifest: IngestionSuccessManifest,
    ) -> StoredIngestionManifest:
        """
        Write one ingestion-success-v1 manifest.
        """
        if not isinstance(
            manifest,
            IngestionSuccessManifest,
        ):
            raise TypeError(
                "manifest must be an "
                "IngestionSuccessManifest."
            )

        key = self.build_success_key(
            manifest.ingestion_id
        )

        return self._write_manifest(
            key=key,
            payload=manifest.to_payload(),
            ingestion_id=manifest.ingestion_id,
            processing_status=(
                manifest.processing_status
            ),
            manifest_schema_version=(
                manifest
                .manifest_schema_version
            ),
        )

    def write_failure(
        self,
        manifest: IngestionFailureManifest,
    ) -> StoredIngestionManifest:
        """
        Write one ingestion-failure-v1 manifest.
        """
        if not isinstance(
            manifest,
            IngestionFailureManifest,
        ):
            raise TypeError(
                "manifest must be an "
                "IngestionFailureManifest."
            )

        key = self.build_failure_key(
            manifest.ingestion_id
        )

        return self._write_manifest(
            key=key,
            payload=manifest.to_payload(),
            ingestion_id=manifest.ingestion_id,
            processing_status=(
                manifest.processing_status
            ),
            manifest_schema_version=(
                manifest
                .manifest_schema_version
            ),
        )

    def build_success_key(
        self,
        ingestion_id: str,
    ) -> str:
        """
        Build the deterministic success-manifest
        key.
        """
        return self._build_key(
            ingestion_id=ingestion_id,
            file_name=self.SUCCESS_FILE_NAME,
        )

    def build_failure_key(
        self,
        ingestion_id: str,
    ) -> str:
        """
        Build the deterministic failure-manifest
        key.
        """
        return self._build_key(
            ingestion_id=ingestion_id,
            file_name=self.FAILURE_FILE_NAME,
        )

    def success_manifest_exists(
        self,
        ingestion_id: str,
    ) -> bool:
        """
        Return whether the deterministic success
        manifest currently exists.
        """
        return self.s3_service.object_exists(
            bucket=self.bucket,
            key=self.build_success_key(
                ingestion_id
            ),
        )

    def _write_manifest(
        self,
        *,
        key: str,
        payload: dict[str, Any],
        ingestion_id: str,
        processing_status: str,
        manifest_schema_version: str,
    ) -> StoredIngestionManifest:
        """
        Serialize and write one canonical manifest.
        """
        content = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )

        content_bytes = content.encode(
            "utf-8"
        )

        checksum_sha256 = (
            hashlib.sha256(
                content_bytes
            )
            .hexdigest()
        )

        try:
            response = (
                self.s3_service
                .upload_text(
                    bucket=self.bucket,
                    key=key,
                    content=content,
                    content_type=(
                        "application/json"
                    ),
                    metadata={
                        "ingestion-id": (
                            ingestion_id
                        ),
                        "processing-status": (
                            processing_status
                        ),
                        "manifest-schema-version": (
                            manifest_schema_version
                        ),
                        "content-sha256": (
                            checksum_sha256
                        ),
                    },
                )
            )
        except (
            BotoCoreError,
            ClientError,
            OSError,
            UnicodeError,
        ) as exception:
            raise IngestionManifestWriteError(
                "Ingestion manifest could not be "
                "written to Amazon S3."
            ) from exception

        version_id = self._read_optional_response_string(
            response=response,
            field_name="VersionId",
        )

        etag = self._read_optional_response_string(
            response=response,
            field_name="ETag",
        )

        if etag is not None:
            etag = etag.strip(
                '"'
            )

        return StoredIngestionManifest(
            bucket=self.bucket,
            key=key,
            version_id=version_id,
            etag=etag,
            checksum_sha256=(
                checksum_sha256
            ),
            content_length=len(
                content_bytes
            ),
        )

    def _build_key(
        self,
        *,
        ingestion_id: str,
        file_name: str,
    ) -> str:
        normalized_ingestion_id = (
            self._normalize_required_string(
                value=ingestion_id,
                field_name="ingestion_id",
            )
        )

        if "/" in normalized_ingestion_id:
            raise ValueError(
                "ingestion_id must not contain '/'."
            )

        return (
            f"{self.prefix}/"
            f"{normalized_ingestion_id}/"
            f"{file_name}"
        )

    @staticmethod
    def _read_optional_response_string(
        *,
        response: dict[str, Any],
        field_name: str,
    ) -> str | None:
        value = response.get(
            field_name
        )

        if value is None:
            return None

        if not isinstance(
            value,
            str,
        ):
            raise IngestionManifestWriteError(
                "Amazon S3 response field "
                f"'{field_name}' must be a string "
                "when returned."
            )

        normalized_value = value.strip()

        return (
            normalized_value
            if normalized_value
            else None
        )

    @staticmethod
    def _normalize_required_string(
        *,
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

    @staticmethod
    def _normalize_prefix(
        value: str,
    ) -> str:
        normalized_value = (
            S3IngestionManifestStore
            ._normalize_required_string(
                value=value,
                field_name="prefix",
            )
            .strip("/")
        )

        if not normalized_value:
            raise ValueError(
                "prefix must contain a usable "
                "Amazon S3 key prefix."
            )

        if "\\" in normalized_value:
            raise ValueError(
                "prefix must use forward slashes."
            )

        empty_components = [
            component
            for component
            in normalized_value.split("/")
            if not component
        ]

        if empty_components:
            raise ValueError(
                "prefix must not contain empty "
                "path components."
            )

        return normalized_value