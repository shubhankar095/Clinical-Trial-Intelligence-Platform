import math

from exceptions.processing import PermanentIngestionError
from models.canonical_document import CanonicalDocument
from models.embedded_chunk import EmbeddedChunk
from models.index_record import IndexRecord
from models.ingestion_profile import IngestionIdentity, IngestionProfile


class IndexRecordService:
    """Build and validate provider-independent index records."""

    def create_records(
        self,
        *,
        document: CanonicalDocument,
        identity: IngestionIdentity,
        profile: IngestionProfile,
        embedded_chunks: tuple[EmbeddedChunk, ...],
    ) -> tuple[IndexRecord, ...]:
        if not isinstance(document, CanonicalDocument):
            raise TypeError("document must be a CanonicalDocument.")
        if not isinstance(identity, IngestionIdentity):
            raise TypeError("identity must be an IngestionIdentity.")
        if not isinstance(profile, IngestionProfile):
            raise TypeError("profile must be an IngestionProfile.")
        if not isinstance(embedded_chunks, tuple):
            raise TypeError("embedded_chunks must be a tuple.")
        if not embedded_chunks:
            raise PermanentIngestionError("embedded_chunks must not be empty.")

        records = tuple(
            self._create_record(
                document=document,
                identity=identity,
                profile=profile,
                embedded_chunk=embedded_chunk,
            )
            for embedded_chunk in embedded_chunks
        )
        self._check_records(
            document=document,
            identity=identity,
            profile=profile,
            embedded_chunks=embedded_chunks,
            records=records,
        )
        return records

    def _create_record(
        self,
        *,
        document: CanonicalDocument,
        identity: IngestionIdentity,
        profile: IngestionProfile,
        embedded_chunk: EmbeddedChunk,
    ) -> IndexRecord:
        if not isinstance(embedded_chunk, EmbeddedChunk):
            raise TypeError("Every embedded chunk must be an EmbeddedChunk.")
        chunk = embedded_chunk.chunk
        metadata = document.metadata
        return IndexRecord(
            index_record_id=chunk.chunk_id,
            index_schema_version=profile.index_schema_version,
            document_id=chunk.document_id,
            ingestion_id=chunk.ingestion_id,
            ingestion_profile_id=chunk.ingestion_profile_id,
            chunk_id=chunk.chunk_id,
            chunk_index=chunk.chunk_index,
            text=chunk.text,
            character_count=chunk.character_count,
            start_offset=chunk.start_offset,
            end_offset=chunk.end_offset,
            start_page=chunk.start_page,
            end_page=chunk.end_page,
            embedding=embedded_chunk.embedding,
            embedding_provider=embedded_chunk.embedding_provider,
            embedding_model_id=embedded_chunk.embedding_model_id,
            embedding_dimensions=embedded_chunk.embedding_dimensions,
            embedding_normalized=embedded_chunk.embedding_normalized,
            input_token_count=embedded_chunk.input_token_count,
            file_name=document.file_name,
            file_format=document.file_format,
            source_bucket=document.source_bucket,
            source_key=document.source_key,
            source_version_id=document.source_version_id,
            canonical_bucket=document.canonical_bucket,
            canonical_key=document.canonical_key,
            study_id=metadata.study_id,
            document_type=metadata.document_type,
            document_version=metadata.version,
            sponsor=metadata.sponsor,
            phase=metadata.phase,
        )

    def _check_records(
        self,
        *,
        document: CanonicalDocument,
        identity: IngestionIdentity,
        profile: IngestionProfile,
        embedded_chunks: tuple[EmbeddedChunk, ...],
        records: tuple[IndexRecord, ...],
    ) -> None:
        if len(records) != len(embedded_chunks):
            raise PermanentIngestionError(
                "Index record count does not match embedded chunk count."
            )
        record_ids: set[str] = set()
        for embedded_chunk, record in zip(embedded_chunks, records, strict=True):
            if not isinstance(record, IndexRecord):
                raise PermanentIngestionError(
                    "Index record service returned an invalid record type."
                )
            chunk = embedded_chunk.chunk
            if record.index_record_id != chunk.chunk_id:
                raise PermanentIngestionError(
                    "Index record ID must match the deterministic chunk ID."
                )
            if record.document_id != document.document_id or record.document_id != identity.document_id:
                raise PermanentIngestionError(
                    "Index record document lineage does not match the current document."
                )
            if record.ingestion_id != identity.ingestion_id:
                raise PermanentIngestionError(
                    "Index record ingestion_id does not match the current identity."
                )
            if record.ingestion_profile_id != identity.ingestion_profile_id:
                raise PermanentIngestionError(
                    "Index record profile lineage does not match the current identity."
                )
            if record.index_schema_version != profile.index_schema_version:
                raise PermanentIngestionError(
                    "Index record schema version does not match the profile."
                )
            if record.text != chunk.text:
                raise PermanentIngestionError(
                    "Index record text does not match its document chunk."
                )
            if record.start_offset != chunk.start_offset or record.end_offset != chunk.end_offset:
                raise PermanentIngestionError(
                    "Index record offsets do not match its document chunk."
                )
            if record.start_page != chunk.start_page or record.end_page != chunk.end_page:
                raise PermanentIngestionError(
                    "Index record page range does not match its document chunk."
                )
            if (
                record.embedding_dimensions != profile.embedding_dimensions
                or len(record.embedding) != profile.embedding_dimensions
            ):
                raise PermanentIngestionError(
                    "Index record embedding dimensions do not match the profile."
                )
            if not all(
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(value)
                for value in record.embedding
            ):
                raise PermanentIngestionError(
                    "Index record embedding must contain only finite numeric values."
                )
            if record.index_record_id in record_ids:
                raise PermanentIngestionError("Index record IDs must be unique.")
            record_ids.add(record.index_record_id)
