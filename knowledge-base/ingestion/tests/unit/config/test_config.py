import math
import pytest
from config import config

pytestmark = pytest.mark.unit


def _set_valid_runtime_config(monkeypatch):
    values = {
        "environment": "dev",
        "aws_region": "ap-south-1",
        "ingestion_queue_url": "https://sqs.ap-south-1.amazonaws.com/123/queue",
        "canonical_document_bucket": "canonical",
        "processing_registry_table": "registry",
        "ingestion_result_bucket": "results",
        "ingestion_result_prefix": "ingestion-results",
        "embedding_model_id": "sentence-transformers/all-MiniLM-L6-v2",
        "embedding_provider": config.BEDROCK_EMBEDDING_PROVIDER,
        "opensearch_endpoint": "https://example.test",
        "opensearch_region": "ap-south-1",
        "opensearch_deployment_type": "serverless",
        "opensearch_visibility_timeout_seconds": 60.0,
        "opensearch_visibility_poll_seconds": 1.0,
        "sqs_wait_time_seconds": 20,
        "sqs_visibility_timeout_seconds": 600,
        "sqs_visibility_heartbeat_seconds": 180,
        "sqs_visibility_extension_seconds": 600,
        "processing_claim_lease_seconds": 900,
        "processing_claim_heartbeat_seconds": 180,
        "processing_record_ttl_days": 30,
        "chunk_size": 1000,
        "chunk_overlap": 100,
        "embedding_dimensions": 384,
        "opensearch_bulk_max_records": 250,
        "opensearch_bulk_max_bytes": 5_242_880,
        "opensearch_bulk_max_attempts": 3,
    }

    for name, value in values.items():
        monkeypatch.setattr(config, name, value)


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("60", 60.0),
        (" 0.5 ", 0.5),
        ("1e1", 10.0),
    ],
)
def test_number_parses_finite_values(monkeypatch, raw_value, expected):
    monkeypatch.setenv("DAVV_NUMBER", raw_value)

    assert config._number("DAVV_NUMBER", "1") == expected


def test_number_uses_default_when_environment_is_missing(monkeypatch):
    monkeypatch.delenv("DAVV_NUMBER", raising=False)

    assert config._number("DAVV_NUMBER", "2.5") == 2.5


def test_number_rejects_invalid_text(monkeypatch):
    monkeypatch.setenv("DAVV_NUMBER", "not-a-number")

    with pytest.raises(RuntimeError, match="valid number"):
        config._number("DAVV_NUMBER", "1")


@pytest.mark.parametrize(
    "raw_value",
    [
        "nan",
        "inf",
        "+inf",
        "-inf",
    ],
)
def test_number_rejects_nonfinite_values(monkeypatch, raw_value):
    monkeypatch.setenv("DAVV_NUMBER", raw_value)

    with pytest.raises(RuntimeError, match="finite number"):
        config._number("DAVV_NUMBER", "1")


@pytest.mark.parametrize(
    "value",
    [
        1,
        0.5,
        60.0,
    ],
)
def test_positive_number_accepts_positive_finite_values(value):
    config._positive_number(value, "DAVV_VALUE")


@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
        "1",
        None,
        0,
        -1,
        math.nan,
        math.inf,
        -math.inf,
    ],
)
def test_positive_number_rejects_invalid_values(value):
    with pytest.raises(RuntimeError, match="positive finite number"):
        config._positive_number(value, "DAVV_VALUE")


def test_validate_runtime_config_accepts_davv_values(monkeypatch):
    _set_valid_runtime_config(monkeypatch)

    config.validate_runtime_config()


def test_validate_runtime_config_accepts_poll_equal_to_timeout(monkeypatch):
    _set_valid_runtime_config(monkeypatch)
    monkeypatch.setattr(config, "opensearch_visibility_timeout_seconds", 1.0)
    monkeypatch.setattr(config, "opensearch_visibility_poll_seconds", 1.0)

    config.validate_runtime_config()


@pytest.mark.parametrize(
    ("field", "value", "environment_name"),
    [
        (
            "opensearch_visibility_timeout_seconds",
            0,
            "OPENSEARCH_VISIBILITY_TIMEOUT_SECONDS",
        ),
        (
            "opensearch_visibility_timeout_seconds",
            math.inf,
            "OPENSEARCH_VISIBILITY_TIMEOUT_SECONDS",
        ),
        (
            "opensearch_visibility_poll_seconds",
            -1,
            "OPENSEARCH_VISIBILITY_POLL_SECONDS",
        ),
        (
            "opensearch_visibility_poll_seconds",
            math.nan,
            "OPENSEARCH_VISIBILITY_POLL_SECONDS",
        ),
    ],
)
def test_validate_runtime_config_rejects_invalid_davv_values(
    monkeypatch,
    field,
    value,
    environment_name,
):
    _set_valid_runtime_config(monkeypatch)
    monkeypatch.setattr(config, field, value)

    with pytest.raises(RuntimeError, match=environment_name):
        config.validate_runtime_config()


def test_validate_runtime_config_rejects_poll_above_timeout(monkeypatch):
    _set_valid_runtime_config(monkeypatch)
    monkeypatch.setattr(config, "opensearch_visibility_timeout_seconds", 1.0)
    monkeypatch.setattr(config, "opensearch_visibility_poll_seconds", 1.1)

    with pytest.raises(
        RuntimeError,
        match="OPENSEARCH_VISIBILITY_POLL_SECONDS must be less than or equal",
    ):
        config.validate_runtime_config()
