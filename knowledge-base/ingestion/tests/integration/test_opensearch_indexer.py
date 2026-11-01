from __future__ import annotations

import pytest

from chunkers.recursive_character_chunker import RecursiveCharacterChunker
from indexers.opensearch_indexer import OpenSearchIndexer
from services.canonical_document_parser import CanonicalDocumentParser
from services.chunking_service import ChunkingService
from services.embedding_service import EmbeddingService
from services.extraction_manifest_parser import ExtractionManifestParser
from services.index_record_service import IndexRecordService
from services.ingestion_identity_service import IngestionIdentityService
from tests.fakes.pipeline import DeterministicEmbedder


pytestmark = [pytest.mark.integration, pytest.mark.local]


def build_records(canonical_fixture_dir, profile_factory):
    manifest = ExtractionManifestParser().parse(
            (canonical_fixture_dir / "_SUCCESS.json").read_text()
        )

    document = CanonicalDocumentParser().parse(
            (canonical_fixture_dir / "extracted-document.json").read_text()
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
        document, manifest, profile,
    )
    

    chunks = ChunkingService(RecursiveCharacterChunker()).chunk_document(
        document=document, identity=identity, profile=profile,
    )

    embedded_chunks = EmbeddingService(DeterministicEmbedder(3)).embed_chunks(
        chunks, profile,
    )

    records = IndexRecordService().create_records(
        document=document, identity=identity, profile=profile,
        embedded_chunks=embedded_chunks,
    )

    return identity, records


def test_real_opensearch_mapping_bulk_count_and_delete(
    opensearch_service,
    canonical_fixture_dir,
    profile_factory,
) -> None:
    identity, records = build_records(
        canonical_fixture_dir,
        profile_factory,
    )

    assert records

    indexer = OpenSearchIndexer(
        deployment_type="domain",
        endpoint="http://localhost:9200",
        region_name="ap-south-1",
        index_prefix=(
            "integration-chunks"
        ),
        refresh_after_index=True,
        opensearch_service=(
            opensearch_service
        ),
        sleep_function=lambda _: None,
        random_function=lambda: 0.0,
    )

    index_name = indexer.build_index_name(
        records[0]
    )

    try:
        destination = (
            indexer.index_records(
                ingestion_id=(
                    identity.ingestion_id
                ),
                records=records,
            )
        )

        assert destination == (
            f"opensearch://{index_name}"
        )

        indexed_count = (
            indexer.count_records(
                index_name=index_name,
                ingestion_id=(
                    identity.ingestion_id
                ),
            )
        )

        assert indexed_count == len(
            records
        )

        # Repeat the same deterministic indexing
        # operation. Existing document IDs should be
        # overwritten rather than duplicated.
        second_destination = (
            indexer.index_records(
                ingestion_id=(
                    identity.ingestion_id
                ),
                records=records,
            )
        )

        assert second_destination == (
            destination
        )

        repeated_count = (
            indexer.count_records(
                index_name=index_name,
                ingestion_id=(
                    identity.ingestion_id
                ),
            )
        )

        assert repeated_count == len(
            records
        )

        deleted_count = (
            indexer
            .delete_records_by_ingestion_id(
                index_name=index_name,
                ingestion_id=(
                    identity.ingestion_id
                ),
                refresh=True,
            )
        )

        assert deleted_count == len(
            records
        )

        remaining_count = (
            indexer.count_records(
                index_name=index_name,
                ingestion_id=(
                    identity.ingestion_id
                ),
            )
        )

        assert remaining_count == 0

    finally:
        if (
            opensearch_service
            .index_exists(
                index_name=index_name
            )
        ):
            opensearch_service.delete_index(
                index_name=index_name
            )