import pytest
from unittest.mock import patch
from indexers.indexer_factory import IndexerFactory

pytestmark = pytest.mark.unit

def test_forwards_opensearch_configuration():
    
    with patch("indexers.indexer_factory.OpenSearchIndexer") as indexer:
        result = IndexerFactory.create(
            opensearch_deployment_type="serverless",
            opensearch_endpoint="https://example.test",
            opensearch_region="ap-south-1",
            opensearch_index_prefix="clinical",
            opensearch_refresh_after_index=False,
            opensearch_bulk_max_records=100,
            opensearch_bulk_max_bytes=1024,
            opensearch_bulk_max_attempts=3,
            opensearch_visibility_timeout_seconds=45.0,
            opensearch_visibility_poll_seconds=0.5,
        )

    assert result is indexer.return_value

    indexer.assert_called_once_with(
        deployment_type="serverless",
        endpoint="https://example.test",
        region_name="ap-south-1",
        index_prefix="clinical",
        refresh_after_index=False,
        bulk_max_records=100,
        bulk_max_bytes=1024,
        bulk_max_attempts=3,
        visibility_timeout_seconds=45.0,
        visibility_poll_seconds=0.5,
    )