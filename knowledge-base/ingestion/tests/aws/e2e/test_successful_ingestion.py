import pytest
from tests.aws.support.polling import read_result_manifest, wait_for_queue_empty, wait_for_registry
pytestmark = [pytest.mark.e2e, pytest.mark.aws]


def test_full_fixture_is_ingested(deployed_ingestion_environment, published_fixture):
    deployment = deployed_ingestion_environment
    item = wait_for_registry(deployment, published_fixture.document_id)
    payload, bucket, key = read_result_manifest(deployment, item)
    chunk_count = int(item["chunk_count"]["N"])
    record_count = int(item["index_record_count"]["N"])
    assert chunk_count > 0
    assert record_count == chunk_count
    assert payload["processing_status"] == "SUCCESS"
    assert payload["chunk_count"] == chunk_count
    assert payload["index_record_count"] == record_count
    assert item["success_manifest_bucket"]["S"] == bucket
    assert item["success_manifest_key"]["S"] == key
    wait_for_queue_empty(deployment)
