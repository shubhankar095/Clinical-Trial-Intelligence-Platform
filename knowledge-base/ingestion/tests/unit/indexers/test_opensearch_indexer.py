from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from aws_utils.opensearch import OpenSearchService
from exceptions.processing import (
    IngestionConfigurationError,
    PermanentIngestionError,
    RetryableIngestionError,
)
from indexers.opensearch_indexer import (
    OpenSearchConfigurationError,
    OpenSearchIndexer,
    OpenSearchPermanentBulkError,
    OpenSearchRetryableBulkError,
)
from models.index_record import IndexRecord

pytestmark = pytest.mark.unit
PROFILE_ID = "a" * 64
INGESTION_ID = "ingestion-1"


def record(**changes):
    values = dict(
        index_record_id="record-1", index_schema_version="V1", document_id="d" * 64,
        ingestion_id=INGESTION_ID, ingestion_profile_id=PROFILE_ID, chunk_id="chunk-1",
        chunk_index=0, text="clinical trial", character_count=14,
        start_offset=0, end_offset=14, start_page=1, end_page=1,
        embedding=(0.1, 0.2), embedding_provider="bedrock",
        embedding_model_id="amazon.titan-embed-text-v2:0", embedding_dimensions=2,
        embedding_normalized=True, input_token_count=3, file_name="trial.pdf",
        file_format="pdf", source_bucket="source", source_key="trial.pdf",
        source_version_id="v1", canonical_bucket="canonical",
        canonical_key="canonical.json", study_id="study", document_type="protocol",
        document_version="1", sponsor="sponsor", phase="2",
    )
    values.update(changes)
    return IndexRecord(**values)


def make_indexer(**changes):
    client = Mock()

    service = OpenSearchService(
        deployment_type="serverless",
        endpoint="https://example.test",
        region_name="ap-south-1",
        client=client,
    )

    values = dict(
        deployment_type=" Serverless ",
        endpoint=" https://example.test ",
        region_name=" ap-south-1 ",
        index_prefix=" Clinical_Chunks ",
        refresh_after_index=True,
        bulk_max_records=2,
        bulk_max_bytes=100000,
        bulk_max_attempts=3,
        visibility_timeout_seconds=60.0,
        visibility_poll_seconds=1.0,
        opensearch_service=service,
        sleep_function=Mock(),
        random_function=lambda: 0.25,
        monotonic_function=Mock(return_value=0.0),
    )

    values.update(changes)
    return OpenSearchIndexer(**values), client


def test_constructor_normalizes_configuration():
    indexer, _ = make_indexer(
        visibility_timeout_seconds=45,
        visibility_poll_seconds=0.5,
    )

    assert indexer.deployment_type == "serverless"
    assert indexer.endpoint == "https://example.test"
    assert indexer.region_name == "ap-south-1"
    assert indexer.index_prefix == "clinical-chunks"
    assert indexer.visibility_timeout_seconds == 45.0
    assert indexer.visibility_poll_seconds == 0.5


@pytest.mark.parametrize("deployment", ["bad", "collection"])
def test_constructor_rejects_deployment(deployment):
    with pytest.raises(ValueError, match="Unsupported deployment_type"):
        make_indexer(deployment_type=deployment)


@pytest.mark.parametrize("field", ["deployment_type", "endpoint", "region_name", "index_prefix"])
def test_constructor_rejects_blank_strings(field):
    with pytest.raises(ValueError): make_indexer(**{field: " "})


def test_constructor_rejects_nonboolean_refresh():
    with pytest.raises(TypeError): make_indexer(refresh_after_index="true")


@pytest.mark.parametrize("field", ["bulk_max_records", "bulk_max_bytes", "bulk_max_attempts"])
def test_constructor_validates_positive_integers(field):
    with pytest.raises(TypeError): make_indexer(**{field: True})
    with pytest.raises(ValueError): make_indexer(**{field: 0})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("visibility_timeout_seconds", "60"),
        ("visibility_timeout_seconds", True),
        ("visibility_timeout_seconds", None),
        ("visibility_poll_seconds", "1"),
        ("visibility_poll_seconds", False),
        ("visibility_poll_seconds", None),
    ],
)
def test_constructor_requires_numeric_visibility_values(field, value):
    with pytest.raises(TypeError, match="must be a number"):
        make_indexer(**{field: value})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("visibility_timeout_seconds", 0),
        ("visibility_timeout_seconds", -1),
        ("visibility_timeout_seconds", float("nan")),
        ("visibility_timeout_seconds", float("inf")),
        ("visibility_timeout_seconds", -float("inf")),
        ("visibility_poll_seconds", 0),
        ("visibility_poll_seconds", -1),
        ("visibility_poll_seconds", float("nan")),
        ("visibility_poll_seconds", float("inf")),
        ("visibility_poll_seconds", -float("inf")),
    ],
)
def test_constructor_requires_positive_finite_visibility_values(field, value):
    with pytest.raises(ValueError, match="positive finite number"):
        make_indexer(**{field: value})


def test_constructor_rejects_poll_interval_above_timeout():
    with pytest.raises(ValueError, match="less than or equal"):
        make_indexer(
            visibility_timeout_seconds=1.0,
            visibility_poll_seconds=1.1,
        )


def test_constructor_accepts_poll_interval_equal_to_timeout():
    indexer, _ = make_indexer(
        visibility_timeout_seconds=1.0,
        visibility_poll_seconds=1.0,
    )

    assert indexer.visibility_timeout_seconds == 1.0
    assert indexer.visibility_poll_seconds == 1.0


def test_constructor_validates_collaborators():
    with pytest.raises(TypeError):
        make_indexer(opensearch_service=object())

    with pytest.raises(TypeError):
        make_indexer(sleep_function=1)

    with pytest.raises(TypeError):
        make_indexer(random_function=1)

    with pytest.raises(TypeError, match="monotonic_function"):
        make_indexer(monotonic_function=1)


def test_build_index_name():
    indexer, _ = make_indexer()
    assert indexer.build_index_name(record()) == f"clinical-chunks-v1-{PROFILE_ID}"


def test_build_index_name_validates_record_and_profile():
    indexer, _ = make_indexer()
    with pytest.raises(TypeError): indexer.build_index_name(object())
    with pytest.raises(PermanentIngestionError):
        indexer.build_index_name(record(ingestion_profile_id="bad"))


def test_index_definition_contains_vector_mapping():
    indexer, _ = make_indexer()
    value = indexer._index_definition(384)
    assert value["settings"]["index"]["knn"] is True
    assert value["mappings"]["properties"]["embedding"]["dimension"] == 384


def test_index_component_and_required_helpers():
    indexer, _ = make_indexer()
    assert indexer._index_component(" A_B c! ", "field") == "a-b-c"
    with pytest.raises(ValueError): indexer._index_component("!!!", "field")
    with pytest.raises(TypeError): indexer._required(1, "field")
    with pytest.raises(ValueError): indexer._required(" ", "field")


def test_record_payload_and_bulk_operations():
    indexer, _ = make_indexer()
    item = record()
    payload = indexer._record_payload(item)
    assert payload["index_record_id"] == "record-1"
    operations = indexer._bulk_operations("index", (item,))
    assert operations[0] == {"index": {"_index": "index", "_id": "record-1"}}
    assert operations[1]["ingestion_id"] == INGESTION_ID


def test_batches_by_record_count():
    indexer, _ = make_indexer(bulk_max_records=2)
    records = tuple(record(index_record_id=f"r-{i}") for i in range(5))
    batches = indexer._build_batches(index_name="index", records=records)
    assert [len(batch) for batch in batches] == [2, 2, 1]


def test_rejects_record_larger_than_batch_limit():
    indexer, _ = make_indexer(bulk_max_bytes=1)
    with pytest.raises(OpenSearchPermanentBulkError, match="exceeds bulk_max_bytes"):
        indexer._build_batches(index_name="index", records=(record(),))


def test_validate_records_requires_nonempty_tuple():
    indexer, _ = make_indexer()
    with pytest.raises(PermanentIngestionError, match="non-empty tuple"):
        indexer._validate_records(INGESTION_ID, [])


def test_validate_records_requires_index_records():
    indexer, _ = make_indexer()
    with pytest.raises(TypeError, match="IndexRecord"):
        indexer._validate_records(INGESTION_ID, (object(),))


@pytest.mark.parametrize(
    "records,message",
    [
        ((record(ingestion_id="other"),), "ingestion_id"),
        ((record(embedding_dimensions=3),), "dimensions"),
        ((record(), record(index_record_id="r2", embedding_provider="other")), "multiple embedding models"),
        ((record(embedding=(0.1, float("nan"))),), "invalid value"),
        ((record(), record()), "duplicate"),
    ],
)
def test_validate_records_rejects_invalid_inputs(records, message):
    indexer, _ = make_indexer()
    with pytest.raises(OpenSearchPermanentBulkError, match=message):
        indexer._validate_records(INGESTION_ID, records)


def test_validate_records_accepts_compatible_records():
    indexer, _ = make_indexer()
    records = (record(), record(index_record_id="record-2", chunk_id="chunk-2"))
    indexer._validate_records(INGESTION_ID, records)


def test_retryable_status_and_error_types():
    indexer, _ = make_indexer()
    assert indexer._retryable(429, None)
    assert indexer._retryable(400, "timeout_exception")
    assert not indexer._retryable(True, None)
    assert not indexer._retryable(400, "mapping_exception")


def test_retry_delay_clamps_jitter_and_validates():
    indexer, _ = make_indexer(random_function=lambda: 2.0)
    assert indexer._retry_delay(1) == 2.0
    indexer._random = lambda: -1.0
    assert indexer._retry_delay(2) == 2.0
    indexer._random = lambda: float("nan")
    with pytest.raises(OpenSearchConfigurationError): indexer._retry_delay(1)
    indexer._random = lambda: "bad"
    with pytest.raises(OpenSearchConfigurationError): indexer._retry_delay(1)


@pytest.mark.parametrize(
    "error,expected",
    [
        (SimpleNamespace(status_code=401), 401),
        (SimpleNamespace(status=429), 429),
        (SimpleNamespace(info={"status": 503}), 503),
        (SimpleNamespace(response={"ResponseMetadata": {"HTTPStatusCode": 500}}), 500),
        (SimpleNamespace(info={"status": "503"}, response={"ResponseMetadata": {"HTTPStatusCode": 500}}), 500),
        (SimpleNamespace(info={"status": "503"}, response={"ResponseMetadata": {"HTTPStatusCode": True}}), None),
        (SimpleNamespace(response={"ResponseMetadata": None}), None),
        (SimpleNamespace(), None),
    ],
)
def test_transport_status_code(error, expected):
    assert OpenSearchIndexer._transport_status_code(error) == expected


def test_count_records_and_delete():
    indexer, client = make_indexer()
    client.count.return_value = {"count": 2}
    client.delete_by_query.return_value = {"deleted": 2}
    assert indexer.count_records(index_name="index", ingestion_id=INGESTION_ID) == 2
    assert indexer.delete_records_by_ingestion_id(index_name="index", ingestion_id=INGESTION_ID) == 2


@pytest.mark.parametrize("value", [None, True, -1, "2"])
def test_count_rejects_invalid_count(value):
    indexer, client = make_indexer(); client.count.return_value = {"count": value}
    with pytest.raises(OpenSearchRetryableBulkError):
        indexer.count_records(index_name="index", ingestion_id=INGESTION_ID)


@pytest.mark.parametrize("value", [True, -1, "2"])
def test_delete_rejects_invalid_deleted(value):
    indexer, client = make_indexer(); client.delete_by_query.return_value = {"deleted": value}
    with pytest.raises(OpenSearchRetryableBulkError):
        indexer.delete_records_by_ingestion_id(index_name="index", ingestion_id=INGESTION_ID)


def test_build_index_name_rejects_generated_name_over_255_characters():
    indexer, _ = make_indexer(index_prefix="a" * 190)
    with pytest.raises(OpenSearchConfigurationError, match="exceeds 255"):
        indexer.build_index_name(record())


def test_ensure_index_creates_missing_index():
    indexer, _ = make_indexer()
    indexer.opensearch_service.index_exists = Mock(return_value=False)
    indexer.opensearch_service.create_index = Mock(return_value={})

    indexer.ensure_index(index_name="index", record=record())

    indexer.opensearch_service.create_index.assert_called_once()
    assert indexer.opensearch_service.create_index.call_args.kwargs[
        "definition"
    ]["mappings"]["properties"]["embedding"]["dimension"] == 2


@pytest.mark.parametrize(
    "mapping",
    [
        {"index": {"mappings": {"properties": {"embedding": {"type": "knn_vector", "dimension": 2}}}}},
        {"index": {"mappings": {"properties": {"embedding": {"type": "knn_vector", "dimension": 3}}}}},
        {"index": {"mappings": {"properties": {"embedding": {"type": "text", "dimension": 2}}}}},
        {},
        {"index": []},
    ],
)
def test_ensure_index_validates_existing_mapping(mapping):
    indexer, _ = make_indexer()
    indexer.opensearch_service.index_exists = Mock(return_value=True)
    indexer.opensearch_service.get_index_mapping = Mock(return_value=mapping)

    if mapping == {"index": {"mappings": {"properties": {"embedding": {"type": "knn_vector", "dimension": 2}}}}}:
        indexer.ensure_index(index_name="index", record=record())
    else:
        with pytest.raises(OpenSearchConfigurationError):
            indexer.ensure_index(index_name="index", record=record())


def test_ensure_index_accepts_single_mapping_under_alternate_index_key():
    indexer, _ = make_indexer()
    indexer.opensearch_service.index_exists = Mock(return_value=True)
    indexer.opensearch_service.get_index_mapping = Mock(return_value={
        "alias": {
            "mappings": {
                "properties": {"embedding": {"type": "knn_vector", "dimension": 2}}
            }
        }
    })

    indexer.ensure_index(index_name="index", record=record())


def test_ensure_index_recovers_create_race_when_index_appears():
    indexer, _ = make_indexer()
    indexer.opensearch_service.index_exists = Mock(side_effect=[False, True])
    indexer.opensearch_service.create_index = Mock(side_effect=RuntimeError("already exists"))
    indexer.opensearch_service.get_index_mapping = Mock(return_value={
        "index": {
            "mappings": {
                "properties": {"embedding": {"type": "knn_vector", "dimension": 2}}
            }
        }
    })

    indexer.ensure_index(index_name="index", record=record())


def test_ensure_index_classifies_create_failure_if_index_is_still_missing():
    indexer, _ = make_indexer()
    indexer.opensearch_service.index_exists = Mock(side_effect=[False, False])
    indexer.opensearch_service.create_index = Mock(side_effect=RuntimeError("offline"))

    with pytest.raises(RetryableIngestionError):
        indexer.ensure_index(index_name="index", record=record())


def test_ensure_index_swallows_index_exists_check_failure_and_classifies_create_failure():
    indexer, _ = make_indexer()
    indexer.opensearch_service.index_exists = Mock(
        side_effect=[False, RuntimeError("lookup failed")]
    )
    indexer.opensearch_service.create_index = Mock(side_effect=RuntimeError("offline"))

    with pytest.raises(RetryableIngestionError):
        indexer.ensure_index(index_name="index", record=record())


def test_ensure_index_classifies_mapping_lookup_failure():
    indexer, _ = make_indexer()
    indexer.opensearch_service.index_exists = Mock(return_value=True)
    indexer.opensearch_service.get_index_mapping = Mock(side_effect=RuntimeError("offline"))

    with pytest.raises(RetryableIngestionError):
        indexer.ensure_index(index_name="index", record=record())


def _configure_successful_single_record_indexing(indexer, count=1):
    service = indexer.opensearch_service
    service.index_exists = Mock(return_value=False)
    service.create_index = Mock(return_value={})
    service.bulk = Mock(
        return_value={"items": [{"index": {"status": 201}}]}
    )
    service.refresh_index = Mock(return_value={})
    service.count = Mock(return_value={"count": count})
    return service


def test_serverless_indexes_without_explicit_refresh():
    indexer, _ = make_indexer(deployment_type="serverless")
    service = _configure_successful_single_record_indexing(indexer)

    destination = indexer.index_records(
        ingestion_id=INGESTION_ID,
        records=(record(),),
    )

    assert destination == f"opensearch://clinical-chunks-v1-{PROFILE_ID}"
    service.create_index.assert_called_once()
    service.bulk.assert_called_once()
    service.refresh_index.assert_not_called()
    service.count.assert_called_once()
    indexer._sleep.assert_not_called()


def test_domain_refreshes_before_count_verification():
    indexer, _ = make_indexer(
        deployment_type="domain",
        refresh_after_index=True,
    )
    service = _configure_successful_single_record_indexing(indexer)

    destination = indexer.index_records(
        ingestion_id=INGESTION_ID,
        records=(record(),),
    )

    assert destination == f"opensearch://clinical-chunks-v1-{PROFILE_ID}"
    service.refresh_index.assert_called_once_with(
        index_name=f"clinical-chunks-v1-{PROFILE_ID}"
    )
    service.count.assert_called_once()
    indexer._sleep.assert_not_called()


def test_domain_can_skip_explicit_refresh():
    indexer, _ = make_indexer(
        deployment_type="domain",
        refresh_after_index=False,
    )
    service = _configure_successful_single_record_indexing(indexer)

    indexer.index_records(
        ingestion_id=INGESTION_ID,
        records=(record(),),
    )

    service.refresh_index.assert_not_called()
    service.count.assert_called_once()
    indexer._sleep.assert_not_called()


def test_domain_count_mismatch_is_retryable():
    indexer, _ = make_indexer(deployment_type="domain")
    service = _configure_successful_single_record_indexing(indexer, count=0)

    with pytest.raises(
        OpenSearchRetryableBulkError,
        match="DAVV visibility timeout",
    ):
        indexer.index_records(
            ingestion_id=INGESTION_ID,
            records=(record(),),
        )

    service.refresh_index.assert_called_once()
    service.count.assert_called_once()
    indexer._sleep.assert_not_called()


def test_serverless_polls_until_exact_count_is_visible():
    sleep = Mock()
    monotonic = Mock(side_effect=[100.0, 100.0, 101.0])
    indexer, _ = make_indexer(
        deployment_type="serverless",
        visibility_timeout_seconds=60.0,
        visibility_poll_seconds=1.5,
        sleep_function=sleep,
        monotonic_function=monotonic,
    )
    service = indexer.opensearch_service
    service.count = Mock(
        side_effect=[{"count": 0}, {"count": 8}, {"count": 15}]
    )
    service.refresh_index = Mock()

    actual = indexer._verify_record_visibility(
        index_name="index",
        ingestion_id=INGESTION_ID,
        expected_count=15,
    )

    assert actual == 15
    assert service.count.call_count == 3
    service.refresh_index.assert_not_called()
    assert sleep.call_args_list == [call(1.5), call(1.5)]


def test_serverless_returns_last_count_at_timeout():
    sleep = Mock()
    monotonic = Mock(side_effect=[100.0, 100.0, 160.0])
    indexer, _ = make_indexer(
        deployment_type="serverless",
        visibility_timeout_seconds=60.0,
        visibility_poll_seconds=1.0,
        sleep_function=sleep,
        monotonic_function=monotonic,
    )
    service = indexer.opensearch_service
    service.count = Mock(side_effect=[{"count": 0}, {"count": 8}])

    actual = indexer._wait_for_record_count(
        index_name="index",
        ingestion_id=INGESTION_ID,
        expected_count=15,
    )

    assert actual == 8
    assert service.count.call_count == 2
    sleep.assert_called_once_with(1.0)


def test_serverless_visibility_timeout_is_retryable():
    sleep = Mock()
    monotonic = Mock(side_effect=[100.0, 160.0])
    indexer, _ = make_indexer(
        deployment_type="serverless",
        visibility_timeout_seconds=60.0,
        visibility_poll_seconds=1.0,
        sleep_function=sleep,
        monotonic_function=monotonic,
    )
    service = _configure_successful_single_record_indexing(indexer, count=0)

    with pytest.raises(
        OpenSearchRetryableBulkError,
        match="DAVV visibility timeout",
    ):
        indexer.index_records(
            ingestion_id=INGESTION_ID,
            records=(record(),),
        )

    service.refresh_index.assert_not_called()
    service.bulk.assert_called_once()
    service.count.assert_called_once()
    sleep.assert_not_called()


def test_serverless_excess_count_does_not_pass_verification():
    sleep = Mock()
    monotonic = Mock(side_effect=[10.0, 70.0])
    indexer, _ = make_indexer(
        deployment_type="serverless",
        visibility_timeout_seconds=60.0,
        visibility_poll_seconds=1.0,
        sleep_function=sleep,
        monotonic_function=monotonic,
    )
    service = indexer.opensearch_service
    service.count = Mock(return_value={"count": 2})

    actual = indexer._wait_for_record_count(
        index_name="index",
        ingestion_id=INGESTION_ID,
        expected_count=1,
    )

    assert actual == 2
    service.count.assert_called_once()
    sleep.assert_not_called()


@pytest.mark.parametrize(
    "method_name",
    ["_verify_record_visibility", "_wait_for_record_count"],
)
@pytest.mark.parametrize(
    ("expected_count", "error"),
    [
        (True, TypeError),
        (1.5, TypeError),
        ("1", TypeError),
        (0, ValueError),
        (-1, ValueError),
    ],
)
def test_visibility_methods_require_positive_integer_count(
    method_name,
    expected_count,
    error,
):
    indexer, _ = make_indexer()
    method = getattr(indexer, method_name)

    with pytest.raises(error):
        method(
            index_name="index",
            ingestion_id=INGESTION_ID,
            expected_count=expected_count,
        )


def test_index_records_classifies_unexpected_provider_failure():
    indexer, _ = make_indexer()
    indexer.ensure_index = Mock(side_effect=RuntimeError("connection reset"))

    with pytest.raises(RetryableIngestionError):
        indexer.index_records(ingestion_id=INGESTION_ID, records=(record(),))


def test_build_batches_by_byte_limit_and_utf8_size():
    indexer, _ = make_indexer(bulk_max_records=10)
    one_record_size = indexer._estimate_record_bytes("index", record())
    indexer.bulk_max_bytes = one_record_size * 2
    records = (
        record(index_record_id="one", text="clinical"),
        record(index_record_id="two", text="trial"),
        record(index_record_id="three", text="protocol"),
    )

    batches = indexer._build_batches(index_name="index", records=records)

    assert [len(batch) for batch in batches] == [2, 1]


def test_build_batches_accepts_empty_tuple():
    indexer, _ = make_indexer()
    assert indexer._build_batches(index_name="index", records=()) == ()


def test_estimate_record_bytes_rejects_non_json_embedding():
    indexer, _ = make_indexer()
    with pytest.raises(ValueError):
        indexer._estimate_record_bytes(
            "index",
            record(embedding=(float("nan"), 0.1)),
        )


@pytest.mark.parametrize(
    "response",
    [None, {}, {"items": "invalid"}, {"items": []}],
)
def test_inspect_bulk_response_rejects_invalid_response(response):
    indexer, _ = make_indexer()
    with pytest.raises(OpenSearchRetryableBulkError):
        indexer._inspect_bulk_response(response, (record(),))


def test_inspect_bulk_response_classifies_item_results():
    indexer, _ = make_indexer()
    records = (
        record(index_record_id="success"),
        record(index_record_id="retry"),
        record(index_record_id="permanent"),
        record(index_record_id="malformed"),
    )

    retryable, permanent = indexer._inspect_bulk_response(
        {
            "items": [
                {"index": {"status": 201}},
                {"index": {"status": 429, "error": {"type": "busy"}}},
                {"index": {"status": 400, "error": "bad request"}},
                {"delete": {"status": 201}},
            ]
        },
        records,
    )

    assert retryable == (records[1],)
    assert len(permanent) == 2
    assert "permanent" in permanent[0]
    assert "malformed" in permanent[1]


def test_bulk_index_retries_only_retryable_records():
    indexer, _ = make_indexer()
    service = indexer.opensearch_service
    service.bulk = Mock(side_effect=[
        {"items": [
            {"index": {"status": 429, "error": {"type": "busy"}}},
            {"index": {"status": 201}},
        ]},
        {"items": [{"index": {"status": 200}}]},
    ])

    indexer._index_batch_with_retry(
        index_name="index",
        ingestion_id=INGESTION_ID,
        batch=(record(), record(index_record_id="record-2")),
        batch_number=1,
        batch_count=1,
    )

    assert service.bulk.call_count == 2
    assert len(service.bulk.call_args_list[1].kwargs["operations"]) == 2


def test_bulk_index_retries_transport_status_then_succeeds():
    indexer, _ = make_indexer()
    service = indexer.opensearch_service
    unavailable = RuntimeError("unavailable")
    unavailable.status_code = 503
    service.bulk = Mock(side_effect=[
        unavailable,
        {"items": [{"index": {"status": 200}}]},
    ])

    indexer._index_batch_with_retry(
        index_name="index",
        ingestion_id=INGESTION_ID,
        batch=(record(),),
        batch_number=1,
        batch_count=1,
    )

    assert service.bulk.call_count == 2


@pytest.mark.parametrize(
    "status,error",
    [
        (401, OpenSearchConfigurationError),
        (403, OpenSearchConfigurationError),
        (400, OpenSearchPermanentBulkError),
        (404, OpenSearchPermanentBulkError),
        (418, OpenSearchPermanentBulkError),
    ],
)
def test_bulk_index_classifies_nonretryable_transport_status(status, error):
    indexer, _ = make_indexer()
    failure = RuntimeError("provider rejected request")
    failure.status_code = status
    indexer.opensearch_service.bulk = Mock(side_effect=failure)

    with pytest.raises(error):
        indexer._index_batch_with_retry(
            index_name="index",
            ingestion_id=INGESTION_ID,
            batch=(record(),),
            batch_number=1,
            batch_count=1,
        )


def test_bulk_index_exhausts_retryable_transport_attempts():
    indexer, _ = make_indexer(bulk_max_attempts=1)
    indexer.opensearch_service.bulk = Mock(side_effect=RuntimeError("offline"))

    with pytest.raises(OpenSearchRetryableBulkError, match="after 1 attempts"):
        indexer._index_batch_with_retry(
            index_name="index",
            ingestion_id=INGESTION_ID,
            batch=(record(),),
            batch_number=1,
            batch_count=1,
        )


def test_bulk_index_exhausts_retryable_item_attempts():
    indexer, _ = make_indexer(bulk_max_attempts=1)
    indexer.opensearch_service.bulk = Mock(return_value={
        "items": [{"index": {"status": 429}}]
    })

    with pytest.raises(OpenSearchRetryableBulkError, match="record-1"):
        indexer._index_batch_with_retry(
            index_name="index",
            ingestion_id=INGESTION_ID,
            batch=(record(),),
            batch_number=1,
            batch_count=1,
        )


def test_bulk_index_rejects_permanent_item_error():
    indexer, _ = make_indexer()
    indexer.opensearch_service.bulk = Mock(return_value={
        "items": [{"index": {"status": 400, "error": "bad mapping"}}]
    })

    with pytest.raises(OpenSearchPermanentBulkError, match="permanent failures"):
        indexer._index_batch_with_retry(
            index_name="index",
            ingestion_id=INGESTION_ID,
            batch=(record(),),
            batch_number=1,
            batch_count=1,
        )


@pytest.mark.parametrize(
    "records,message",
    [
        ((record(), record(index_record_id="r2", ingestion_profile_id="b" * 64)), "multiple ingestion profiles"),
        ((record(), record(index_record_id="r2", index_schema_version="v2")), "multiple index schemas"),
        ((record(embedding=(0.1, "bad")),), "invalid value"),
    ],
)
def test_validate_records_rejects_profile_schema_and_non_numeric_embeddings(records, message):
    indexer, _ = make_indexer()
    with pytest.raises(OpenSearchPermanentBulkError, match=message):
        indexer._validate_records(INGESTION_ID, records)


def test_validate_records_checks_every_record_type():
    indexer, _ = make_indexer()
    with pytest.raises(TypeError, match="Every record"):
        indexer._validate_records(INGESTION_ID, (record(), object()))


def test_delete_records_normalizes_and_passes_refresh():
    indexer, _ = make_indexer()
    service = indexer.opensearch_service
    service.delete_by_query = Mock(return_value={"deleted": 3})

    assert indexer.delete_records_by_ingestion_id(
        index_name=" index ",
        ingestion_id=" ingestion ",
        refresh=False,
    ) == 3
    assert service.delete_by_query.call_args.kwargs["refresh"] is False


def test_delete_rejects_blank_identifiers():
    indexer, _ = make_indexer()
    with pytest.raises(RetryableIngestionError):
        indexer.delete_records_by_ingestion_id(index_name=" ", ingestion_id=INGESTION_ID)
    with pytest.raises(RetryableIngestionError):
        indexer.delete_records_by_ingestion_id(index_name="index", ingestion_id=" ")


def test_count_and_delete_classify_provider_failures():
    indexer, _ = make_indexer()
    indexer.opensearch_service.count = Mock(side_effect=RuntimeError("connection reset"))
    with pytest.raises(RetryableIngestionError):
        indexer.count_records(index_name="index", ingestion_id=INGESTION_ID)

    indexer.opensearch_service.delete_by_query = Mock(
        side_effect=RuntimeError("connection reset")
    )
    with pytest.raises(RetryableIngestionError):
        indexer.delete_records_by_ingestion_id(
            index_name="index",
            ingestion_id=INGESTION_ID,
        )
