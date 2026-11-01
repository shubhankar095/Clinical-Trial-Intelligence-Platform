import pytest
from unittest.mock import Mock, patch
from workers.ingestion_worker import IngestionWorker

pytestmark = pytest.mark.unit

def test_worker_forwards_davv_configuration_to_indexer_factory(monkeypatch):
    monkeypatch.setattr(
        "workers.ingestion_worker.config.opensearch_visibility_timeout_seconds",
        45.0,
    )
    monkeypatch.setattr(
        "workers.ingestion_worker.config.opensearch_visibility_poll_seconds",
        0.5,
    )

    indexer = Mock()
    indexing_service = Mock()

    with (
        patch.object(
            IngestionWorker,
            "_build_profile",
            return_value=Mock(),
        ),
        patch(
            "workers.ingestion_worker.IndexerFactory.create",
            return_value=indexer,
        ) as create_indexer,
        patch(
            "workers.ingestion_worker.IndexingService",
            return_value=indexing_service,
        ) as create_indexing_service,
    ):
        worker = IngestionWorker(
            text_store=Mock(),
            event_parser=Mock(),
            event_consumer=Mock(),
            processing_registry=Mock(),
            result_store=Mock(),
            shutdown_controller=Mock(),
            manifest_service=Mock(),
            canonical_document_service=Mock(),
            identity_service=Mock(),
            chunking_service=Mock(),
            embedding_service=Mock(),
            index_record_service=Mock(),
        )

    assert worker.indexing_service is indexing_service

    create_indexing_service.assert_called_once_with(
        indexer=indexer,
    )

    call_arguments = create_indexer.call_args.kwargs

    assert call_arguments["opensearch_visibility_timeout_seconds"] == 45.0
    assert call_arguments["opensearch_visibility_poll_seconds"] == 0.5

    assert call_arguments["opensearch_deployment_type"]
    assert call_arguments["opensearch_endpoint"] is not None
    assert call_arguments["opensearch_region"]
    assert call_arguments["opensearch_index_prefix"]
