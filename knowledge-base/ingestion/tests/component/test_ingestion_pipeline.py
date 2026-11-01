import pytest
from chunkers.recursive_character_chunker import RecursiveCharacterChunker
from services.canonical_document_parser import CanonicalDocumentParser
from services.extraction_manifest_parser import ExtractionManifestParser
from services.ingestion_identity_service import IngestionIdentityService
from services.chunking_service import ChunkingService
from services.embedding_service import EmbeddingService
from services.index_record_service import IndexRecordService
from services.indexing_service import IndexingService
from tests.fakes.pipeline import DeterministicEmbedder,RecordingIndexer
pytestmark=[pytest.mark.component,pytest.mark.local]

def test_complete_deterministic_pipeline_reaches_index_destination(canonical_fixture_dir,profile_factory):
    manifest=ExtractionManifestParser().parse((canonical_fixture_dir/"_SUCCESS.json").read_text())
    document=CanonicalDocumentParser().parse((canonical_fixture_dir/"extracted-document.json").read_text())
    profile=profile_factory(chunker_type="page-aware-recursive-character",chunk_size=600,chunk_overlap=50,embedding_provider="test",embedding_model_id="deterministic-v1",embedding_dimensions=3,embedding_normalize=False)
    identity=IngestionIdentityService().create_ingestion_identity(document,manifest,profile)
    chunks=ChunkingService(RecursiveCharacterChunker()).chunk_document(document=document,identity=identity,profile=profile)
    embedded=EmbeddingService(DeterministicEmbedder(3)).embed_chunks(chunks,profile)
    records=IndexRecordService().create_records(document=document,identity=identity,profile=profile,embedded_chunks=embedded)
    indexer=RecordingIndexer();destination=IndexingService(indexer).index_records(ingestion_id=identity.ingestion_id,records=records)
    assert destination==f"recording://{identity.ingestion_id}"
    assert indexer.calls==[(identity.ingestion_id,records)]
    assert len(records)==len(chunks)>1
