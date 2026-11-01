from embedders.base_embedder import BaseEmbedder
from indexers.base_indexer import BaseIndexer

class ControlledEmbeddingFailure(BaseEmbedder):
    def __init__(self, exception): self.exception=exception; self.calls=0
    def embed(self, chunk): self.calls+=1; raise self.exception

class ControlledIndexFailure(BaseIndexer):
    def __init__(self, exception): self.exception=exception; self.calls=0
    def index_records(self, *, ingestion_id, records): self.calls+=1; raise self.exception
