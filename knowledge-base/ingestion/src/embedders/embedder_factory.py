import json

from aws_utils.bedrock import BedrockRuntimeService
from embedders.base_embedder import BaseEmbedder
from embedders.bedrock_embedder import BedrockEmbedder
from embedders.huggingface_api_embedder import HuggingFaceApiEmbedder
from models.ingestion_profile import IngestionProfile


class EmbedderFactory:
    """Create either the development API embedder or production Bedrock embedder."""

    BEDROCK_PROVIDER = "bedrock"
    HUGGINGFACE_API_PROVIDER = "huggingface-api"

    @classmethod
    def create(
        cls,
        profile: IngestionProfile,
        *,
        aws_region: str | None = None,
        bedrock_runtime: BedrockRuntimeService | None = None,
        huggingface_api_token: str | None = None,
        huggingface_api_provider: str = "hf-inference",
        huggingface_api_base_url: str = "https://router.huggingface.co",
        huggingface_api_timeout_seconds: int = 60,
        huggingface_api_max_attempts: int = 3,
    ) -> BaseEmbedder:

        if not isinstance(profile, IngestionProfile):
            raise TypeError("profile must be an IngestionProfile.")
        
        options = cls._read_model_options(profile)

        if profile.embedding_provider == cls.BEDROCK_PROVIDER:
            runtime = bedrock_runtime or BedrockRuntimeService(region_name=aws_region)
            return BedrockEmbedder(
                bedrock_runtime=runtime,
                model_id=profile.embedding_model_id,
                dimensions=profile.embedding_dimensions,
                normalize=profile.embedding_normalize,
                model_options=options,
            )

        if profile.embedding_provider == cls.HUGGINGFACE_API_PROVIDER:
            if options:
                raise ValueError("huggingface-api does not currently support EMBEDDING_MODEL_OPTIONS.")
            return HuggingFaceApiEmbedder(
                model_id=profile.embedding_model_id,
                dimensions=profile.embedding_dimensions,
                normalize=profile.embedding_normalize,
                api_token=huggingface_api_token or "",
                api_provider=huggingface_api_provider,
                api_base_url=huggingface_api_base_url,
                timeout_seconds=huggingface_api_timeout_seconds,
                max_attempts=huggingface_api_max_attempts,
            )

        raise ValueError(f"Unsupported embedding_provider '{profile.embedding_provider}'.")

    @staticmethod
    def _read_model_options(profile: IngestionProfile) -> dict:

        try:
            value = json.loads(profile.embedding_model_options_json)

        except json.JSONDecodeError as exception:
            raise RuntimeError("Ingestion profile embedding model options are invalid JSON.") from exception
        
        if not isinstance(value, dict):
            raise RuntimeError("Ingestion profile embedding model options must be an object.")
        
        return value
