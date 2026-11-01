from unittest.mock import patch
import pytest
from embedders.embedder_factory import EmbedderFactory
from models.ingestion_profile import IngestionProfile


pytestmark = pytest.mark.unit


def test_creates_bedrock_embedder(profile_factory) -> None:
    profile = profile_factory(embedding_provider="bedrock")
    runtime = object()

    with patch(
        "embedders.embedder_factory."
        "BedrockEmbedder"
    ) as embedder_class:
        result = EmbedderFactory.create(
            profile,
            aws_region="ap-south-1",
            bedrock_runtime=runtime,
        )

    assert result is embedder_class.return_value

    embedder_class.assert_called_once_with(
        bedrock_runtime=runtime,
        model_id="amazon.titan-embed-text-v2:0",
        dimensions=1024,
        normalize=True,
        model_options={},
    )


def test_creates_huggingface_api_embedder(
    profile_factory,
) -> None:
    profile = profile_factory(
        embedding_provider="huggingface-api",
        embedding_model_id=(
            "sentence-transformers/"
            "all-MiniLM-L6-v2"
        ),
        embedding_dimensions=384,
    )

    with patch(
        "embedders.embedder_factory."
        "HuggingFaceApiEmbedder"
    ) as embedder_class:
        result = EmbedderFactory.create(
            profile,
            huggingface_api_token="test-token",
            huggingface_api_provider="hf-inference",
            huggingface_api_base_url=(
                "https://router.huggingface.co"
            ),
            huggingface_api_timeout_seconds=60,
            huggingface_api_max_attempts=3,
        )

    assert result is embedder_class.return_value

    embedder_class.assert_called_once_with(
        model_id=(
            "sentence-transformers/"
            "all-MiniLM-L6-v2"
        ),
        dimensions=384,
        normalize=True,
        api_token="test-token",
        api_provider="hf-inference",
        api_base_url=(
            "https://router.huggingface.co"
        ),
        timeout_seconds=60,
        max_attempts=3,
    )


def test_huggingface_api_uses_empty_token_by_default(
    profile_factory,
) -> None:
    profile = profile_factory(
        embedding_provider="huggingface-api",
        embedding_model_id="test-model",
        embedding_dimensions=384,
    )

    with patch(
        "embedders.embedder_factory."
        "HuggingFaceApiEmbedder"
    ) as embedder_class:
        EmbedderFactory.create(profile)

    assert embedder_class.call_args.kwargs["api_token"] == ""


def test_huggingface_api_rejects_model_options(
    profile_factory,
) -> None:
    profile = profile_factory(
        embedding_provider="huggingface-api",
        embedding_model_id="test-model",
        embedding_dimensions=384,
        embedding_model_options_json=(
            '{"option":"value"}'
        ),
    )

    with pytest.raises(
        ValueError,
        match=(
            "huggingface-api does not currently "
            "support EMBEDDING_MODEL_OPTIONS"
        ),
    ):
        EmbedderFactory.create(profile)


def test_rejects_unknown_provider(
    profile_factory,
) -> None:
    profile = profile_factory(
        embedding_provider="other",
    )

    with pytest.raises(
        ValueError,
        match=(
            "Unsupported embedding_provider "
            "'other'"
        ),
    ):
        EmbedderFactory.create(profile)


def test_rejects_non_profile() -> None:
    with pytest.raises(
        TypeError,
        match="profile must be an IngestionProfile",
    ):
        EmbedderFactory.create(
            None,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "options",
    ["not-json", "[]"],
)
def test_read_model_options_rejects_corrupt_profile(options):
    profile = object.__new__(IngestionProfile)
    object.__setattr__(profile, "embedding_model_options_json", options)

    with pytest.raises(RuntimeError):
        EmbedderFactory._read_model_options(profile)
