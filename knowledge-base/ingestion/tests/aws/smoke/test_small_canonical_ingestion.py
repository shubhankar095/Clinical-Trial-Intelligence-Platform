import pytest
from tests.aws.support.polling import (
    queue_counts,
    read_result_manifest,
    wait_for_queue_empty,
    wait_for_registry,
)
pytestmark = [pytest.mark.smoke, pytest.mark.aws]


def test_real_canonical_ingestion_completes(deployed_ingestion_environment, published_fixture):
    deployment = deployed_ingestion_environment
    item = wait_for_registry(deployment, published_fixture.document_id)
    payload, _, _ = read_result_manifest(deployment, item)
    assert item["status"]["S"] == "COMPLETED"
    assert payload["processing_status"] == "SUCCESS"
    assert payload["document_id"] == published_fixture.document_id
    wait_for_queue_empty(deployment)
    assert queue_counts(deployment, deployment.dlq_url) == (0, 0)
