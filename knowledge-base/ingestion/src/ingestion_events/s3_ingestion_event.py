import json
from datetime import datetime, timezone
from json import JSONDecodeError
from typing import Any
from urllib.parse import unquote_plus

from exceptions.ingestion_event import IgnorableIngestionEvent
from ingestion_events.ingestion_event import (
    ExtractionCompletedEvent,
    IngestionEventFieldError,
    IngestionEventJsonError,
)


class S3IngestionEventParser:
    """Parse a native S3-to-SQS _SUCCESS.json notification for Ingestion."""

    PREFIX = "canonical-documents"
    FILE_NAME = "_SUCCESS.json"

    def parse(self, message_body: str) -> ExtractionCompletedEvent:
        if not isinstance(message_body, str) or not message_body.strip():
            raise IngestionEventJsonError("Ingestion event body must be nonblank text.")
        try:
            payload = json.loads(message_body)
        except JSONDecodeError as exception:
            raise IngestionEventJsonError("Ingestion event body is not valid JSON.") from exception
        if not isinstance(payload, dict):
            raise IngestionEventJsonError("Ingestion event must be a JSON object.")

        # S3 can publish a subscription confirmation/test event during setup.
        if payload.get("Event") == "s3:TestEvent":
            raise IgnorableIngestionEvent(
                "Amazon S3 test event requires no document processing."
            )

        records = payload.get("Records")
        if not isinstance(records, list) or len(records) != 1:
            raise IngestionEventFieldError("Ingestion requires exactly one S3 record per SQS message.")
        record = records[0]
        if not isinstance(record, dict) or record.get("eventSource") != "aws:s3":
            raise IngestionEventFieldError("Ingestion event must originate from Amazon S3.")
        event_name = record.get("eventName")
        if not isinstance(event_name, str) or not event_name.startswith("ObjectCreated:"):
            raise IngestionEventFieldError("Ingestion requires an S3 ObjectCreated event.")

        s3 = record.get("s3")
        if not isinstance(s3, dict):
            raise IngestionEventFieldError("S3 event record is missing s3 details.")
        bucket = s3.get("bucket")
        obj = s3.get("object")
        if not isinstance(bucket, dict) or not isinstance(obj, dict):
            raise IngestionEventFieldError("S3 event record has invalid bucket or object details.")
        bucket_name = bucket.get("name")
        raw_key = obj.get("key")
        if not isinstance(bucket_name, str) or not bucket_name.strip():
            raise IngestionEventFieldError("S3 event bucket name is invalid.")
        if not isinstance(raw_key, str) or not raw_key.strip():
            raise IngestionEventFieldError("S3 event object key is invalid.")
        key = unquote_plus(raw_key)
        parts = key.split("/")
        if len(parts) != 3 or parts[0] != self.PREFIX or parts[2] != self.FILE_NAME:
            raise IngestionEventFieldError("S3 event key is not an Extraction success manifest.")
        document_id = parts[1]
        if len(document_id) != 64 or any(c not in "0123456789abcdef" for c in document_id):
            raise IngestionEventFieldError("S3 event document ID is invalid.")

        version_id = obj.get("versionId")
        if version_id is not None and (not isinstance(version_id, str) or not version_id.strip()):
            raise IngestionEventFieldError("S3 object versionId must be nonblank when present.")
        event_time = record.get("eventTime")
        occurred_at = self._timestamp(event_time)
        return ExtractionCompletedEvent(
            event_type="EXTRACTION_COMPLETED",
            event_version="1",
            document_id=document_id,
            processing_schema_version="extraction-v1",
            manifest_bucket=bucket_name.strip(),
            manifest_key=key,
            manifest_version_id=version_id.strip() if isinstance(version_id, str) else None,
            occurred_at=occurred_at,
        )

    @staticmethod
    def _timestamp(value: Any) -> datetime:
        if not isinstance(value, str) or not value.strip():
            raise IngestionEventFieldError("S3 eventTime must be a nonblank timestamp.")
        normalized = value[:-1] + "+00:00" if value.endswith(("Z", "z")) else value
        try:
            result = datetime.fromisoformat(normalized)
        except ValueError as exception:
            raise IngestionEventFieldError("S3 eventTime is not valid ISO 8601.") from exception
        if result.tzinfo is None or result.utcoffset() is None:
            raise IngestionEventFieldError("S3 eventTime must include a timezone.")
        return result.astimezone(timezone.utc)
