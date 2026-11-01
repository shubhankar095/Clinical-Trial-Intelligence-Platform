from ingestion_events.ingestion_event import IngestionEventError


class IgnorableIngestionEvent(IngestionEventError):
    """A valid infrastructure event that requires no document processing."""
