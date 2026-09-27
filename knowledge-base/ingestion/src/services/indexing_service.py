from models.document import ClinicalDocument
from indexers.base_indexer import BaseIndexer

class IndexingService:

    def __init__(
        self,
        indexer: BaseIndexer
    ):

        self.indexer = indexer

    def index_document(
        self,
        document: ClinicalDocument
    ) -> ClinicalDocument:

        return self.indexer.index(
            document
        )