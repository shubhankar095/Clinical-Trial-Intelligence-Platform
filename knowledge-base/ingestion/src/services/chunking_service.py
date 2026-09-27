from chunkers.base_chunker import BaseChunker
from models.document import ClinicalDocument


class ChunkingService:

    def __init__(
        self,
        chunker: BaseChunker
    ):

        self.chunker = chunker

    def chunk_document(
        self,
        document: ClinicalDocument
    ) -> ClinicalDocument:

        document.chunks = self.chunker.chunk(document)
    
        return document