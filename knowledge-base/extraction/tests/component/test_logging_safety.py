import json
import logging

import pytest

from models.document import (
    ClinicalDocument,
)
from workers.extraction_worker import (
    ExtractionWorker,
)


pytestmark = pytest.mark.component


SENSITIVE_TEXT = (
    "SENSITIVE_CLINICAL_VALUE_12345"
)


class RecordingConsumer:

    def __init__(
        self,
    ):
        self.deleted_receipts = []
        self.visibility_calls = []

    def receive_message(
        self,
    ):
        return {
            "Messages": [],
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


class SensitiveDocumentService:

    def process_document(
        self,
        bucket_name,
        object_key,
        version_id,
        s3_metadata,
    ):
        return ClinicalDocument(
            document_id="document-123",
            file_name="sample.pdf",
            file_format="pdf",
            source_bucket=bucket_name,
            source_key=object_key,
            source_version_id=version_id,
            processing_schema_version=(
                "extraction-v1"
            ),
            raw_text=SENSITIVE_TEXT,
            page_count=1,
            processing_status="SUCCESS",
        )


class SensitiveFailureService:

    def process_document(
        self,
        bucket_name,
        object_key,
        version_id,
        s3_metadata,
    ):
        raise RuntimeError(
            "Safe operational error"
        )


def build_message():
    body = {
        "bucket": "raw-bucket",
        "key": (
            "documents/TEST001/"
            "protocols/sample.pdf"
        ),
        "version_id": "version-1",
        "metadata": {},
    }

    return {
        "MessageId": "message-123",
        "ReceiptHandle": "receipt-123",
        "Attributes": {
            "ApproximateReceiveCount": "1",
        },
        "Body": json.dumps(
            body
        ),
    }


def test_successful_processing_does_not_log_raw_text(
    caplog,
):
    caplog.set_level(
        logging.INFO
    )

    consumer = RecordingConsumer()

    worker = ExtractionWorker(
        consumer=consumer,
        extraction_service=(
            SensitiveDocumentService()
        ),
    )

    worker._process_message(
        build_message()
    )

    assert (
        SENSITIVE_TEXT
        not in caplog.text
    )

    assert (
        consumer.deleted_receipts
        == ["receipt-123"]
    )


def test_processing_failure_does_not_log_document_content(
    caplog,
):
    caplog.set_level(
        logging.ERROR
    )

    consumer = RecordingConsumer()

    worker = ExtractionWorker(
        consumer=consumer,
        extraction_service=(
            SensitiveFailureService()
        ),
    )

    worker._process_message(
        build_message()
    )

    assert (
        SENSITIVE_TEXT
        not in caplog.text
    )

    assert (
        consumer.deleted_receipts
        == []
    )


def test_structured_success_log_contains_counts_not_content(
    caplog,
):
    caplog.set_level(
        logging.INFO
    )

    consumer = RecordingConsumer()

    worker = ExtractionWorker(
        consumer=consumer,
        extraction_service=(
            SensitiveDocumentService()
        ),
    )

    worker._process_message(
        build_message()
    )

    success_records = [
        record
        for record in caplog.records
        if getattr(
            record,
            "event",
            None,
        ) == "document_processed"
    ]

    assert len(
        success_records
    ) == 1

    success_record = (
        success_records[0]
    )

    assert (
        success_record.document_id
        == "document-123"
    )

    assert (
        success_record
        .source_version_id
        == "version-1"
    )

    assert (
        success_record
        .processing_schema_version
        == "extraction-v1"
    )

    assert (
        success_record
        .processing_status
        == "SUCCESS"
    )

    assert success_record.page_count == 1
    assert success_record.ocr_page_count == 0
    assert success_record.image_count == 0
    assert success_record.table_count == 0
    assert success_record.warning_count == 0

    assert not hasattr(
        success_record,
        "raw_text",
    )


def test_failure_log_does_not_include_message_body(
    caplog,
):
    caplog.set_level(
        logging.ERROR
    )

    consumer = RecordingConsumer()

    worker = ExtractionWorker(
        consumer=consumer,
        extraction_service=(
            SensitiveFailureService()
        ),
    )

    message = build_message()

    worker._process_message(
        message
    )

    assert (
        SENSITIVE_TEXT
        not in caplog.text
    )
    assert (
        message["Body"]
        not in caplog.text
    )