import json
import time
from datetime import datetime, timezone
from enum import Enum

from chunkers.chunker_factory import ChunkerFactory
from config import config
from embedders.embedder_factory import EmbedderFactory
from ingestion_events.base_ingestion_event_parser import BaseIngestionEventParser
from ingestion_events.ingestion_event import IngestionEventError
from ingestion_events.s3_ingestion_event import S3IngestionEventParser
from ingestion_events.sqs_event_consumer import SQSMessage, SQSEventConsumer
from exceptions.extraction_manifest import IngestionInputError
from exceptions.ingestion_event import IgnorableIngestionEvent
from exceptions.processing import (
    IngestionConfigurationError,
    PermanentIngestionError,
    ProcessingOwnershipLostError,
    RetryableIngestionError,
)
from indexers.indexer_factory import IndexerFactory
from models.canonical_document import CanonicalDocument
from models.document import DocumentChunk
from models.embedded_chunk import EmbeddedChunk
from models.extraction_manifest import ExtractionSuccessManifest
from models.index_record import IndexRecord
from models.ingestion_manifest import IngestionFailureManifest, IngestionSuccessManifest
from models.ingestion_profile import IngestionIdentity, IngestionProfile
from models.storage_location import StorageLocation
from repositories.processing_registry import ClaimDisposition, ProcessingClaim, ProcessingRegistry
from services.canonical_document_parser import CanonicalDocumentParser
from services.canonical_document_service import CanonicalDocumentService
from services.canonical_document_validator import CanonicalDocumentValidator
from services.chunking_service import ChunkingService
from services.embedding_service import EmbeddingService
from services.extraction_manifest_parser import ExtractionManifestParser
from services.extraction_manifest_service import ExtractionManifestService
from services.extraction_manifest_validator import ExtractionManifestValidator
from services.index_record_service import IndexRecordService
from services.indexing_service import IndexingService
from services.ingestion_identity_service import IngestionIdentityService
from services.message_visibility_heartbeat import MessageVisibilityHeartbeat
from services.processing_claim_heartbeat import ProcessingClaimHeartbeat
from services.shutdown_controller import ShutdownController
from storage.base_text_store import BaseTextStore
from storage.s3_ingestion_manifest_store import S3IngestionManifestStore
from storage.s3_text_store import S3TextStore
from utils.logger import get_logger

logger = get_logger(__name__)


class MessageDisposition(str, Enum):
    ACKNOWLEDGE = "ACKNOWLEDGE"
    RELEASE = "RELEASE"
    RETRY = "RETRY"


class IngestionWorker:
    """Production-shaped SQS to OpenSearch worker with safe finalization ordering."""

    def __init__(
        self,
        *,
        text_store: BaseTextStore | None = None,
        event_parser: BaseIngestionEventParser | None = None,
        event_consumer: SQSEventConsumer | None = None,
        processing_registry: ProcessingRegistry | None = None,
        result_store: S3IngestionManifestStore | None = None,
        shutdown_controller: ShutdownController | None = None,
        manifest_service: ExtractionManifestService | None = None,
        canonical_document_service: CanonicalDocumentService | None = None,
        identity_service: IngestionIdentityService | None = None,
        chunking_service: ChunkingService | None = None,
        embedding_service: EmbeddingService | None = None,
        index_record_service: IndexRecordService | None = None,
        indexing_service: IndexingService | None = None,
    ):
        self.text_store = text_store or S3TextStore()
        self.event_parser = event_parser or S3IngestionEventParser()
        self.event_consumer = event_consumer or SQSEventConsumer(
            queue_url=config.ingestion_queue_url,
            wait_time_seconds=config.sqs_wait_time_seconds,
            visibility_timeout_seconds=config.sqs_visibility_timeout_seconds,
            maximum_messages=1,
        )
        self.processing_registry = processing_registry or ProcessingRegistry(
            table_name=config.processing_registry_table,
            lease_seconds=config.processing_claim_lease_seconds,
            record_ttl_days=config.processing_record_ttl_days,
        )
        self.result_store = result_store or S3IngestionManifestStore(
            bucket=config.ingestion_result_bucket,
            prefix=config.ingestion_result_prefix,
        )
        self.shutdown_controller = shutdown_controller or ShutdownController()
        self.manifest_service = manifest_service or ExtractionManifestService(
            text_store=self.text_store,
            parser=ExtractionManifestParser(),
            validator=ExtractionManifestValidator(
                expected_canonical_bucket=config.canonical_document_bucket
            ),
        )
        self.canonical_document_service = canonical_document_service or CanonicalDocumentService(
            text_store=self.text_store,
            parser=CanonicalDocumentParser(),
            validator=CanonicalDocumentValidator(),
        )
        self.identity_service = identity_service or IngestionIdentityService()
        self.ingestion_profile = self._build_profile()
        self.chunking_service = chunking_service or ChunkingService(
            chunker=ChunkerFactory.create(self.ingestion_profile)
        )
        self.embedding_service = embedding_service or EmbeddingService(
            embedder=EmbedderFactory.create(
                profile=self.ingestion_profile,
                aws_region=config.aws_region,
                huggingface_api_token=config.huggingface_api_token,
                huggingface_api_provider=config.huggingface_api_provider,
                huggingface_api_base_url=config.huggingface_api_base_url,
                huggingface_api_timeout_seconds=config.huggingface_api_timeout_seconds,
                huggingface_api_max_attempts=config.huggingface_api_max_attempts,
            )
        )
        self.index_record_service = index_record_service or IndexRecordService()
        self.indexing_service = indexing_service or IndexingService(
            indexer=IndexerFactory.create(
                opensearch_deployment_type=config.opensearch_deployment_type,
                opensearch_endpoint=config.opensearch_endpoint,
                opensearch_region=config.opensearch_region,
                opensearch_index_prefix=config.opensearch_index_prefix,
                opensearch_refresh_after_index=config.opensearch_refresh_after_index,
                opensearch_bulk_max_records=config.opensearch_bulk_max_records,
                opensearch_bulk_max_bytes=config.opensearch_bulk_max_bytes,
                opensearch_bulk_max_attempts=config.opensearch_bulk_max_attempts,
                opensearch_visibility_timeout_seconds=config.opensearch_visibility_timeout_seconds,
                opensearch_visibility_poll_seconds=config.opensearch_visibility_poll_seconds,
            )
        )

    def run(self) -> None:
        self.shutdown_controller.install_signal_handlers()
        try:
            while not self.shutdown_controller.shutdown_requested:
                for message in self.event_consumer.receive_messages():
                    if self.shutdown_controller.shutdown_requested:
                        self.event_consumer.release_message(message)
                        break
                    self._process_message(message)
        finally:
            try:
                self.embedding_service.close()
            finally:
                self.shutdown_controller.restore_signal_handlers()

    def _process_message(self, message: SQSMessage) -> None:
        visibility = MessageVisibilityHeartbeat(
            consumer=self.event_consumer,
            message=message,
            heartbeat_seconds=config.sqs_visibility_heartbeat_seconds,
            extension_seconds=config.sqs_visibility_extension_seconds,
        )
        disposition = MessageDisposition.RETRY
        visibility.start()
        try:
            disposition = self._route_message(message, visibility)
        except IngestionConfigurationError:
            logger.exception("Ingestion deployment configuration failure.")
        except (RetryableIngestionError, ProcessingOwnershipLostError):
            logger.exception("Retryable Ingestion processing failure.")
        except Exception:
            logger.exception("Unexpected retryable Ingestion message failure.")
        finally:
            visibility.stop()

        if disposition == MessageDisposition.ACKNOWLEDGE:
            self.event_consumer.acknowledge_message(message)
        elif disposition == MessageDisposition.RELEASE:
            self.event_consumer.release_message(message)

    def _route_message(
        self,
        message: SQSMessage,
        visibility: MessageVisibilityHeartbeat,
    ) -> MessageDisposition:
        try:
            event = self.event_parser.parse(message.body)
        except IgnorableIngestionEvent:
            logger.info(
                "Ignoring Amazon S3 test event.",
                extra={
                    "event": "ingestion_s3_test_event_ignored",
                    "message_id": message.message_id,
                },
            )
            return MessageDisposition.ACKNOWLEDGE
        except IngestionEventError:
            logger.exception("Invalid pre-claim Ingestion event; retaining for SQS redrive.")
            return MessageDisposition.RETRY

        started_at = time.time()
        location = StorageLocation(
            bucket=event.manifest_bucket,
            key=event.manifest_key,
            version_id=event.manifest_version_id,
        )
        try:
            manifest = self.manifest_service.load_and_validate(location)
            document = self.canonical_document_service.load_and_validate(manifest)
        except IngestionInputError:
            logger.exception("Invalid pre-claim input; retaining for SQS redrive.")
            return MessageDisposition.RETRY

        identity = self.identity_service.create_ingestion_identity(
            document=document,
            manifest=manifest,
            profile=self.ingestion_profile,
        )
        claim_result = self.processing_registry.acquire_claim(
            ingestion_id=identity.ingestion_id,
            document_id=identity.document_id,
            ingestion_profile_id=identity.ingestion_profile_id,
            manifest_bucket=location.bucket,
            manifest_key=location.key,
            manifest_version_id=location.version_id,
        )
        if claim_result.disposition == ClaimDisposition.COMPLETED:
            visibility.raise_for_failure()
            return MessageDisposition.ACKNOWLEDGE
        if claim_result.disposition == ClaimDisposition.UNAVAILABLE:
            return MessageDisposition.RELEASE
        if claim_result.claim is None:
            raise RetryableIngestionError("Acquired processing claim is missing.")

        return self._process_claimed(
            manifest=manifest,
            document=document,
            identity=identity,
            claim=claim_result.claim,
            location=location,
            visibility=visibility,
            started_at=started_at
        )

    def _process_claimed(
        self,
        *,
        manifest: ExtractionSuccessManifest,
        document: CanonicalDocument,
        identity: IngestionIdentity,
        claim: ProcessingClaim,
        location: StorageLocation,
        visibility: MessageVisibilityHeartbeat,
        started_at: float,
    ) -> MessageDisposition:
        
        heartbeat = ProcessingClaimHeartbeat(
            registry=self.processing_registry,
            claim=claim,
            heartbeat_seconds=config.processing_claim_heartbeat_seconds,
        )
        heartbeat.start()
        try:
            chunks, records, destination = self._execute_pipeline(document, identity)
            visibility.raise_for_failure()
            heartbeat.raise_for_failure()
            stored = self.result_store.write_success(
                self._success_manifest(manifest, identity, chunks, records, destination)
            )
            visibility.raise_for_failure()
            heartbeat.raise_for_failure()
            heartbeat.stop()
            heartbeat.raise_for_failure()
            self.processing_registry.mark_completed(
                heartbeat.claim,
                index_destination=destination,
                index_record_count=len(records),
                chunk_count=len(chunks),
                success_manifest_bucket=stored.bucket,
                success_manifest_key=stored.key,
                success_manifest_version_id=stored.version_id,
            )

            logger.info("ingestion_completed",
                extra={
                    "event": "ingestion_completed",
                    "processing_status": "SUCCESS",
                    "ingestion_id": identity.ingestion_id,
                    "document_id": identity.document_id,
                    "ingestion_profile_id": identity.ingestion_profile_id,
                    "duration_seconds": round(time.time() - started_at, 3),
                    "index_record_count": len(records),
                    "chunk_count": len(chunks),
                    "index_destination": destination,
                },
            )
            return MessageDisposition.ACKNOWLEDGE
        except (PermanentIngestionError, IngestionInputError) as exception:
            heartbeat.stop()
            heartbeat.raise_for_failure()
            failure = IngestionFailureManifest(
                event_type="INGESTION_FAILED",
                manifest_schema_version="ingestion-failure-v1",
                processing_status="FAILED",
                document_id=identity.document_id,
                ingestion_id=identity.ingestion_id,
                ingestion_profile_id=identity.ingestion_profile_id,
                processing_schema_version=manifest.processing_schema_version,
                ingestion_schema_version=self.ingestion_profile.ingestion_schema_version,
                manifest_bucket=location.bucket,
                manifest_key=location.key,
                manifest_version_id=location.version_id,
                error_type=type(exception).__name__,
                error_message=str(exception),
                failed_at=datetime.now(timezone.utc),
            )
            self.result_store.write_failure(failure)
            self.processing_registry.mark_failed(
                heartbeat.claim,
                error_type=type(exception).__name__,
                error_message=str(exception),
            )
            logger.error("ingestion_failed",
                extra={
                    "event": "ingestion_failed",
                    "processing_status": "FAILED",
                    "ingestion_id": identity.ingestion_id,
                    "document_id": identity.document_id,
                    "ingestion_profile_id": identity.ingestion_profile_id,
                    "duration_seconds": round(time.time() - started_at, 3),
                    "error_type": type(exception).__name__,
                    "error_message": str(exception),
                },
            )

            return MessageDisposition.ACKNOWLEDGE
        finally:
            heartbeat.stop()

    def _execute_pipeline(
        self,
        document: CanonicalDocument,
        identity: IngestionIdentity,
    ) -> tuple[tuple[DocumentChunk, ...], tuple[IndexRecord, ...], str]:
        chunks = self.chunking_service.chunk_document(
            document=document,
            identity=identity,
            profile=self.ingestion_profile,
        )
        embedded: tuple[EmbeddedChunk, ...] = self.embedding_service.embed_chunks(
            chunks=chunks,
            profile=self.ingestion_profile,
        )
        records = self.index_record_service.create_records(
            document=document,
            identity=identity,
            profile=self.ingestion_profile,
            embedded_chunks=embedded,
        )
        destination = self.indexing_service.index_records(
            ingestion_id=identity.ingestion_id,
            records=records,
        )
        return chunks, records, destination

    def _success_manifest(
        self,
        manifest: ExtractionSuccessManifest,
        identity: IngestionIdentity,
        chunks: tuple[DocumentChunk, ...],
        records: tuple[IndexRecord, ...],
        destination: str,
    ) -> IngestionSuccessManifest:
        return IngestionSuccessManifest(
            event_type="INGESTION_COMPLETED",
            manifest_schema_version="ingestion-success-v1",
            processing_status="SUCCESS",
            document_id=identity.document_id,
            ingestion_id=identity.ingestion_id,
            ingestion_profile_id=identity.ingestion_profile_id,
            processing_schema_version=manifest.processing_schema_version,
            ingestion_schema_version=self.ingestion_profile.ingestion_schema_version,
            index_schema_version=self.ingestion_profile.index_schema_version,
            source_bucket=manifest.source_bucket,
            source_key=manifest.source_key,
            source_version_id=manifest.source_version_id,
            canonical_bucket=identity.canonical_bucket,
            canonical_key=identity.canonical_key,
            canonical_version_id=identity.canonical_version_id,
            canonical_sha256=identity.canonical_sha256,
            index_destination=destination,
            index_record_count=len(records),
            chunk_count=len(chunks),
            embedding_provider=self.ingestion_profile.embedding_provider,
            embedding_model_id=self.ingestion_profile.embedding_model_id,
            embedding_dimensions=self.ingestion_profile.embedding_dimensions,
            embedding_normalized=self.ingestion_profile.embedding_normalize,
            completed_at=datetime.now(timezone.utc),
        )

    def _build_profile(self) -> IngestionProfile:
        return IngestionProfile(
            ingestion_schema_version=config.ingestion_schema_version,
            chunker_type=config.chunker_type,
            chunker_version=config.chunker_version,
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
            embedding_provider=config.embedding_provider,
            embedding_model_id=config.embedding_model_id,
            embedding_dimensions=config.embedding_dimensions,
            embedding_normalize=config.embedding_normalize,
            embedding_model_options_json=json.dumps(
                config.embedding_model_options,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ),
            index_schema_version=config.index_schema_version,
        )
