from unittest.mock import Mock

import httpx
import pytest
from huggingface_hub.errors import HfHubHTTPError

from embedders.huggingface_api_embedder import (
    HuggingFaceApiEmbedder,
)
from exceptions.processing import (
    IngestionConfigurationError,
    PermanentIngestionError,
    RetryableIngestionError,
)
from models.document import DocumentChunk


pytestmark = pytest.mark.unit


def make_chunk(
    text: str = "Clinical trial protocol",
) -> DocumentChunk:
    return DocumentChunk(
        chunk_id="chunk-1",
        ingestion_id="ingestion-1",
        ingestion_profile_id="profile-1",
        document_id="a" * 64,
        chunk_index=0,
        text=text,
        start_offset=0,
        end_offset=len(text),
        start_page=1,
        end_page=1,
        character_count=len(text),
    )


def make_client(
    *results,
) -> Mock:
    client = Mock()

    client.feature_extraction.side_effect = list(
        results
    )

    return client


def make_embedder(**changes):
    values = {
        "model_id": "org/model",
        "dimensions": 2,
        "normalize": True,
        "api_token": "token-value",
        "api_provider": "hf-inference",
        "api_base_url": "https://router.example",
        "client": make_client([3, 4]),
        "sleep_function": Mock(),
    }

    values.update(changes)

    return HuggingFaceApiEmbedder(**values)


def make_hf_error(
    status_code: int,
    *,
    retry_after: str | None = None,
) -> HfHubHTTPError:
    headers = {}

    if retry_after is not None:
        headers["Retry-After"] = retry_after

    request = httpx.Request(
        "POST",
        (
            "https://router.example/"
            "hf-inference/models/org/model"
        ),
    )

    response = httpx.Response(
        status_code,
        headers=headers,
        request=request,
        json={
            "error": (
                f"Provider returned HTTP "
                f"{status_code}"
            )
        },
    )

    return HfHubHTTPError(
        f"HTTP {status_code}",
        response=response,
    )


class ArrayLike:
    def __init__(
        self,
        values: list[float],
    ) -> None:
        self.values = values

    def tolist(
        self,
    ) -> list[float]:
        return self.values


def test_constructor_builds_endpoint_and_requests_feature_extraction():
    client = make_client([[3, 4]])

    embedder = make_embedder(
        model_id=" org/a model ",
        api_provider=" provider/name ",
        api_base_url="https://router.example/",
        client=client,
    )

    embedded = embedder.embed(
        make_chunk()
    )

    assert embedder.endpoint == (
        "https://router.example/"
        "provider%2Fname/models/"
        "org/a%20model"
    )

    client.feature_extraction.assert_called_once_with(
        "Clinical trial protocol",
        model="org/a model",
    )

    assert embedded.embedding == pytest.approx(
        (0.6, 0.8)
    )
    assert (
        embedded.embedding_provider
        == "huggingface-api"
    )
    assert (
        embedded.embedding_model_id
        == "org/a model"
    )
    assert embedded.embedding_dimensions == 2
    assert embedded.embedding_normalized is True
    assert embedded.input_token_count is None


def test_default_client_is_configured_for_feature_extraction(
    monkeypatch,
):
    inference_client = Mock()

    constructor = Mock(
        return_value=inference_client
    )

    monkeypatch.setattr(
        (
            "embedders."
            "huggingface_api_embedder."
            "InferenceClient"
        ),
        constructor,
    )

    embedder = HuggingFaceApiEmbedder(
        model_id="org/model",
        dimensions=2,
        normalize=False,
        api_token="token-value",
        api_provider="hf-inference",
        api_base_url=(
            "https://router.huggingface.co"
        ),
        timeout_seconds=45,
    )

    constructor.assert_called_once_with(
        provider="hf-inference",
        api_key="token-value",
        timeout=45.0,
    )

    assert embedder._client is inference_client


@pytest.mark.parametrize(
    "field,value,error",
    [
        (
            "model_id",
            None,
            TypeError,
        ),
        (
            "model_id",
            " ",
            ValueError,
        ),
        (
            "api_token",
            None,
            TypeError,
        ),
        (
            "api_token",
            " ",
            ValueError,
        ),
        (
            "api_provider",
            " ",
            ValueError,
        ),
        (
            "api_base_url",
            "http://router.example",
            ValueError,
        ),
        (
            "api_base_url",
            "https:///missing-host",
            ValueError,
        ),
        (
            "api_base_url",
            (
                "https://router.example"
                "?token=secret"
            ),
            ValueError,
        ),
        (
            "api_base_url",
            (
                "https://router.example"
                "#fragment"
            ),
            ValueError,
        ),
        (
            "dimensions",
            True,
            TypeError,
        ),
        (
            "dimensions",
            0,
            ValueError,
        ),
        (
            "timeout_seconds",
            False,
            TypeError,
        ),
        (
            "max_attempts",
            -1,
            ValueError,
        ),
        (
            "normalize",
            1,
            TypeError,
        ),
    ],
)
def test_constructor_validation(
    field,
    value,
    error,
):
    with pytest.raises(error):
        make_embedder(
            **{
                field: value,
            }
        )


@pytest.mark.parametrize(
    "field,value",
    [
        (
            "dimensions",
            "2",
        ),
        (
            "timeout_seconds",
            1.5,
        ),
        (
            "max_attempts",
            True,
        ),
    ],
)
def test_constructor_requires_integer_limits(
    field,
    value,
):
    with pytest.raises(TypeError):
        make_embedder(
            **{
                field: value,
            }
        )


def test_close_preserves_lifecycle_compatibility():
    client = make_client([1, 2])

    embedder = make_embedder(
        client=client
    )

    assert embedder.close() is None

    client.close.assert_not_called()


@pytest.mark.parametrize(
    "chunk",
    [
        None,
        object(),
    ],
)
def test_embed_rejects_non_document_chunks(
    chunk,
):
    with pytest.raises(
        TypeError,
        match="DocumentChunk",
    ):
        make_embedder().embed(
            chunk
        )


def test_embed_rejects_blank_text():
    with pytest.raises(
        PermanentIngestionError,
        match="must not be blank",
    ):
        make_embedder().embed(
            make_chunk(" \t")
        )


def test_embed_accepts_list_without_normalization():
    client = make_client(
        [0.25, -0.5]
    )

    embedder = make_embedder(
        normalize=False,
        client=client,
    )

    embedded = embedder.embed(
        make_chunk()
    )

    assert embedded.embedding == (
        0.25,
        -0.5,
    )
    assert (
        embedded.embedding_normalized
        is False
    )


def test_embed_accepts_numpy_like_array():
    client = make_client(
        ArrayLike(
            [
                3.0,
                4.0,
            ]
        )
    )

    embedded = make_embedder(
        client=client
    ).embed(
        make_chunk()
    )

    assert embedded.embedding == pytest.approx(
        (
            0.6,
            0.8,
        )
    )


@pytest.mark.parametrize(
    "payload",
    [
        {
            "error": "model unavailable",
        },
        {},
        [],
        [[]],
        [
            [1],
            [2],
        ],
    ],
)
def test_embedding_parser_rejects_invalid_shapes(
    payload,
):
    with pytest.raises(
        PermanentIngestionError
    ):
        make_embedder()._parse_embedding(
            payload
        )


@pytest.mark.parametrize(
    "value",
    [
        [
            1,
            True,
        ],
        [
            1,
            "2",
        ],
        [
            1,
            None,
        ],
    ],
)
def test_embedding_parser_rejects_nonnumeric_values(
    value,
):
    with pytest.raises(
        PermanentIngestionError,
        match="nonnumeric",
    ):
        make_embedder()._parse_embedding(
            value
        )


@pytest.mark.parametrize(
    "value",
    [
        [
            1,
            float("nan"),
        ],
        [
            float("inf"),
            1,
        ],
    ],
)
def test_embedding_parser_rejects_nonfinite_values(
    value,
):
    with pytest.raises(
        PermanentIngestionError,
        match="nonfinite",
    ):
        make_embedder()._parse_embedding(
            value
        )


def test_embedding_parser_accepts_embedding_alias():
    assert make_embedder()._parse_embedding(
        {
            "embedding": [
                1,
                2,
            ],
        }
    ) == (
        1.0,
        2.0,
    )


def test_embedding_parser_accepts_embeddings_alias_and_flattens():
    assert make_embedder()._parse_embedding(
        {
            "embeddings": [
                [
                    1,
                    2,
                ],
            ],
        }
    ) == (
        1.0,
        2.0,
    )


def test_embedding_parser_rejects_dimension_mismatch():
    with pytest.raises(
        PermanentIngestionError,
        match="dimension mismatch",
    ):
        make_embedder()._parse_embedding(
            [1]
        )


def test_normalize_rejects_zero_or_nonfinite_magnitude():
    embedder = make_embedder()

    with pytest.raises(
        PermanentIngestionError,
        match="cannot be normalized",
    ):
        embedder._normalize(
            (
                0.0,
                0.0,
            )
        )

    with pytest.raises(
        PermanentIngestionError,
        match="cannot be normalized",
    ):
        embedder._normalize(
            (
                1e308,
                1e308,
            )
        )


@pytest.mark.parametrize(
    "retry_after,expected",
    [
        (
            None,
            2.0,
        ),
        (
            "4.5",
            4.5,
        ),
        (
            "-4",
            0.0,
        ),
        (
            "90",
            60.0,
        ),
        (
            "invalid",
            2.0,
        ),
    ],
)
def test_retry_delay(
    retry_after,
    expected,
):
    assert HuggingFaceApiEmbedder._delay(
        2,
        retry_after,
    ) == expected


@pytest.mark.parametrize(
    "status",
    [
        401,
        402,
        403,
    ],
)
def test_feature_extraction_classifies_configuration_failures(
    status,
):
    client = make_client(
        make_hf_error(status)
    )

    embedder = make_embedder(
        client=client
    )

    with pytest.raises(
        IngestionConfigurationError,
        match=f"HTTP {status}",
    ):
        embedder._feature_extraction_with_retry(
            text="protocol"
        )

    assert (
        client.feature_extraction.call_count
        == 1
    )


@pytest.mark.parametrize(
    "status",
    [
        400,
        404,
        405,
        413,
        415,
        422,
    ],
)
def test_feature_extraction_classifies_permanent_failures(
    status,
):
    client = make_client(
        make_hf_error(status)
    )

    embedder = make_embedder(
        client=client
    )

    with pytest.raises(
        PermanentIngestionError,
        match=f"HTTP {status}",
    ):
        embedder._feature_extraction_with_retry(
            text="protocol"
        )

    assert (
        client.feature_extraction.call_count
        == 1
    )


def test_feature_extraction_classifies_unknown_http_failure():
    client = make_client(
        make_hf_error(418)
    )

    embedder = make_embedder(
        client=client
    )

    with pytest.raises(
        RetryableIngestionError,
        match="unclassified",
    ):
        embedder._feature_extraction_with_retry(
            text="protocol"
        )


@pytest.mark.parametrize(
    "status",
    [
        408,
        425,
        429,
        500,
        502,
        503,
        504,
    ],
)
def test_feature_extraction_retries_retryable_status(
    status,
):
    client = make_client(
        make_hf_error(
            status,
            retry_after="3",
        ),
        [1, 2],
    )

    sleep = Mock()

    embedder = make_embedder(
        client=client,
        sleep_function=sleep,
    )

    result = (
        embedder
        ._feature_extraction_with_retry(
            text="protocol"
        )
    )

    assert result == [
        1,
        2,
    ]
    sleep.assert_called_once_with(
        3.0
    )
    assert (
        client.feature_extraction.call_count
        == 2
    )


def test_feature_extraction_raises_after_retryable_status_exhausted():
    client = make_client(
        make_hf_error(503),
        make_hf_error(503),
    )

    sleep = Mock()

    embedder = make_embedder(
        client=client,
        max_attempts=2,
        sleep_function=sleep,
    )

    with pytest.raises(
        RetryableIngestionError,
        match="HTTP 503",
    ):
        embedder._feature_extraction_with_retry(
            text="protocol"
        )

    sleep.assert_called_once_with(
        1.0
    )


@pytest.mark.parametrize(
    "exception,message",
    [
        (
            httpx.ReadTimeout(
                "timeout"
            ),
            "timed out",
        ),
        (
            httpx.ConnectError(
                "offline"
            ),
            "transport failed",
        ),
    ],
)
def test_feature_extraction_retries_transport_failures(
    exception,
    message,
):
    client = make_client(
        exception,
        [1, 2],
    )

    sleep = Mock()

    embedder = make_embedder(
        client=client,
        sleep_function=sleep,
    )

    result = (
        embedder
        ._feature_extraction_with_retry(
            text="protocol"
        )
    )

    assert result == [
        1,
        2,
    ]
    sleep.assert_called_once_with(
        1.0
    )
    assert (
        client.feature_extraction.call_count
        == 2
    )


@pytest.mark.parametrize(
    "exception,message",
    [
        (
            httpx.ReadTimeout(
                "timeout"
            ),
            "timed out",
        ),
        (
            httpx.ConnectError(
                "offline"
            ),
            "transport failed",
        ),
    ],
)
def test_feature_extraction_raises_after_transport_exhausted(
    exception,
    message,
):
    client = make_client(
        exception
    )

    embedder = make_embedder(
        client=client,
        max_attempts=1,
    )

    with pytest.raises(
        RetryableIngestionError,
        match=message,
    ):
        embedder._feature_extraction_with_retry(
            text="protocol"
        )


def test_feature_extraction_defensive_fallthrough():
    embedder = make_embedder()

    embedder.max_attempts = 0

    with pytest.raises(
        RetryableIngestionError,
        match="did not complete",
    ):
        embedder._feature_extraction_with_retry(
            text="protocol"
        )


def test_hf_error_helpers_without_response():
    exception = Mock(
        spec=HfHubHTTPError
    )
    exception.response = None

    assert (
        HuggingFaceApiEmbedder._status_code(
            exception
        )
        is None
    )

    assert (
        HuggingFaceApiEmbedder._retry_after(
            exception
        )
        is None
    )


def test_required_helpers_validate_values():
    with pytest.raises(TypeError):
        HuggingFaceApiEmbedder._required(
            1,
            "field",
        )

    with pytest.raises(ValueError):
        HuggingFaceApiEmbedder._required(
            " ",
            "field",
        )

    assert HuggingFaceApiEmbedder._https_url(
        "https://example.com/",
        "url",
    ) == "https://example.com"