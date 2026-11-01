from __future__ import annotations

import json
import pytest

from chunkers.recursive_character_chunker import RecursiveCharacterChunker
from indexers.opensearch_indexer import OpenSearchIndexer
from models.storage_location import StorageLocation
from services.canonical_document_parser import CanonicalDocumentParser
from services.extraction_manifest_parser import ExtractionManifestParser
from services.ingestion_identity_service import IngestionIdentityService
from services.chunking_service import ChunkingService
from services.embedding_service import EmbeddingService
from services.index_record_service import IndexRecordService
from services.indexing_service import IndexingService
from storage.s3_text_store import S3TextStore
from tests.fakes.pipeline import DeterministicEmbedder

pytestmark = [pytest.mark.integration, pytest.mark.local]


def test_local_s3_to_opensearch_pipeline(
    local_resources,
    opensearch_service,
    canonical_fixture_dir,
    profile_factory,
):
    bucket = local_resources["bucket"]
    manifest_key = "canonical-documents/test/_SUCCESS.json"
    document_key = "canonical-documents/test/extracted-document.json"
    local_resources["s3_client"].put_object(
        Bucket=bucket,
        Key=manifest_key,
        Body=(canonical_fixture_dir / "_SUCCESS.json").read_bytes(),
    )
    local_resources["s3_client"].put_object(
        Bucket=bucket,
        Key=document_key,
        Body=(canonical_fixture_dir / "extracted-document.json").read_bytes(),
    )
    store = S3TextStore(local_resources["s3_service"])
    manifest_payload = json.loads(
        store.load_text(StorageLocation(bucket=bucket, key=manifest_key))
    )
    manifest_payload["canonical_bucket"] = bucket
    manifest_payload["canonical_key"] = document_key
    manifest = ExtractionManifestParser().parse(json.dumps(manifest_payload))
    document = CanonicalDocumentParser().parse(
        store.load_text(StorageLocation(bucket=bucket, key=document_key))
    )
    profile = profile_factory(
        chunker_type="page-aware-recursive-character",
        chunk_size=600,
        chunk_overlap=50,
        embedding_provider="test",
        embedding_model_id="deterministic-v1",
        embedding_dimensions=3,
        embedding_normalize=False,
    )
    identity = IngestionIdentityService().create_ingestion_identity(
        document, manifest, profile
    )
    chunks = ChunkingService(RecursiveCharacterChunker()).chunk_document(
        document=document, identity=identity, profile=profile
    )
    embedded = EmbeddingService(DeterministicEmbedder(3)).embed_chunks(chunks, profile)
    records = IndexRecordService().create_records(
        document=document,
        identity=identity,
        profile=profile,
        embedded_chunks=embedded,
    )
    indexer = OpenSearchIndexer(
        deployment_type="domain",
        endpoint="http://localhost:9200",
        region_name="ap-south-1",
        index_prefix="pipeline-chunks",
        refresh_after_index=True,
        opensearch_service=opensearch_service,
        sleep_function=lambda _: None,
        random_function=lambda: 0.0,
    )
    index_name = indexer.build_index_name(records[0])
    try:
        destination = IndexingService(indexer).index_records(
            ingestion_id=identity.ingestion_id,
            records=records,
        )
        assert destination == f"opensearch://{index_name}"
        assert indexer.count_records(
            index_name=index_name,
            ingestion_id=identity.ingestion_id,
        ) == len(records) > 1
    finally:
        if opensearch_service.index_exists(index_name=index_name):
            opensearch_service.delete_index(index_name=index_name)
