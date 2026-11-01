import json
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Mapping

from aws_utils.bedrock import BedrockRuntimeService
from embedders.base_embedder import BaseEmbedder
from exceptions.processing import PermanentIngestionError
from models.document import DocumentChunk
from models.embedded_chunk import EmbeddedChunk


@dataclass(frozen=True, slots=True)
class BedrockEmbeddingResponse:
    """Provider-neutral result parsed from a model-specific Bedrock response."""

    embedding: tuple[float, ...]
    input_token_count: int | None = None


class BedrockEmbeddingModelCodec(ABC):
    """Translate between the generic embedding contract and one Bedrock model API."""

    @property
    @abstractmethod
    def supported_model_ids(self) -> frozenset[str]:
        raise NotImplementedError

    @abstractmethod
    def validate_configuration(
        self,
        *,
        model_id: str,
        dimensions: int,
        normalize: bool,
        model_options: Mapping[str, Any],
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def build_request(
        self,
        *,
        text: str,
        dimensions: int,
        normalize: bool,
        model_options: Mapping[str, Any],
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def parse_response(self, payload: dict[str, Any]) -> BedrockEmbeddingResponse:
        raise NotImplementedError


class TitanTextEmbeddingsV2Codec(BedrockEmbeddingModelCodec):
    """Native request and response codec for Amazon Titan Text Embeddings V2."""

    MODEL_IDS = frozenset({"amazon.titan-embed-text-v2:0"})
    SUPPORTED_DIMENSIONS = frozenset({256, 512, 1024})

    @property
    def supported_model_ids(self) -> frozenset[str]:
        return self.MODEL_IDS

    def validate_configuration(
        self,
        *,
        model_id: str,
        dimensions: int,
        normalize: bool,
        model_options: Mapping[str, Any],
    ) -> None:
        if model_id not in self.MODEL_IDS:
            raise ValueError(
                "Titan Text Embeddings V2 codec does not support model_id "
                f"'{model_id}'."
            )
        if dimensions not in self.SUPPORTED_DIMENSIONS:
            supported = ", ".join(str(value) for value in sorted(self.SUPPORTED_DIMENSIONS))
            raise ValueError(
                "Titan Text Embeddings V2 dimensions must be one of: "
                f"{supported}."
            )
        if not isinstance(normalize, bool):
            raise TypeError("normalize must be a boolean.")
        if model_options:
            unsupported = ", ".join(sorted(model_options))
            raise ValueError(
                "Titan Text Embeddings V2 does not support the configured model "
                f"options: {unsupported}."
            )

    def build_request(
        self,
        *,
        text: str,
        dimensions: int,
        normalize: bool,
        model_options: Mapping[str, Any],
    ) -> dict[str, Any]:
        return {
            "inputText": text,
            "dimensions": dimensions,
            "normalize": normalize,
        }

    def parse_response(self, payload: dict[str, Any]) -> BedrockEmbeddingResponse:
        if not isinstance(payload, dict):
            raise TypeError("payload must be a dictionary.")
        return BedrockEmbeddingResponse(
            embedding=self._read_embedding(payload),
            input_token_count=self._read_input_token_count(payload),
        )

    def _read_embedding(self, payload: dict[str, Any]) -> tuple[float, ...]:
        embedding_value = payload.get("embedding")
        if not isinstance(embedding_value, list):
            raise PermanentIngestionError(
                "Titan embedding response does not contain an embedding list."
            )
        if not embedding_value:
            raise PermanentIngestionError(
                "Titan embedding response contains an empty embedding."
            )

        embedding: list[float] = []
        for value in embedding_value:
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise PermanentIngestionError(
                    "Titan embedding contains a nonnumeric value."
                )
            number = float(value)
            if not math.isfinite(number):
                raise PermanentIngestionError(
                    "Titan embedding contains a nonfinite value."
                )
            embedding.append(number)
        return tuple(embedding)

    def _read_input_token_count(self, payload: dict[str, Any]) -> int | None:
        value = payload.get("inputTextTokenCount")
        if value is None:
            return None
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise PermanentIngestionError(
                "Titan inputTextTokenCount must be a nonnegative integer when returned."
            )
        return value


class BedrockEmbeddingCodecRegistry:
    """Resolve a Bedrock embedding codec from a model ID."""

    def __init__(self, codecs: tuple[BedrockEmbeddingModelCodec, ...] | None = None):
        registered = codecs if codecs is not None else (TitanTextEmbeddingsV2Codec(),)
        model_codecs: dict[str, BedrockEmbeddingModelCodec] = {}
        for codec in registered:
            if not isinstance(codec, BedrockEmbeddingModelCodec):
                raise TypeError("Every codec must implement BedrockEmbeddingModelCodec.")
            for model_id in codec.supported_model_ids:
                if model_id in model_codecs:
                    raise ValueError(f"Duplicate Bedrock embedding model_id '{model_id}'.")
                model_codecs[model_id] = codec
        self._model_codecs = model_codecs

    def get(self, model_id: str) -> BedrockEmbeddingModelCodec:
        if not isinstance(model_id, str) or not model_id.strip():
            raise ValueError("model_id must be a nonblank string.")
        normalized = model_id.strip()
        codec = self._model_codecs.get(normalized)
        if codec is None:
            supported = ", ".join(sorted(self._model_codecs)) or "none"
            raise ValueError(
                f"Unsupported Bedrock embedding model_id '{normalized}'. "
                f"Supported models: {supported}."
            )
        return codec


class BedrockEmbedder(BaseEmbedder):
    """Generic Amazon Bedrock embedding adapter."""

    PROVIDER = "bedrock"

    def __init__(
        self,
        bedrock_runtime: BedrockRuntimeService,
        *,
        model_id: str,
        dimensions: int,
        normalize: bool,
        model_options: Mapping[str, Any] | None = None,
        codec_registry: BedrockEmbeddingCodecRegistry | None = None,
    ):
        if not isinstance(bedrock_runtime, BedrockRuntimeService):
            raise TypeError("bedrock_runtime must be a BedrockRuntimeService.")
        if not isinstance(model_id, str) or not model_id.strip():
            raise ValueError("model_id must be a nonblank string.")
        if not isinstance(dimensions, int) or isinstance(dimensions, bool):
            raise TypeError("dimensions must be an integer.")
        if dimensions <= 0:
            raise ValueError("dimensions must be greater than zero.")
        if not isinstance(normalize, bool):
            raise TypeError("normalize must be a boolean.")
        if model_options is not None and not isinstance(model_options, Mapping):
            raise TypeError("model_options must be a mapping or None.")
        if codec_registry is not None and not isinstance(
            codec_registry, BedrockEmbeddingCodecRegistry
        ):
            raise TypeError(
                "codec_registry must be a BedrockEmbeddingCodecRegistry or None."
            )

        normalized_options = dict(model_options or {})
        registry = codec_registry or BedrockEmbeddingCodecRegistry()
        normalized_model_id = model_id.strip()
        codec = registry.get(normalized_model_id)
        codec.validate_configuration(
            model_id=normalized_model_id,
            dimensions=dimensions,
            normalize=normalize,
            model_options=normalized_options,
        )

        self.bedrock_runtime = bedrock_runtime
        self.model_id = normalized_model_id
        self.dimensions = dimensions
        self.normalize = normalize
        self.model_options = normalized_options
        self.codec = codec

    def embed(self, chunk: DocumentChunk) -> EmbeddedChunk:
        if not isinstance(chunk, DocumentChunk):
            raise TypeError("chunk must be a DocumentChunk.")
        native_request = self.codec.build_request(
            text=chunk.text,
            dimensions=self.dimensions,
            normalize=self.normalize,
            model_options=self.model_options,
        )
        # AWS ClientError/BotoCoreError exceptions intentionally propagate to
        # EmbeddingService, which classifies transport, throttling, and permission errors.
        response = self.bedrock_runtime.invoke_model(
            model_id=self.model_id,
            body=json.dumps(native_request),
            accept="application/json",
            content_type="application/json",
        )
        parsed = self.codec.parse_response(self._read_response_payload(response))
        if len(parsed.embedding) != self.dimensions:
            raise PermanentIngestionError(
                "Bedrock embedding dimensions do not match the configured dimensions."
            )
        return EmbeddedChunk(
            chunk=chunk,
            embedding=parsed.embedding,
            embedding_provider=self.PROVIDER,
            embedding_model_id=self.model_id,
            embedding_dimensions=self.dimensions,
            embedding_normalized=self.normalize,
            input_token_count=parsed.input_token_count,
        )

    def _read_response_payload(self, response: Any) -> dict[str, Any]:
        if not isinstance(response, dict):
            raise PermanentIngestionError(
                "Bedrock embedding response must be a mapping."
            )
        response_body = response.get("body")
        if response_body is None:
            raise PermanentIngestionError(
                "Bedrock embedding response does not contain a body."
            )
        try:
            body_value = response_body.read()
        except AttributeError as exception:
            raise PermanentIngestionError(
                "Bedrock embedding response body is not readable."
            ) from exception
        try:
            body_text = body_value.decode("utf-8") if isinstance(body_value, bytes) else body_value
            payload = json.loads(body_text)
        except (TypeError, UnicodeDecodeError, json.JSONDecodeError) as exception:
            raise PermanentIngestionError(
                "Bedrock embedding response body is not valid JSON."
            ) from exception
        if not isinstance(payload, dict):
            raise PermanentIngestionError(
                "Bedrock embedding response JSON must be an object."
            )
        return payload
