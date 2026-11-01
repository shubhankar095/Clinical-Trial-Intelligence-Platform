from indexers.base_indexer import BaseIndexer
from indexers.opensearch_indexer import OpenSearchIndexer


class IndexerFactory:
    """Create the mandatory Amazon OpenSearch indexing adapter."""

    @classmethod
    def create(
        cls,
        *,
        opensearch_deployment_type: str,
        opensearch_endpoint: str,
        opensearch_region: str,
        opensearch_index_prefix: str,
        opensearch_refresh_after_index: bool,
        opensearch_bulk_max_records: int,
        opensearch_bulk_max_bytes: int,
        opensearch_bulk_max_attempts: int,
        opensearch_visibility_timeout_seconds: float,
        opensearch_visibility_poll_seconds: float,
    ) -> BaseIndexer:
        return OpenSearchIndexer(
            deployment_type=opensearch_deployment_type,
            endpoint=opensearch_endpoint,
            region_name=opensearch_region,
            index_prefix=opensearch_index_prefix,
            refresh_after_index=opensearch_refresh_after_index,
            bulk_max_records=opensearch_bulk_max_records,
            bulk_max_bytes=opensearch_bulk_max_bytes,
            bulk_max_attempts=opensearch_bulk_max_attempts,
            visibility_timeout_seconds=opensearch_visibility_timeout_seconds,
            visibility_poll_seconds=opensearch_visibility_poll_seconds,
        )