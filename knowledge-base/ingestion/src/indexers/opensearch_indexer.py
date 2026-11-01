import json
import math
import random
import re
import time
from dataclasses import asdict
from typing import Any, Callable
from utils.logger import get_logger
from models.index_record import IndexRecord
from indexers.base_indexer import BaseIndexer
from aws_utils.opensearch import OpenSearchService
from services.provider_error_classifier import raise_classified_provider_error
from exceptions.processing import IngestionConfigurationError, PermanentIngestionError, RetryableIngestionError

logger = get_logger(__name__)


class OpenSearchIndexingError(RuntimeError):
    """Base exception for OpenSearch indexing failures."""


class OpenSearchBulkError(OpenSearchIndexingError):
    """One or more OpenSearch bulk operations failed without a safe classification."""


class OpenSearchRetryableBulkError(RetryableIngestionError):
    """A retryable OpenSearch write or visibility failure occurred."""


class OpenSearchPermanentBulkError(PermanentIngestionError):
    """A bulk request contained a permanent operation failure."""


class OpenSearchConfigurationError(IngestionConfigurationError):
    """The OpenSearch deployment or existing index mapping is incompatible."""


class OpenSearchIndexer(BaseIndexer):
    """Persist deterministic, profile-specific records in OpenSearch."""

    SERVERLESS_DEPLOYMENT = "serverless"
    DOMAIN_DEPLOYMENT = "domain"
    SUPPORTED_DEPLOYMENT_TYPES = frozenset({SERVERLESS_DEPLOYMENT, DOMAIN_DEPLOYMENT})
    INDEX_NAME_PATTERN = re.compile(r"[^a-z0-9-]+")
    PROFILE_ID_PATTERN = re.compile(r"^[0-9a-f]{64}$")

    # 409 remains explicitly retryable for this deterministic bulk-index workflow.
    RETRYABLE_STATUS_CODES = frozenset({408, 409, 425, 429, 500, 502, 503, 504})
    CONFIGURATION_STATUS_CODES = frozenset({401, 403})
    PERMANENT_STATUS_CODES = frozenset({400, 404, 405, 413, 415, 422})
    
    RETRYABLE_ERROR_TYPES = frozenset({
        "cluster_block_exception",
        "es_rejected_execution_exception",
        "master_not_discovered_exception",
        "node_not_connected_exception",
        "process_cluster_event_timeout_exception",
        "receive_timeout_transport_exception",
        "snapshot_in_progress_exception",
        "timeout_exception",
        "unavailable_shards_exception",
        "version_conflict_engine_exception",
    })

    def __init__(
        self,
        *,
        deployment_type: str,
        endpoint: str,
        region_name: str,
        index_prefix: str = "clinical-chunks",
        refresh_after_index: bool = True,
        bulk_max_records: int = 250,
        bulk_max_bytes: int = 5_242_880,
        bulk_max_attempts: int = 3,
        visibility_timeout_seconds: float = 60.0,
        visibility_poll_seconds: float = 1.0,
        opensearch_service: OpenSearchService | None = None,
        sleep_function: Callable[[float], None] | None = None,
        random_function: Callable[[], float] | None = None,
        monotonic_function: Callable[[], float] | None = None,
    ):
        deployment_type = self._required(deployment_type, "deployment_type").lower()
        if deployment_type not in self.SUPPORTED_DEPLOYMENT_TYPES:
            supported = ", ".join(sorted(self.SUPPORTED_DEPLOYMENT_TYPES))
            raise ValueError(
                f"Unsupported deployment_type '{deployment_type}'. Supported: {supported}."
            )
        if not isinstance(refresh_after_index, bool):
            raise TypeError("refresh_after_index must be a boolean.")
        self._positive_int(bulk_max_records, "bulk_max_records")
        self._positive_int(bulk_max_bytes, "bulk_max_bytes")
        self._positive_int(bulk_max_attempts, "bulk_max_attempts")

        self._positive_number(visibility_timeout_seconds, "visibility_timeout_seconds")
        self._positive_number(visibility_poll_seconds, "visibility_poll_seconds")

        if visibility_poll_seconds > visibility_timeout_seconds:
            raise ValueError("visibility_poll_seconds must be less than or equal to visibility_timeout_seconds.")


        if opensearch_service is not None and not isinstance(opensearch_service, OpenSearchService):
            raise TypeError("opensearch_service must be an OpenSearchService or None.")
        if sleep_function is not None and not callable(sleep_function):
            raise TypeError("sleep_function must be callable or None.")
        if random_function is not None and not callable(random_function):
            raise TypeError("random_function must be callable or None.")

        if monotonic_function is not None and not callable(monotonic_function):
            raise TypeError("monotonic_function must be callable or None.")

        self.deployment_type = deployment_type
        self.endpoint = self._required(endpoint, "endpoint")
        self.region_name = self._required(region_name, "region_name")
        self.index_prefix = self._index_component(index_prefix, "index_prefix")
        self.refresh_after_index = refresh_after_index
        self.bulk_max_records = bulk_max_records
        self.bulk_max_bytes = bulk_max_bytes
        self.bulk_max_attempts = bulk_max_attempts
        self.visibility_timeout_seconds = float(visibility_timeout_seconds)
        self.visibility_poll_seconds = float(visibility_poll_seconds)
        self.opensearch_service = opensearch_service or OpenSearchService(
            deployment_type=self.deployment_type,
            endpoint=self.endpoint,
            region_name=self.region_name,
        )
        self._sleep = sleep_function or time.sleep
        self._random = random_function or random.random
        self._monotonic = monotonic_function or time.monotonic

    def index_records(self, *, ingestion_id: str, records: tuple[IndexRecord, ...]) -> str:
        ingestion_id = self._required(ingestion_id, "ingestion_id")
        self._validate_records(ingestion_id, records)
        index_name = self.build_index_name(records[0])
        try:
            self.ensure_index(index_name=index_name, record=records[0])
            batches = self._build_batches(index_name=index_name, records=records)
            for number, batch in enumerate(batches, start=1):
                self._index_batch_with_retry(
                    index_name=index_name,
                    ingestion_id=ingestion_id,
                    batch=batch,
                    batch_number=number,
                    batch_count=len(batches),
                )

            actual = self._verify_record_visibility(
                index_name=index_name,
                ingestion_id=ingestion_id,
                expected_count=len(records),
            )

            if actual != len(records):
                raise OpenSearchRetryableBulkError(
                    "OpenSearch records did not become searchable before "
                    "the DAVV visibility timeout: "
                    f"expected={len(records)}, "
                    f"actual={actual}, "
                    f"index='{index_name}', "
                    f"ingestion_id='{ingestion_id}'."
                )

        except (RetryableIngestionError, PermanentIngestionError, IngestionConfigurationError):
            logger.exception(
                "Classified OpenSearch indexing failure.",
                extra={
                    "event": "opensearch_indexing_failed",
                    "index_name": index_name,
                    "ingestion_id": ingestion_id,
                    "record_count": len(records),
                },
            )
            raise
        except Exception as exception:
            logger.exception(
                "Unclassified OpenSearch indexing failure.",
                extra={
                    "event": "opensearch_indexing_failed",
                    "index_name": index_name,
                    "ingestion_id": ingestion_id,
                    "record_count": len(records),
                },
            )
            raise_classified_provider_error(exception, operation="OpenSearch indexing")
        return f"opensearch://{index_name}"

    def build_index_name(self, record: IndexRecord) -> str:
        if not isinstance(record, IndexRecord):
            raise TypeError("record must be an IndexRecord.")
        if not self.PROFILE_ID_PATTERN.fullmatch(record.ingestion_profile_id):
            raise PermanentIngestionError(
                "ingestion_profile_id must be a 64-character lowercase SHA-256 value."
            )
        schema = self._index_component(record.index_schema_version, "index_schema_version")
        name = f"{self.index_prefix}-{schema}-{record.ingestion_profile_id}"
        if len(name) > 255:
            raise OpenSearchConfigurationError(
                "Generated OpenSearch index name exceeds 255 characters."
            )
        return name

    def ensure_index(self, *, index_name: str, record: IndexRecord) -> None:
        try:
            if self.opensearch_service.index_exists(index_name=index_name):
                self._validate_existing_index(index_name, record.embedding_dimensions)
                return
            self.opensearch_service.create_index(
                index_name=index_name,
                definition=self._index_definition(record.embedding_dimensions),
            )
        except (RetryableIngestionError, PermanentIngestionError, IngestionConfigurationError):
            raise
        except Exception as exception:
            try:
                if self.opensearch_service.index_exists(index_name=index_name):
                    self._validate_existing_index(index_name, record.embedding_dimensions)
                    return
            except Exception:
                pass
            raise_classified_provider_error(exception, operation="OpenSearch index creation")

    def _index_definition(self, dimensions: int) -> dict[str, Any]:
        self._positive_int(dimensions, "dimensions")
        keyword_fields = (
            "index_record_id", "index_schema_version", "document_id", "ingestion_id",
            "ingestion_profile_id", "chunk_id", "embedding_provider", "embedding_model_id",
            "file_name", "file_format", "source_bucket", "source_key", "source_version_id",
            "canonical_bucket", "canonical_key", "study_id", "document_type",
            "document_version", "sponsor", "phase",
        )
        integer_fields = (
            "chunk_index", "character_count", "start_offset", "end_offset", "start_page",
            "end_page", "embedding_dimensions", "input_token_count",
        )
        properties: dict[str, Any] = {name: {"type": "keyword"} for name in keyword_fields}
        properties.update({name: {"type": "integer"} for name in integer_fields})
        properties.update({
            "text": {"type": "text"},
            "embedding": {
                "type": "knn_vector",
                "dimension": dimensions,
                "method": {"name": "hnsw", "space_type": "cosinesimil"},
            },
            "embedding_normalized": {"type": "boolean"},
        })
        return {
            "settings": {"index": {"knn": True}},
            "mappings": {"dynamic": "strict", "properties": properties},
        }

    def _validate_existing_index(self, index_name: str, expected_dimensions: int) -> None:
        try:
            response = self.opensearch_service.get_index_mapping(index_name=index_name)
        except Exception as exception:
            raise_classified_provider_error(exception, operation="OpenSearch mapping lookup")
        mapping = response.get(index_name)
        if not isinstance(mapping, dict) and len(response) == 1:
            mapping = next(iter(response.values()))
        if not isinstance(mapping, dict):
            raise OpenSearchConfigurationError(
                "OpenSearch mapping response does not contain the requested index."
            )
        embedding = mapping.get("mappings", {}).get("properties", {}).get("embedding")
        if not isinstance(embedding, dict) or embedding.get("type") != "knn_vector":
            raise OpenSearchConfigurationError(
                "Existing index does not contain a compatible knn_vector embedding field."
            )
        if embedding.get("dimension") != expected_dimensions:
            raise OpenSearchConfigurationError(
                f"Existing vector dimension mismatch: expected={expected_dimensions}, "
                f"actual={embedding.get('dimension')}."
            )

    def _build_batches(
        self, *, index_name: str, records: tuple[IndexRecord, ...]
    ) -> tuple[tuple[IndexRecord, ...], ...]:
        batches: list[tuple[IndexRecord, ...]] = []
        current: list[IndexRecord] = []
        current_bytes = 0
        for record in records:
            size = self._estimate_record_bytes(index_name, record)
            if size > self.bulk_max_bytes:
                raise OpenSearchPermanentBulkError(
                    f"Record '{record.index_record_id}' exceeds bulk_max_bytes: "
                    f"{size} > {self.bulk_max_bytes}."
                )
            if current and (
                len(current) >= self.bulk_max_records
                or current_bytes + size > self.bulk_max_bytes
            ):
                batches.append(tuple(current))
                current = []
                current_bytes = 0
            current.append(record)
            current_bytes += size
        if current:
            batches.append(tuple(current))
        return tuple(batches)

    def _estimate_record_bytes(self, index_name: str, record: IndexRecord) -> int:
        meta = {"index": {"_index": index_name, "_id": record.index_record_id}}
        source = self._record_payload(record)
        return (
            len(json.dumps(meta, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
            + 1
            + len(
                json.dumps(
                    source,
                    separators=(",", ":"),
                    ensure_ascii=False,
                    allow_nan=False,
                ).encode("utf-8")
            )
            + 1
        )

    def _index_batch_with_retry(
        self,
        *,
        index_name: str,
        ingestion_id: str,
        batch: tuple[IndexRecord, ...],
        batch_number: int,
        batch_count: int,
    ) -> None:
        pending = batch
        attempt = 1
        while True:
            try:
                response = self.opensearch_service.bulk(
                    operations=self._bulk_operations(index_name, pending)
                )
            except Exception as exception:
                status_code = self._transport_status_code(exception)
                

                if status_code in self.CONFIGURATION_STATUS_CODES:
                    raise OpenSearchConfigurationError(
                        "OpenSearch bulk request failed "
                        "because authentication or "
                        "authorization is invalid. "
                        f"HTTP status={status_code}."
                    ) from exception

                if status_code in self.PERMANENT_STATUS_CODES:
                    raise OpenSearchPermanentBulkError(
                        "OpenSearch permanently rejected "
                        "the bulk request. "
                        f"HTTP status={status_code}."
                    ) from exception

                if (
                    status_code is not None
                    and status_code
                    not in self.RETRYABLE_STATUS_CODES
                ):
                    raise OpenSearchPermanentBulkError(
                        "OpenSearch bulk request failed "
                        "with a non-retryable HTTP status. "
                        f"HTTP status={status_code}."
                    ) from exception

                if attempt >= self.bulk_max_attempts:
                    raise OpenSearchRetryableBulkError(
                        "OpenSearch bulk transport failed "
                        f"after {attempt} attempts for "
                        f"batch {batch_number}/"
                        f"{batch_count}."
                    ) from exception

                self._sleep(self._retry_delay(attempt))

                attempt += 1
                continue

            retryable, permanent = self._inspect_bulk_response(response, pending)
            if permanent:
                raise OpenSearchPermanentBulkError(
                    "OpenSearch bulk indexing reported permanent failures: "
                    + "; ".join(permanent[:10])
                )
            if not retryable:
                return
            if attempt >= self.bulk_max_attempts:
                ids = ", ".join(record.index_record_id for record in retryable[:10])
                raise OpenSearchRetryableBulkError(
                    f"Retryable bulk failures remained after {attempt} attempts. "
                    f"record_ids={ids}."
                )
            logger.warning(
                "Retrying OpenSearch bulk records.",
                extra={
                    "event": "opensearch_bulk_item_retry",
                    "index_name": index_name,
                    "ingestion_id": ingestion_id,
                    "attempt": attempt,
                    "retryable_record_count": len(retryable),
                },
            )
            self._sleep(self._retry_delay(attempt))
            pending = retryable
            attempt += 1

    def _bulk_operations(
        self, index_name: str, records: tuple[IndexRecord, ...]
    ) -> list[dict[str, Any]]:
        operations: list[dict[str, Any]] = []
        for record in records:
            operations.append({"index": {"_index": index_name, "_id": record.index_record_id}})
            operations.append(self._record_payload(record))
        return operations

    @staticmethod
    def _record_payload(record: IndexRecord) -> dict[str, Any]:
        payload = asdict(record)
        payload["embedding"] = list(record.embedding)
        return payload

    def _inspect_bulk_response(
        self, response: dict[str, Any], records: tuple[IndexRecord, ...]
    ) -> tuple[tuple[IndexRecord, ...], list[str]]:
        if not isinstance(response, dict) or not isinstance(response.get("items"), list):
            raise OpenSearchRetryableBulkError(
                "OpenSearch bulk response does not contain an items list."
            )
        items = response["items"]
        if len(items) != len(records):
            raise OpenSearchRetryableBulkError(
                "OpenSearch bulk response item count does not match the request."
            )
        retryable: list[IndexRecord] = []
        permanent: list[str] = []
        for record, item in zip(records, items, strict=True):
            operation = item.get("index") if isinstance(item, dict) else None
            if not isinstance(operation, dict):
                permanent.append(f"{record.index_record_id}: invalid index result")
                continue
            status = operation.get("status")
            if isinstance(status, int) and not isinstance(status, bool) and 200 <= status < 300:
                continue
            error = operation.get("error")
            error_type = (
                error.get("type")
                if isinstance(error, dict)
                else error if isinstance(error, str) else None
            )
            if self._retryable(status, error_type):
                retryable.append(record)
            else:
                permanent.append(
                    f"{record.index_record_id}: status={status}, "
                    f"error_type={error_type}, error={error}"
                )
        return tuple(retryable), permanent

    @staticmethod
    def _transport_status_code(
        exception: BaseException,
    ) -> int | None:
        """
        Extract an HTTP status code from common
        OpenSearch transport exceptions.
        """
        for attribute_name in ("status_code", "status"):
            value = getattr(exception, attribute_name, None)

            if isinstance(value, int) and not isinstance(value, bool):
                return value

        info = getattr(exception, "info", None)

        if isinstance(info, dict):
            value = info.get("status")

            if isinstance(value, int) and not isinstance(value, bool):
                return value

        response = getattr(exception, "response", None)

        if isinstance(response, dict):
            response_metadata = response.get("ResponseMetadata")

            if isinstance(response_metadata, dict):
                value = response_metadata.get("HTTPStatusCode")

                if isinstance(value, int) and not isinstance(value, bool):
                    return value

        return None

    def _retryable(self, status: Any, error_type: str | None) -> bool:
        return (
            isinstance(status, int)
            and not isinstance(status, bool)
            and status in self.RETRYABLE_STATUS_CODES
        ) or error_type in self.RETRYABLE_ERROR_TYPES

    def _retry_delay(self, completed_attempt: int) -> float:
        jitter = self._random()
        if (
            not isinstance(jitter, (int, float))
            or isinstance(jitter, bool)
            or not math.isfinite(float(jitter))
        ):
            raise OpenSearchConfigurationError("random_function returned an invalid value.")
        return float(min(2 ** (completed_attempt - 1), 30)) + min(
            max(float(jitter), 0.0), 1.0
        )

    def count_records(self, *, index_name: str, ingestion_id: str) -> int:
        try:
            response = self.opensearch_service.count(
                index_name=index_name,
                query={"query": {"term": {"ingestion_id": ingestion_id}}},
            )
        except Exception as exception:
            raise_classified_provider_error(exception, operation="OpenSearch record count")
        count = response.get("count")
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise OpenSearchRetryableBulkError(
                "OpenSearch count response did not contain a valid count."
            )
        return count

    def _verify_record_visibility(
        self,
        *,
        index_name: str,
        ingestion_id: str,
        expected_count: int,
    ) -> int:
        """
        Verify that all indexed records are searchable.

        OpenSearch domains support explicit index refresh. OpenSearch
        Serverless manages refresh internally, so DAVV polls the record
        count until the exact expected count is visible or the bounded
        timeout expires.
        """

        self._positive_int(expected_count, "expected_count")

        if self.deployment_type == self.DOMAIN_DEPLOYMENT:
            if self.refresh_after_index:
                self.opensearch_service.refresh_index(index_name=index_name)

            return self.count_records(index_name=index_name, ingestion_id=ingestion_id)

        return self._wait_for_record_count(
            index_name=index_name,
            ingestion_id=ingestion_id,
            expected_count=expected_count,
        )


    def _wait_for_record_count(
        self,
        *,
        index_name: str,
        ingestion_id: str,
        expected_count: int,
    ) -> int:
        """
        Poll Serverless until the exact expected record count is visible.

        Polling performs count requests only. It does not repeat bulk
        indexing and therefore does not create duplicate documents.
        """

        self._positive_int(expected_count, "expected_count")

        deadline = self._monotonic() + self.visibility_timeout_seconds

        actual = self.count_records(index_name=index_name, ingestion_id=ingestion_id)

        while actual != expected_count:
            if self._monotonic() >= deadline:
                return actual

            self._sleep(self.visibility_poll_seconds)

            actual = self.count_records(index_name=index_name, ingestion_id=ingestion_id)

        return actual


    def delete_records_by_ingestion_id(
        self, *, index_name: str, ingestion_id: str, refresh: bool = True
    ) -> int:
        try:
            response = self.opensearch_service.delete_by_query(
                index_name=self._required(index_name, "index_name"),
                query={
                    "query": {
                        "term": {
                            "ingestion_id": self._required(ingestion_id, "ingestion_id")
                        }
                    }
                },
                refresh=refresh,
                conflicts="proceed",
            )
        except Exception as exception:
            raise_classified_provider_error(exception, operation="OpenSearch repair deletion")
        deleted = response.get("deleted", 0)
        if not isinstance(deleted, int) or isinstance(deleted, bool) or deleted < 0:
            raise OpenSearchRetryableBulkError(
                "OpenSearch delete response contains an invalid deleted count."
            )
        return deleted

    def _validate_records(self, ingestion_id: str, records: tuple[IndexRecord, ...]) -> None:
        if not isinstance(records, tuple) or not records:
            raise PermanentIngestionError("records must be a non-empty tuple.")
        first = records[0]
        if not isinstance(first, IndexRecord):
            raise TypeError("Every record must be an IndexRecord.")
        seen: set[str] = set()
        for record in records:
            if not isinstance(record, IndexRecord):
                raise TypeError("Every record must be an IndexRecord.")
            if record.ingestion_id != ingestion_id:
                raise OpenSearchPermanentBulkError(
                    "Record ingestion_id does not match the request."
                )
            if record.ingestion_profile_id != first.ingestion_profile_id:
                raise OpenSearchPermanentBulkError(
                    "Records contain multiple ingestion profiles."
                )
            if record.index_schema_version != first.index_schema_version:
                raise OpenSearchPermanentBulkError("Records contain multiple index schemas.")
            if (
                record.embedding_dimensions != first.embedding_dimensions
                or len(record.embedding) != first.embedding_dimensions
            ):
                raise OpenSearchPermanentBulkError(
                    "Records contain incompatible embedding dimensions."
                )
            if (
                record.embedding_provider != first.embedding_provider
                or record.embedding_model_id != first.embedding_model_id
            ):
                raise OpenSearchPermanentBulkError(
                    "Records contain multiple embedding models."
                )
            if not all(
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(value)
                for value in record.embedding
            ):
                raise OpenSearchPermanentBulkError(
                    "Record embedding contains an invalid value."
                )
            if record.index_record_id in seen:
                raise OpenSearchPermanentBulkError(
                    "Records contain duplicate index_record_id values."
                )
            seen.add(record.index_record_id)

    def _index_component(self, value: str, field_name: str) -> str:
        value = self.INDEX_NAME_PATTERN.sub(
            "-", self._required(value, field_name).lower().replace("_", "-")
        ).strip("-")
        if not value:
            raise ValueError(f"{field_name} does not contain a usable index component.")
        return value

    @staticmethod
    def _required(value: str, field_name: str) -> str:
        if not isinstance(value, str):
            raise TypeError(f"{field_name} must be a string.")
        value = value.strip()
        if not value:
            raise ValueError(f"{field_name} must not be blank.")
        return value

    @staticmethod
    def _positive_int(value: int, field_name: str) -> None:
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(f"{field_name} must be an integer.")
        if value <= 0:
            raise ValueError(f"{field_name} must be greater than zero.")

    @staticmethod
    def _positive_number(value: int | float, field_name: str) -> None:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise TypeError(f"{field_name} must be a number.")

        if not math.isfinite(float(value)) or value <= 0:
            raise ValueError(f"{field_name} must be a positive finite number.")
