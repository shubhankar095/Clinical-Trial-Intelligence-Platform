import pytest
from tests.aws.support.polling import running_tasks, wait_for_queue_empty, wait_for_registry, wait_until
pytestmark = [pytest.mark.resilience, pytest.mark.aws, pytest.mark.slow, pytest.mark.destructive]


def test_running_task_is_replaced_and_processing_completes(
    deployed_ingestion_environment,
    published_fixture,
    require_destructive_aws_tests,
):
    deployment = deployed_ingestion_environment
    ecs = deployment.client("ecs")
    original = wait_until(
        lambda: running_tasks(deployment),
        timeout=deployment.timeout,
        interval=5,
        description="original running task",
    )[0]
    ecs.stop_task(cluster=deployment.ecs_cluster, task=original, reason="AWS resilience test")
    wait_until(
        lambda: ecs.describe_tasks(cluster=deployment.ecs_cluster, tasks=[original])["tasks"][0]["lastStatus"] == "STOPPED",
        timeout=deployment.timeout,
        interval=5,
        description="original task stopped",
    )
    replacement = wait_until(
        lambda: [task for task in running_tasks(deployment) if task != original],
        timeout=deployment.timeout,
        interval=10,
        description="replacement running task",
    )
    assert replacement
    assert wait_for_registry(deployment, published_fixture.document_id)["status"]["S"] == "COMPLETED"
    wait_for_queue_empty(deployment)
