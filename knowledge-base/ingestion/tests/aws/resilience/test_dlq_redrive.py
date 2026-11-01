import json
import pytest
from tests.aws.support.actions import send_owned_queue_marker
from tests.aws.support.polling import wait_until
pytestmark = [pytest.mark.resilience, pytest.mark.aws, pytest.mark.slow, pytest.mark.destructive]


def test_test_owned_dlq_message_is_selectively_received_and_deleted(
    deployed_ingestion_environment,
    require_destructive_aws_tests,
):
    deployment = deployed_ingestion_environment
    expected_body = send_owned_queue_marker(deployment, deployment.dlq_url, "dlq-selective-test")
    sqs = deployment.client("sqs")
    message = wait_until(
        lambda: sqs.receive_message(
            QueueUrl=deployment.dlq_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=1,
            VisibilityTimeout=30,
        ).get("Messages"),
        timeout=120,
        interval=2,
        description="test-owned DLQ message",
    )[0]
    assert json.loads(message["Body"]) == json.loads(expected_body)
    sqs.delete_message(QueueUrl=deployment.dlq_url, ReceiptHandle=message["ReceiptHandle"])
