from chunkers.base_chunker import BaseChunker
from exceptions.processing import PermanentIngestionError
from models.canonical_document import CanonicalDocument
from models.document import DocumentChunk
from models.ingestion_profile import IngestionIdentity, IngestionProfile


class ChunkingService:
    """Execute the configured chunker and enforce deterministic invariants."""

    def __init__(self, chunker: BaseChunker):
        if not isinstance(chunker, BaseChunker):
            raise TypeError("chunker must implement BaseChunker.")
        self.chunker = chunker

    def chunk_document(
        self,
        document: CanonicalDocument,
        identity: IngestionIdentity,
        profile: IngestionProfile,
    ) -> tuple[DocumentChunk, ...]:

        chunks = self.chunker.chunk(
            document=document,
            identity=identity,
            profile=profile,
        )
        self._check_chunks(document=document, identity=identity, chunks=chunks)
        return chunks

    def _check_chunks(
        self,
        document: CanonicalDocument,
        identity: IngestionIdentity,
        chunks: tuple[DocumentChunk, ...],
    ) -> None:
    
        if not isinstance(chunks, tuple):
            raise PermanentIngestionError("Chunker output must be a tuple.")
        if not chunks:
            raise PermanentIngestionError("Chunking produced no usable document chunks.")

        chunk_ids: set[str] = set()
        raw_text_length = len(document.raw_text)
        for expected_index, chunk in enumerate(chunks):
            if not isinstance(chunk, DocumentChunk):
                raise PermanentIngestionError("Chunker returned an invalid chunk type.")
            if chunk.chunk_index != expected_index:
                raise PermanentIngestionError(
                    "Chunk indexes must be sequential and begin at zero."
                )
            if not chunk.text.strip():
                raise PermanentIngestionError("Chunk text must not be blank.")
            if (
                chunk.start_offset < 0
                or chunk.end_offset <= chunk.start_offset
                or chunk.end_offset > raw_text_length
            ):
                raise PermanentIngestionError("Chunk contains an invalid source offset range.")
            expected_text = document.raw_text[chunk.start_offset:chunk.end_offset]
            if chunk.text != expected_text:
                raise PermanentIngestionError(
                    "Chunk text does not match its canonical raw_text slice."
                )
            if chunk.character_count != len(chunk.text):
                raise PermanentIngestionError(
                    "Chunk character_count does not match its text length."
                )
            if (
                chunk.document_id != document.document_id
                or chunk.ingestion_id != identity.ingestion_id
                or chunk.ingestion_profile_id != identity.ingestion_profile_id
            ):
                raise PermanentIngestionError(
                    "Chunk lineage does not match the document and ingestion identity."
                )
            if chunk.chunk_id in chunk_ids:
                raise PermanentIngestionError("Chunk IDs must be unique.")
            chunk_ids.add(chunk.chunk_id)
