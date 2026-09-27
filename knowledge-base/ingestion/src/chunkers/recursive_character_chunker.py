from uuid import uuid4
from chunkers.base_chunker import BaseChunker
from models.document import DocumentChunk
from langchain_text_splitters import RecursiveCharacterTextSplitter


class RecursiveCharacterChunker(BaseChunker):

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ):

        self.splitter = (
            RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap
            )
        )

    def chunk(
        self,
        document
    ) -> list[DocumentChunk]:

        texts = self.splitter.split_text(document.raw_text)

        chunks = []

        current_position = 0

        for text in texts:

            start_offset = document.raw_text.find(text, current_position)
            end_offset   = start_offset + len(text)
            current_position = end_offset
            start_page = self._find_page(document, start_offset)
            end_page = self._find_page(document, end_offset)

            chunks.append(
                DocumentChunk(
                    chunk_id=str(uuid4()),
                    text=text,
                    start_offset=start_offset,
                    end_offset=end_offset,
                    start_page=start_page,
                    end_page=end_page,
                    metadata={
                        "study_id": document.metadata.study_id,
                        "document_type": document.metadata.document_type,
                        "version": document.metadata.version
                    }
                )
            )

        return chunks
    
    def _find_page(
        self,
        document,
        offset: int
    ) -> int | None:

        for page in document.pages:

            if page.start_offset <= offset < page.end_offset :
                return page.page_number

        return None