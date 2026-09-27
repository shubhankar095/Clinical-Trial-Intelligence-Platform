from dataclasses import dataclass


@dataclass
class DocumentUploadedEvent:
    bucket: str
    key: str
    version_id: str
    event_name: str | None = None
    event_time: str | None = None
    sequencer: str | None = None