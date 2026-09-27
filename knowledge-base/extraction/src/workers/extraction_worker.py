import json
import time
import signal
from utils.logger import get_logger
from urllib.parse import unquote_plus
from events.sqs_event_consumer import SQSEventConsumer
from exceptions.processing_claim import ProcessingClaimUnavailableError
from services.document_extraction_service import DocumentExtractionService
from services.message_visibility_heartbeat import MessageVisibilityHeartbeat
from config.config import document_uploaded_queue_url, sqs_visibility_extension_seconds, sqs_visibility_heartbeat_seconds



logger = get_logger(__name__)


class ExtractionWorker:

    def __init__(
        self,
        consumer=None,
        extraction_service=None,
    ):
        self.consumer = (
            consumer
            or SQSEventConsumer(
                document_uploaded_queue_url
            )

            
        )

        self.extraction_service = (
            extraction_service
            or DocumentExtractionService()
        )

        self.shutdown_requested = False
        self.processing_active = False
        self.active_message_id = None

    def _process_object(
        self,
        bucket: str,
        key: str,
        version_id: str,
        s3_metadata: dict | None = None,
    ) -> None:
        started_at = time.monotonic()

        if not version_id:
            raise ValueError(
                "S3 source version ID is required."
            )

        logger.info(
            "Processing object",
            extra={
                "event": (
                    "document_processing_started"
                ),
                "source_bucket": bucket,
                "source_key": key,
                "source_version_id": (
                    version_id
                ),
            },
        )

        document = (
            self.extraction_service
            .process_document(
                bucket_name=bucket,
                object_key=key,
                version_id=version_id,
                s3_metadata=(
                    s3_metadata or {}
                ),
            )
        )

        if (
            document.processing_status
            != "SUCCESS"
        ):
            raise RuntimeError(
                document.error_message
                or "Document processing failed."
            )

        if document.already_processed:
            logger.info(
                "Duplicate document event "
                "completed without reprocessing.",
                extra={
                    "event": (
                        "duplicate_document_event_"
                        "completed"
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

            return

        duration_seconds = round(
            time.monotonic()
            - started_at,
            3,
        )

        logger.info(
            "Document processed successfully",
            extra={
                "event": (
                    "document_processed"
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
                "processing_status": (
                    document.processing_status
                ),
                "page_count": (
                    document.page_count
                ),
                "ocr_page_count": (
                    document.ocr_page_count
                ),
                "image_count": (
                    document.image_count
                ),
                "table_count": (
                    document.table_count
                ),
                "warning_count": len(
                    document.warnings
                ),
                "duration_seconds": (
                    duration_seconds
                ),
            },
        )


    def _process_s3_record(
        self,
        record: dict,
    ) -> None:
        if record.get("eventSource") != "aws:s3":
            raise ValueError(
                "Unsupported event source: "
                f"{record.get('eventSource')}"
            )

        s3              = record.get("s3", {} )
        bucket          = s3.get("bucket", {} ).get("name")
        object_details  = s3.get("object", {})
        key             = object_details.get("key")
        version_id      = object_details.get("versionId")
        event_name      = record.get("eventName")
        event_time      = record.get("eventTime")
        sequencer       = object_details.get("sequencer")

        if not bucket or not key:
            raise ValueError("S3 event is missing bucket or object key.")

        if not version_id:
            raise ValueError(
                "S3 event is missing object "
                "versionId. Version-aware "
                "processing is required."
            )

        decoded_key = unquote_plus(key)

        logger.info(
            "Received S3 object event",
            extra={
                "event": (
                    "s3_object_event_received"
                ),
                "source_bucket": bucket,
                "source_key": decoded_key,
                "source_version_id": (
                    version_id
                ),
                "event_name": event_name,
                "event_time": event_time,
                "sequencer": sequencer,
            },
        )

        self._process_object(
            bucket=bucket,
            key=decoded_key,
            version_id=version_id,
            s3_metadata={},
        )

    def _process_message_body(
        self,
        body: dict,
    ) -> None:

        if body.get("Event") == "s3:TestEvent":
            logger.info(
                "Ignoring S3 test event."
            )
            return

        records = body.get("Records")

        if records is not None:

            if not isinstance(records, list):
                raise ValueError(
                    "S3 Records must be a list."
                )

            if not records:
                raise ValueError(
                    "S3 event contains no records."
                )

            record_count = len(records)

            for record_index, record in enumerate(records, start=1):
                logger.info(
                    "Processing S3 event record",
                    extra={
                        "event": (
                            "s3_event_record_started"
                        ),
                        "record_index": (
                            record_index
                        ),
                        "record_count": (
                            record_count
                        ),
                    },
                )

                self._process_s3_record(record)

                logger.info(
                    "S3 event record completed",
                    extra={
                        "event": (
                            "s3_event_record_completed"
                        ),
                        "record_index": (
                            record_index
                        ),
                        "record_count": (
                            record_count
                        ),
                    },
                )

            return

        bucket = body.get("bucket")
        key = body.get("key")
        version_id = body.get("version_id")

        if bucket and key:
            if not version_id:
                raise ValueError(
                    "Custom document message is "
                    "missing version_id."
                )

            metadata = body.get("metadata",{})

            if not isinstance(metadata, dict):
                raise ValueError("Document metadata must be a JSON object.")

            self._process_object(
                bucket=bucket,
                key=key,
                version_id=version_id,
                s3_metadata=metadata,
            )

            return

        raise ValueError("Unsupported queue message format.")

    def _release_unstarted_message(
        self,
        message: dict,
    ) -> None:
        message_id = message.get("MessageId", "unknown" )

        receipt_handle = message.get("ReceiptHandle")

        if not receipt_handle:
            logger.warning(
                "Cannot release unstarted "
                "message because its receipt "
                "handle is missing.",
                extra={
                    "event": (
                        "unstarted_message_"
                        "release_skipped"
                    ),
                    "message_id": message_id,
                },
            )

            return

        try:
            (
                self.consumer
                .change_message_visibility(
                    receipt_handle=receipt_handle,
                    visibility_timeout=0,
                )
            )

            logger.info(
                "Released unstarted message "
                "after shutdown request.",
                extra={
                    "event": (
                        "unstarted_message_"
                        "released"
                    ),
                    "message_id": message_id,
                },
            )

        except Exception:
            logger.exception(
                "Failed to release unstarted "
                "message after shutdown request.",
                extra={
                    "event": (
                        "unstarted_message_"
                        "release_failed"
                    ),
                    "message_id": message_id,
                },
            )

    def _process_message(
        self,
        message: dict,
    ) -> None:

        message_id = message.get("MessageId", "unknown")
        receipt_handle = message.get("ReceiptHandle")
        receive_count = message.get("Attributes", {}).get("ApproximateReceiveCount","unknown")
        

        if not receipt_handle:
            logger.error( "SQS message is missing its receipt handle.",
                extra={
                    "event": (
                        "message_receipt_"
                        "handle_missing"
                    ),
                    "message_id": message_id,
                },
            )

            return

        heartbeat = (
            MessageVisibilityHeartbeat(
                consumer=self.consumer,
                receipt_handle=receipt_handle,
                heartbeat_seconds=sqs_visibility_heartbeat_seconds,
                extension_seconds=sqs_visibility_extension_seconds,
            )
        )

        self.processing_active = True
        self.active_message_id = message_id
        heartbeat_started = False

        try:
            body = json.loads(message["Body"])

            if not isinstance(body, dict):
                raise ValueError("Queue message body must be a JSON object.")

            heartbeat.start()
            heartbeat_started = True

            self._process_message_body(body)

            

            if heartbeat.failed:
                logger.warning(
                    "SQS visibility heartbeat "
                    "failed during processing, "
                    "but document processing "
                    "completed. Attempting to "
                    "acknowledge the message.",
                    extra={
                        "event": (
                            "message_visibility_"
                            "heartbeat_degraded"
                        ),
                        "message_id": message_id,
                    },
                )

            self.consumer.delete_message(receipt_handle)

            logger.info("Message acknowledged.",
                extra={
                    "event": "message_acknowledged",
                    "message_id": message_id,
                },
            )

        except ProcessingClaimUnavailableError:
            logger.info(
                "Message processing deferred because "
                "another worker owns the document "
                "processing claim.",
                extra={
                    "event": (
                    "message_processing_deferred"
                ),
                "message_id": message_id,
                "receive_count": receive_count,
                },
            )    

        except Exception:

            logger.exception("Message processing failed.",
                extra={
                    "event": "message_processing_failed",
                    "message_id": message_id,
                    "receive_count": receive_count
                },
            )

        finally:
            if heartbeat_started:
                heartbeat.stop()
            self.processing_active = False
            self.active_message_id = None

    def _request_shutdown(
        self,
        signum,
        frame,
    ) -> None:

        if self.shutdown_requested:
            return

        self.shutdown_requested = True

        logger.warning(
            f"Shutdown requested. "
            f"signal={signum}. "
            f"The worker will stop receiving "
            f"new messages after the current "
            f"message completes."
        )

    def _register_signal_handlers(
        self,
    ) -> None:

        signal.signal(
            signal.SIGTERM,
            self._request_shutdown,
        )

        signal.signal(
            signal.SIGINT,
            self._request_shutdown,
        )

    def run(self) -> None:

        self._register_signal_handlers()

        logger.info("Waiting for document upload events...")

        receive_failure_count = 0

        while not self.shutdown_requested:

            try:
                response = self.consumer.receive_message()
                receive_failure_count = 0

                messages = response.get("Messages", [] )

                if not messages:
                    logger.debug("No messages available.")
                    continue

                logger.info(
                    f"Received {len(messages)} "
                    f"message(s)."
                )

                for message in messages:

                    if self.shutdown_requested:
                        self._release_unstarted_message(message)
                        logger.info(
                            "Shutdown requested. "
                            "The unstarted message was "
                            "returned to SQS.",
                            extra={
                                "event": (
                                    "shutdown_message_"
                                    "released"
                                ),
                            },
                        )

                        break

                    self._process_message(
                        message
                    )

            except Exception:

                receive_failure_count += 1

                backoff_seconds = min(
                    2 ** receive_failure_count,
                    60,
                )

                logger.exception(
                    f"Failed to receive messages "
                    f"from SQS. "
                    f"Retrying in "
                    f"{backoff_seconds} seconds."
                )

                time.sleep(
                    backoff_seconds
                )

        logger.info("Extraction worker stopped.")