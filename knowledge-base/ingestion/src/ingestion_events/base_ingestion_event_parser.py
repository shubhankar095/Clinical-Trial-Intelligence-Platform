from typing import Protocol

from ingestion_events.ingestion_event import ExtractionCompletedEvent


class BaseIngestionEventParser(Protocol):
    """Structural contract shared by native-S3 and custom event parsers."""

    def parse(self, message_body: str) -> ExtractionCompletedEvent:
        """Parse one SQS message body into the normalized Ingestion event."""
        ...
