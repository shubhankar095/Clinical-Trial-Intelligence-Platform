from utils.logger import get_logger
from models.document import ClinicalDocument
from indexers.base_indexer import BaseIndexer


class OpenSearchIndexer(BaseIndexer):

    def __init__(self):

        self.logger = get_logger(
            self.__class__.__name__
        )

    def index(
        self,
        document: ClinicalDocument
    ) -> ClinicalDocument:

        for chunk in document.chunks:

            payload = {
                "chunk_id": chunk.chunk_id,
                "text": chunk.text,
                "embedding": chunk.embedding,
                "metadata": chunk.metadata,
                "start_page": chunk.start_page,
                "end_page": chunk.end_page
            }

            self.logger.info(
                f"Indexing chunk "
                f"{chunk.chunk_id}"
            )

            # Future:
            # self.client.index(...)

        document.indexed = True

        return document