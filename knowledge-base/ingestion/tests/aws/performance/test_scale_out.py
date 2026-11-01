import pytest
from tests.aws.support.polling import service_counts, wait_until
pytestmark = [pytest.mark.performance, pytest.mark.aws, pytest.mark.slow]


def test_queue_work_bootstraps_at_least_one_worker(
    deployed_ingestion_environment,
    published_fixture,
):
    deployment = deployed_ingestion_environment
    assert wait_until(
        lambda: service_counts(deployment)[0] >= 1,
        timeout=deployment.timeout,
        interval=10,
        description="ECS bootstrap scale out",
    )
