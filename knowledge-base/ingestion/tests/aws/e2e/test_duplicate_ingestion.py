import pytest
from tests.aws.support.actions import retrigger
from tests.aws.support.polling import wait_for_queue_empty, wait_for_registry
pytestmark = [pytest.mark.e2e, pytest.mark.aws]


def test_duplicate_trigger_is_idempotent(deployed_ingestion_environment, published_fixture):
    deployment = deployed_ingestion_environment
    first = wait_for_registry(deployment, published_fixture.document_id)
    retrigger(deployment, published_fixture)
    wait_for_queue_empty(deployment)
    second = wait_for_registry(deployment, published_fixture.document_id)
    assert second["ingestion_id"] == first["ingestion_id"]
    assert second["attempt_count"] == first["attempt_count"]
    assert second["index_record_count"] == first["index_record_count"]
