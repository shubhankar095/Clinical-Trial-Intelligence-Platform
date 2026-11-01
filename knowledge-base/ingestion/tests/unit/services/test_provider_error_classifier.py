from types import SimpleNamespace

import pytest
from botocore.exceptions import BotoCoreError, ClientError

from exceptions.processing import (
    IngestionConfigurationError,
    PermanentIngestionError,
    RetryableIngestionError,
)
from services.provider_error_classifier import (
    _status_code,
    raise_classified_provider_error,
)

pytestmark = pytest.mark.unit


def client_error(code: str, status: int) -> ClientError:
    return ClientError(
        {
            "Error": {"Code": code, "Message": "failure"},
            "ResponseMetadata": {"HTTPStatusCode": status},
        },
        "TestOperation",
    )


@pytest.mark.parametrize(
    "error,expected",
    [
        (client_error("AccessDeniedException", 500), IngestionConfigurationError),
        (client_error("Unknown", 403), IngestionConfigurationError),
        (client_error("ThrottlingException", 400), RetryableIngestionError),
        (client_error("Unknown", 503), RetryableIngestionError),
        (client_error("ValidationException", 418), PermanentIngestionError),
        (client_error("Unknown", 422), PermanentIngestionError),
        (client_error("Unknown", 418), RetryableIngestionError),
    ],
)
def test_classifies_aws_client_errors(error, expected):
    with pytest.raises(expected):
        raise_classified_provider_error(error, operation="Embedding")


def test_preserves_existing_ingestion_error():
    error = PermanentIngestionError("already classified")
    with pytest.raises(PermanentIngestionError) as raised:
        raise_classified_provider_error(error, operation="Embedding")
    assert raised.value is error


def test_classifies_botocore_transport_error():
    error = BotoCoreError()
    with pytest.raises(RetryableIngestionError):
        raise_classified_provider_error(error, operation="Embedding")


@pytest.mark.parametrize(
    "status,expected",
    [
        (401, IngestionConfigurationError),
        (429, RetryableIngestionError),
        (404, PermanentIngestionError),
    ],
)
def test_classifies_provider_http_status(status, expected):
    error = RuntimeError("provider failure")
    error.status_code = status
    with pytest.raises(expected):
        raise_classified_provider_error(error, operation="Embedding")


@pytest.mark.parametrize("message", ["request timeout", "connection reset", "throttled", "too many requests"])
def test_classifies_temporary_messages(message):
    with pytest.raises(RetryableIngestionError):
        raise_classified_provider_error(RuntimeError(message), operation="Embedding")


@pytest.mark.parametrize("message", ["unauthorized", "forbidden", "access denied", "bad signature", "credential missing"])
def test_classifies_configuration_messages(message):
    with pytest.raises(IngestionConfigurationError):
        raise_classified_provider_error(RuntimeError(message), operation="Embedding")


def test_unclassified_provider_error_is_retryable():
    with pytest.raises(RetryableIngestionError):
        raise_classified_provider_error(RuntimeError("other"), operation="Embedding")


@pytest.mark.parametrize(
    "error,expected",
    [
        (SimpleNamespace(status_code=201), 201),
        (SimpleNamespace(status=202), 202),
        (SimpleNamespace(info={"status": 203}), 203),
        (SimpleNamespace(status_code=True, info={}), None),
        (SimpleNamespace(), None),
    ],
)
def test_status_code_resolution(error, expected):
    assert _status_code(error) == expected
