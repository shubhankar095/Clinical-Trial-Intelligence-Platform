import pytest
from tests.aws.support.polling import service_counts, wait_for_queue_empty, wait_until
pytestmark = [pytest.mark.performance, pytest.mark.aws, pytest.mark.slow]


def test_idle_service_scales_to_zero(deployed_ingestion_environment, published_fixture):
    deployment = deployed_ingestion_environment
    wait_for_queue_empty(deployment)
    assert wait_until(
        lambda: service_counts(deployment) == (0, 0, 0),
        timeout=deployment.timeout,
        interval=15,
        description="ECS scale to zero",
    )
