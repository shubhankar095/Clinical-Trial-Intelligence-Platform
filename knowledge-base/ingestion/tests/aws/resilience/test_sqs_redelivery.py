import json
import pytest
from tests.aws.support.actions import send_owned_queue_marker
from tests.aws.support.polling import wait_until
pytestmark = [pytest.mark.resilience, pytest.mark.aws, pytest.mark.slow, pytest.mark.destructive]


def test_test_owned_message_can_be_released_and_redelivered(
    deployed_ingestion_environment,
    require_destructive_aws_tests,
):
    deployment = deployed_ingestion_environment
    ecs = deployment.client("ecs")
    service = ecs.describe_services(
        cluster=deployment.ecs_cluster,
        services=[deployment.ecs_service],
    )["services"][0]
    original_desired = service["desiredCount"]
    ecs.update_service(cluster=deployment.ecs_cluster, service=deployment.ecs_service, desiredCount=0)
    try:
        body = send_owned_queue_marker(deployment, deployment.queue_url, "redelivery-test")
        sqs = deployment.client("sqs")
        first = wait_until(
            lambda: sqs.receive_message(
                QueueUrl=deployment.queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=1,
                VisibilityTimeout=30,
                AttributeNames=["ApproximateReceiveCount"],
            ).get("Messages"),
            timeout=120,
            interval=2,
            description="first marker receive",
        )[0]
        assert json.loads(first["Body"]) == json.loads(body)
        sqs.change_message_visibility(
            QueueUrl=deployment.queue_url,
            ReceiptHandle=first["ReceiptHandle"],
            VisibilityTimeout=0,
        )
        second = wait_until(
            lambda: sqs.receive_message(
                QueueUrl=deployment.queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=1,
                VisibilityTimeout=30,
                AttributeNames=["ApproximateReceiveCount"],
            ).get("Messages"),
            timeout=120,
            interval=2,
            description="redelivered marker",
        )[0]
        assert second["MessageId"] == first["MessageId"]
        assert int(second["Attributes"]["ApproximateReceiveCount"]) >= 2
        sqs.delete_message(QueueUrl=deployment.queue_url, ReceiptHandle=second["ReceiptHandle"])
    finally:
        ecs.update_service(
            cluster=deployment.ecs_cluster,
            service=deployment.ecs_service,
            desiredCount=original_desired,
        )
