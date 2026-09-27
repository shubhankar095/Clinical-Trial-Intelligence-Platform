from embedders.base_embedder import BaseEmbedder
from models.document import ClinicalDocument


class EmbeddingService:

    def __init__(
        self,
        embedder: BaseEmbedder
    ):

        self.embedder = embedder

    def embed_document(
        self,
        document: ClinicalDocument
    ) -> ClinicalDocument:

        for chunk in document.chunks:

            chunk.embedding = (
                self.embedder.embed(
                    chunk.text
                )
            )

        return document