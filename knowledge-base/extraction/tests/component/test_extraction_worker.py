import json
from dataclasses import replace
from unittest.mock import Mock

import pytest

from exceptions.processing_claim import (
    ProcessingClaimUnavailableError,
)
from models.document import ClinicalDocument
from workers.extraction_worker import ExtractionWorker


pytestmark = pytest.mark.component


class FakeConsumer:

    def __init__(
        self,
        messages=None,
    ):
        self.messages = messages or []
        self.deleted_receipts = []
        self.visibility_calls = []
        self.receive_calls = 0

    def receive_message(
        self,
    ):
        self.receive_calls += 1

        return {
            "Messages": self.messages,
        }

    def delete_message(
        self,
        receipt_handle,
    ):
        self.deleted_receipts.append(
            receipt_handle
        )

    def change_message_visibility(
        self,
        receipt_handle,
        visibility_timeout,
    ):
        self.visibility_calls.append(
            {
                "receipt_handle": (
                    receipt_handle
                ),
                "visibility_timeout": (
                    visibility_timeout
                ),
            }
        )


class FakeExtractionService:

    def __init__(
        self,
        document=None,
        exception=None,
    ):
        self.document = document
        self.exception = exception
        self.calls = []

    def process_document(
        self,
        bucket_name,
        object_key,
        version_id,
        s3_metadata,
    ):
        self.calls.append(
            {
                "bucket_name": (
                    bucket_name
                ),
                "object_key": (
                    object_key
                ),
                "version_id": (
                    version_id
                ),
                "s3_metadata": (
                    s3_metadata
                ),
            }
        )

        if self.exception:
            raise self.exception

        return self.document


@pytest.fixture
def successful_document():
    return ClinicalDocument(
        document_id="document-123",
        file_name="sample.pdf",
        file_format="pdf",
        source_bucket="raw-bucket",
        source_key=(
            "documents/TEST001/"
            "protocols/sample.pdf"
        ),
        source_version_id="version-1",
        processing_schema_version=(
            "extraction-v1"
        ),
        canonical_bucket=(
            "canonical-bucket"
        ),
        canonical_key=(
            "canonical-documents/"
            "document-123/"
            "extracted-document.json"
        ),
        page_count=2,
        ocr_page_count=1,
        image_count=2,
        table_count=1,
        processing_status="SUCCESS",
        error_message=None,
    )


@pytest.fixture
def failed_document(
    successful_document,
):
    return replace(
        successful_document,
        processing_status="FAILED",
        error_message=(
            "Document extraction failed"
        ),
    )


@pytest.fixture
def duplicate_document(
    successful_document,
):
    return replace(
        successful_document,
        already_processed=True,
    )


def build_s3_record(
    *,
    bucket="raw-bucket",
    key=(
        "documents/TEST001/"
        "protocols/sample.pdf"
    ),
    event_source="aws:s3",
    version_id="version-1",
    etag="etag-123",
    sequencer="001",
):
    return {
        "eventSource": event_source,
        "eventName": (
            "ObjectCreated:Put"
        ),
        "eventTime": (
            "2026-01-01T00:00:00Z"
        ),
        "s3": {
            "bucket": {
                "name": bucket,
            },
            "object": {
                "key": key,
                "versionId": (
                    version_id
                ),
                "eTag": etag,
                "sequencer": (
                    sequencer
                ),
            },
        },
    }


def build_sqs_message(
    body,
    *,
    message_id="message-123",
    receipt_handle="receipt-123",
    receive_count="1",
):
    return {
        "MessageId": message_id,
        "ReceiptHandle": (
            receipt_handle
        ),
        "Attributes": {
            "ApproximateReceiveCount": (
                receive_count
            ),
        },
        "Body": json.dumps(
            body
        ),
    }


def build_raw_sqs_message(
    body,
    *,
    message_id="message-123",
    receipt_handle="receipt-123",
):
    return {
        "MessageId": message_id,
        "ReceiptHandle": (
            receipt_handle
        ),
        "Body": body,
    }


def build_worker(
    document=None,
    exception=None,
):
    consumer = FakeConsumer()

    extraction_service = (
        FakeExtractionService(
            document=document,
            exception=exception,
        )
    )

    worker = ExtractionWorker(
        consumer=consumer,
        extraction_service=(
            extraction_service
        ),
    )

    return (
        worker,
        consumer,
        extraction_service,
    )


def test_successful_document_deletes_message(
    successful_document,
):
    (
        worker,
        consumer,
        extraction_service,
    ) = build_worker(
        document=successful_document
    )

    message = build_sqs_message(
        {
            "Records": [
                build_s3_record()
            ]
        }
    )

    worker._process_message(
        message
    )

    assert (
        consumer.deleted_receipts
        == ["receipt-123"]
    )

    assert extraction_service.calls == [
        {
            "bucket_name": "raw-bucket",
            "object_key": (
                "documents/TEST001/"
                "protocols/sample.pdf"
            ),
            "version_id": "version-1",
            "s3_metadata": {},
        }
    ]

    assert worker.processing_active is False
    assert worker.active_message_id is None


def test_failed_document_does_not_delete_message(
    failed_document,
):
    (
        worker,
        consumer,
        extraction_service,
    ) = build_worker(
        document=failed_document
    )

    worker._process_message(
        build_sqs_message(
            {
                "Records": [
                    build_s3_record()
                ]
            }
        )
    )

    assert (
        consumer.deleted_receipts
        == []
    )
    assert len(
        extraction_service.calls
    ) == 1


def test_extraction_exception_does_not_delete_message():
    (
        worker,
        consumer,
        extraction_service,
    ) = build_worker(
        exception=RuntimeError(
            "Extraction service failed"
        )
    )

    worker._process_message(
        build_sqs_message(
            {
                "Records": [
                    build_s3_record()
                ]
            }
        )
    )

    assert (
        consumer.deleted_receipts
        == []
    )
    assert len(
        extraction_service.calls
    ) == 1


def test_processing_claim_contention_defers_message():
    (
        worker,
        consumer,
        extraction_service,
    ) = build_worker(
        exception=(
            ProcessingClaimUnavailableError(
                "Claim is owned"
            )
        )
    )

    worker._process_message(
        build_sqs_message(
            {
                "Records": [
                    build_s3_record()
                ]
            }
        )
    )

    assert (
        consumer.deleted_receipts
        == []
    )
    assert len(
        extraction_service.calls
    ) == 1


def test_malformed_json_does_not_delete_message():
    (
        worker,
        consumer,
        extraction_service,
    ) = build_worker()

    worker._process_message(
        build_raw_sqs_message(
            "{invalid-json"
        )
    )

    assert (
        consumer.deleted_receipts
        == []
    )
    assert (
        extraction_service.calls
        == []
    )


@pytest.mark.parametrize(
    "body",
    [
        "[]",
        '"text"',
        "123",
        "null",
    ],
)
def test_non_object_json_does_not_delete_message(
    body,
):
    (
        worker,
        consumer,
        extraction_service,
    ) = build_worker()

    worker._process_message(
        build_raw_sqs_message(
            body
        )
    )

    assert (
        consumer.deleted_receipts
        == []
    )
    assert (
        extraction_service.calls
        == []
    )


def test_s3_test_event_is_acknowledged():
    (
        worker,
        consumer,
        extraction_service,
    ) = build_worker()

    worker._process_message(
        build_sqs_message(
            {
                "Event": "s3:TestEvent",
            }
        )
    )

    assert (
        consumer.deleted_receipts
        == ["receipt-123"]
    )
    assert (
        extraction_service.calls
        == []
    )


def test_all_s3_records_are_processed(
    successful_document,
):
    (
        worker,
        consumer,
        extraction_service,
    ) = build_worker(
        document=successful_document
    )

    worker._process_message(
        build_sqs_message(
            {
                "Records": [
                    build_s3_record(
                        key=(
                            "documents/TEST001/"
                            "protocols/first.pdf"
                        ),
                        version_id=(
                            "version-1"
                        ),
                        sequencer="001",
                    ),
                    build_s3_record(
                        key=(
                            "documents/TEST002/"
                            "csr/second.pdf"
                        ),
                        version_id=(
                            "version-2"
                        ),
                        sequencer="002",
                    ),
                ]
            }
        )
    )

    assert len(
        extraction_service.calls
    ) == 2

    assert (
        extraction_service.calls[0]
        ["object_key"]
        == (
            "documents/TEST001/"
            "protocols/first.pdf"
        )
    )

    assert (
        extraction_service.calls[0]
        ["version_id"]
        == "version-1"
    )

    assert (
        extraction_service.calls[1]
        ["object_key"]
        == (
            "documents/TEST002/"
            "csr/second.pdf"
        )
    )

    assert (
        extraction_service.calls[1]
        ["version_id"]
        == "version-2"
    )

    assert (
        consumer.deleted_receipts
        == ["receipt-123"]
    )


def test_message_is_not_deleted_when_later_record_fails(
    successful_document,
):
    consumer = FakeConsumer()

    class PartiallyFailingService:

        def __init__(
            self,
        ):
            self.calls = []

        def process_document(
            self,
            bucket_name,
            object_key,
            version_id,
            s3_metadata,
        ):
            self.calls.append(
                {
                    "bucket_name": (
                        bucket_name
                    ),
                    "object_key": (
                        object_key
                    ),
                    "version_id": (
                        version_id
                    ),
                    "s3_metadata": (
                        s3_metadata
                    ),
                }
            )

            if object_key.endswith(
                "second.pdf"
            ):
                raise RuntimeError(
                    "Second record failed"
                )

            return successful_document

    extraction_service = (
        PartiallyFailingService()
    )

    worker = ExtractionWorker(
        consumer=consumer,
        extraction_service=(
            extraction_service
        ),
    )

    worker._process_message(
        build_sqs_message(
            {
                "Records": [
                    build_s3_record(
                        key=(
                            "documents/TEST001/"
                            "protocols/first.pdf"
                        ),
                        version_id=(
                            "version-1"
                        ),
                    ),
                    build_s3_record(
                        key=(
                            "documents/TEST002/"
                            "csr/second.pdf"
                        ),
                        version_id=(
                            "version-2"
                        ),
                    ),
                ]
            }
        )
    )

    assert len(
        extraction_service.calls
    ) == 2
    assert (
        consumer.deleted_receipts
        == []
    )


def test_url_encoded_key_is_decoded(
    successful_document,
):
    (
        worker,
        consumer,
        extraction_service,
    ) = build_worker(
        document=successful_document
    )

    worker._process_message(
        build_sqs_message(
            {
                "Records": [
                    build_s3_record(
                        key=(
                            "documents/TEST001/"
                            "protocols/"
                            "clinical+protocol"
                            "%20v1.pdf"
                        )
                    )
                ]
            }
        )
    )

    assert (
        extraction_service.calls[0]
        ["object_key"]
        == (
            "documents/TEST001/"
            "protocols/"
            "clinical protocol v1.pdf"
        )
    )
    assert (
        consumer.deleted_receipts
        == ["receipt-123"]
    )


def test_s3_version_is_forwarded_and_event_metadata_is_not(
    successful_document,
):
    (
        worker,
        consumer,
        extraction_service,
    ) = build_worker(
        document=successful_document
    )

    worker._process_message(
        build_sqs_message(
            {
                "Records": [
                    build_s3_record(
                        version_id=(
                            "version-7"
                        ),
                        etag="etag-789",
                        sequencer=(
                            "sequencer-456"
                        ),
                    )
                ]
            }
        )
    )

    assert extraction_service.calls == [
        {
            "bucket_name": "raw-bucket",
            "object_key": (
                "documents/TEST001/"
                "protocols/sample.pdf"
            ),
            "version_id": "version-7",
            "s3_metadata": {},
        }
    ]

    assert (
        consumer.deleted_receipts
        == ["receipt-123"]
    )


def test_missing_s3_version_is_not_acknowledged():
    (
        worker,
        consumer,
        extraction_service,
    ) = build_worker()

    worker._process_message(
        build_sqs_message(
            {
                "Records": [
                    build_s3_record(
                        version_id=None
                    )
                ]
            }
        )
    )

    assert (
        extraction_service.calls
        == []
    )
    assert (
        consumer.deleted_receipts
        == []
    )


def test_empty_records_are_not_acknowledged():
    (
        worker,
        consumer,
        extraction_service,
    ) = build_worker()

    worker._process_message(
        build_sqs_message(
            {
                "Records": [],
            }
        )
    )

    assert (
        consumer.deleted_receipts
        == []
    )
    assert (
        extraction_service.calls
        == []
    )


@pytest.mark.parametrize(
    "records",
    [
        {},
        "not-a-list",
        123,
    ],
)
def test_non_list_records_are_not_acknowledged(
    records,
):
    (
        worker,
        consumer,
        extraction_service,
    ) = build_worker()

    worker._process_message(
        build_sqs_message(
            {
                "Records": records,
            }
        )
    )

    assert (
        consumer.deleted_receipts
        == []
    )
    assert (
        extraction_service.calls
        == []
    )


def test_missing_bucket_is_not_acknowledged():
    (
        worker,
        consumer,
        extraction_service,
    ) = build_worker()

    record = build_s3_record()
    record["s3"]["bucket"] = {}

    worker._process_message(
        build_sqs_message(
            {
                "Records": [
                    record
                ],
            }
        )
    )

    assert (
        extraction_service.calls
        == []
    )
    assert (
        consumer.deleted_receipts
        == []
    )


def test_missing_object_key_is_not_acknowledged():
    (
        worker,
        consumer,
        extraction_service,
    ) = build_worker()

    record = build_s3_record()
    record["s3"]["object"].pop(
        "key"
    )

    worker._process_message(
        build_sqs_message(
            {
                "Records": [
                    record
                ],
            }
        )
    )

    assert (
        extraction_service.calls
        == []
    )
    assert (
        consumer.deleted_receipts
        == []
    )


def test_unsupported_event_source_is_not_acknowledged():
    (
        worker,
        consumer,
        extraction_service,
    ) = build_worker()

    worker._process_message(
        build_sqs_message(
            {
                "Records": [
                    build_s3_record(
                        event_source="aws:sns"
                    )
                ]
            }
        )
    )

    assert (
        extraction_service.calls
        == []
    )
    assert (
        consumer.deleted_receipts
        == []
    )


def test_direct_message_is_supported(
    successful_document,
):
    (
        worker,
        consumer,
        extraction_service,
    ) = build_worker(
        document=successful_document
    )

    worker._process_message(
        build_sqs_message(
            {
                "bucket": "raw-bucket",
                "key": (
                    "documents/TEST001/"
                    "protocols/direct.pdf"
                ),
                "version_id": (
                    "version-3"
                ),
                "metadata": {
                    "study_id": (
                        "OVERRIDE001"
                    ),
                },
            }
        )
    )

    assert extraction_service.calls == [
        {
            "bucket_name": "raw-bucket",
            "object_key": (
                "documents/TEST001/"
                "protocols/direct.pdf"
            ),
            "version_id": "version-3",
            "s3_metadata": {
                "study_id": (
                    "OVERRIDE001"
                ),
            },
        }
    ]

    assert (
        consumer.deleted_receipts
        == ["receipt-123"]
    )


def test_direct_message_without_version_is_rejected():
    (
        worker,
        consumer,
        extraction_service,
    ) = build_worker()

    worker._process_message(
        build_sqs_message(
            {
                "bucket": "raw-bucket",
                "key": (
                    "documents/TEST001/"
                    "protocols/direct.pdf"
                ),
                "metadata": {},
            }
        )
    )

    assert (
        extraction_service.calls
        == []
    )
    assert (
        consumer.deleted_receipts
        == []
    )


@pytest.mark.parametrize(
    "metadata",
    [
        "not-an-object",
        [],
        123,
        True,
    ],
)
def test_direct_message_rejects_non_object_metadata(
    metadata,
):
    (
        worker,
        consumer,
        extraction_service,
    ) = build_worker()

    worker._process_message(
        build_sqs_message(
            {
                "bucket": "raw-bucket",
                "key": (
                    "documents/TEST001/"
                    "protocols/direct.pdf"
                ),
                "version_id": (
                    "version-3"
                ),
                "metadata": metadata,
            }
        )
    )

    assert (
        extraction_service.calls
        == []
    )
    assert (
        consumer.deleted_receipts
        == []
    )


def test_unsupported_message_format_is_not_acknowledged():
    (
        worker,
        consumer,
        extraction_service,
    ) = build_worker()

    worker._process_message(
        build_sqs_message(
            {
                "unexpected": "value",
            }
        )
    )

    assert (
        consumer.deleted_receipts
        == []
    )
    assert (
        extraction_service.calls
        == []
    )


def test_missing_receipt_handle_prevents_processing(
    successful_document,
):
    (
        worker,
        consumer,
        extraction_service,
    ) = build_worker(
        document=successful_document
    )

    message = {
        "MessageId": "message-123",
        "Body": json.dumps(
            {
                "Records": [
                    build_s3_record()
                ]
            }
        ),
    }

    worker._process_message(
        message
    )

    assert (
        extraction_service.calls
        == []
    )
    assert (
        consumer.deleted_receipts
        == []
    )


def test_duplicate_document_is_acknowledged(
    duplicate_document,
):
    (
        worker,
        consumer,
        extraction_service,
    ) = build_worker(
        document=duplicate_document
    )

    worker._process_message(
        build_sqs_message(
            {
                "Records": [
                    build_s3_record()
                ]
            }
        )
    )

    assert len(
        extraction_service.calls
    ) == 1
    assert (
        consumer.deleted_receipts
        == ["receipt-123"]
    )


def test_release_unstarted_message_sets_visibility_to_zero():
    (
        worker,
        consumer,
        _,
    ) = build_worker()

    worker._release_unstarted_message(
        {
            "MessageId": "message-123",
            "ReceiptHandle": (
                "receipt-123"
            ),
        }
    )

    assert consumer.visibility_calls == [
        {
            "receipt_handle": (
                "receipt-123"
            ),
            "visibility_timeout": 0,
        }
    ]


def test_release_unstarted_message_without_receipt_is_skipped():
    (
        worker,
        consumer,
        _,
    ) = build_worker()

    worker._release_unstarted_message(
        {
            "MessageId": "message-123",
        }
    )

    assert (
        consumer.visibility_calls
        == []
    )


def test_release_unstarted_message_failure_is_ignored():
    (
        worker,
        consumer,
        _,
    ) = build_worker()

    consumer.change_message_visibility = (
        Mock(
            side_effect=RuntimeError(
                "Visibility update failed"
            )
        )
    )

    worker._release_unstarted_message(
        {
            "MessageId": "message-123",
            "ReceiptHandle": (
                "receipt-123"
            ),
        }
    )

    (
        consumer
        .change_message_visibility
        .assert_called_once_with(
            receipt_handle="receipt-123",
            visibility_timeout=0,
        )
    )



def test_constructor_creates_default_extraction_service(
    monkeypatch,
):
    from workers import extraction_worker

    consumer = FakeConsumer()
    extraction_service = object()
    extraction_service_factory = Mock(
        return_value=extraction_service
    )

    monkeypatch.setattr(
        extraction_worker,
        "DocumentExtractionService",
        extraction_service_factory,
    )

    worker = ExtractionWorker(
        consumer=consumer,
    )

    extraction_service_factory.assert_called_once_with()

    assert (
        worker.extraction_service
        is extraction_service
    )


def test_visibility_heartbeat_failure_still_acknowledges_success(
    monkeypatch,
    successful_document,
):
    from workers import extraction_worker

    class FailedVisibilityHeartbeat:

        instances = []

        def __init__(
            self,
            consumer,
            receipt_handle,
            heartbeat_seconds,
            extension_seconds,
        ):
            self.consumer = consumer
            self.receipt_handle = (
                receipt_handle
            )
            self.heartbeat_seconds = (
                heartbeat_seconds
            )
            self.extension_seconds = (
                extension_seconds
            )
            self.failed = True
            self.start_calls = 0
            self.stop_calls = 0

            self.__class__.instances.append(
                self
            )

        def start(
            self,
        ):
            self.start_calls += 1

        def stop(
            self,
        ):
            self.stop_calls += 1

    monkeypatch.setattr(
        extraction_worker,
        "MessageVisibilityHeartbeat",
        FailedVisibilityHeartbeat,
    )

    (
        worker,
        consumer,
        extraction_service,
    ) = build_worker(
        document=successful_document
    )

    worker._process_message(
        build_sqs_message(
            {
                "Records": [
                    build_s3_record()
                ]
            }
        )
    )

    assert len(
        extraction_service.calls
    ) == 1

    assert (
        consumer.deleted_receipts
        == ["receipt-123"]
    )

    assert len(
        FailedVisibilityHeartbeat.instances
    ) == 1

    heartbeat = (
        FailedVisibilityHeartbeat
        .instances[0]
    )

    assert heartbeat.start_calls == 1
    assert heartbeat.stop_calls == 1


def test_process_object_rejects_missing_version_id():
    (
        worker,
        _,
        extraction_service,
    ) = build_worker()

    with pytest.raises(
        ValueError,
        match="S3 source version ID is required",
    ):
        worker._process_object(
            bucket="raw-bucket",
            key=(
                "documents/TEST001/"
                "protocols/sample.pdf"
            ),
            version_id="",
            s3_metadata={},
        )

    assert extraction_service.calls == []