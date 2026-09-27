import hashlib
import json
import os
import time

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import boto3
import pytest

from botocore.exceptions import ClientError


POLL_SECONDS = 10

CANONICAL_PREFIX = (
    "canonical-documents/"
)

CANONICAL_FILE_NAME = (
    "extracted-document.json"
)

SUCCESS_MANIFEST_FILE_NAME = (
    "_SUCCESS.json"
)


@dataclass(frozen=True)
class AWSDeployment:
    region: str

    raw_bucket: str
    canonical_bucket: str

    queue_url: str
    dlq_arn: str

    processing_registry_table: str
    processing_schema_version: str

    ecs_cluster: str
    ecs_service: str

    log_group: str

    ecr_repository_url: str
    image_tag: str

    timeout_seconds: int

    @property
    def dlq_name(
        self,
    ) -> str:
        return self.dlq_arn.rsplit(
            ":",
            1,
        )[-1]

    @property
    def ecr_repository_name(
        self,
    ) -> str:
        return (
            self.ecr_repository_url
            .split(
                "/",
                1,
            )[-1]
        )

    @property
    def expected_image_uri(
        self,
    ) -> str:
        return (
            f"{self.ecr_repository_url}:"
            f"{self.image_tag}"
        )


def _required_environment(
    name: str,
) -> str:
    value = os.getenv(
        name,
        "",
    ).strip()

    if not value:
        pytest.fail(
            "Missing required environment "
            f"variable: {name}. "
            "Run these tests through "
            "'make test-aws'."
        )

    return value


@pytest.fixture(scope="session")
def aws_deployment() -> AWSDeployment:
    return AWSDeployment(
        region=os.getenv(
            "AWS_DEFAULT_REGION",
            "ap-south-1",
        ),
        raw_bucket=(
            _required_environment(
                "RAW_BUCKET"
            )
        ),
        canonical_bucket=(
            _required_environment(
                "CANONICAL_BUCKET"
            )
        ),
        queue_url=(
            _required_environment(
                "EXTRACTION_QUEUE_URL"
            )
        ),
        dlq_arn=(
            _required_environment(
                "EXTRACTION_DLQ_ARN"
            )
        ),
        processing_registry_table=(
            _required_environment(
                "PROCESSING_REGISTRY_TABLE"
            )
        ),
        processing_schema_version=(
            os.getenv(
                "PROCESSING_SCHEMA_VERSION",
                "extraction-v1",
            ).strip()
            or "extraction-v1"
        ),
        ecs_cluster=(
            _required_environment(
                "ECS_CLUSTER"
            )
        ),
        ecs_service=(
            _required_environment(
                "ECS_SERVICE"
            )
        ),
        log_group=(
            _required_environment(
                "CLOUDWATCH_LOG_GROUP"
            )
        ),
        ecr_repository_url=(
            _required_environment(
                "ECR_REPOSITORY_URL"
            )
        ),
        image_tag=os.getenv(
            "IMAGE_TAG",
            "dev",
        ),
        timeout_seconds=int(
            os.getenv(
                "AWS_TEST_TIMEOUT",
                "1200",
            )
        ),
    )


@pytest.fixture(scope="session")
def aws_session(
    aws_deployment,
):
    profile = (
        os.getenv(
            "AWS_PROFILE",
            "",
        ).strip()
        or None
    )

    return boto3.Session(
        profile_name=profile,
        region_name=(
            aws_deployment.region
        ),
    )


@pytest.fixture(scope="session")
def s3_client(
    aws_session,
):
    return aws_session.client(
        "s3"
    )


@pytest.fixture(scope="session")
def sqs_client(
    aws_session,
):
    return aws_session.client(
        "sqs"
    )


@pytest.fixture(scope="session")
def ecs_client(
    aws_session,
):
    return aws_session.client(
        "ecs"
    )


@pytest.fixture(scope="session")
def logs_client(
    aws_session,
):
    return aws_session.client(
        "logs"
    )


@pytest.fixture(scope="session")
def ecr_client(
    aws_session,
):
    return aws_session.client(
        "ecr"
    )


@pytest.fixture(scope="session")
def dynamodb_client(
    aws_session,
):
    return aws_session.client(
        "dynamodb"
    )


@pytest.fixture(scope="session")
def data_dir() -> Path:
    return (
        Path(__file__)
        .resolve()
        .parents[1]
        / "data"
    )


@pytest.fixture(scope="session")
def aws_test_helpers(
    aws_deployment,
    s3_client,
    sqs_client,
    ecs_client,
    dynamodb_client,
):
    class Helpers:

        created_source_versions = []
        created_document_ids = set()

        @staticmethod
        def queue_counts(
            queue_url=None,
        ):
            response = (
                sqs_client
                .get_queue_attributes(
                    QueueUrl=(
                        queue_url
                        or aws_deployment
                        .queue_url
                    ),
                    AttributeNames=[
                        (
                            "ApproximateNumber"
                            "OfMessages"
                        ),
                        (
                            "ApproximateNumber"
                            "OfMessagesNotVisible"
                        ),
                    ],
                )
            )

            attributes = response.get(
                "Attributes",
                {},
            )

            return (
                int(
                    attributes.get(
                        (
                            "ApproximateNumber"
                            "OfMessages"
                        ),
                        "0",
                    )
                ),
                int(
                    attributes.get(
                        (
                            "ApproximateNumber"
                            "OfMessagesNotVisible"
                        ),
                        "0",
                    )
                ),
            )

        @staticmethod
        def dlq_url():
            response = (
                sqs_client
                .get_queue_url(
                    QueueName=(
                        aws_deployment
                        .dlq_name
                    ),
                )
            )

            return response[
                "QueueUrl"
            ]

        @staticmethod
        def wait_for_queue_to_drain(
            timeout_seconds=None,
        ):
            timeout = (
                timeout_seconds
                or aws_deployment
                .timeout_seconds
            )

            deadline = (
                time.monotonic()
                + timeout
            )

            last_counts = (
                0,
                0,
            )

            while (
                time.monotonic()
                < deadline
            ):
                last_counts = (
                    Helpers.queue_counts()
                )

                if last_counts == (
                    0,
                    0,
                ):
                    return

                time.sleep(
                    POLL_SECONDS
                )

            pytest.fail(
                "Extraction queue did not "
                "drain before timeout. "
                f"visible={last_counts[0]}, "
                f"in_flight={last_counts[1]}"
            )

        @staticmethod
        def wait_for_dlq_to_be_empty(
            timeout_seconds=60,
        ):
            deadline = (
                time.monotonic()
                + timeout_seconds
            )

            last_counts = (
                0,
                0,
            )

            while (
                time.monotonic()
                < deadline
            ):
                last_counts = (
                    Helpers.queue_counts(
                        Helpers.dlq_url()
                    )
                )

                if last_counts == (
                    0,
                    0,
                ):
                    return

                time.sleep(
                    POLL_SECONDS
                )

            pytest.fail(
                "Extraction DLQ was not empty "
                "before timeout. "
                f"visible={last_counts[0]}, "
                f"in_flight={last_counts[1]}"
            )

        @staticmethod
        def service_counts():
            response = (
                ecs_client
                .describe_services(
                    cluster=(
                        aws_deployment
                        .ecs_cluster
                    ),
                    services=[
                        (
                            aws_deployment
                            .ecs_service
                        )
                    ],
                )
            )

            services = response.get(
                "services",
                [],
            )

            if not services:
                pytest.fail(
                    "ECS extraction service "
                    "was not found."
                )

            service = services[0]

            return {
                "status": (
                    service["status"]
                ),
                "desired": (
                    service[
                        "desiredCount"
                    ]
                ),
                "running": (
                    service[
                        "runningCount"
                    ]
                ),
                "pending": (
                    service[
                        "pendingCount"
                    ]
                ),
            }

        @staticmethod
        def wait_for_service_capacity(
            minimum_desired=1,
            timeout_seconds=None,
        ):
            timeout = (
                timeout_seconds
                or aws_deployment
                .timeout_seconds
            )

            deadline = (
                time.monotonic()
                + timeout
            )

            last_counts = None

            while (
                time.monotonic()
                < deadline
            ):
                last_counts = (
                    Helpers.service_counts()
                )

                if (
                    last_counts[
                        "desired"
                    ]
                    >= minimum_desired
                    or last_counts[
                        "running"
                    ]
                    >= minimum_desired
                ):
                    return last_counts

                time.sleep(
                    POLL_SECONDS
                )

            pytest.fail(
                "ECS service did not "
                "scale out before timeout. "
                f"Last counts: "
                f"{last_counts}"
            )

        @staticmethod
        def wait_for_service_to_scale_to_zero(
            timeout_seconds=None,
        ):
            timeout = (
                timeout_seconds
                or aws_deployment
                .timeout_seconds
            )

            deadline = (
                time.monotonic()
                + timeout
            )

            last_counts = None

            while (
                time.monotonic()
                < deadline
            ):
                last_counts = (
                    Helpers.service_counts()
                )

                if (
                    last_counts[
                        "desired"
                    ]
                    == 0
                    and last_counts[
                        "running"
                    ]
                    == 0
                    and last_counts[
                        "pending"
                    ]
                    == 0
                ):
                    return last_counts

                time.sleep(
                    POLL_SECONDS
                )

            pytest.fail(
                "ECS service did not "
                "scale to zero before "
                "timeout. "
                f"Last counts: "
                f"{last_counts}"
            )

        @staticmethod
        def create_document_id(
            source_bucket,
            source_key,
            source_version_id,
            processing_schema_version=None,
        ):
            schema_version = (
                processing_schema_version
                or aws_deployment
                .processing_schema_version
            )

            identity_payload = {
                (
                    "processing_schema_"
                    "version"
                ): schema_version.strip(),
                "source_bucket": (
                    source_bucket.strip()
                ),
                "source_key": (
                    source_key.strip()
                ),
                "source_version_id": (
                    source_version_id
                    .strip()
                ),
            }

            serialized_identity = (
                json.dumps(
                    identity_payload,
                    sort_keys=True,
                    separators=(
                        ",",
                        ":",
                    ),
                    ensure_ascii=False,
                )
            )

            return hashlib.sha256(
                serialized_identity.encode(
                    "utf-8"
                )
            ).hexdigest()

        @staticmethod
        def canonical_document_key(
            document_id,
        ):
            return (
                f"{CANONICAL_PREFIX}"
                f"{document_id}/"
                f"{CANONICAL_FILE_NAME}"
            )

        @staticmethod
        def success_manifest_key(
            document_id,
        ):
            return (
                f"{CANONICAL_PREFIX}"
                f"{document_id}/"
                f"{SUCCESS_MANIFEST_FILE_NAME}"
            )

        @staticmethod
        def object_exists(
            bucket,
            key,
        ):
            try:
                s3_client.head_object(
                    Bucket=bucket,
                    Key=key,
                )

                return True

            except ClientError as exception:
                error_code = (
                    exception.response
                    .get(
                        "Error",
                        {},
                    )
                    .get(
                        "Code"
                    )
                )

                if error_code in {
                    "404",
                    "NoSuchKey",
                    "NotFound",
                }:
                    return False

                raise

        @staticmethod
        def load_json_object(
            bucket,
            key,
        ):
            response = (
                s3_client
                .get_object(
                    Bucket=bucket,
                    Key=key,
                )
            )

            return json.loads(
                response["Body"]
                .read()
                .decode(
                    "utf-8"
                )
            )

        @staticmethod
        def get_registry_item(
            document_id,
        ):
            response = (
                dynamodb_client
                .get_item(
                    TableName=(
                        aws_deployment
                        .processing_registry_table
                    ),
                    Key={
                        "document_id": {
                            "S": document_id,
                        }
                    },
                    ConsistentRead=True,
                )
            )

            return response.get(
                "Item"
            )

        @staticmethod
        def wait_for_registry_status(
            document_id,
            expected_status="COMPLETED",
            timeout_seconds=None,
        ):
            timeout = (
                timeout_seconds
                or aws_deployment
                .timeout_seconds
            )

            deadline = (
                time.monotonic()
                + timeout
            )

            last_item = None

            while (
                time.monotonic()
                < deadline
            ):
                last_item = (
                    Helpers
                    .get_registry_item(
                        document_id
                    )
                )

                if last_item:
                    status = (
                        last_item
                        .get(
                            "status",
                            {},
                        )
                        .get(
                            "S"
                        )
                    )

                    if (
                        status
                        == expected_status
                    ):
                        return last_item

                time.sleep(
                    POLL_SECONDS
                )

            pytest.fail(
                "Processing registry did not "
                "reach expected status before "
                "timeout. "
                f"document_id={document_id}, "
                f"expected_status="
                f"{expected_status}, "
                f"last_item={last_item}"
            )

        @staticmethod
        def wait_for_success_manifest(
            document_id,
            timeout_seconds=None,
        ):
            timeout = (
                timeout_seconds
                or aws_deployment
                .timeout_seconds
            )

            deadline = (
                time.monotonic()
                + timeout
            )

            manifest_key = (
                Helpers
                .success_manifest_key(
                    document_id
                )
            )

            while (
                time.monotonic()
                < deadline
            ):
                if Helpers.object_exists(
                    bucket=(
                        aws_deployment
                        .canonical_bucket
                    ),
                    key=manifest_key,
                ):
                    manifest = (
                        Helpers
                        .load_json_object(
                            bucket=(
                                aws_deployment
                                .canonical_bucket
                            ),
                            key=manifest_key,
                        )
                    )

                    return (
                        manifest_key,
                        manifest,
                    )

                time.sleep(
                    POLL_SECONDS
                )

            pytest.fail(
                "Processing success manifest "
                "was not created before "
                "timeout. "
                f"document_id={document_id}, "
                f"manifest_key={manifest_key}"
            )

        @staticmethod
        def wait_for_canonical_document(
            source_key,
            source_version_id,
            timeout_seconds=None,
        ):
            timeout = (
                timeout_seconds
                or aws_deployment
                .timeout_seconds
            )

            document_id = (
                Helpers.create_document_id(
                    source_bucket=(
                        aws_deployment
                        .raw_bucket
                    ),
                    source_key=source_key,
                    source_version_id=(
                        source_version_id
                    ),
                )
            )

            canonical_key = (
                Helpers
                .canonical_document_key(
                    document_id
                )
            )

            deadline = (
                time.monotonic()
                + timeout
            )

            while (
                time.monotonic()
                < deadline
            ):
                if Helpers.object_exists(
                    bucket=(
                        aws_deployment
                        .canonical_bucket
                    ),
                    key=canonical_key,
                ):
                    payload = (
                        Helpers
                        .load_json_object(
                            bucket=(
                                aws_deployment
                                .canonical_bucket
                            ),
                            key=canonical_key,
                        )
                    )

                    if (
                        payload.get(
                            "document_id"
                        )
                        == document_id
                        and payload.get(
                            "source_bucket"
                        )
                        == (
                            aws_deployment
                            .raw_bucket
                        )
                        and payload.get(
                            "source_key"
                        )
                        == source_key
                        and payload.get(
                            "source_version_id"
                        )
                        == source_version_id
                        and payload.get(
                            (
                                "processing_schema_"
                                "version"
                            )
                        )
                        == (
                            aws_deployment
                            .processing_schema_version
                        )
                    ):
                        return (
                            document_id,
                            canonical_key,
                            payload,
                        )

                dlq_counts = (
                    Helpers.queue_counts(
                        Helpers.dlq_url()
                    )
                )

                if (
                    dlq_counts[0] > 0
                    or dlq_counts[1] > 0
                ):
                    pytest.fail(
                        "Document-processing "
                        "message reached the DLQ "
                        "before canonical output "
                        "was created. "
                        f"source_key={source_key}, "
                        f"source_version_id="
                        f"{source_version_id}, "
                        f"dlq_visible="
                        f"{dlq_counts[0]}, "
                        f"dlq_in_flight="
                        f"{dlq_counts[1]}"
                    )

                time.sleep(
                    POLL_SECONDS
                )

            queue_counts = (
                Helpers.queue_counts()
            )

            dlq_counts = (
                Helpers.queue_counts(
                    Helpers.dlq_url()
                )
            )

            service_counts = (
                Helpers.service_counts()
            )

            registry_item = (
                Helpers.get_registry_item(
                    document_id
                )
            )

            pytest.fail(
                "Canonical document was not "
                "created before timeout. "
                f"document_id={document_id}, "
                f"source_key={source_key}, "
                f"source_version_id="
                f"{source_version_id}, "
                f"queue_visible="
                f"{queue_counts[0]}, "
                f"queue_in_flight="
                f"{queue_counts[1]}, "
                f"dlq_visible="
                f"{dlq_counts[0]}, "
                f"dlq_in_flight="
                f"{dlq_counts[1]}, "
                f"ecs={service_counts}, "
                f"registry_item="
                f"{registry_item}"
            )

        @staticmethod
        def upload_document(
            file_path,
            category="protocols",
            source_key=None,
        ):
            if source_key is None:
                unique_name = (
                    f"{file_path.stem}-"
                    f"{uuid4().hex[:12]}"
                    f"{file_path.suffix}"
                )

                source_key = (
                    "documents/"
                    "AWSTEST001/"
                    f"{category}/"
                    f"{unique_name}"
                )

            started_at = datetime.now(
                timezone.utc
            )

            response = (
                s3_client
                .put_object(
                    Bucket=(
                        aws_deployment
                        .raw_bucket
                    ),
                    Key=source_key,
                    Body=file_path.read_bytes(),
                    ContentType=(
                        "application/pdf"
                    ),
                )
            )

            version_id = response.get(
                "VersionId"
            )

            if not version_id:
                pytest.fail(
                    "S3 upload did not return "
                    "a VersionId. The raw bucket "
                    "must have versioning enabled."
                )

            Helpers.created_source_versions.append(
                {
                    "bucket": (
                        aws_deployment
                        .raw_bucket
                    ),
                    "key": source_key,
                    "version_id": (
                        version_id
                    ),
                }
            )

            document_id = (
                Helpers.create_document_id(
                    source_bucket=(
                        aws_deployment
                        .raw_bucket
                    ),
                    source_key=source_key,
                    source_version_id=(
                        version_id
                    ),
                )
            )

            Helpers.created_document_ids.add(
                document_id
            )

            return (
                source_key,
                version_id,
                started_at,
            )

        @staticmethod
        def process_document(
            file_path,
            category="protocols",
            source_key=None,
        ):
            (
                source_key,
                version_id,
                started_at,
            ) = Helpers.upload_document(
                file_path=file_path,
                category=category,
                source_key=source_key,
            )

            del started_at

            (
                document_id,
                canonical_key,
                payload,
            ) = (
                Helpers
                .wait_for_canonical_document(
                    source_key=source_key,
                    source_version_id=(
                        version_id
                    ),
                )
            )

            (
                manifest_key,
                manifest,
            ) = (
                Helpers
                .wait_for_success_manifest(
                    document_id
                )
            )

            registry_item = (
                Helpers
                .wait_for_registry_status(
                    document_id=document_id,
                    expected_status=(
                        "COMPLETED"
                    ),
                )
            )

            Helpers.wait_for_queue_to_drain(
                timeout_seconds=180
            )

            return {
                "source_key": source_key,
                "source_version_id": (
                    version_id
                ),
                "document_id": (
                    document_id
                ),
                "canonical_key": (
                    canonical_key
                ),
                "payload": payload,
                "manifest_key": (
                    manifest_key
                ),
                "manifest": manifest,
                "registry_item": (
                    registry_item
                ),
            }

        @staticmethod
        def send_duplicate_s3_event(
            source_key,
            source_version_id,
        ):
            event = {
                "Records": [
                    {
                        "eventSource": (
                            "aws:s3"
                        ),
                        "eventName": (
                            "ObjectCreated:Put"
                        ),
                        "eventTime": (
                            datetime.now(
                                timezone.utc
                            ).isoformat()
                        ),
                        "s3": {
                            "bucket": {
                                "name": (
                                    aws_deployment
                                    .raw_bucket
                                ),
                            },
                            "object": {
                                "key": (
                                    source_key
                                ),
                                "versionId": (
                                    source_version_id
                                ),
                                "sequencer": (
                                    uuid4().hex
                                ),
                            },
                        },
                    }
                ]
            }

            response = (
                sqs_client
                .send_message(
                    QueueUrl=(
                        aws_deployment
                        .queue_url
                    ),
                    MessageBody=json.dumps(
                        event
                    ),
                )
            )

            return response[
                "MessageId"
            ]

        @staticmethod
        def delete_object_versions(
            bucket,
            key,
        ):
            paginator = (
                s3_client
                .get_paginator(
                    "list_object_versions"
                )
            )

            delete_items = []

            for page in paginator.paginate(
                Bucket=bucket,
                Prefix=key,
            ):
                for item in page.get(
                    "Versions",
                    [],
                ):
                    if item[
                        "Key"
                    ].startswith(
                        key
                    ):
                        delete_items.append(
                            {
                                "Key": (
                                    item["Key"]
                                ),
                                "VersionId": (
                                    item[
                                        "VersionId"
                                    ]
                                ),
                            }
                        )

                for item in page.get(
                    "DeleteMarkers",
                    [],
                ):
                    if item[
                        "Key"
                    ].startswith(
                        key
                    ):
                        delete_items.append(
                            {
                                "Key": (
                                    item["Key"]
                                ),
                                "VersionId": (
                                    item[
                                        "VersionId"
                                    ]
                                ),
                            }
                        )

            for start in range(
                0,
                len(delete_items),
                1000,
            ):
                batch = delete_items[
                    start:
                    start + 1000
                ]

                if batch:
                    s3_client.delete_objects(
                        Bucket=bucket,
                        Delete={
                            "Objects": batch,
                            "Quiet": True,
                        },
                    )

        @classmethod
        def cleanup(
            cls,
        ):
            cleanup_errors = []

            for source in (
                cls.created_source_versions
            ):
                try:
                    s3_client.delete_object(
                        Bucket=source[
                            "bucket"
                        ],
                        Key=source["key"],
                        VersionId=source[
                            "version_id"
                        ],
                    )

                except Exception as exception:
                    cleanup_errors.append(
                        (
                            "source object "
                            f"{source}: "
                            f"{exception}"
                        )
                    )

            for document_id in (
                cls.created_document_ids
            ):
                canonical_prefix = (
                    f"{CANONICAL_PREFIX}"
                    f"{document_id}/"
                )

                try:
                    cls.delete_object_versions(
                        bucket=(
                            aws_deployment
                            .canonical_bucket
                        ),
                        key=canonical_prefix,
                    )

                except Exception as exception:
                    cleanup_errors.append(
                        (
                            "canonical prefix "
                            f"{canonical_prefix}: "
                            f"{exception}"
                        )
                    )

                try:
                    dynamodb_client.delete_item(
                        TableName=(
                            aws_deployment
                            .processing_registry_table
                        ),
                        Key={
                            "document_id": {
                                "S": (
                                    document_id
                                ),
                            }
                        },
                    )

                except Exception as exception:
                    cleanup_errors.append(
                        (
                            "registry item "
                            f"{document_id}: "
                            f"{exception}"
                        )
                    )

            if cleanup_errors:
                print(
                    "AWS test cleanup encountered "
                    "errors:"
                )

                for error in cleanup_errors:
                    print(
                        f"  - {error}"
                    )

    yield Helpers

    Helpers.cleanup()