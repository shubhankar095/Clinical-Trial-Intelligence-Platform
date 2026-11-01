import pytest
from tests.aws.support.actions import retrigger
from tests.aws.support.polling import wait_for_queue_empty, wait_for_registry
pytestmark = [pytest.mark.resilience, pytest.mark.aws, pytest.mark.slow, pytest.mark.destructive]


def test_repeated_trigger_has_single_registry_generation(
    deployed_ingestion_environment,
    published_fixture,
    require_destructive_aws_tests,
):
    deployment = deployed_ingestion_environment
    retrigger(deployment, published_fixture)
    retrigger(deployment, published_fixture)
    record = wait_for_registry(deployment, published_fixture.document_id)
    wait_for_queue_empty(deployment)
    response = deployment.client("dynamodb").scan(
        TableName=deployment.registry_table,
        FilterExpression="document_id = :document_id",
        ExpressionAttributeValues={":document_id": {"S": published_fixture.document_id}},
        Select="COUNT",
    )
    assert response["Count"] == 1
    assert record["status"]["S"] == "COMPLETED"
