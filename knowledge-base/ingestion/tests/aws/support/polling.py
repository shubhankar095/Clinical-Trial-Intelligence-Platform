from __future__ import annotations
import json
import time


def wait_until(predicate, *, timeout: int, interval: int = 5, description: str = "condition"):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = predicate()
        if last:
            return last
        time.sleep(interval)
    raise TimeoutError(f"Timed out waiting for {description}; last={last!r}")


def queue_counts(deployment, url):
    attributes = deployment.client("sqs").get_queue_attributes(
        QueueUrl=url,
        AttributeNames=["ApproximateNumberOfMessages", "ApproximateNumberOfMessagesNotVisible"],
    )["Attributes"]
    return (
        int(attributes.get("ApproximateNumberOfMessages", 0)),
        int(attributes.get("ApproximateNumberOfMessagesNotVisible", 0)),
    )


def find_registry_record(deployment, document_id):
    response = deployment.client("dynamodb").scan(
        TableName=deployment.registry_table,
        FilterExpression="document_id = :document_id",
        ExpressionAttributeValues={":document_id": {"S": document_id}},
    )
    items = response.get("Items", [])
    return items[0] if items else None


def wait_for_registry(deployment, document_id, statuses=("COMPLETED",)):
    def check():
        item = find_registry_record(deployment, document_id)
        return item if item and item.get("status", {}).get("S") in statuses else None
    return wait_until(
        check,
        timeout=deployment.timeout,
        interval=10,
        description=f"registry status in {statuses}",
    )


def wait_for_queue_empty(deployment):
    return wait_until(
        lambda: queue_counts(deployment, deployment.queue_url) == (0, 0),
        timeout=deployment.timeout,
        interval=10,
        description="main queue drain",
    )


def service_counts(deployment):
    service = deployment.client("ecs").describe_services(
        cluster=deployment.ecs_cluster,
        services=[deployment.ecs_service],
    )["services"][0]
    return service["desiredCount"], service["runningCount"], service["pendingCount"]


def running_tasks(deployment):
    return deployment.client("ecs").list_tasks(
        cluster=deployment.ecs_cluster,
        serviceName=deployment.ecs_service,
        desiredStatus="RUNNING",
    )["taskArns"]


def read_result_manifest(deployment, item):
    bucket = item["success_manifest_bucket"]["S"]
    key = item["success_manifest_key"]["S"]
    body = deployment.client("s3").get_object(Bucket=bucket, Key=key)["Body"].read()
    return json.loads(body), bucket, key
