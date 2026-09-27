import importlib

import pytest


pytestmark = pytest.mark.unit


def load_config(
    monkeypatch,
    *,
    canonical_bucket="canonical-bucket",
    queue_url="https://example.invalid/queue",
    processing_registry_table="processing-table",
    processing_schema_version="extraction-v1",
    pages_to_read="all",
    min_words_per_page="20",
    min_quality_score="0.6",
    sqs_visibility_extension_seconds="600",
    sqs_visibility_heartbeat_seconds="180",
    processing_claim_lease_seconds="1800",
    processing_claim_heartbeat_seconds="300",
):
    monkeypatch.setenv(
        "CANONICAL_DOCUMENT_BUCKET",
        canonical_bucket,
    )
    monkeypatch.setenv(
        "DOCUMENT_UPLOADED_QUEUE_URL",
        queue_url,
    )
    monkeypatch.setenv(
        "PROCESSING_REGISTRY_TABLE",
        processing_registry_table,
    )
    monkeypatch.setenv(
        "PROCESSING_SCHEMA_VERSION",
        processing_schema_version,
    )
    monkeypatch.setenv(
        "PAGES_TO_READ",
        pages_to_read,
    )
    monkeypatch.setenv(
        "MIN_WORDS_PER_PAGE",
        min_words_per_page,
    )
    monkeypatch.setenv(
        "MIN_QUALITY_SCORE",
        min_quality_score,
    )
    monkeypatch.setenv(
        "SQS_VISIBILITY_EXTENSION_SECONDS",
        sqs_visibility_extension_seconds,
    )
    monkeypatch.setenv(
        "SQS_VISIBILITY_HEARTBEAT_SECONDS",
        sqs_visibility_heartbeat_seconds,
    )
    monkeypatch.setenv(
        "PROCESSING_CLAIM_LEASE_SECONDS",
        processing_claim_lease_seconds,
    )
    monkeypatch.setenv(
        "PROCESSING_CLAIM_HEARTBEAT_SECONDS",
        processing_claim_heartbeat_seconds,
    )

    import config.config as config

    return importlib.reload(config)


def test_valid_runtime_configuration_is_accepted(
    monkeypatch,
):
    config = load_config(monkeypatch)

    config.validate_runtime_config()


@pytest.mark.parametrize(
    (
        "keyword",
        "setting_name",
    ),
    [
        (
            "canonical_bucket",
            "CANONICAL_DOCUMENT_BUCKET",
        ),
        (
            "queue_url",
            "DOCUMENT_UPLOADED_QUEUE_URL",
        ),
        (
            "processing_registry_table",
            "PROCESSING_REGISTRY_TABLE",
        ),
    ],
)
def test_missing_required_setting_is_rejected(
    monkeypatch,
    keyword,
    setting_name,
):
    arguments = {
        keyword: "",
    }

    config = load_config(
        monkeypatch,
        **arguments,
    )

    with pytest.raises(
        RuntimeError,
        match=setting_name,
    ):
        config.validate_runtime_config()


def test_all_missing_required_settings_are_reported(
    monkeypatch,
):
    config = load_config(
        monkeypatch,
        canonical_bucket="",
        queue_url="",
        processing_registry_table="",
    )

    with pytest.raises(
        RuntimeError,
    ) as exception_info:
        config.validate_runtime_config()

    message = str(exception_info.value)

    assert "CANONICAL_DOCUMENT_BUCKET" in message
    assert "DOCUMENT_UPLOADED_QUEUE_URL" in message
    assert "PROCESSING_REGISTRY_TABLE" in message


@pytest.mark.parametrize(
    "pages_to_read",
    [
        "all",
        "ALL",
        "All",
        "1",
        "5",
        "100",
    ],
)
def test_valid_page_setting_is_accepted(
    monkeypatch,
    pages_to_read,
):
    config = load_config(
        monkeypatch,
        pages_to_read=pages_to_read,
    )

    config.validate_runtime_config()


@pytest.mark.parametrize(
    "pages_to_read",
    [
        "0",
        "-1",
        "-10",
        "invalid",
        "1.5",
        "two",
    ],
)
def test_invalid_page_setting_is_rejected(
    monkeypatch,
    pages_to_read,
):
    config = load_config(
        monkeypatch,
        pages_to_read=pages_to_read,
    )

    with pytest.raises(
        ValueError,
        match="PAGES_TO_READ",
    ):
        config.validate_runtime_config()


def test_negative_minimum_word_count_is_rejected(
    monkeypatch,
):
    config = load_config(
        monkeypatch,
        min_words_per_page="-1",
    )

    with pytest.raises(
        ValueError,
        match="MIN_WORDS_PER_PAGE",
    ):
        config.validate_runtime_config()


@pytest.mark.parametrize(
    "minimum_word_count",
    [
        "0",
        "1",
        "20",
    ],
)
def test_valid_minimum_word_count_is_accepted(
    monkeypatch,
    minimum_word_count,
):
    config = load_config(
        monkeypatch,
        min_words_per_page=minimum_word_count,
    )

    config.validate_runtime_config()


@pytest.mark.parametrize(
    "quality_score",
    [
        "-0.1",
        "1.1",
        "2.0",
    ],
)
def test_out_of_range_quality_score_is_rejected(
    monkeypatch,
    quality_score,
):
    config = load_config(
        monkeypatch,
        min_quality_score=quality_score,
    )

    with pytest.raises(
        ValueError,
        match="MIN_QUALITY_SCORE",
    ):
        config.validate_runtime_config()


@pytest.mark.parametrize(
    "quality_score",
    [
        "0.0",
        "0.5",
        "0.6",
        "1.0",
    ],
)
def test_valid_quality_score_is_accepted(
    monkeypatch,
    quality_score,
):
    config = load_config(
        monkeypatch,
        min_quality_score=quality_score,
    )

    config.validate_runtime_config()


@pytest.mark.parametrize(
    "extension_seconds",
    [
        "0",
        "-1",
    ],
)
def test_nonpositive_visibility_extension_is_rejected(
    monkeypatch,
    extension_seconds,
):
    config = load_config(
        monkeypatch,
        sqs_visibility_extension_seconds=(
            extension_seconds
        ),
    )

    with pytest.raises(
        ValueError,
        match="SQS_VISIBILITY_EXTENSION_SECONDS",
    ):
        config.validate_runtime_config()


def test_visibility_extension_above_aws_limit_is_rejected(
    monkeypatch,
):
    config = load_config(
        monkeypatch,
        sqs_visibility_extension_seconds="43201",
        processing_claim_lease_seconds="50000",
    )

    with pytest.raises(
        ValueError,
        match="cannot exceed 43200",
    ):
        config.validate_runtime_config()


@pytest.mark.parametrize(
    "heartbeat_seconds",
    [
        "0",
        "-1",
    ],
)
def test_nonpositive_visibility_heartbeat_is_rejected(
    monkeypatch,
    heartbeat_seconds,
):
    config = load_config(
        monkeypatch,
        sqs_visibility_heartbeat_seconds=(
            heartbeat_seconds
        ),
    )

    with pytest.raises(
        ValueError,
        match="SQS_VISIBILITY_HEARTBEAT_SECONDS",
    ):
        config.validate_runtime_config()


@pytest.mark.parametrize(
    "heartbeat_seconds",
    [
        "600",
        "601",
    ],
)
def test_visibility_heartbeat_must_be_less_than_extension(
    monkeypatch,
    heartbeat_seconds,
):
    config = load_config(
        monkeypatch,
        sqs_visibility_extension_seconds="600",
        sqs_visibility_heartbeat_seconds=(
            heartbeat_seconds
        ),
    )

    with pytest.raises(
        ValueError,
        match=(
            "SQS_VISIBILITY_HEARTBEAT_SECONDS"
        ),
    ):
        config.validate_runtime_config()


def test_empty_processing_schema_version_is_rejected(
    monkeypatch,
):
    config = load_config(
        monkeypatch,
        processing_schema_version="   ",
    )

    with pytest.raises(
        ValueError,
        match="PROCESSING_SCHEMA_VERSION",
    ):
        config.validate_runtime_config()


@pytest.mark.parametrize(
    "lease_seconds",
    [
        "0",
        "-1",
    ],
)
def test_nonpositive_processing_claim_lease_is_rejected(
    monkeypatch,
    lease_seconds,
):
    config = load_config(
        monkeypatch,
        processing_claim_lease_seconds=(
            lease_seconds
        ),
    )

    with pytest.raises(
        ValueError,
        match="PROCESSING_CLAIM_LEASE_SECONDS",
    ):
        config.validate_runtime_config()


@pytest.mark.parametrize(
    "lease_seconds",
    [
        "600",
        "599",
    ],
)
def test_processing_claim_lease_must_exceed_visibility_extension(
    monkeypatch,
    lease_seconds,
):
    config = load_config(
        monkeypatch,
        sqs_visibility_extension_seconds="600",
        processing_claim_lease_seconds=(
            lease_seconds
        ),
        processing_claim_heartbeat_seconds="300",
    )

    with pytest.raises(
        ValueError,
        match="PROCESSING_CLAIM_LEASE_SECONDS",
    ):
        config.validate_runtime_config()


@pytest.mark.parametrize(
    "heartbeat_seconds",
    [
        "0",
        "-1",
    ],
)
def test_nonpositive_processing_claim_heartbeat_is_rejected(
    monkeypatch,
    heartbeat_seconds,
):
    config = load_config(
        monkeypatch,
        processing_claim_heartbeat_seconds=(
            heartbeat_seconds
        ),
    )

    with pytest.raises(
        ValueError,
        match=(
            "PROCESSING_CLAIM_HEARTBEAT_SECONDS"
        ),
    ):
        config.validate_runtime_config()


@pytest.mark.parametrize(
    "heartbeat_seconds",
    [
        "1800",
        "1801",
    ],
)
def test_processing_claim_heartbeat_must_be_less_than_lease(
    monkeypatch,
    heartbeat_seconds,
):
    config = load_config(
        monkeypatch,
        processing_claim_lease_seconds="1800",
        processing_claim_heartbeat_seconds=(
            heartbeat_seconds
        ),
    )

    with pytest.raises(
        ValueError,
        match=(
            "PROCESSING_CLAIM_HEARTBEAT_SECONDS"
        ),
    ):
        config.validate_runtime_config()


def test_accelerated_heartbeat_configuration_is_valid(
    monkeypatch,
):
    config = load_config(
        monkeypatch,
        sqs_visibility_extension_seconds="600",
        sqs_visibility_heartbeat_seconds="180",
        processing_claim_lease_seconds="900",
        processing_claim_heartbeat_seconds="5",
    )

    config.validate_runtime_config()