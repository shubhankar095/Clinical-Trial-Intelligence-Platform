from __future__ import annotations

import math
import time
from collections.abc import Callable
from typing import Any, Protocol
from urllib.parse import quote, urlparse

import httpx
from huggingface_hub import InferenceClient
from huggingface_hub.errors import HfHubHTTPError

from embedders.base_embedder import BaseEmbedder
from exceptions.processing import (
    IngestionConfigurationError,
    PermanentIngestionError,
    RetryableIngestionError,
)
from models.document import DocumentChunk
from models.embedded_chunk import EmbeddedChunk


class FeatureExtractionClient(Protocol):
    """Client interface required for Hugging Face feature extraction."""

    def feature_extraction(
        self,
        text: str,
        *,
        model: str,
    ) -> Any:
        """Return an embedding for the supplied text."""


class HuggingFaceApiEmbedder(BaseEmbedder):
    """Managed Hugging Face feature-extraction adapter."""

    PROVIDER = "huggingface-api"

    RETRYABLE_STATUS_CODES = frozenset(
        {
            408,
            425,
            429,
            500,
            502,
            503,
            504,
        }
    )

    CONFIGURATION_STATUS_CODES = frozenset(
        {
            401,
            402,
            403,
        }
    )

    PERMANENT_STATUS_CODES = frozenset(
        {
            400,
            404,
            405,
            413,
            415,
            422,
        }
    )

    def __init__(
        self,
        *,
        model_id: str,
        dimensions: int,
        normalize: bool,
        api_token: str,
        api_provider: str = "hf-inference",
        api_base_url: str = "https://router.huggingface.co",
        timeout_seconds: int = 60,
        max_attempts: int = 3,
        client: FeatureExtractionClient | None = None,
        sleep_function: Callable[[float], None] | None = None,
    ) -> None:
        self.model_id = self._required(
            model_id,
            "model_id",
        )
        self.api_token = self._required(
            api_token,
            "api_token",
        )
        self.api_provider = self._required(
            api_provider,
            "api_provider",
        )
        self.api_base_url = self._https_url(
            api_base_url,
            "api_base_url",
        )

        self._positive(
            dimensions,
            "dimensions",
        )
        self._positive(
            timeout_seconds,
            "timeout_seconds",
        )
        self._positive(
            max_attempts,
            "max_attempts",
        )

        if not isinstance(normalize, bool):
            raise TypeError(
                "normalize must be a boolean."
            )

        self.dimensions = dimensions
        self.normalize = normalize
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max_attempts

        self._client: FeatureExtractionClient = (
            client
            if client is not None
            else InferenceClient(
                provider=self.api_provider,
                api_key=self.api_token,
                timeout=float(
                    self.timeout_seconds
                ),
            )
        )

        self._sleep = (
            sleep_function
            or time.sleep
        )

    @property
    def endpoint(self) -> str:
        """Return the resolved provider route for diagnostics."""

        return (
            f"{self.api_base_url}/"
            f"{quote(self.api_provider, safe='')}"
            f"/models/"
            f"{quote(self.model_id, safe='/')}"
        )

    def embed(
        self,
        chunk: DocumentChunk,
    ) -> EmbeddedChunk:
        if not isinstance(
            chunk,
            DocumentChunk,
        ):
            raise TypeError(
                "chunk must be a DocumentChunk."
            )

        if not chunk.text.strip():
            raise PermanentIngestionError(
                "Chunk text must not be blank."
            )

        response_payload = (
            self._feature_extraction_with_retry(
                text=chunk.text,
            )
        )

        embedding = self._parse_embedding(
            response_payload
        )

        if self.normalize:
            embedding = self._normalize(
                embedding
            )

        return EmbeddedChunk(
            chunk=chunk,
            embedding=embedding,
            embedding_provider=self.PROVIDER,
            embedding_model_id=self.model_id,
            embedding_dimensions=self.dimensions,
            embedding_normalized=self.normalize,
            input_token_count=None,
        )

    def close(self) -> None:
        """Retained for compatibility with the embedder lifecycle."""

    def _feature_extraction_with_retry(
        self,
        *,
        text: str,
    ) -> Any:
        for attempt in range(
            1,
            self.max_attempts + 1,
        ):
            try:
                return (
                    self._client.feature_extraction(
                        text,
                        model=self.model_id,
                    )
                )

            except HfHubHTTPError as exception:
                status = self._status_code(
                    exception
                )

                if (
                    status
                    in self.CONFIGURATION_STATUS_CODES
                ):
                    raise IngestionConfigurationError(
                        "Hugging Face feature-extraction "
                        "authorization, credits, or billing "
                        f"failed with HTTP {status}."
                    ) from exception

                if (
                    status
                    in self.PERMANENT_STATUS_CODES
                ):
                    raise PermanentIngestionError(
                        "Hugging Face feature-extraction "
                        "request was rejected with "
                        f"HTTP {status}."
                    ) from exception

                if (
                    status
                    not in self.RETRYABLE_STATUS_CODES
                ):
                    raise RetryableIngestionError(
                        "Hugging Face feature-extraction "
                        "request failed with an unclassified "
                        "provider response."
                    ) from exception

                if attempt == self.max_attempts:
                    raise RetryableIngestionError(
                        "Hugging Face feature-extraction "
                        "API remained unavailable with "
                        f"HTTP {status}."
                    ) from exception

                self._sleep(
                    self._delay(
                        attempt,
                        self._retry_after(
                            exception
                        ),
                    )
                )

            except httpx.TimeoutException as exception:
                if attempt == self.max_attempts:
                    raise RetryableIngestionError(
                        "Hugging Face feature-extraction "
                        "request timed out after all "
                        "attempts."
                    ) from exception

                self._sleep(
                    self._delay(
                        attempt,
                        None,
                    )
                )

            except httpx.RequestError as exception:
                if attempt == self.max_attempts:
                    raise RetryableIngestionError(
                        "Hugging Face feature-extraction "
                        "transport failed after all "
                        "attempts."
                    ) from exception

                self._sleep(
                    self._delay(
                        attempt,
                        None,
                    )
                )

        raise RetryableIngestionError(
            "Hugging Face feature-extraction "
            "request did not complete."
        )

    def _parse_embedding(
        self,
        payload: Any,
    ) -> tuple[float, ...]:
        value = (
            payload.tolist()
            if hasattr(
                payload,
                "tolist",
            )
            else payload
        )

        if isinstance(value, dict):
            if "error" in value:
                raise PermanentIngestionError(
                    "Hugging Face returned an "
                    "error payload."
                )

            value = value.get(
                "embedding",
                value.get("embeddings"),
            )

        while (
            isinstance(value, list)
            and len(value) == 1
            and isinstance(value[0], list)
        ):
            value = value[0]

        if (
            not isinstance(value, list)
            or not value
        ):
            raise PermanentIngestionError(
                "Hugging Face response does not "
                "contain an embedding vector."
            )

        vector: list[float] = []

        for item in value:
            if (
                not isinstance(
                    item,
                    (int, float),
                )
                or isinstance(item, bool)
            ):
                raise PermanentIngestionError(
                    "Hugging Face embedding contains "
                    "a nonnumeric value."
                )

            number = float(item)

            if not math.isfinite(number):
                raise PermanentIngestionError(
                    "Hugging Face embedding contains "
                    "a nonfinite value."
                )

            vector.append(number)

        if len(vector) != self.dimensions:
            raise PermanentIngestionError(
                "Embedding dimension mismatch: "
                f"configured={self.dimensions}, "
                f"returned={len(vector)}."
            )

        return tuple(vector)

    def _normalize(
        self,
        vector: tuple[float, ...],
    ) -> tuple[float, ...]:
        magnitude = math.sqrt(
            sum(
                value * value
                for value in vector
            )
        )

        if (
            magnitude == 0.0
            or not math.isfinite(
                magnitude
            )
        ):
            raise PermanentIngestionError(
                "Embedding vector cannot be "
                "normalized."
            )

        return tuple(
            value / magnitude
            for value in vector
        )

    @staticmethod
    def _status_code(
        exception: HfHubHTTPError,
    ) -> int | None:
        response = getattr(
            exception,
            "response",
            None,
        )

        status = getattr(
            response,
            "status_code",
            None,
        )

        return (
            status
            if isinstance(status, int)
            else None
        )

    @staticmethod
    def _retry_after(
        exception: HfHubHTTPError,
    ) -> str | None:
        response = getattr(
            exception,
            "response",
            None,
        )

        headers = getattr(
            response,
            "headers",
            None,
        )

        if headers is None:
            return None

        return headers.get(
            "Retry-After"
        )

    @staticmethod
    def _delay(
        attempt: int,
        retry_after: str | None,
    ) -> float:
        if retry_after is not None:
            try:
                return max(
                    0.0,
                    min(
                        float(
                            retry_after
                        ),
                        60.0,
                    ),
                )
            except ValueError:
                pass

        return float(
            min(
                2 ** (attempt - 1),
                30,
            )
        )

    @staticmethod
    def _required(
        value: str,
        name: str,
    ) -> str:
        if not isinstance(value, str):
            raise TypeError(
                f"{name} must be a string."
            )

        value = value.strip()

        if not value:
            raise ValueError(
                f"{name} must not be blank."
            )

        return value

    @classmethod
    def _https_url(
        cls,
        value: str,
        name: str,
    ) -> str:
        value = cls._required(
            value,
            name,
        ).rstrip("/")

        parsed = urlparse(
            value
        )

        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                f"{name} must be an HTTPS URL "
                "without query or fragment."
            )

        return value

    @staticmethod
    def _positive(
        value: int,
        name: str,
    ) -> None:
        if (
            not isinstance(value, int)
            or isinstance(value, bool)
        ):
            raise TypeError(
                f"{name} must be an integer."
            )

        if value <= 0:
            raise ValueError(
                f"{name} must be greater "
                "than zero."
            )