from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError

from exceptions.processing_claim import (
    ProcessingClaimLostError,
    ProcessingClaimUnavailableError,
)
from models.document import ClinicalDocument
from repositories import processing_registry
from repositories.processing_registry import (
    ProcessingClaim,
    ProcessingRegistry,
)


pytestmark = pytest.mark.unit


def conditional_failure(operation_name):
    return ClientError(
        {
            "Error": {
                "Code": (
                    "ConditionalCheckFailedException"
                ),
                "Message": "Conditional request failed",
            }
        },
        operation_name,
    )


def service_failure(operation_name):
    return ClientError(
        {
            "Error": {
                "Code": "InternalServerError",
                "Message": "DynamoDB unavailable",
            }
        },
        operation_name,
    )


@pytest.fixture
def dynamodb():
    return Mock()


@pytest.fixture
def registry(dynamodb):
    return ProcessingRegistry(
        table_name="processing-table",
        lease_seconds=900,
        dynamodb_service=dynamodb,
    )


@pytest.fixture
def document():
    return ClinicalDocument(
        document_id="document-123",
        file_name="sample.pdf",
        file_format="pdf",
        source_bucket="raw-bucket",
        source_key=(
            "documents/TEST001/"
            "protocols/sample.pdf"
        ),
        source_version_id="version-1",
        processing_schema_version="extraction-v1",
    )


@pytest.fixture
def claim():
    return ProcessingClaim(
        document_id="document-123",
        owner_token="owner-token-123",
        lease_expires_at=1900,
    )


def test_constructor_rejects_empty_table_name():
    with pytest.raises(
        ValueError,
        match="table name must not be empty",
    ):
        ProcessingRegistry(
            table_name="   ",
            lease_seconds=900,
            dynamodb_service=Mock(),
        )


@pytest.mark.parametrize(
    "lease_seconds",
    [
        0,
        -1,
        -900,
    ],
)
def test_constructor_rejects_invalid_lease(
    lease_seconds,
):
    with pytest.raises(
        ValueError,
        match="must be greater than zero",
    ):
        ProcessingRegistry(
            table_name="processing-table",
            lease_seconds=lease_seconds,
            dynamodb_service=Mock(),
        )


def test_constructor_stores_dependencies(
    dynamodb,
):
    registry = ProcessingRegistry(
        table_name="processing-table",
        lease_seconds=900,
        dynamodb_service=dynamodb,
    )

    assert registry.table_name == (
        "processing-table"
    )
    assert registry.lease_seconds == 900
    assert registry.dynamodb is dynamodb


def test_key_builds_dynamodb_primary_key(
    registry,
):
    assert registry._key(
        "document-123"
    ) == {
        "document_id": {
            "S": "document-123",
        }
    }


def test_conditional_failure_is_detected(
    registry,
):
    exception = conditional_failure(
        "PutItem"
    )

    assert (
        registry._is_conditional_failure(
            exception
        )
        is True
    )


def test_nonconditional_failure_is_not_detected(
    registry,
):
    exception = service_failure(
        "PutItem"
    )

    assert (
        registry._is_conditional_failure(
            exception
        )
        is False
    )


def test_acquire_creates_processing_claim(
    monkeypatch,
    registry,
    dynamodb,
    document,
):
    monkeypatch.setattr(
        processing_registry.time,
        "time",
        lambda: 1000,
    )
    monkeypatch.setattr(
        processing_registry,
        "uuid4",
        lambda: "owner-token-123",
    )

    claim = registry.acquire(
        document
    )

    assert claim == ProcessingClaim(
        document_id="document-123",
        owner_token="owner-token-123",
        lease_expires_at=1900,
    )

    dynamodb.put_item.assert_called_once_with(
        table_name="processing-table",
        item={
            "document_id": {
                "S": "document-123",
            },
            "owner_token": {
                "S": "owner-token-123",
            },
            "status": {
                "S": "PROCESSING",
            },
            "source_bucket": {
                "S": "raw-bucket",
            },
            "source_key": {
                "S": (
                    "documents/TEST001/"
                    "protocols/sample.pdf"
                ),
            },
            "source_version_id": {
                "S": "version-1",
            },
            "processing_schema_version": {
                "S": "extraction-v1",
            },
            "claimed_at": {
                "N": "1000",
            },
            "updated_at": {
                "N": "1000",
            },
            "lease_expires_at": {
                "N": "1900",
            },
            "ttl": {
                "N": "88300",
            },
        },
        condition_expression=(
            "attribute_not_exists("
            "#document_id"
            ") OR "
            "#lease_expires_at < :now"
        ),
        expression_attribute_names={
            "#document_id": "document_id",
            "#lease_expires_at": (
                "lease_expires_at"
            ),
        },
        expression_attribute_values={
            ":now": {
                "N": "1000",
            }
        },
    )


def test_acquire_translates_conditional_failure(
    registry,
    dynamodb,
    document,
):
    dynamodb.put_item.side_effect = (
        conditional_failure(
            "PutItem"
        )
    )

    with pytest.raises(
        ProcessingClaimUnavailableError,
        match="different worker owns",
    ):
        registry.acquire(
            document
        )


def test_acquire_propagates_unexpected_failure(
    registry,
    dynamodb,
    document,
):
    dynamodb.put_item.side_effect = (
        service_failure(
            "PutItem"
        )
    )

    with pytest.raises(
        ClientError,
    ):
        registry.acquire(
            document
        )


def test_renew_extends_owned_claim(
    monkeypatch,
    registry,
    dynamodb,
    claim,
):
    monkeypatch.setattr(
        processing_registry.time,
        "time",
        lambda: 1100,
    )

    renewed = registry.renew(
        claim
    )

    assert renewed == ProcessingClaim(
        document_id="document-123",
        owner_token="owner-token-123",
        lease_expires_at=2000,
    )

    dynamodb.update_item.assert_called_once_with(
        table_name="processing-table",
        key={
            "document_id": {
                "S": "document-123",
            }
        },
        update_expression=(
            "SET #lease_expires_at = "
            ":lease_expires_at, "
            "#updated_at = :now, "
            "#ttl = :ttl"
        ),
        condition_expression=(
            "#owner_token = :owner_token "
            "AND #status = :processing "
            "AND #lease_expires_at >= :now"
        ),
        expression_attribute_names={
            "#owner_token": "owner_token",
            "#status": "status",
            "#lease_expires_at": (
                "lease_expires_at"
            ),
            "#updated_at": "updated_at",
            "#ttl": "ttl",
        },
        expression_attribute_values={
            ":owner_token": {
                "S": "owner-token-123",
            },
            ":processing": {
                "S": "PROCESSING",
            },
            ":lease_expires_at": {
                "N": "2000",
            },
            ":now": {
                "N": "1100",
            },
            ":ttl": {
                "N": "88400",
            },
        },
    )


def test_renew_translates_conditional_failure(
    registry,
    dynamodb,
    claim,
):
    dynamodb.update_item.side_effect = (
        conditional_failure(
            "UpdateItem"
        )
    )

    with pytest.raises(
        ProcessingClaimLostError,
        match="ownership was lost",
    ):
        registry.renew(
            claim
        )


def test_renew_propagates_unexpected_failure(
    registry,
    dynamodb,
    claim,
):
    dynamodb.update_item.side_effect = (
        service_failure(
            "UpdateItem"
        )
    )

    with pytest.raises(
        ClientError,
    ):
        registry.renew(
            claim
        )


def test_mark_completed_updates_registry(
    monkeypatch,
    registry,
    dynamodb,
    claim,
):
    monkeypatch.setattr(
        processing_registry.time,
        "time",
        lambda: 1200,
    )

    registry.mark_completed(
        claim=claim,
        canonical_key=(
            "canonical-documents/"
            "document-123/"
            "extracted-document.json"
        ),
    )

    dynamodb.update_item.assert_called_once_with(
        table_name="processing-table",
        key={
            "document_id": {
                "S": "document-123",
            }
        },
        update_expression=(
            "SET #status = :completed, "
            "#canonical_key = :canonical_key, "
            "#updated_at = :now, "
            "#completed_at = :now, "
            "#ttl = :ttl "
            "REMOVE #lease_expires_at"
        ),
        condition_expression=(
            "#owner_token = :owner_token "
            "AND #status = :processing "
            "AND #lease_expires_at >= :now"
        ),
        expression_attribute_names={
            "#status": "status",
            "#owner_token": "owner_token",
            "#canonical_key": "canonical_key",
            "#updated_at": "updated_at",
            "#completed_at": "completed_at",
            "#ttl": "ttl",
            "#lease_expires_at": (
                "lease_expires_at"
            ),
        },
        expression_attribute_values={
            ":completed": {
                "S": "COMPLETED",
            },
            ":processing": {
                "S": "PROCESSING",
            },
            ":owner_token": {
                "S": "owner-token-123",
            },
            ":canonical_key": {
                "S": (
                    "canonical-documents/"
                    "document-123/"
                    "extracted-document.json"
                ),
            },
            ":now": {
                "N": "1200",
            },
            ":ttl": {
                "N": "2593200",
            },
        },
    )


def test_mark_completed_translates_conditional_failure(
    registry,
    dynamodb,
    claim,
):
    dynamodb.update_item.side_effect = (
        conditional_failure(
            "UpdateItem"
        )
    )

    with pytest.raises(
        ProcessingClaimLostError,
        match="before completion",
    ):
        registry.mark_completed(
            claim=claim,
            canonical_key="canonical-key",
        )


def test_mark_completed_propagates_unexpected_failure(
    registry,
    dynamodb,
    claim,
):
    dynamodb.update_item.side_effect = (
        service_failure(
            "UpdateItem"
        )
    )

    with pytest.raises(
        ClientError,
    ):
        registry.mark_completed(
            claim=claim,
            canonical_key="canonical-key",
        )


def test_release_deletes_owned_processing_claim(
    registry,
    dynamodb,
    claim,
):
    registry.release(
        claim
    )

    dynamodb.delete_item.assert_called_once_with(
        table_name="processing-table",
        key={
            "document_id": {
                "S": "document-123",
            }
        },
        condition_expression=(
            "#owner_token = :owner_token "
            "AND #status = :processing"
        ),
        expression_attribute_names={
            "#owner_token": "owner_token",
            "#status": "status",
        },
        expression_attribute_values={
            ":owner_token": {
                "S": "owner-token-123",
            },
            ":processing": {
                "S": "PROCESSING",
            },
        },
    )


def test_release_ignores_conditional_failure(
    registry,
    dynamodb,
    claim,
):
    dynamodb.delete_item.side_effect = (
        conditional_failure(
            "DeleteItem"
        )
    )

    registry.release(
        claim
    )


def test_release_propagates_unexpected_failure(
    registry,
    dynamodb,
    claim,
):
    dynamodb.delete_item.side_effect = (
        service_failure(
            "DeleteItem"
        )
    )

    with pytest.raises(
        ClientError,
    ):
        registry.release(
            claim
        )