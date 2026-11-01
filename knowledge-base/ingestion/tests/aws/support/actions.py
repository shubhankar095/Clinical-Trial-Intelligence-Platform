from __future__ import annotations
import json
import uuid


def retrigger(deployment, fixture) -> None:
    s3 = deployment.client("s3")
    body = s3.get_object(
        Bucket=deployment.canonical_bucket,
        Key=fixture.manifest_key,
    )["Body"].read()
    s3.put_object(
        Bucket=deployment.canonical_bucket,
        Key=fixture.manifest_key,
        Body=body,
        ContentType="application/json",
    )


def send_owned_queue_marker(deployment, queue_url: str, document_id: str) -> str:
    body = json.dumps(
        {
            "test_type": "aws-post-deploy-marker",
            "document_id": document_id,
            "marker_id": uuid.uuid4().hex,
        },
        sort_keys=True,
    )
    deployment.client("sqs").send_message(QueueUrl=queue_url, MessageBody=body)
    return body
