from abc import ABC, abstractmethod
from models.document import DocumentChunk
from models.embedded_chunk import EmbeddedChunk


class BaseEmbedder(ABC):
    """
    Common interface for embedding-model adapters.

    Provider-specific API requests and response
    parsing belong inside concrete implementations.
    """

    @abstractmethod
    def embed(self, chunk: DocumentChunk) -> EmbeddedChunk:
        """
        Generate an embedding for one document
        chunk.
        """
        raise NotImplementedError