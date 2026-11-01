import pytest

from config import config
from test_config import _set_valid_runtime_config


pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("true", True), (" FALSE ", False)],
)
def test_boolean_parses_supported_values(monkeypatch, raw, expected):
    monkeypatch.setenv("DAVV_BOOLEAN", raw)
    assert config._boolean("DAVV_BOOLEAN", "true") is expected


def test_boolean_rejects_unsupported_text(monkeypatch):
    monkeypatch.setenv("DAVV_BOOLEAN", "yes")
    with pytest.raises(RuntimeError, match="DAVV_BOOLEAN"):
        config._boolean("DAVV_BOOLEAN", "false")


def test_integer_rejects_invalid_text(monkeypatch):
    monkeypatch.setenv("DAVV_INTEGER", "1.5")
    with pytest.raises(RuntimeError, match="DAVV_INTEGER"):
        config._integer("DAVV_INTEGER", "1")


@pytest.mark.parametrize(
    "raw",
    ["{", "[]"],
)
def test_json_object_rejects_invalid_values(monkeypatch, raw):
    monkeypatch.setenv("DAVV_JSON", raw)
    with pytest.raises(RuntimeError, match="DAVV_JSON"):
        config._json_object("DAVV_JSON")


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://example.test",
        "https://",
        "https://example.test?query=1",
        "https://example.test#fragment",
    ],
)
def test_https_rejects_invalid_endpoint_shapes(endpoint):
    with pytest.raises(RuntimeError, match="ENDPOINT"):
        config._https(endpoint, "ENDPOINT", allow_host_only=True)


def test_https_supports_host_only_and_rejects_host_only_when_disabled():
    config._https("search.example.test", "ENDPOINT", allow_host_only=True)
    with pytest.raises(RuntimeError, match="ENDPOINT"):
        config._https("search.example.test", "ENDPOINT")


@pytest.mark.parametrize("value", [0, -1])
def test_positive_integer_rejects_nonpositive_values(value):
    with pytest.raises(RuntimeError):
        config._positive(value, "FIELD")


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("environment", "", "Missing required"),
        ("environment", "unknown", "ENVIRONMENT"),
        ("embedding_provider", "unknown", "EMBEDDING_PROVIDER"),
        ("environment", "prod", "Production requires"),
        ("huggingface_api_token", "", "HUGGINGFACE_API_TOKEN"),
        ("huggingface_api_base_url", "http://bad", "HUGGINGFACE_API_BASE_URL"),
        ("opensearch_endpoint", "http://bad", "OPENSEARCH_ENDPOINT"),
        ("opensearch_deployment_type", "unknown", "OPENSEARCH_DEPLOYMENT_TYPE"),
        ("ingestion_queue_url", "http://queue.test", "INGESTION_QUEUE_URL"),
        ("sqs_wait_time_seconds", 21, "SQS_WAIT_TIME_SECONDS"),
        ("sqs_visibility_heartbeat_seconds", 600, "SQS heartbeat"),
        ("processing_claim_heartbeat_seconds", 900, "Claim heartbeat"),
        ("chunk_overlap", -1, "CHUNK_OVERLAP"),
        ("chunk_size", 0, "CHUNK_SIZE"),
        ("embedding_dimensions", 0, "EMBEDDING_DIMENSIONS"),
        ("opensearch_bulk_max_records", 0, "OPENSEARCH_BULK_MAX_RECORDS"),
    ],
)
def test_validate_runtime_config_rejects_invalid_values(
    monkeypatch,
    field,
    value,
    message,
):
    _set_valid_runtime_config(monkeypatch)
    if (
        (field == "environment" and value == "prod")
        or field in {"huggingface_api_token", "huggingface_api_base_url"}
    ):
        monkeypatch.setattr(
            config,
            "embedding_provider",
            config.HUGGINGFACE_API_EMBEDDING_PROVIDER,
        )
    if field == "huggingface_api_base_url":
        monkeypatch.setattr(config, "huggingface_api_token", "test-token")
    monkeypatch.setattr(config, field, value)
    with pytest.raises(RuntimeError, match=message):
        config.validate_runtime_config()


def test_validate_runtime_config_accepts_production_bedrock(monkeypatch):
    _set_valid_runtime_config(monkeypatch)
    monkeypatch.setattr(config, "environment", "prod")
    monkeypatch.setattr(config, "embedding_provider", config.BEDROCK_EMBEDDING_PROVIDER)
    config.validate_runtime_config()


def test_validate_runtime_config_accepts_domain_deployment(monkeypatch):
    _set_valid_runtime_config(monkeypatch)
    monkeypatch.setattr(config, "opensearch_deployment_type", "domain")
    monkeypatch.setattr(config, "embedding_provider", config.BEDROCK_EMBEDDING_PROVIDER)
    config.validate_runtime_config()


def test_validate_runtime_config_checks_huggingface_positive_settings(monkeypatch):
    _set_valid_runtime_config(monkeypatch)
    monkeypatch.setattr(
        config,
        "embedding_provider",
        config.HUGGINGFACE_API_EMBEDDING_PROVIDER,
    )
    monkeypatch.setattr(config, "huggingface_api_token", "test-token")
    config.validate_runtime_config()
