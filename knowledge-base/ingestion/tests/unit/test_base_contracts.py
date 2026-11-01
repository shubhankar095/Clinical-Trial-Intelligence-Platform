import pytest

from chunkers.base_chunker import BaseChunker
from embedders.base_embedder import BaseEmbedder
from indexers.base_indexer import BaseIndexer
from ingestion_events.base_ingestion_event_parser import BaseIngestionEventParser

pytestmark = pytest.mark.unit


def test_abstract_chunker_method_raises():
    class ConcreteChunker(BaseChunker):
        def chunk(self, document, identity, profile):
            return super().chunk(document, identity, profile)

    with pytest.raises(NotImplementedError):
        ConcreteChunker().chunk(None, None, None)


def test_abstract_embedder_method_raises():
    class ConcreteEmbedder(BaseEmbedder):
        def embed(self, chunk):
            return super().embed(chunk)

    with pytest.raises(NotImplementedError):
        ConcreteEmbedder().embed(None)


def test_abstract_indexer_method_raises():
    class ConcreteIndexer(BaseIndexer):
        def index_records(self, *, ingestion_id, records):
            return super().index_records(ingestion_id=ingestion_id, records=records)

    with pytest.raises(NotImplementedError):
        ConcreteIndexer().index_records(ingestion_id="id", records=())


def test_base_ingestion_event_parser_protocol_stub():
    assert BaseIngestionEventParser.parse(None, "body") is None
