import hashlib
import json

from typing import Any

from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
)

from chunkers.base_chunker import (
    BaseChunker,
)
from models.canonical_document import (
    CanonicalDocument,
)
from models.document import (
    DocumentChunk,
)
from models.ingestion_profile import (
    IngestionIdentity,
    IngestionProfile,
)


class RecursiveCharacterChunker(
    BaseChunker
):
    """
    LangChain-backed recursive-character chunker.

    LangChain is contained inside this adapter.
    The rest of the ingestion application depends
    only on BaseChunker and DocumentChunk.
    """

    CHUNK_IDENTITY_TYPE = (
        "document-chunk"
    )

    def chunk(
        self,
        document: CanonicalDocument,
        identity: IngestionIdentity,
        profile: IngestionProfile,
    ) -> tuple[DocumentChunk, ...]:
        """
        Split canonical raw text and return
        deterministic document chunks.
        """
        if not isinstance(
            document,
            CanonicalDocument,
        ):
            raise TypeError(
                "document must be a "
                "CanonicalDocument."
            )

        if not isinstance(
            identity,
            IngestionIdentity,
        ):
            raise TypeError(
                "identity must be an "
                "IngestionIdentity."
            )

        if not isinstance(
            profile,
            IngestionProfile,
        ):
            raise TypeError(
                "profile must be an "
                "IngestionProfile."
            )

        splitter = (
            RecursiveCharacterTextSplitter(
                chunk_size=(
                    profile.chunk_size
                ),
                chunk_overlap=(
                    profile.chunk_overlap
                ),
                add_start_index=True,
                keep_separator=True,
                strip_whitespace=False,
            )
        )

        split_documents = (
            splitter.create_documents(
                texts=[
                    document.raw_text
                ],
            )
        )

        chunks: list[DocumentChunk] = []

        for split_document in split_documents:
            chunk_text = (
                split_document.page_content
            )

            if not chunk_text.strip():
                continue

            start_offset = (
                self._read_start_offset(
                    split_document.metadata
                )
            )

            end_offset = (
                start_offset
                + len(chunk_text)
            )

            authoritative_text = (
                document.raw_text[
                    start_offset:
                    end_offset
                ]
            )

            chunk_index = len(
                chunks
            )

            (
                start_page,
                end_page,
            ) = self._find_page_range(
                document=document,
                start_offset=start_offset,
                end_offset=end_offset,
            )

            chunk_id = (
                self._create_chunk_id(
                    identity=identity,
                    chunk_index=chunk_index,
                    start_offset=start_offset,
                    end_offset=end_offset,
                    text=authoritative_text,
                )
            )

            chunks.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    ingestion_id=(
                        identity.ingestion_id
                    ),
                    ingestion_profile_id=(
                        identity
                        .ingestion_profile_id
                    ),
                    document_id=(
                        document.document_id
                    ),
                    chunk_index=chunk_index,
                    text=authoritative_text,
                    start_offset=start_offset,
                    end_offset=end_offset,
                    start_page=start_page,
                    end_page=end_page,
                    character_count=len(
                        authoritative_text
                    ),
                )
            )

        return tuple(
            chunks
        )

    def _read_start_offset(
        self,
        metadata: dict[str, Any],
    ) -> int:
        """
        Read the source start offset supplied by the
        LangChain splitter.
        """
        start_offset = metadata.get(
            "start_index"
       )

        if (
            not isinstance(
                start_offset,
                int,
            )
            or isinstance(
                start_offset,
                bool,
            )
        ):
            raise RuntimeError(
                "Recursive character splitter "
                "did not return a valid "
                "start_index."
            )

        if start_offset < 0:
            raise RuntimeError(
                "Recursive character splitter "
                "returned a negative start_index."
            )

        return start_offset

    def _create_chunk_id(
        self,
        identity: IngestionIdentity,
        chunk_index: int,
        start_offset: int,
        end_offset: int,
        text: str,
    ) -> str:
        """
        Create a deterministic SHA-256 chunk ID.
        """
        text_sha256 = hashlib.sha256(
            text.encode(
                "utf-8"
            )
        ).hexdigest()

        identity_payload = {
            "identity_type": (
                self.CHUNK_IDENTITY_TYPE
            ),
            "ingestion_id": (
                identity.ingestion_id
            ),
            "chunk_index": (
                chunk_index
            ),
            "start_offset": (
                start_offset
            ),
            "end_offset": (
                end_offset
            ),
            "text_sha256": (
                text_sha256
            ),
        }

        serialized_payload = json.dumps(
            identity_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

        return hashlib.sha256(
            serialized_payload.encode(
                "utf-8"
            )
        ).hexdigest()