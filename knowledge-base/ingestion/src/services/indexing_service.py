from exceptions.processing import PermanentIngestionError
from indexers.base_indexer import BaseIndexer
from models.index_record import IndexRecord
from services.provider_error_classifier import raise_classified_provider_error


class IndexingService:
    """Validate and persist one complete, deterministic Ingestion generation."""

    def __init__(self, indexer: BaseIndexer):
        if not isinstance(indexer, BaseIndexer):
            raise TypeError("indexer must implement BaseIndexer.")
        self.indexer = indexer

    def index_records(
        self,
        *,
        ingestion_id: str,
        records: tuple[IndexRecord, ...],
    ) -> str:
        if not isinstance(ingestion_id, str) or not ingestion_id.strip():
            raise ValueError("ingestion_id must be a nonblank string.")
        normalized_ingestion_id = ingestion_id.strip()
        if not isinstance(records, tuple):
            raise TypeError("records must be a tuple.")
        if not records:
            raise PermanentIngestionError("records must not be empty.")

        record_ids: set[str] = set()
        for record in records:
            if not isinstance(record, IndexRecord):
                raise PermanentIngestionError("Every record must be an IndexRecord.")
            if record.ingestion_id != normalized_ingestion_id:
                raise PermanentIngestionError(
                    "Index record ingestion_id does not match the requested generation."
                )
            if record.index_record_id in record_ids:
                raise PermanentIngestionError(
                    "Index record IDs must be unique within one indexing request."
                )
            record_ids.add(record.index_record_id)

        try:
            destination = self.indexer.index_records(
                ingestion_id=normalized_ingestion_id,
                records=records,
            )
        except Exception as exception:
            raise_classified_provider_error(
                exception,
                operation="OpenSearch indexing",
            )

        if not isinstance(destination, str) or not destination.strip():
            raise PermanentIngestionError(
                "Indexer did not return a valid destination."
            )
        return destination.strip()
