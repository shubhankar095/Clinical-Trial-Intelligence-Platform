import pytest
pytestmark = [pytest.mark.smoke, pytest.mark.aws]


def test_deployed_resources_are_accessible(deployed_ingestion_environment):
    deployment = deployed_ingestion_environment
    deployment.client("s3").head_bucket(Bucket=deployment.canonical_bucket)
    table = deployment.client("dynamodb").describe_table(
        TableName=deployment.registry_table
    )["Table"]
    assert table["TableStatus"] == "ACTIVE"
    service = deployment.client("ecs").describe_services(
        cluster=deployment.ecs_cluster,
        services=[deployment.ecs_service],
    )["services"][0]
    assert service["status"] == "ACTIVE"
    collection = deployment.client("opensearchserverless").batch_get_collection(
        names=[deployment.collection_name]
    )["collectionDetails"][0]
    assert collection["status"] == "ACTIVE"
    assert deployment.client("logs").describe_log_groups(
        logGroupNamePrefix=deployment.log_group
    )["logGroups"]
    repository_name = deployment.ecr_repository_url.rsplit("/", 1)[-1]
    assert deployment.client("ecr").describe_images(
        repositoryName=repository_name
    )["imageDetails"]

########################################################################
