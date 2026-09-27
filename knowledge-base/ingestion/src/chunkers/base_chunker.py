from abc import ABC, abstractmethod
from models.document import ClinicalDocument, DocumentChunk

class BaseChunker(ABC):

    @abstractmethod
    def chunk(
        self,
        document: ClinicalDocument
    ) -> list[DocumentChunk]:
        pass