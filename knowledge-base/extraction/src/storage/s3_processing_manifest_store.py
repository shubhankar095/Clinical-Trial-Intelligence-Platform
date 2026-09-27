import json
from dataclasses import asdict
from aws_utils.s3 import S3Service
from utils.logger import get_logger
from datetime import datetime, timezone
from models.document import ClinicalDocument 
from models.processing_manifest import ProcessingManifest


logger = get_logger(__name__)


class S3ProcessingManifestStore:

    def __init__(
        self,
        bucket_name: str,
        s3_service=None,
    ):
        self.bucket_name = bucket_name
        self.s3 = s3_service or S3Service()

    def build_object_key(
        self,
        document_id: str,
    ) -> str:
        if not document_id:
            raise ValueError("document_id must not be empty.")

        return f"canonical-documents/{document_id}/_SUCCESS.json"

    def exists(
        self,
        document_id: str,
    ) -> bool:
        return self.s3.object_exists(
            bucket=self.bucket_name,
            key=self.build_object_key(document_id),
        )

    def load(
        self,
        document_id: str,
    ) -> ProcessingManifest:
        object_key = (
            self.build_object_key(
                document_id
            )
        )

        payload = self.s3.download_text(
            bucket=self.bucket_name,
            key=object_key,
        )

        data = json.loads(payload)
        
        return ProcessingManifest(**data)

    def validate(
        self,
        document: ClinicalDocument,
        manifest: ProcessingManifest,
    ) -> None:
        expected = {
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
        }

        actual = {
            "document_id": (
                manifest.document_id
            ),
            "source_bucket": (
                manifest.source_bucket
            ),
            "source_key": (
                manifest.source_key
            ),
            "source_version_id": (
                manifest.source_version_id
            ),
            "processing_schema_version": (
                manifest
                .processing_schema_version
            ),
        }

        if actual != expected:
            raise ValueError(
                "Existing success manifest "
                "does not match the expected "
                "document identity."
            )

        if (
            manifest.processing_status
            != "SUCCESS"
        ):
            raise ValueError(
                "Existing processing manifest "
                "does not contain SUCCESS "
                "status."
            )

    def save(
        self,
        document: ClinicalDocument,
    ) -> str:
        if (
            document.processing_status
            != "SUCCESS"
        ):
            raise ValueError(
                "A success manifest cannot "
                "be written for a document "
                "that is not successful."
            )

        if not document.canonical_key:
            raise ValueError(
                "canonical_key must be set "
                "before writing the success "
                "manifest."
            )

        manifest = ProcessingManifest(
            document_id=(
                document.document_id
            ),
            source_bucket=(
                document.source_bucket
            ),
            source_key=(
                document.source_key
            ),
            source_version_id=(
                document.source_version_id
            ),
            processing_schema_version=(
                document
                .processing_schema_version
            ),
            canonical_bucket=(
                document.canonical_bucket
            ),
            canonical_key=(
                document.canonical_key
            ),
            completed_at=(
                datetime.now(
                    timezone.utc
                )
                .isoformat()
            ),
        )

        object_key = (
            self.build_object_key(
                document.document_id
            )
        )

        self.s3.upload_text(
            bucket=self.bucket_name,
            key=object_key,
            content=json.dumps(
                asdict(
                    manifest
                ),
                indent=2,
                ensure_ascii=False,
            ),
        )

        logger.info(
            "Saved processing success "
            "manifest.",
            extra={
                "event": (
                    "processing_manifest_saved"
                ),
                "document_id": (
                    document.document_id
                ),
                "manifest_key": object_key,
            },
        )

        return object_key