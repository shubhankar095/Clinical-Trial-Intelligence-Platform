from __future__ import annotations
import os
import pytest
from .support.cleanup import cleanup_fixture
from .support.deployment import AwsDeployment
from .support.fixture_factory import publish_fixture


@pytest.fixture(scope="session")
def deployed_ingestion_environment():
    if os.getenv("RUN_AWS_TESTS") != "1":
        pytest.fail("AWS tests require RUN_AWS_TESTS=1")
    deployment = AwsDeployment.load()
    if deployment.environment != "dev":
        pytest.fail(f"Deployed AWS tests are restricted to dev; received {deployment.environment!r}")
    account = deployment.client("sts").get_caller_identity()["Account"]
    if account != deployment.account_id:
        pytest.fail(f"AWS account mismatch: expected={deployment.account_id}, actual={account}")
    return deployment


@pytest.fixture
def published_fixture(deployed_ingestion_environment):
    fixture = publish_fixture(deployed_ingestion_environment)
    try:
        yield fixture
    finally:
        cleanup_fixture(deployed_ingestion_environment, fixture)


@pytest.fixture
def invalid_published_fixture(deployed_ingestion_environment):
    fixture = publish_fixture(deployed_ingestion_environment, invalid=True)
    try:
        yield fixture
    finally:
        cleanup_fixture(deployed_ingestion_environment, fixture)


@pytest.fixture(scope="session")
def require_destructive_aws_tests():
    if os.getenv("RUN_DESTRUCTIVE_AWS_TESTS") != "1":
        pytest.fail("Set RUN_DESTRUCTIVE_AWS_TESTS=1")
