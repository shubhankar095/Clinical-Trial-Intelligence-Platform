import json
import os
import math
from typing import Any
from urllib.parse import urlparse

HUGGINGFACE_API_EMBEDDING_PROVIDER = "huggingface-api"
BEDROCK_EMBEDDING_PROVIDER = "bedrock"
SUPPORTED_EMBEDDING_PROVIDERS = frozenset({HUGGINGFACE_API_EMBEDDING_PROVIDER, BEDROCK_EMBEDDING_PROVIDER})
SUPPORTED_ENVIRONMENTS = frozenset({"dev", "uat", "stage", "prod"})
SUPPORTED_OPENSEARCH_DEPLOYMENTS = frozenset({"serverless", "domain"})


def _integer(name: str, default: str) -> int:
    try:
        return int(os.getenv(name, default).strip())
    except ValueError as exception:
        raise RuntimeError(f"{name} must contain a valid integer.") from exception

def _number(name: str, default: str) -> float:
    raw_value = os.getenv(name, default).strip()

    try:
        value = float(raw_value)
    except ValueError as exception:
        raise RuntimeError(f"{name} must contain a valid number.") from exception

    if not math.isfinite(value):
        raise RuntimeError(f"{name} must contain a finite number.")

    return value

def _boolean(name: str, default: str) -> bool:
    value = os.getenv(name, default).strip().lower()
    if value not in {"true", "false"}:
        raise RuntimeError(f"{name} must be 'true' or 'false'.")
    return value == "true"


def _json_object(name: str, default: str = "{}") -> dict[str, Any]:
    try:
        value = json.loads(os.getenv(name, default).strip())
    except json.JSONDecodeError as exception:
        raise RuntimeError(f"{name} must contain valid JSON.") from exception
    if not isinstance(value, dict):
        raise RuntimeError(f"{name} must contain a JSON object.")
    return value


environment = os.getenv("ENVIRONMENT", "dev").strip().lower()
aws_region = os.getenv("AWS_REGION", "us-east-1").strip()
ingestion_queue_url = os.getenv("INGESTION_QUEUE_URL", "").strip()
canonical_document_bucket = os.getenv("CANONICAL_DOCUMENT_BUCKET", "").strip()
processing_registry_table = os.getenv("PROCESSING_REGISTRY_TABLE", "").strip()
ingestion_result_bucket = os.getenv("INGESTION_RESULT_BUCKET", "").strip()
ingestion_result_prefix = os.getenv("INGESTION_RESULT_PREFIX", "ingestion-results").strip()

sqs_wait_time_seconds = _integer("SQS_WAIT_TIME_SECONDS", "20")
sqs_visibility_timeout_seconds = _integer("SQS_VISIBILITY_TIMEOUT_SECONDS", "900")
sqs_visibility_heartbeat_seconds = _integer("SQS_VISIBILITY_HEARTBEAT_SECONDS", "300")
sqs_visibility_extension_seconds = _integer("SQS_VISIBILITY_EXTENSION_SECONDS", "900")
processing_claim_lease_seconds = _integer("PROCESSING_CLAIM_LEASE_SECONDS", "900")
processing_claim_heartbeat_seconds = _integer("PROCESSING_CLAIM_HEARTBEAT_SECONDS", "300")
processing_record_ttl_days = _integer("PROCESSING_RECORD_TTL_DAYS", "90")

ingestion_schema_version = os.getenv("INGESTION_SCHEMA_VERSION", "ingestion-v1").strip()
chunker_type = os.getenv("CHUNKER_TYPE", "page-aware-recursive-character").strip()
chunker_version = os.getenv("CHUNKER_VERSION", "1").strip()
chunk_size = _integer("CHUNK_SIZE", "1200")
chunk_overlap = _integer("CHUNK_OVERLAP", "200")

embedding_provider = os.getenv("EMBEDDING_PROVIDER", HUGGINGFACE_API_EMBEDDING_PROVIDER).strip().lower()
embedding_model_id = os.getenv("EMBEDDING_MODEL_ID", "sentence-transformers/all-MiniLM-L6-v2").strip()
embedding_dimensions = _integer("EMBEDDING_DIMENSIONS", "384")
embedding_normalize = _boolean("EMBEDDING_NORMALIZE", "true")
embedding_model_options = _json_object("EMBEDDING_MODEL_OPTIONS")

huggingface_api_token = os.getenv("HUGGINGFACE_API_TOKEN", "").strip()
huggingface_api_provider = os.getenv("HUGGINGFACE_API_PROVIDER", "hf-inference").strip()
huggingface_api_base_url = os.getenv("HUGGINGFACE_API_BASE_URL", "https://router.huggingface.co").strip()
huggingface_api_timeout_seconds = _integer("HUGGINGFACE_API_TIMEOUT_SECONDS", "60")
huggingface_api_max_attempts = _integer("HUGGINGFACE_API_MAX_ATTEMPTS", "3")

index_schema_version = os.getenv("INDEX_SCHEMA_VERSION", "v1").strip()
opensearch_deployment_type = os.getenv("OPENSEARCH_DEPLOYMENT_TYPE", "serverless").strip().lower()
opensearch_endpoint = os.getenv("OPENSEARCH_ENDPOINT", "").strip()
opensearch_region = os.getenv("OPENSEARCH_REGION", aws_region).strip()
opensearch_index_prefix = os.getenv("OPENSEARCH_INDEX_PREFIX", "clinical-chunks").strip()
opensearch_refresh_after_index = _boolean("OPENSEARCH_REFRESH_AFTER_INDEX", "true")
opensearch_bulk_max_records = _integer("OPENSEARCH_BULK_MAX_RECORDS", "250")
opensearch_bulk_max_bytes = _integer("OPENSEARCH_BULK_MAX_BYTES", "5242880")
opensearch_bulk_max_attempts = _integer("OPENSEARCH_BULK_MAX_ATTEMPTS", "3")
opensearch_visibility_timeout_seconds = _number("OPENSEARCH_VISIBILITY_TIMEOUT_SECONDS", "60")
opensearch_visibility_poll_seconds = _number("OPENSEARCH_VISIBILITY_POLL_SECONDS", "1")


def validate_runtime_config() -> None:
    required = {
        "ENVIRONMENT": environment,
        "AWS_REGION": aws_region,
        "INGESTION_QUEUE_URL": ingestion_queue_url,
        "CANONICAL_DOCUMENT_BUCKET": canonical_document_bucket,
        "PROCESSING_REGISTRY_TABLE": processing_registry_table,
        "INGESTION_RESULT_BUCKET": ingestion_result_bucket,
        "INGESTION_RESULT_PREFIX": ingestion_result_prefix,
        "EMBEDDING_MODEL_ID": embedding_model_id,
        "OPENSEARCH_ENDPOINT": opensearch_endpoint,
        "OPENSEARCH_REGION": opensearch_region,
    }
    missing = sorted(name for name, value in required.items() if not value)
    
    if missing:
        raise RuntimeError("Missing required runtime configuration: " + ", ".join(missing))
    
    if environment not in SUPPORTED_ENVIRONMENTS:
        raise RuntimeError("ENVIRONMENT must be dev, test, staging, or prod.")

    if embedding_provider not in SUPPORTED_EMBEDDING_PROVIDERS:
        raise RuntimeError("Unsupported EMBEDDING_PROVIDER: " + embedding_provider)

    if environment == "prod" and embedding_provider != BEDROCK_EMBEDDING_PROVIDER:
        raise RuntimeError("Production requires EMBEDDING_PROVIDER=bedrock.")

    if embedding_provider == HUGGINGFACE_API_EMBEDDING_PROVIDER:
        if not huggingface_api_token:
            raise RuntimeError("HUGGINGFACE_API_TOKEN is required for huggingface-api.")
        _https(huggingface_api_base_url, "HUGGINGFACE_API_BASE_URL")
        _positive(huggingface_api_timeout_seconds, "HUGGINGFACE_API_TIMEOUT_SECONDS")
        _positive(huggingface_api_max_attempts, "HUGGINGFACE_API_MAX_ATTEMPTS")
    _https(opensearch_endpoint, "OPENSEARCH_ENDPOINT", allow_host_only=True)

    if opensearch_deployment_type not in SUPPORTED_OPENSEARCH_DEPLOYMENTS:
        raise RuntimeError("OPENSEARCH_DEPLOYMENT_TYPE must be serverless or domain.")

    _positive_number(opensearch_visibility_timeout_seconds,"OPENSEARCH_VISIBILITY_TIMEOUT_SECONDS")
    _positive_number(opensearch_visibility_poll_seconds, "OPENSEARCH_VISIBILITY_POLL_SECONDS")

    if opensearch_visibility_poll_seconds > opensearch_visibility_timeout_seconds:
        raise RuntimeError("OPENSEARCH_VISIBILITY_POLL_SECONDS must be less than or equal to OPENSEARCH_VISIBILITY_TIMEOUT_SECONDS.")

    if not ingestion_queue_url.startswith("https://"):
        raise RuntimeError("INGESTION_QUEUE_URL must be an HTTPS URL.")
    
    if sqs_wait_time_seconds < 0 or sqs_wait_time_seconds > 20:
        raise RuntimeError("SQS_WAIT_TIME_SECONDS must be between 0 and 20.")
    
    if sqs_visibility_heartbeat_seconds >= sqs_visibility_extension_seconds:
        raise RuntimeError("SQS heartbeat must be shorter than visibility extension.")
    
    if processing_claim_heartbeat_seconds >= processing_claim_lease_seconds:
        raise RuntimeError("Claim heartbeat must be shorter than claim lease.")
    
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise RuntimeError("CHUNK_OVERLAP must be nonnegative and less than CHUNK_SIZE.")
    
    for name, value in {
        "SQS_VISIBILITY_TIMEOUT_SECONDS": sqs_visibility_timeout_seconds,
        "SQS_VISIBILITY_HEARTBEAT_SECONDS": sqs_visibility_heartbeat_seconds,
        "SQS_VISIBILITY_EXTENSION_SECONDS": sqs_visibility_extension_seconds,
        "PROCESSING_CLAIM_LEASE_SECONDS": processing_claim_lease_seconds,
        "PROCESSING_CLAIM_HEARTBEAT_SECONDS": processing_claim_heartbeat_seconds,
        "PROCESSING_RECORD_TTL_DAYS": processing_record_ttl_days,
        "CHUNK_SIZE": chunk_size,
        "EMBEDDING_DIMENSIONS": embedding_dimensions,
        "OPENSEARCH_BULK_MAX_RECORDS": opensearch_bulk_max_records,
        "OPENSEARCH_BULK_MAX_BYTES": opensearch_bulk_max_bytes,
        "OPENSEARCH_BULK_MAX_ATTEMPTS": opensearch_bulk_max_attempts,
    }.items():
        _positive(value, name)


def _positive(value: int, name: str) -> None:
    if value <= 0:
        raise RuntimeError(f"{name} must be greater than zero.")

def _positive_number(value: int | float, name: str) -> None:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(float(value))
        or value <= 0
    ):
        raise RuntimeError(f"{name} must be a positive finite number.")

def _https(value: str, name: str, allow_host_only: bool = False) -> None:
    candidate = value if "://" in value else (f"https://{value}" if allow_host_only else value)
    parsed = urlparse(candidate)
    if parsed.scheme != "https" or not parsed.hostname or parsed.query or parsed.fragment:
        raise RuntimeError(f"{name} must be a valid HTTPS endpoint.")
