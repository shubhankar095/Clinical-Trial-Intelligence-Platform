from __future__ import annotations
import json
import time


def _message_matches(body: str, document_id: str) -> bool:
    if document_id in body:
        return True
    try:
        payload = json.loads(body)
    except (TypeError, ValueError):
        return False
    return document_id in json.dumps(payload, sort_keys=True)


def delete_owned_messages(deployment, queue_url: str, document_id: str, attempts: int = 6) -> None:
    sqs = deployment.client("sqs")
    for _ in range(attempts):
        response = sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=10,
            WaitTimeSeconds=1,
            VisibilityTimeout=5,
            AttributeNames=["All"],
        )
        messages = response.get("Messages", [])
        if not messages:
            return
        for message in messages:
            if _message_matches(message.get("Body", ""), document_id):
                sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=message["ReceiptHandle"])
            else:
                sqs.change_message_visibility(
                    QueueUrl=queue_url,
                    ReceiptHandle=message["ReceiptHandle"],
                    VisibilityTimeout=0,
                )
        time.sleep(1)


def _delete_prefix(s3, bucket: str, prefix: str) -> None:
    continuation = None
    while True:
        request = {"Bucket": bucket, "Prefix": prefix}
        if continuation:
            request["ContinuationToken"] = continuation
        response = s3.list_objects_v2(**request)
        contents = response.get("Contents", [])
        if contents:
            s3.delete_objects(
                Bucket=bucket,
                Delete={"Objects": [{"Key": item["Key"]} for item in contents]},
            )
        if not response.get("IsTruncated"):
            return
        continuation = response["NextContinuationToken"]


def cleanup_fixture(deployment, fixture) -> None:
    delete_owned_messages(deployment, deployment.queue_url, fixture.document_id)
    delete_owned_messages(deployment, deployment.dlq_url, fixture.document_id)
    s3 = deployment.client("s3")
    _delete_prefix(s3, deployment.canonical_bucket, fixture.prefix)
    ddb = deployment.client("dynamodb")
    response = ddb.scan(
        TableName=deployment.registry_table,
        ProjectionExpression="ingestion_id, document_id, success_manifest_bucket, success_manifest_key",
    )
    for item in response.get("Items", []):
        if item.get("document_id", {}).get("S") != fixture.document_id:
            continue
        ingestion_id = item["ingestion_id"]["S"]
        result_bucket = item.get("success_manifest_bucket", {}).get("S", deployment.canonical_bucket)
        _delete_prefix(s3, result_bucket, f"ingestion-results/{ingestion_id}/")
        ddb.delete_item(
            TableName=deployment.registry_table,
            Key={"ingestion_id": item["ingestion_id"]},
        )
