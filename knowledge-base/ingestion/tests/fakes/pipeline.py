from indexers.base_indexer import BaseIndexer
from embedders.base_embedder import BaseEmbedder
from models.embedded_chunk import EmbeddedChunk
from storage.base_text_store import BaseTextStore

class InMemoryTextStore(BaseTextStore):
    def __init__(self, values): self.values=dict(values); self.loads=[]
    def load_text(self, location):
        self.loads.append(location)
        return self.values[(location.bucket, location.key, location.version_id)]

class DeterministicEmbedder(BaseEmbedder):
    def __init__(self, dimensions=3): self.dimensions=dimensions; self.chunks=[]
    def embed(self, chunk):
        self.chunks.append(chunk)
        return EmbeddedChunk(chunk=chunk, embedding=tuple((i+1)/10 for i in range(self.dimensions)), embedding_provider="test", embedding_model_id="deterministic-v1", embedding_dimensions=self.dimensions, embedding_normalized=False, input_token_count=None)

class RecordingIndexer(BaseIndexer):
    def __init__(self): self.calls=[]
    def index_records(self, *, ingestion_id, records):
        self.calls.append((ingestion_id, records))
        return f"recording://{ingestion_id}"
