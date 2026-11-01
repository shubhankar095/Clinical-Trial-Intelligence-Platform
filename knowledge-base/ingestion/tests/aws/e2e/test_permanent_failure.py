import json

import pytest

from tests.aws.support.cleanup import cleanup_fixture
from tests.aws.support.fixture_factory import publish_fixture
from tests.aws.support.polling import (
    find_registry_record,
    wait_until,
)


pytestmark = [
    pytest.mark.e2e,
    pytest.mark.aws,
    pytest.mark.slow,
    pytest.mark.destructive,
]


def test_invalid_canonical_document_is_redriven_to_dlq(
    deployed_ingestion_environment,
    require_destructive_aws_tests,
):
    deployment = deployed_ingestion_environment

    ecs = deployment.client("ecs")
    sqs = deployment.client("sqs")
    autoscaling = deployment.client(
        "application-autoscaling"
    )

    resource_id = (
        f"service/{deployment.ecs_cluster}/"
        f"{deployment.ecs_service}"
    )

    scalable_target = (
        autoscaling.describe_scalable_targets(
            ServiceNamespace="ecs",
            ResourceIds=[resource_id],
            ScalableDimension=(
                "ecs:service:DesiredCount"
            ),
        )["ScalableTargets"][0]
    )

    original_minimum = scalable_target["MinCapacity"]
    original_maximum = scalable_target["MaxCapacity"]
    original_suspended_state = scalable_target.get(
        "SuspendedState",
        {},
    )

    service = ecs.describe_services(
        cluster=deployment.ecs_cluster,
        services=[deployment.ecs_service],
    )["services"][0]

    original_desired = service["desiredCount"]
    fixture = None

    try:
        # Stop autoscaling before forcing the worker to zero.
        # Otherwise, publishing the S3 fixture could trigger the
        # bootstrap alarm and restart a worker during the test.
        _set_scaling_suspension(
            autoscaling=autoscaling,
            resource_id=resource_id,
            minimum=original_minimum,
            maximum=original_maximum,
            suspended=True,
        )

        ecs.update_service(
            cluster=deployment.ecs_cluster,
            service=deployment.ecs_service,
            desiredCount=0,
        )

        wait_until(
            lambda: _service_is_stopped(
                ecs=ecs,
                cluster=deployment.ecs_cluster,
                service=deployment.ecs_service,
            ),
            timeout=300,
            interval=5,
            description="ECS worker scale-to-zero",
        )

        # Publish an intentionally malformed canonical document
        # after the worker has stopped. The S3 notification places
        # a real message on the deployed ingestion queue.
        fixture = publish_fixture(
            deployment,
            invalid=True,
        )

        source_message_ids = set()
        source_receive_counts = []

        # Check the source queue and DLQ together. SQS may move the
        # message as soon as the redrive threshold is reached, so
        # the test must not require an exact number of source-queue
        # receives before it begins checking the DLQ.
        dlq_message = wait_until(
            lambda: _drive_message_to_dlq(
                sqs=sqs,
                source_queue_url=deployment.queue_url,
                dlq_url=deployment.dlq_url,
                document_id=fixture.document_id,
                source_message_ids=source_message_ids,
                source_receive_counts=(
                    source_receive_counts
                ),
            ),
            timeout=300,
            interval=2,
            description=(
                "invalid canonical-document message in DLQ"
            ),
        )

        # The test must have observed the message on the source
        # queue before SQS redrives it.
        assert source_message_ids
        assert source_receive_counts

        # Every source receive must refer to the same message.
        assert len(source_message_ids) == 1

        # Receive counts must move forward. The first value may be
        # greater than one if a worker received and released the
        # message during shutdown.
        assert source_receive_counts == sorted(
            source_receive_counts
        )
        assert max(source_receive_counts) >= 2

        body = json.loads(dlq_message["Body"])

        # Correlate using the unique test-owned document ID instead
        # of relying on message identity across two queues.
        assert fixture.document_id in json.dumps(
            body,
            sort_keys=True,
        )

        # A pre-claim canonical parsing failure must not create a
        # normal DynamoDB processing-registry record.
        assert (
            find_registry_record(
                deployment,
                fixture.document_id,
            )
            is None
        )

        # Delete only the DLQ message owned by this test.
        sqs.delete_message(
            QueueUrl=deployment.dlq_url,
            ReceiptHandle=dlq_message["ReceiptHandle"],
        )

    finally:
        if fixture is not None:
            cleanup_fixture(
                deployment,
                fixture,
            )

        _restore_scaling_target(
            autoscaling=autoscaling,
            resource_id=resource_id,
            minimum=original_minimum,
            maximum=original_maximum,
            suspended_state=original_suspended_state,
        )

        ecs.update_service(
            cluster=deployment.ecs_cluster,
            service=deployment.ecs_service,
            desiredCount=original_desired,
        )


def _service_is_stopped(
    *,
    ecs,
    cluster,
    service,
):
    response = ecs.describe_services(
        cluster=cluster,
        services=[service],
    )

    deployed_service = response["services"][0]

    return (
        deployed_service["desiredCount"] == 0
        and deployed_service["runningCount"] == 0
        and deployed_service["pendingCount"] == 0
    )


def _receive_matching_message(
    *,
    sqs,
    queue_url,
    document_id,
    visibility_timeout,
):
    response = sqs.receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=10,
        WaitTimeSeconds=1,
        VisibilityTimeout=visibility_timeout,
        AttributeNames=[
            "ApproximateReceiveCount",
        ],
    )

    messages = response.get("Messages", [])

    for message in messages:
        body = message.get("Body", "")

        if document_id in body:
            return message

        # Do not consume a message owned by another test.
        sqs.change_message_visibility(
            QueueUrl=queue_url,
            ReceiptHandle=message["ReceiptHandle"],
            VisibilityTimeout=0,
        )

    return None


def _drive_message_to_dlq(
    *,
    sqs,
    source_queue_url,
    dlq_url,
    document_id,
    source_message_ids,
    source_receive_counts,
):
    # Check the DLQ first. The message may already have crossed the
    # redrive threshold and no longer be available in the source
    # queue.
    dlq_message = _receive_matching_message(
        sqs=sqs,
        queue_url=dlq_url,
        document_id=document_id,
        visibility_timeout=30,
    )

    if dlq_message is not None:
        return dlq_message

    # If it has not reached the DLQ, receive it from the source
    # queue and release it immediately. This advances the receive
    # count without waiting for the normal visibility timeout.
    source_message = _receive_matching_message(
        sqs=sqs,
        queue_url=source_queue_url,
        document_id=document_id,
        visibility_timeout=5,
    )

    if source_message is None:
        return None

    source_message_ids.add(
        source_message["MessageId"]
    )

    source_receive_counts.append(
        int(
            source_message["Attributes"][
                "ApproximateReceiveCount"
            ]
        )
    )

    sqs.change_message_visibility(
        QueueUrl=source_queue_url,
        ReceiptHandle=source_message[
            "ReceiptHandle"
        ],
        VisibilityTimeout=0,
    )

    return None


def _set_scaling_suspension(
    *,
    autoscaling,
    resource_id,
    minimum,
    maximum,
    suspended,
):
    autoscaling.register_scalable_target(
        ServiceNamespace="ecs",
        ResourceId=resource_id,
        ScalableDimension=(
            "ecs:service:DesiredCount"
        ),
        MinCapacity=minimum,
        MaxCapacity=maximum,
        SuspendedState={
            "DynamicScalingInSuspended": suspended,
            "DynamicScalingOutSuspended": suspended,
            "ScheduledScalingSuspended": suspended,
        },
    )


def _restore_scaling_target(
    *,
    autoscaling,
    resource_id,
    minimum,
    maximum,
    suspended_state,
):
    autoscaling.register_scalable_target(
        ServiceNamespace="ecs",
        ResourceId=resource_id,
        ScalableDimension=(
            "ecs:service:DesiredCount"
        ),
        MinCapacity=minimum,
        MaxCapacity=maximum,
        SuspendedState={
            "DynamicScalingInSuspended": (
                suspended_state.get(
                    "DynamicScalingInSuspended",
                    False,
                )
            ),
            "DynamicScalingOutSuspended": (
                suspended_state.get(
                    "DynamicScalingOutSuspended",
                    False,
                )
            ),
            "ScheduledScalingSuspended": (
                suspended_state.get(
                    "ScheduledScalingSuspended",
                    False,
                )
            ),
        },
    )
