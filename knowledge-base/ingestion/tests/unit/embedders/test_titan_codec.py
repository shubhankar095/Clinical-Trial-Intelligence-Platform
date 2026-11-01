import math
import pytest
from embedders.bedrock_embedder import BedrockEmbeddingCodecRegistry, TitanTextEmbeddingsV2Codec
from exceptions.processing import PermanentIngestionError


pytestmark = pytest.mark.unit

MODEL_ID = "amazon.titan-embed-text-v2:0"


def test_supported_model_ids() -> None:
    codec = TitanTextEmbeddingsV2Codec()

    assert codec.supported_model_ids == frozenset({MODEL_ID})


@pytest.mark.parametrize("dimensions", [256, 512, 1024])
def test_accepts_supported_dimensions(dimensions: int) -> None:
    codec = TitanTextEmbeddingsV2Codec()

    codec.validate_configuration(
        model_id=MODEL_ID,
        dimensions=dimensions,
        normalize=True,
        model_options={},
    )


@pytest.mark.parametrize("dimensions", [0, 128, 2048])
def test_rejects_unsupported_dimensions(dimensions: int) -> None:
    codec = TitanTextEmbeddingsV2Codec()

    with pytest.raises(ValueError, match="dimensions must be one of"):
        codec.validate_configuration(
            model_id=MODEL_ID,
            dimensions=dimensions,
            normalize=True,
            model_options={},
        )


def test_rejects_unsupported_model() -> None:
    codec = TitanTextEmbeddingsV2Codec()

    with pytest.raises(ValueError, match="does not support model_id"):
        codec.validate_configuration(
            model_id="unsupported-model",
            dimensions=1024,
            normalize=True,
            model_options={},
        )


def test_rejects_nonboolean_normalize() -> None:
    codec = TitanTextEmbeddingsV2Codec()

    with pytest.raises(TypeError, match="normalize must be a boolean"):
        codec.validate_configuration(
            model_id=MODEL_ID,
            dimensions=1024,
            normalize="true",  # type: ignore[arg-type]
            model_options={},
        )


def test_rejects_model_options() -> None:
    codec = TitanTextEmbeddingsV2Codec()

    with pytest.raises(ValueError, match=("does not support the configured model options")):
        codec.validate_configuration(
            model_id=MODEL_ID,
            dimensions=1024,
            normalize=True,
            model_options={"option": "value"},
        )


def test_build_request() -> None:
    codec = TitanTextEmbeddingsV2Codec()

    request = codec.build_request(
        text="Clinical trial protocol",
        dimensions=1024,
        normalize=True,
        model_options={},
    )

    assert request == {
        "inputText": "Clinical trial protocol",
        "dimensions": 1024,
        "normalize": True,
    }


def test_parse_response() -> None:
    codec = TitanTextEmbeddingsV2Codec()

    response = codec.parse_response(
        {
            "embedding": [0.1, 0.2],
            "inputTextTokenCount": 3,
        }
    )

    assert response.embedding == (0.1, 0.2)
    assert response.input_token_count == 3


def test_parse_response_allows_missing_token_count() -> None:
    codec = TitanTextEmbeddingsV2Codec()

    response = codec.parse_response(
        {"embedding": [0.1, 0.2]}
    )

    assert response.embedding == (0.1, 0.2)
    assert response.input_token_count is None


def test_parse_response_rejects_non_dictionary() -> None:
    codec = TitanTextEmbeddingsV2Codec()

    with pytest.raises(
        TypeError,
        match="payload must be a dictionary",
    ):
        codec.parse_response([])  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "embedding",
    [None, "not-a-list", {}],
)
def test_parse_response_requires_embedding_list(
    embedding: object,
) -> None:
    codec = TitanTextEmbeddingsV2Codec()

    with pytest.raises(
        PermanentIngestionError,
        match="does not contain an embedding list",
    ):
        codec.parse_response({"embedding": embedding})


def test_parse_response_rejects_empty_embedding() -> None:
    codec = TitanTextEmbeddingsV2Codec()

    with pytest.raises(
        PermanentIngestionError,
        match="contains an empty embedding",
    ):
        codec.parse_response({"embedding": []})


@pytest.mark.parametrize(
    "value",
    ["0.1", None, True, {}, []],
)
def test_parse_response_rejects_nonnumeric_values(
    value: object,
) -> None:
    codec = TitanTextEmbeddingsV2Codec()

    with pytest.raises(
        PermanentIngestionError,
        match="contains a nonnumeric value",
    ):
        codec.parse_response(
            {"embedding": [0.1, value]}
        )


@pytest.mark.parametrize(
    "value",
    [math.nan, math.inf, -math.inf],
)
def test_parse_response_rejects_nonfinite_values(
    value: float,
) -> None:
    codec = TitanTextEmbeddingsV2Codec()

    with pytest.raises(
        PermanentIngestionError,
        match="contains a nonfinite value",
    ):
        codec.parse_response(
            {"embedding": [0.1, value]}
        )


@pytest.mark.parametrize(
    "token_count",
    [-1, 1.5, "3", True],
)
def test_parse_response_rejects_invalid_token_count(
    token_count: object,
) -> None:
    codec = TitanTextEmbeddingsV2Codec()

    with pytest.raises(
        PermanentIngestionError,
        match=(
            "inputTextTokenCount must be "
            "a nonnegative integer"
        ),
    ):
        codec.parse_response(
            {
                "embedding": [0.1, 0.2],
                "inputTextTokenCount": token_count,
            }
        )


def test_registry_returns_titan_codec() -> None:
    registry = BedrockEmbeddingCodecRegistry()

    codec = registry.get(MODEL_ID)

    assert isinstance(codec, TitanTextEmbeddingsV2Codec)


@pytest.mark.parametrize(
    "model_id",
    ["", " ", None],
)
def test_registry_rejects_blank_model_id(
    model_id: object,
) -> None:
    registry = BedrockEmbeddingCodecRegistry()

    with pytest.raises(
        ValueError,
        match="model_id must be a nonblank string",
    ):
        registry.get(model_id)  # type: ignore[arg-type]


def test_registry_rejects_unknown_model() -> None:
    registry = BedrockEmbeddingCodecRegistry()

    with pytest.raises(
        ValueError,
        match="Unsupported Bedrock embedding model_id",
    ):
        registry.get("unknown-model")
