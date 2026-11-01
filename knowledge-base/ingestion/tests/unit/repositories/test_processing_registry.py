from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError

from aws_utils.dynamodb import DynamoDBService

from repositories.processing_registry import (
    ClaimDisposition,
    ProcessingClaim,
    ProcessingClaimLostError,
    ProcessingRegistry,
    ProcessingRegistryError,
    ProcessingRegistryWriteError,
)


pytestmark = [
    pytest.mark.unit,
    pytest.mark.local,
]


def build_dynamodb_service() -> MagicMock:
    service = MagicMock(spec=DynamoDBService)

    service.update_item.return_value = {
        "Attributes": {
            "ingestion_id": {
                "S": "ingestion-123",
            },
            "attempt_count": {
                "N": "1",
            },
        },
    }

    return service


def test_acquire_claim_aliases_reserved_ttl_attribute() -> None:
    dynamodb_service = build_dynamodb_service()

    registry = ProcessingRegistry(
        table_name="processing-registry",
        lease_seconds=900,
        record_ttl_days=90,
        dynamodb_service=dynamodb_service,
        clock=lambda: 1_700_000_000,
    )

    result = registry.acquire_claim(
        ingestion_id="ingestion-123",
        document_id="document-123",
        ingestion_profile_id="profile-123",
        manifest_bucket="canonical-bucket",
        manifest_key=(
            "canonical-documents/"
            "document-123/"
            "_SUCCESS.json"
        ),
        manifest_version_id="version-123",
    )

    assert result.disposition is ClaimDisposition.ACQUIRED
    assert result.claim is not None
    assert result.claim.ingestion_id == "ingestion-123"
    assert result.claim.attempt_count == 1

    update_call = (
        dynamodb_service
        .update_item
        .call_args
        .kwargs
    )

    update_expression = update_call[
        "update_expression"
    ]
    expression_attribute_names = update_call[
        "expression_attribute_names"
    ]
    expression_attribute_values = update_call[
        "expression_attribute_values"
    ]

    assert "#ttl = :ttl" in update_expression
    assert expression_attribute_names[
        "#ttl"
    ] == "ttl"

    expression_without_alias = (
        update_expression.replace(
            "#ttl = :ttl",
            "",
        )
    )

    assert "ttl = :ttl" not in (
        expression_without_alias
    )

    assert expression_attribute_values[
        ":ttl"
    ] == {
        "N": str(
            1_700_000_000
            + 90 * 86_400
        ),
    }


def test_acquire_claim_uses_status_alias() -> None:
    dynamodb_service = build_dynamodb_service()

    registry = ProcessingRegistry(
        table_name="processing-registry",
        lease_seconds=900,
        record_ttl_days=90,
        dynamodb_service=dynamodb_service,
        clock=lambda: 1_700_000_000,
    )

    registry.acquire_claim(
        ingestion_id="ingestion-123",
        document_id="document-123",
        ingestion_profile_id="profile-123",
        manifest_bucket="canonical-bucket",
        manifest_key=(
            "canonical-documents/"
            "document-123/"
            "_SUCCESS.json"
        ),
        manifest_version_id=None,
    )

    update_call = (
        dynamodb_service
        .update_item
        .call_args
        .kwargs
    )

    assert update_call[
        "expression_attribute_names"
    ] == {
        "#status": "status",
        "#ttl": "ttl",
    }

    assert (
        "#status = :processing"
        in update_call[
            "update_expression"
        ]
    )

    assert (
        "#status = :failed"
        in update_call[
            "condition_expression"
        ]
    )


def test_acquire_claim_removes_manifest_version_when_absent() -> None:
    dynamodb_service = build_dynamodb_service()

    registry = ProcessingRegistry(
        table_name="processing-registry",
        lease_seconds=900,
        record_ttl_days=90,
        dynamodb_service=dynamodb_service,
        clock=lambda: 1_700_000_000,
    )

    registry.acquire_claim(
        ingestion_id="ingestion-123",
        document_id="document-123",
        ingestion_profile_id="profile-123",
        manifest_bucket="canonical-bucket",
        manifest_key=(
            "canonical-documents/"
            "document-123/"
            "_SUCCESS.json"
        ),
        manifest_version_id=None,
    )

    update_call = (
        dynamodb_service
        .update_item
        .call_args
        .kwargs
    )

    update_expression = update_call[
        "update_expression"
    ]

    assert "REMOVE" in update_expression
    assert (
        "manifest_version_id"
        in update_expression
    )

    assert (
        ":manifest_version_id"
        not in update_call[
            "expression_attribute_values"
        ]
    )

def test_renew_claim_uses_only_referenced_attribute_names() -> None:
    dynamodb_service = build_dynamodb_service()

    registry = ProcessingRegistry(
        table_name="processing-registry",
        lease_seconds=900,
        record_ttl_days=90,
        dynamodb_service=dynamodb_service,
        clock=lambda: 1_700_000_000,
    )

    claim = ProcessingClaim(
        ingestion_id="ingestion-123",
        owner_token="owner-token-123",
        attempt_count=1,
        claimed_at="2023-11-14T22:13:20+00:00",
        lease_expires_at=1_700_000_900,
    )

    renewed_expiry = registry.renew_claim(
        claim,
    )

    assert renewed_expiry == 1_700_000_900

    update_call = (
        dynamodb_service
        .update_item
        .call_args
        .kwargs
    )

    update_expression = update_call[
        "update_expression"
    ]

    condition_expression = update_call[
        "condition_expression"
    ]

    expression_attribute_names = update_call[
        "expression_attribute_names"
    ]

    assert expression_attribute_names == {
        "#status": "status",
    }

    assert (
        "#status = :processing"
        in condition_expression
    )

    assert "#ttl" not in update_expression
    assert "#ttl" not in condition_expression
    assert "#ttl" not in expression_attribute_names




def make_client_error(code: str = "ConditionalCheckFailedException") -> ClientError:
    return ClientError(
        {"Error": {"Code": code, "Message": "failure"}},
        "UpdateItem",
    )


def make_claim() -> ProcessingClaim:
    return ProcessingClaim(
        ingestion_id="ingestion-123",
        owner_token="owner-token-123",
        attempt_count=1,
        claimed_at="2023-11-14T22:13:20+00:00",
        lease_expires_at=1_700_000_900,
    )


def make_registry(service=None) -> ProcessingRegistry:
    return ProcessingRegistry(
        table_name=" processing-registry ",
        lease_seconds=900,
        record_ttl_days=90,
        dynamodb_service=service or build_dynamodb_service(),
        clock=lambda: 1_700_000_000.9,
    )


@pytest.mark.parametrize(
    ("kwargs", "exception"),
    [
        ({"table_name": 1}, TypeError),
        ({"table_name": "  "}, ValueError),
        ({"lease_seconds": True}, TypeError),
        ({"lease_seconds": 0}, ValueError),
        ({"record_ttl_days": 1.2}, TypeError),
        ({"record_ttl_days": -1}, ValueError),
        ({"dynamodb_service": object()}, TypeError),
    ],
)
def test_constructor_validation(kwargs, exception) -> None:
    values = {
        "table_name": "table",
        "lease_seconds": 1,
        "record_ttl_days": 1,
        "dynamodb_service": build_dynamodb_service(),
        "clock": lambda: 1,
    }
    values.update(kwargs)
    with pytest.raises(exception):
        ProcessingRegistry(**values)


def test_constructor_uses_default_service_and_clock() -> None:
    with patch("repositories.processing_registry.DynamoDBService") as service_type, patch(
        "repositories.processing_registry.time.time", return_value=7.9
    ):
        service = service_type.return_value
        registry = ProcessingRegistry(table_name="table", lease_seconds=1, record_ttl_days=1)
        assert registry.dynamodb_service is service
        assert registry._now_epoch() == 7


def invoke_acquire(registry: ProcessingRegistry):
    return registry.acquire_claim(
        ingestion_id=" ingestion-123 ",
        document_id=" document-123 ",
        ingestion_profile_id=" profile-123 ",
        manifest_bucket=" canonical-bucket ",
        manifest_key=" canonical-documents/document-123/_SUCCESS.json ",
        manifest_version_id=" version-123 ",
    )


@pytest.mark.parametrize(
    ("existing", "disposition"),
    [
        ({"status": "COMPLETED"}, ClaimDisposition.COMPLETED),
        ({"status": "PROCESSING"}, ClaimDisposition.UNAVAILABLE),
        (None, ClaimDisposition.UNAVAILABLE),
    ],
)
def test_acquire_claim_handles_conditional_contention(existing, disposition) -> None:
    service = build_dynamodb_service()
    service.update_item.side_effect = make_client_error()
    registry = make_registry(service)
    registry.get_record = MagicMock(return_value=existing)
    result = invoke_acquire(registry)
    assert result.disposition is disposition
    assert result.existing_record == existing


@pytest.mark.parametrize(
    "exception",
    [
        make_client_error("ValidationException"),
        EndpointConnectionError(endpoint_url="http://dynamodb"),
    ],
)
def test_acquire_claim_translates_transport_errors(exception) -> None:
    service = build_dynamodb_service()
    service.update_item.side_effect = exception
    with pytest.raises(ProcessingRegistryWriteError, match="could not be acquired"):
        invoke_acquire(make_registry(service))


@pytest.mark.parametrize("attributes", [{}, {"attempt_count": {"N": "0"}}, {"attempt_count": {"S": "1"}}])
def test_acquire_claim_rejects_invalid_attempt_count(attributes) -> None:
    service = build_dynamodb_service()
    service.update_item.return_value = {"Attributes": attributes}
    with pytest.raises(ProcessingRegistryWriteError, match="valid attempt_count"):
        invoke_acquire(make_registry(service))


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (None, None),
        ({"status": {"S": "COMPLETED"}, "attempt_count": {"N": "2"}}, {"status": "COMPLETED", "attempt_count": 2}),
    ],
)
def test_get_record_handles_present_and_missing_items(response, expected) -> None:
    service = build_dynamodb_service()
    service.get_item.return_value = response
    assert make_registry(service).get_record(" ingestion-123 ") == expected


@pytest.mark.parametrize(
    "exception",
    [make_client_error("ValidationException"), EndpointConnectionError(endpoint_url="http://dynamodb")],
)
def test_get_record_translates_errors(exception) -> None:
    service = build_dynamodb_service()
    service.get_item.side_effect = exception
    with pytest.raises(ProcessingRegistryError, match="could not be read"):
        make_registry(service).get_record("ingestion-123")


def test_mark_completed_writes_all_fields_with_version() -> None:
    service = build_dynamodb_service()
    registry = make_registry(service)
    registry.mark_completed(
        make_claim(),
        index_destination=" opensearch://index ",
        index_record_count=4,
        chunk_count=3,
        success_manifest_bucket=" bucket ",
        success_manifest_key=" result/_SUCCESS.json ",
        success_manifest_version_id=" version-1 ",
    )
    call = service.update_item.call_args.kwargs
    assert "success_manifest_version_id = :manifest_version_id" in call["update_expression"]
    assert call["expression_attribute_values"][":record_count"] == {"N": "4"}
    assert call["expression_attribute_values"][":chunk_count"] == {"N": "3"}
    assert call["expression_attribute_values"][":manifest_version_id"] == {"S": "version-1"}


def test_mark_completed_removes_absent_manifest_version() -> None:
    service = build_dynamodb_service()
    make_registry(service).mark_completed(
        make_claim(),
        index_destination="opensearch://index",
        index_record_count=0,
        chunk_count=0,
        success_manifest_bucket="bucket",
        success_manifest_key="result/_SUCCESS.json",
    )
    call = service.update_item.call_args.kwargs
    assert "success_manifest_version_id" in call["update_expression"]
    assert ":manifest_version_id" not in call["expression_attribute_values"]


@pytest.mark.parametrize(
    ("field", "value", "exception"),
    [
        ("index_destination", 1, TypeError),
        ("index_destination", " ", ValueError),
        ("success_manifest_bucket", " ", ValueError),
        ("success_manifest_key", None, TypeError),
        ("success_manifest_version_id", 3, TypeError),
        ("success_manifest_version_id", " ", ValueError),
        ("index_record_count", True, TypeError),
        ("index_record_count", -1, ValueError),
        ("chunk_count", 1.2, TypeError),
        ("chunk_count", -1, ValueError),
    ],
)
def test_mark_completed_validates_inputs(field, value, exception) -> None:
    values = dict(
        index_destination="opensearch://index",
        index_record_count=1,
        chunk_count=1,
        success_manifest_bucket="bucket",
        success_manifest_key="result/_SUCCESS.json",
        success_manifest_version_id=None,
    )
    values[field] = value
    with pytest.raises(exception):
        make_registry().mark_completed(make_claim(), **values)


def test_mark_failed_writes_terminal_fields() -> None:
    service = build_dynamodb_service()
    make_registry(service).mark_failed(
        make_claim(), error_type=" PermanentError ", error_message=" failed permanently "
    )
    call = service.update_item.call_args.kwargs
    assert "#status = :failed" in call["update_expression"]
    assert call["expression_attribute_values"][":error_type"] == {"S": "PermanentError"}
    assert call["expression_attribute_values"][":error_message"] == {"S": "failed permanently"}


@pytest.mark.parametrize(
    ("error_type", "error_message", "exception"),
    [(1, "message", TypeError), (" ", "message", ValueError), ("Error", None, TypeError), ("Error", " ", ValueError)],
)
def test_mark_failed_validates_inputs(error_type, error_message, exception) -> None:
    with pytest.raises(exception):
        make_registry().mark_failed(make_claim(), error_type=error_type, error_message=error_message)


@pytest.mark.parametrize(
    ("exception", "expected"),
    [
        (make_client_error(), ProcessingClaimLostError),
        (make_client_error("ValidationException"), ProcessingRegistryWriteError),
        (EndpointConnectionError(endpoint_url="http://dynamodb"), ProcessingRegistryWriteError),
    ],
)
def test_owned_updates_translate_errors(exception, expected) -> None:
    service = build_dynamodb_service()
    service.update_item.side_effect = exception
    with pytest.raises(expected):
        make_registry(service).renew_claim(make_claim())


def test_deserialize_item_supports_all_dynamodb_scalar_shapes() -> None:
    assert ProcessingRegistry._deserialize_item(
        {
            "ignored": "not-a-map",
            "text": {"S": "value"},
            "integer": {"N": "2"},
            "decimal": {"N": "2.5"},
            "flag": {"BOOL": True},
            "nothing": {"NULL": True},
            "raw": {"L": [{"S": "x"}]},
        }
    ) == {
        "text": "value",
        "integer": 2,
        "decimal": 2.5,
        "flag": True,
        "nothing": None,
        "raw": {"L": [{"S": "x"}]},
    }


@pytest.mark.parametrize("claim", [None, object(), "claim"])
def test_claim_methods_reject_invalid_claim(claim) -> None:
    registry = make_registry()
    with pytest.raises(TypeError, match="ProcessingClaim"):
        registry.renew_claim(claim)


@pytest.mark.parametrize(
    ("method", "value", "exception"),
    [
        ("_normalize_required_string", 1, TypeError),
        ("_normalize_required_string", " ", ValueError),
        ("_normalize_optional_string", 1, TypeError),
        ("_normalize_optional_string", " ", ValueError),
        ("_validate_positive_integer", True, TypeError),
        ("_validate_positive_integer", 0, ValueError),
        ("_validate_nonnegative_integer", False, TypeError),
        ("_validate_nonnegative_integer", -1, ValueError),
    ],
)
def test_validation_helpers_cover_invalid_branches(method, value, exception) -> None:
    function = getattr(ProcessingRegistry, method)
    kwargs = {"value": value, "field_name": "field"}
    with pytest.raises(exception):
        function(**kwargs)


def test_optional_string_accepts_none_and_normalizes_text() -> None:
    assert ProcessingRegistry._normalize_optional_string(value=None, field_name="field") is None
    assert ProcessingRegistry._normalize_optional_string(value=" value ", field_name="field") == "value"


def test_conditional_failure_classifier() -> None:
    assert ProcessingRegistry._is_conditional_failure(make_client_error()) is True
    assert ProcessingRegistry._is_conditional_failure(make_client_error("ValidationException")) is False

