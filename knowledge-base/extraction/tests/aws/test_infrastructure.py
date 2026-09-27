import json

import pytest


pytestmark = pytest.mark.aws


def _encryption_algorithm(
    s3_client,
    bucket,
):
    response = (
        s3_client
        .get_bucket_encryption(
            Bucket=bucket
        )
    )

    rules = (
        response[
            "ServerSideEncryptionConfiguration"
        ]["Rules"]
    )

    return (
        rules[0][
            "ApplyServerSideEncryptionByDefault"
        ][
            "SSEAlgorithm"
        ]
    )


def test_deployed_resources_are_accessible_and_configured(
    aws_deployment,
    aws_test_helpers,
    s3_client,
    sqs_client,
    ecs_client,
    logs_client,
    ecr_client,
    dynamodb_client,
):
    s3_client.head_bucket(
        Bucket=(
            aws_deployment.raw_bucket
        )
    )

    s3_client.head_bucket(
        Bucket=(
            aws_deployment
            .canonical_bucket
        )
    )

    assert (
        s3_client
        .get_bucket_versioning(
            Bucket=(
                aws_deployment.raw_bucket
            )
        )["Status"]
        == "Enabled"
    )

    assert (
        s3_client
        .get_bucket_versioning(
            Bucket=(
                aws_deployment
                .canonical_bucket
            )
        )["Status"]
        == "Enabled"
    )

    assert (
        _encryption_algorithm(
            s3_client,
            aws_deployment.raw_bucket,
        )
        == "AES256"
    )

    assert (
        _encryption_algorithm(
            s3_client,
            (
                aws_deployment
                .canonical_bucket
            ),
        )
        == "AES256"
    )

    queue_response = (
        sqs_client
        .get_queue_attributes(
            QueueUrl=(
                aws_deployment.queue_url
            ),
            AttributeNames=[
                "QueueArn",
                "VisibilityTimeout",
                (
                    "ReceiveMessage"
                    "WaitTimeSeconds"
                ),
                "RedrivePolicy",
            ],
        )
    )

    queue_attributes = (
        queue_response["Attributes"]
    )

    assert queue_attributes["QueueArn"]

    assert int(
        queue_attributes[
            "VisibilityTimeout"
        ]
    ) > 0

    assert (
        queue_attributes[
            "ReceiveMessageWaitTimeSeconds"
        ]
        == "20"
    )

    redrive_policy = json.loads(
        queue_attributes[
            "RedrivePolicy"
        ]
    )

    assert (
        redrive_policy[
            "deadLetterTargetArn"
        ]
        == aws_deployment.dlq_arn
    )

    assert int(
        redrive_policy[
            "maxReceiveCount"
        ]
    ) == 5

    dlq_attributes = (
        sqs_client
        .get_queue_attributes(
            QueueUrl=(
                aws_test_helpers
                .dlq_url()
            ),
            AttributeNames=[
                "QueueArn",
                "MessageRetentionPeriod",
            ],
        )["Attributes"]
    )

    assert (
        dlq_attributes["QueueArn"]
        == aws_deployment.dlq_arn
    )

    assert (
        dlq_attributes[
            "MessageRetentionPeriod"
        ]
        == "1209600"
    )

    table_response = (
        dynamodb_client
        .describe_table(
            TableName=(
                aws_deployment
                .processing_registry_table
            )
        )
    )

    table = table_response["Table"]

    assert (
        table["TableStatus"]
        == "ACTIVE"
    )

    assert table["KeySchema"] == [
        {
            "AttributeName": (
                "document_id"
            ),
            "KeyType": "HASH",
        }
    ]

    attribute_definitions = {
        definition[
            "AttributeName"
        ]: definition[
            "AttributeType"
        ]
        for definition
        in table[
            "AttributeDefinitions"
        ]
    }

    assert (
        attribute_definitions[
            "document_id"
        ]
        == "S"
    )

    ttl_response = (
        dynamodb_client
        .describe_time_to_live(
            TableName=(
                aws_deployment
                .processing_registry_table
            )
        )
    )

    ttl_description = (
        ttl_response[
            "TimeToLiveDescription"
        ]
    )

    assert (
        ttl_description[
            "AttributeName"
        ]
        == "ttl"
    )

    assert (
        ttl_description[
            "TimeToLiveStatus"
        ]
        in {
            "ENABLED",
            "ENABLING",
        }
    )

    service_response = (
        ecs_client
        .describe_services(
            cluster=(
                aws_deployment.ecs_cluster
            ),
            services=[
                aws_deployment.ecs_service
            ],
        )
    )

    assert (
        service_response["failures"]
        == []
    )

    service = (
        service_response[
            "services"
        ][0]
    )

    assert service["status"] == "ACTIVE"

    task_definition = (
        ecs_client
        .describe_task_definition(
            taskDefinition=(
                service[
                    "taskDefinition"
                ]
            )
        )[
            "taskDefinition"
        ]
    )

    assert (
        "FARGATE"
        in task_definition[
            "requiresCompatibilities"
        ]
    )

    assert (
        task_definition[
            "networkMode"
        ]
        == "awsvpc"
    )

    assert (
        task_definition[
            "runtimePlatform"
        ][
            "cpuArchitecture"
        ]
        == "X86_64"
    )

    assert (
        task_definition[
            "runtimePlatform"
        ][
            "operatingSystemFamily"
        ]
        == "LINUX"
    )

    container = (
        task_definition[
            "containerDefinitions"
        ][0]
    )

    assert (
        container["image"]
        == (
            aws_deployment
            .expected_image_uri
        )
    )

    environment = {
        item["name"]: item["value"]
        for item
        in container.get(
            "environment",
            [],
        )
    }

    required_environment = {
        (
            "CANONICAL_DOCUMENT_"
            "BUCKET"
        ),
        (
            "DOCUMENT_UPLOADED_"
            "QUEUE_URL"
        ),
        (
            "PROCESSING_REGISTRY_"
            "TABLE"
        ),
        (
            "PROCESSING_SCHEMA_"
            "VERSION"
        ),
        (
            "SQS_VISIBILITY_"
            "EXTENSION_SECONDS"
        ),
        (
            "SQS_VISIBILITY_"
            "HEARTBEAT_SECONDS"
        ),
        (
            "PROCESSING_CLAIM_"
            "LEASE_SECONDS"
        ),
        (
            "PROCESSING_CLAIM_"
            "HEARTBEAT_SECONDS"
        ),
    }

    assert required_environment.issubset(
        environment
    )

    assert (
        environment[
            "CANONICAL_DOCUMENT_BUCKET"
        ]
        == (
            aws_deployment
            .canonical_bucket
        )
    )

    assert (
        environment[
            "DOCUMENT_UPLOADED_QUEUE_URL"
        ]
        == aws_deployment.queue_url
    )

    assert (
        environment[
            "PROCESSING_REGISTRY_TABLE"
        ]
        == (
            aws_deployment
            .processing_registry_table
        )
    )

    assert (
        environment[
            "PROCESSING_SCHEMA_VERSION"
        ]
        == (
            aws_deployment
            .processing_schema_version
        )
    )

    sqs_extension = int(
        environment[
            "SQS_VISIBILITY_EXTENSION_SECONDS"
        ]
    )

    sqs_heartbeat = int(
        environment[
            "SQS_VISIBILITY_HEARTBEAT_SECONDS"
        ]
    )

    claim_lease = int(
        environment[
            "PROCESSING_CLAIM_LEASE_SECONDS"
        ]
    )

    claim_heartbeat = int(
        environment[
            "PROCESSING_CLAIM_HEARTBEAT_SECONDS"
        ]
    )

    assert 0 < sqs_heartbeat
    assert (
        sqs_heartbeat
        < sqs_extension
        <= 43200
    )

    assert (
        sqs_extension
        < claim_lease
    )

    assert (
        0
        < claim_heartbeat
        < claim_lease
    )

    log_options = (
        container[
            "logConfiguration"
        ][
            "options"
        ]
    )

    assert (
        log_options[
            "awslogs-group"
        ]
        == aws_deployment.log_group
    )

    assert (
        log_options[
            "awslogs-region"
        ]
        == aws_deployment.region
    )

    log_groups = (
        logs_client
        .describe_log_groups(
            logGroupNamePrefix=(
                aws_deployment
                .log_group
            ),
        )[
            "logGroups"
        ]
    )

    assert any(
        (
            group["logGroupName"]
            == aws_deployment.log_group
        )
        for group in log_groups
    )

    images = (
        ecr_client
        .describe_images(
            repositoryName=(
                aws_deployment
                .ecr_repository_name
            ),
            imageIds=[
                {
                    "imageTag": (
                        aws_deployment
                        .image_tag
                    ),
                }
            ],
        )[
            "imageDetails"
        ]
    )

    assert images

    assert (
        images[0]["imageDigest"]
        .startswith(
            "sha256:"
        )
    )