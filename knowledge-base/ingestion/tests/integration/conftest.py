from __future__ import annotations
import os
import uuid
from collections.abc import Iterator
import boto3
import pytest
from aws_utils.dynamodb import DynamoDBService
from aws_utils.s3 import S3Service
from aws_utils.sqs import SQSService
from aws_utils.opensearch import OpenSearchService
from opensearchpy import OpenSearch

REGION = "ap-south-1"
LOCALSTACK = "http://localhost:4566"

@pytest.fixture(scope="session", autouse=True)
def require_local_services() -> None:
    if os.getenv("RUN_LOCAL_INTEGRATION") != "1":
        pytest.skip("Run through make test-integration.")

@pytest.fixture(scope="session")
def local_clients():
    common = dict(region_name=REGION, endpoint_url=LOCALSTACK,
                  aws_access_key_id="test", aws_secret_access_key="test")
    return {name: boto3.client(name, **common) for name in ("s3", "sqs", "dynamodb")}

@pytest.fixture(scope="session")
def opensearch_client():
    return OpenSearch(
        hosts=[{"host": "localhost", "port": 9200}],
        use_ssl=False,
        verify_certs=False,
        http_compress=True,
        timeout=30,
    )


@pytest.fixture(scope="session")
def opensearch_service(opensearch_client):
    return OpenSearchService(
        deployment_type="domain",
        endpoint="http://localhost:9200",
        region_name=REGION,
        client=opensearch_client,
    )


@pytest.fixture
def local_resources(local_clients) -> Iterator[dict]:
    token = uuid.uuid4().hex
    bucket = f"ingestion-test-{token}"
    queue_url = local_clients["sqs"].create_queue(QueueName=f"ingestion-{token}")["QueueUrl"]
    table = f"processing-{token}"
    local_clients["s3"].create_bucket(Bucket=bucket,
        CreateBucketConfiguration={"LocationConstraint": REGION})
    local_clients["dynamodb"].create_table(
        TableName=table, BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[{"AttributeName":"ingestion_id","AttributeType":"S"}],
        KeySchema=[{"AttributeName":"ingestion_id","KeyType":"HASH"}],)
    local_clients["dynamodb"].get_waiter("table_exists").wait(TableName=table)
    yield {"bucket": bucket, "queue_url": queue_url, "table": table,
           "s3_client": local_clients["s3"], "sqs_client": local_clients["sqs"],
           "dynamodb_client": local_clients["dynamodb"],
           "s3_service": S3Service(region_name=REGION, client=local_clients["s3"]),
           "sqs_service": SQSService(region_name=REGION, client=local_clients["sqs"]),
           "dynamodb_service": DynamoDBService(region_name=REGION, client=local_clients["dynamodb"])}
    local_clients["sqs"].delete_queue(QueueUrl=queue_url)
    listed = local_clients["s3"].list_objects_v2(Bucket=bucket)
    for item in listed.get("Contents", []):
        local_clients["s3"].delete_object(Bucket=bucket, Key=item["Key"])
    local_clients["s3"].delete_bucket(Bucket=bucket)
    local_clients["dynamodb"].delete_table(TableName=table)

########################################################################
