import time
import pytest
from tests.aws.support.polling import wait_for_queue_empty
pytestmark = [pytest.mark.performance, pytest.mark.aws, pytest.mark.slow]


def test_queue_drains_within_configured_budget(deployed_ingestion_environment, published_fixture):
    started = time.monotonic()
    wait_for_queue_empty(deployed_ingestion_environment)
    assert time.monotonic() - started <= deployed_ingestion_environment.timeout
