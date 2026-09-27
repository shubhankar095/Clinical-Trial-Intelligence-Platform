from pathlib import Path

from aws_utils.s3 import S3Service

from models.document import (
    ClinicalDocument,
)
from router.document_router import (
    get_processor,
)
from services.document_registration_service import (
    DocumentRegistrationService,
)
from storage.s3_document_store import (
    S3DocumentStore,
)
from storage.s3_processing_manifest_store import (
    S3ProcessingManifestStore,
)
from utils.logger import get_logger

from config.config import (
    canonical_document_bucket,
    processing_claim_heartbeat_seconds,
    processing_claim_lease_seconds,
    processing_registry_table,
)
from repositories.processing_registry import (
    ProcessingRegistry,
)

from services.processing_claim_heartbeat import (
    ProcessingClaimHeartbeat,
)

from exceptions.processing_claim import (
    ProcessingClaimUnavailableError,
)



logger = get_logger(__name__)


class DocumentExtractionService:

    def __init__(
        self,
        registration_service=None,
        s3_service=None,
        document_store=None,
        manifest_store=None,
        processing_registry=None,
    ):
        self.registration_service = (
            registration_service
            or DocumentRegistrationService()
        )

        self.s3_service = (
            s3_service
            or S3Service()
        )

        self.document_store = (
            document_store
            or S3DocumentStore(
                canonical_document_bucket
            )
        )

        self.manifest_store = (
            manifest_store
            or S3ProcessingManifestStore(
                canonical_document_bucket
            )
        )

        self.processing_registry = (
            processing_registry
            or ProcessingRegistry(
                table_name=(
                    processing_registry_table
                ),
                lease_seconds=(
                    processing_claim_lease_seconds
                ),
            )
        )

    def _delete_canonical_object(
        self,
        object_key: str,
        asset_type: str,
    ) -> None:
        if not object_key:
            return

        try:
            self.s3_service.delete_object(
                bucket=(
                    canonical_document_bucket
                ),
                key=object_key,
            )

            logger.info(
                f"Deleted orphaned "
                f"{asset_type}: "
                f"{object_key}"
            )

        except Exception:
            logger.exception(
                f"Failed to delete orphaned "
                f"{asset_type}: "
                f"{object_key}"
            )

    def _cleanup_document_assets(
        self,
        document: ClinicalDocument,
    ) -> None:
        logger.warning(
            "Cleaning canonical assets after "
            "document-save failure.",
            extra={
                "event": (
                    "canonical_asset_cleanup_"
                    "started"
                ),
                "document_id": (
                    document.document_id
                ),
                "image_count": len(
                    document.images
                ),
                "table_count": len(
                    document.tables
                ),
            },
        )

        for image in document.images:
            self._delete_canonical_object(
                object_key=image.s3_key,
                asset_type="image",
            )

        for table in document.tables:
            self._delete_canonical_object(
                object_key=table.s3_key,
                asset_type="table",
            )

        document.images = []
        document.tables = []
        document.image_count = 0
        document.table_count = 0

    def _mark_existing_success(
        self,
        document: ClinicalDocument,
    ) -> ClinicalDocument:
        manifest = (
            self.manifest_store.load(
                document.document_id
            )
        )

        self.manifest_store.validate(
            document=document,
            manifest=manifest,
        )

        document.canonical_bucket = (
            manifest.canonical_bucket
        )

        document.canonical_key = (
            manifest.canonical_key
        )

        document.processing_status = (
            "SUCCESS"
        )

        document.already_processed = True

        logger.info(
            "Document was already processed. "
            "Skipping duplicate extraction.",
            extra={
                "event": (
                    "duplicate_document_skipped"
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
                "canonical_key": (
                    document.canonical_key
                ),
            },
        )

        return document

    def _reconcile_existing_success(
        self,
        document: ClinicalDocument,
    ) -> ClinicalDocument:
        """
        Reconcile the DynamoDB processing registry
        from an authoritative S3 success manifest.

        The success manifest proves that canonical
        persistence completed. If the registry record
        is missing, create it and mark it completed.
        """
        existing_document = (
            self._mark_existing_success(
                document
            )
        )

        claim = None
        claim_completed = False

        try:
            claim = (
                self.processing_registry.acquire(
                    existing_document
                )
            )

            self.processing_registry.mark_completed(
                claim=claim,
                canonical_key=(
                    existing_document
                    .canonical_key
                ),
            )

            claim_completed = True

            logger.info(
                "Processing registry reconciled "
                "from the existing success manifest.",
                extra={
                    "event": (
                        "processing_registry_"
                        "reconciled"
                    ),
                    "document_id": (
                        existing_document
                        .document_id
                    ),
                    "canonical_key": (
                        existing_document
                        .canonical_key
                    ),
                },
            )

        except ProcessingClaimUnavailableError:
            logger.info(
                "Processing registry reconciliation "
                "was skipped because a registry "
                "record already exists.",
                extra={
                    "event": (
                        "processing_registry_"
                        "reconciliation_skipped"
                    ),
                    "document_id": (
                        existing_document
                        .document_id
                    ),
                },
            )

        except Exception:
            logger.exception(
                "Failed to reconcile the processing "
                "registry from the existing success "
                "manifest.",
                extra={
                    "event": (
                        "processing_registry_"
                        "reconciliation_failed"
                    ),
                    "document_id": (
                        existing_document
                        .document_id
                    ),
                },
            )

            raise

        finally:
            if (
                claim is not None
                and not claim_completed
            ):
                try:
                    self.processing_registry.release(
                        claim
                    )

                except Exception:
                    logger.exception(
                        "Failed to release the "
                        "processing claim created "
                        "during reconciliation.",
                        extra={
                            "event": (
                                "processing_registry_"
                                "reconciliation_release_"
                                "failed"
                            ),
                            "document_id": (
                                existing_document
                                .document_id
                            ),
                        },
                    )

        return existing_document

    def process_document(
        self,
        bucket_name: str,
        object_key: str,
        version_id: str,
        s3_metadata: dict,
    ) -> ClinicalDocument:
        document = (
            self.registration_service
            .register(
                bucket_name=bucket_name,
                object_key=object_key,
                version_id=version_id,
                s3_metadata=s3_metadata,
            )
        )

        if self.manifest_store.exists(
            document.document_id
        ):
            return self._reconcile_existing_success(
                document
            )

        claim = self.processing_registry.acquire(
            document
        )

        claim_completed = False

        claim_heartbeat = ProcessingClaimHeartbeat(
            processing_registry=self.processing_registry,
            claim=claim,
            heartbeat_seconds=processing_claim_heartbeat_seconds
        )

        claim_heartbeat.start()

        try:
            # Recheck after acquiring the claim. Another
            # worker may have completed processing between
            # the first marker check and our claim attempt.
            if self.manifest_store.exists(
                document.document_id
            ):
                existing_document = (
                    self._mark_existing_success(
                        document
                    )
                )

                # Stop renewals before changing the registry
                # record from PROCESSING to COMPLETED.
                claim_heartbeat.stop()
                claim_heartbeat.raise_if_failed()

                self.processing_registry.mark_completed(
                    claim=claim,
                    canonical_key=(
                        existing_document
                        .canonical_key
                    ),
                )

                claim_completed = True

                return existing_document

            local_file_path = (
                self.s3_service
                .download_file(
                    bucket=bucket_name,
                    key=object_key,
                    version_id=version_id,
                )
            )

            document.local_file_path = (
                local_file_path
            )

            logger.info(
                "Downloaded exact source "
                "object version.",
                extra={
                    "event": (
                        "source_document_downloaded"
                    ),
                    "document_id": (
                        document.document_id
                    ),
                    "source_bucket": bucket_name,
                    "source_key": object_key,
                    "source_version_id": (
                        version_id
                    ),
                },
            )

            processor = get_processor(
                document.file_format
            )

            document = processor.process(
                document
            )
            claim_heartbeat.raise_if_failed()

            if (
                document.processing_status
                != "SUCCESS"
            ):
                return document

            document.canonical_bucket = (
                canonical_document_bucket
            )

            document.canonical_key = (
                self.document_store
                .build_object_key(
                    document
                )
            )

            # Do not begin canonical persistence if claim
            # renewal has already failed.
            claim_heartbeat.raise_if_failed()

            try:
                self.document_store.save(
                    document
                )

            except Exception:
                logger.exception(
                    "Failed to save canonical "
                    "document. Rolling back "
                    "uploaded assets.",
                    extra={
                        "event": (
                            "canonical_document_"
                            "save_failed"
                        ),
                        "document_id": (
                            document.document_id
                        ),
                        "canonical_key": (
                            document.canonical_key
                        ),
                    },
                )

                self._cleanup_document_assets(
                    document
                )

                document.processing_status = (
                    "FAILED"
                )

                document.error_message = (
                    "Canonical document save failed."
                )

                raise

            # Canonical persistence succeeded. Check that
            # claim ownership was not lost during the save.
            claim_heartbeat.raise_if_failed()

            try:
                self.manifest_store.save(
                    document
                )

            except Exception:
                logger.exception(
                    "Canonical output was written, "
                    "but the success manifest "
                    "could not be saved. The SQS "
                    "message must not be "
                    "acknowledged.",
                    extra={
                        "event": (
                            "processing_manifest_"
                            "save_failed"
                        ),
                        "document_id": (
                            document.document_id
                        ),
                        "canonical_key": (
                            document.canonical_key
                        ),
                    },
                )

                raise
            
            claim_heartbeat.stop()
            claim_heartbeat.raise_if_failed()

            self.processing_registry.mark_completed(
                claim=claim,
                canonical_key=(
                    document.canonical_key
                ),
            )

            claim_completed = True

            return document

        finally:

            if claim_heartbeat is not None:  # pragma: no branch
                claim_heartbeat.stop()
                
            if document.local_file_path:
                try:
                    Path(
                        document.local_file_path
                    ).unlink(
                        missing_ok=True
                    )

                except OSError:
                    logger.exception(
                        "Failed to delete temporary "
                        "document file.",
                        extra={
                            "event": (
                                "temporary_document_"
                                "cleanup_failed"
                            ),
                            "path": (
                                document
                                .local_file_path
                            ),
                        },
                    )

                finally:
                    document.local_file_path = ""

            if not claim_completed:
                try:
                    self.processing_registry.release(
                        claim
                    )

                except Exception:
                    logger.exception(
                        "Failed to release document "
                        "processing claim.",
                        extra={
                            "event": (
                                "processing_claim_"
                                "release_failed"
                            ),
                            "document_id": (
                                document.document_id
                            ),
                        },
                    )