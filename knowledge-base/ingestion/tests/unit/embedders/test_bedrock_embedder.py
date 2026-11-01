import json
from io import BytesIO
from typing import Any, Mapping
from unittest.mock import Mock

import pytest

from aws_utils.bedrock import BedrockRuntimeService
from embedders.bedrock_embedder import (
    BedrockEmbedder,
    BedrockEmbeddingCodecRegistry,
    BedrockEmbeddingModelCodec,
    BedrockEmbeddingResponse,
    TitanTextEmbeddingsV2Codec,
)
from exceptions.processing import PermanentIngestionError
from models.document import DocumentChunk


pytestmark = pytest.mark.unit

MODEL_ID = "amazon.titan-embed-text-v2:0"


class TestCodec(BedrockEmbeddingModelCodec):
    """Controllable codec used by BedrockEmbedder tests."""

    __test__ = False

    def __init__(
        self,
        *,
        model_ids: frozenset[str] | None = None,
        embedding: tuple[float, ...] = (0.1, 0.2),
        input_token_count: int | None = 3,
    ) -> None:
        self._model_ids = (
            model_ids
            if model_ids is not None
            else frozenset({MODEL_ID})
        )
        self.embedding = embedding
        self.input_token_count = input_token_count
        self.validate_calls: list[dict[str, Any]] = []
        self.build_calls: list[dict[str, Any]] = []
        self.parse_calls: list[dict[str, Any]] = []

    @property
    def supported_model_ids(self) -> frozenset[str]:
        return self._model_ids

    def validate_configuration(
        self,
        *,
        model_id: str,
        dimensions: int,
        normalize: bool,
        model_options: Mapping[str, Any],
    ) -> None:
        self.validate_calls.append(
            {
                "model_id": model_id,
                "dimensions": dimensions,
                "normalize": normalize,
                "model_options": dict(model_options),
            }
        )

    def build_request(
        self,
        *,
        text: str,
        dimensions: int,
        normalize: bool,
        model_options: Mapping[str, Any],
    ) -> dict[str, Any]:
        self.build_calls.append(
            {
                "text": text,
                "dimensions": dimensions,
                "normalize": normalize,
                "model_options": dict(model_options),
            }
        )

        return {
            "inputText": text,
            "dimensions": dimensions,
            "normalize": normalize,
        }

    def parse_response(
        self,
        payload: dict[str, Any],
    ) -> BedrockEmbeddingResponse:
        self.parse_calls.append(payload)

        return BedrockEmbeddingResponse(
            embedding=self.embedding,
            input_token_count=self.input_token_count,
        )


def create_chunk(
    *,
    text: str = "Clinical trial protocol",
) -> DocumentChunk:
    return DocumentChunk(
        chunk_id="chunk-001",
        ingestion_id="ingestion-001",
        ingestion_profile_id="profile-001",
        document_id="a" * 64,
        chunk_index=0,
        text=text,
        start_offset=0,
        end_offset=len(text),
        start_page=1,
        end_page=1,
        character_count=len(text),
    )


def create_runtime(
    response: object | None = None,
) -> tuple[BedrockRuntimeService, Mock]:
    client = Mock()

    if response is None:
        response = {
            "body": BytesIO(
                json.dumps(
                    {
                        "embedding": [0.1, 0.2],
                        "inputTextTokenCount": 3,
                    }
                ).encode("utf-8")
            )
        }

    client.invoke_model.return_value = response

    runtime = BedrockRuntimeService(
        region_name="ap-south-1",
        client=client,
    )

    return runtime, client


def create_registry(
    codec: BedrockEmbeddingModelCodec,
) -> BedrockEmbeddingCodecRegistry:
    return BedrockEmbeddingCodecRegistry(
        codecs=(codec,),
    )


def create_embedder(
    *,
    runtime: BedrockRuntimeService | None = None,
    codec: TestCodec | None = None,
    dimensions: int = 2,
    normalize: bool = True,
    model_options: Mapping[str, Any] | None = None,
) -> tuple[BedrockEmbedder, TestCodec, BedrockRuntimeService]:
    if runtime is None:
        runtime, _ = create_runtime()

    if codec is None:
        codec = TestCodec(
            embedding=tuple(0.1 for _ in range(dimensions)),
        )

    embedder = BedrockEmbedder(
        bedrock_runtime=runtime,
        model_id=f" {MODEL_ID} ",
        dimensions=dimensions,
        normalize=normalize,
        model_options=model_options,
        codec_registry=create_registry(codec),
    )

    return embedder, codec, runtime


def test_registry_uses_titan_codec_by_default() -> None:
    registry = BedrockEmbeddingCodecRegistry()

    codec = registry.get(MODEL_ID)

    assert isinstance(codec, TitanTextEmbeddingsV2Codec)


def test_abstract_codec_methods_raise_not_implemented() -> None:
    class IncompleteCodec(BedrockEmbeddingModelCodec):
        @property
        def supported_model_ids(self):
            return super().supported_model_ids

        def validate_configuration(self, *, model_id, dimensions, normalize, model_options):
            return super().validate_configuration(
                model_id=model_id,
                dimensions=dimensions,
                normalize=normalize,
                model_options=model_options,
            )

        def build_request(self, *, text, dimensions, normalize, model_options):
            return super().build_request(
                text=text,
                dimensions=dimensions,
                normalize=normalize,
                model_options=model_options,
            )

        def parse_response(self, payload):
            return super().parse_response(payload)

    codec = IncompleteCodec()
    with pytest.raises(NotImplementedError):
        _ = codec.supported_model_ids
    with pytest.raises(NotImplementedError):
        codec.validate_configuration(
            model_id=MODEL_ID,
            dimensions=2,
            normalize=True,
            model_options={},
        )
    with pytest.raises(NotImplementedError):
        codec.build_request(text="text", dimensions=2, normalize=True, model_options={})
    with pytest.raises(NotImplementedError):
        codec.parse_response({})


def test_registry_returns_custom_codec() -> None:
    codec = TestCodec()
    registry = create_registry(codec)

    assert registry.get(MODEL_ID) is codec


def test_registry_trims_model_id() -> None:
    codec = TestCodec()
    registry = create_registry(codec)

    assert registry.get(f" {MODEL_ID} ") is codec


def test_registry_allows_no_registered_codecs() -> None:
    registry = BedrockEmbeddingCodecRegistry(codecs=())

    with pytest.raises(
        ValueError,
        match="Supported models: none",
    ):
        registry.get("unknown-model")


def test_registry_rejects_non_codec() -> None:
    with pytest.raises(
        TypeError,
        match="Every codec must implement BedrockEmbeddingModelCodec",
    ):
        BedrockEmbeddingCodecRegistry(
            codecs=(object(),),  # type: ignore[arg-type]
        )


def test_registry_rejects_duplicate_model_id() -> None:
    with pytest.raises(
        ValueError,
        match="Duplicate Bedrock embedding model_id",
    ):
        BedrockEmbeddingCodecRegistry(
            codecs=(TestCodec(), TestCodec()),
        )


@pytest.mark.parametrize(
    "model_id",
    ["", " ", "\n", None, 123],
)
def test_registry_rejects_invalid_model_id(
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


def test_constructor_normalizes_and_validates() -> None:
    runtime, _ = create_runtime()
    codec = TestCodec(embedding=(0.1, 0.2))
    options = {"option": "value"}

    embedder = BedrockEmbedder(
        bedrock_runtime=runtime,
        model_id=f" {MODEL_ID} ",
        dimensions=2,
        normalize=False,
        model_options=options,
        codec_registry=create_registry(codec),
    )

    assert embedder.bedrock_runtime is runtime
    assert embedder.model_id == MODEL_ID
    assert embedder.dimensions == 2
    assert embedder.normalize is False
    assert embedder.model_options == options
    assert embedder.model_options is not options
    assert embedder.codec is codec
    assert codec.validate_calls == [
        {
            "model_id": MODEL_ID,
            "dimensions": 2,
            "normalize": False,
            "model_options": options,
        }
    ]


def test_constructor_converts_none_options_to_empty_mapping() -> None:
    runtime, _ = create_runtime()
    codec = TestCodec()

    embedder = BedrockEmbedder(
        bedrock_runtime=runtime,
        model_id=MODEL_ID,
        dimensions=2,
        normalize=True,
        model_options=None,
        codec_registry=create_registry(codec),
    )

    assert embedder.model_options == {}
    assert codec.validate_calls == [
        {
            "model_id": MODEL_ID,
            "dimensions": 2,
            "normalize": True,
            "model_options": {},
        }
    ]


def test_constructor_uses_default_registry() -> None:
    runtime, _ = create_runtime()

    embedder = BedrockEmbedder(
        bedrock_runtime=runtime,
        model_id=MODEL_ID,
        dimensions=256,
        normalize=True,
    )

    assert isinstance(embedder.codec, TitanTextEmbeddingsV2Codec)


def test_constructor_rejects_invalid_runtime() -> None:
    with pytest.raises(
        TypeError,
        match="bedrock_runtime must be a BedrockRuntimeService",
    ):
        BedrockEmbedder(
            bedrock_runtime=object(),  # type: ignore[arg-type]
            model_id=MODEL_ID,
            dimensions=256,
            normalize=True,
        )


@pytest.mark.parametrize(
    "model_id",
    ["", " ", "\n", None, 123],
)
def test_constructor_rejects_invalid_model_id(
    model_id: object,
) -> None:
    runtime, _ = create_runtime()

    with pytest.raises(
        ValueError,
        match="model_id must be a nonblank string",
    ):
        BedrockEmbedder(
            bedrock_runtime=runtime,
            model_id=model_id,  # type: ignore[arg-type]
            dimensions=256,
            normalize=True,
        )


@pytest.mark.parametrize(
    "dimensions",
    [None, "256", 1.5, True, False],
)
def test_constructor_requires_integer_dimensions(
    dimensions: object,
) -> None:
    runtime, _ = create_runtime()

    with pytest.raises(
        TypeError,
        match="dimensions must be an integer",
    ):
        BedrockEmbedder(
            bedrock_runtime=runtime,
            model_id=MODEL_ID,
            dimensions=dimensions,  # type: ignore[arg-type]
            normalize=True,
        )


@pytest.mark.parametrize(
    "dimensions",
    [0, -1, -256],
)
def test_constructor_requires_positive_dimensions(
    dimensions: int,
) -> None:
    runtime, _ = create_runtime()

    with pytest.raises(
        ValueError,
        match="dimensions must be greater than zero",
    ):
        BedrockEmbedder(
            bedrock_runtime=runtime,
            model_id=MODEL_ID,
            dimensions=dimensions,
            normalize=True,
        )


@pytest.mark.parametrize(
    "normalize",
    [None, "true", 1, 0],
)
def test_constructor_requires_boolean_normalize(
    normalize: object,
) -> None:
    runtime, _ = create_runtime()

    with pytest.raises(
        TypeError,
        match="normalize must be a boolean",
    ):
        BedrockEmbedder(
            bedrock_runtime=runtime,
            model_id=MODEL_ID,
            dimensions=256,
            normalize=normalize,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "model_options",
    [[], (), "options", 123],
)
def test_constructor_requires_mapping_options(
    model_options: object,
) -> None:
    runtime, _ = create_runtime()

    with pytest.raises(
        TypeError,
        match="model_options must be a mapping or None",
    ):
        BedrockEmbedder(
            bedrock_runtime=runtime,
            model_id=MODEL_ID,
            dimensions=256,
            normalize=True,
            model_options=model_options,  # type: ignore[arg-type]
        )


def test_constructor_rejects_invalid_registry() -> None:
    runtime, _ = create_runtime()

    with pytest.raises(
        TypeError,
        match=(
            "codec_registry must be a "
            "BedrockEmbeddingCodecRegistry or None"
        ),
    ):
        BedrockEmbedder(
            bedrock_runtime=runtime,
            model_id=MODEL_ID,
            dimensions=256,
            normalize=True,
            codec_registry=object(),  # type: ignore[arg-type]
        )


def test_embed_returns_embedded_chunk() -> None:
    runtime, client = create_runtime(
        {
            "body": BytesIO(
                json.dumps(
                    {"result": "provider-result"}
                ).encode("utf-8")
            )
        }
    )
    codec = TestCodec(
        embedding=(0.1, 0.2),
        input_token_count=7,
    )
    embedder, _, _ = create_embedder(
        runtime=runtime,
        codec=codec,
        dimensions=2,
        normalize=True,
        model_options={"option": "value"},
    )
    chunk = create_chunk()

    result = embedder.embed(chunk)

    assert result.chunk is chunk
    assert result.embedding == (0.1, 0.2)
    assert result.embedding_provider == "bedrock"
    assert result.embedding_model_id == MODEL_ID
    assert result.embedding_dimensions == 2
    assert result.embedding_normalized is True
    assert result.input_token_count == 7
    assert codec.build_calls == [
        {
            "text": chunk.text,
            "dimensions": 2,
            "normalize": True,
            "model_options": {"option": "value"},
        }
    ]
    assert codec.parse_calls == [
        {"result": "provider-result"}
    ]
    client.invoke_model.assert_called_once_with(
        modelId=MODEL_ID,
        body=json.dumps(
            {
                "inputText": chunk.text,
                "dimensions": 2,
                "normalize": True,
            }
        ),
        accept="application/json",
        contentType="application/json",
    )


def test_embed_rejects_non_chunk() -> None:
    embedder, _, _ = create_embedder()

    with pytest.raises(
        TypeError,
        match="chunk must be a DocumentChunk",
    ):
        embedder.embed(object())  # type: ignore[arg-type]


def test_embed_propagates_runtime_exception() -> None:
    runtime, client = create_runtime()
    client.invoke_model.side_effect = RuntimeError(
        "Bedrock unavailable"
    )
    embedder, _, _ = create_embedder(runtime=runtime)

    with pytest.raises(
        RuntimeError,
        match="Bedrock unavailable",
    ):
        embedder.embed(create_chunk())


def test_embed_rejects_dimension_mismatch() -> None:
    runtime, _ = create_runtime()
    codec = TestCodec(embedding=(0.1,))
    embedder, _, _ = create_embedder(
        runtime=runtime,
        codec=codec,
        dimensions=2,
    )

    with pytest.raises(
        PermanentIngestionError,
        match="embedding dimensions do not match",
    ):
        embedder.embed(create_chunk())


def test_read_response_payload_accepts_bytes() -> None:
    embedder, _, _ = create_embedder()

    result = embedder._read_response_payload(
        {
            "body": BytesIO(
                b'{"embedding":[0.1,0.2]}'
            )
        }
    )

    assert result == {"embedding": [0.1, 0.2]}


def test_read_response_payload_accepts_text() -> None:
    embedder, _, _ = create_embedder()
    body = Mock()
    body.read.return_value = '{"embedding":[0.1,0.2]}'

    result = embedder._read_response_payload(
        {"body": body}
    )

    assert result == {"embedding": [0.1, 0.2]}


@pytest.mark.parametrize(
    "response",
    [None, [], "response", 123],
)
def test_read_response_payload_requires_mapping(
    response: object,
) -> None:
    embedder, _, _ = create_embedder()

    with pytest.raises(
        PermanentIngestionError,
        match="response must be a mapping",
    ):
        embedder._read_response_payload(response)


def test_read_response_payload_requires_body() -> None:
    embedder, _, _ = create_embedder()

    with pytest.raises(
        PermanentIngestionError,
        match="response does not contain a body",
    ):
        embedder._read_response_payload({})


def test_read_response_payload_requires_readable_body() -> None:
    embedder, _, _ = create_embedder()

    with pytest.raises(
        PermanentIngestionError,
        match="body is not readable",
    ):
        embedder._read_response_payload(
            {"body": object()}
        )


@pytest.mark.parametrize(
    "body_value",
    [b"\xff", b"not-json", "not-json", None, 123],
)
def test_read_response_payload_rejects_invalid_json(
    body_value: object,
) -> None:
    embedder, _, _ = create_embedder()
    body = Mock()
    body.read.return_value = body_value

    with pytest.raises(
        PermanentIngestionError,
        match="body is not valid JSON",
    ):
        embedder._read_response_payload(
            {"body": body}
        )


@pytest.mark.parametrize(
    "body_value",
    ["[]", '"text"', "123", "null"],
)
def test_read_response_payload_requires_json_object(
    body_value: str,
) -> None:
    embedder, _, _ = create_embedder()
    body = Mock()
    body.read.return_value = body_value

    with pytest.raises(
        PermanentIngestionError,
        match="response JSON must be an object",
    ):
        embedder._read_response_payload(
            {"body": body}
        )