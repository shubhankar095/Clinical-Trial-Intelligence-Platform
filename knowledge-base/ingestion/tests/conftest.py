import pytest
from models.ingestion_profile import IngestionProfile

@pytest.fixture
def profile_factory():
    def create(**overrides):
        values = dict(
            ingestion_schema_version="ingestion-v1",
            chunker_type="recursive_character",
            chunker_version="1",
            chunk_size=1000,
            chunk_overlap=100,
            embedding_provider="bedrock",
            embedding_model_id="amazon.titan-embed-text-v2:0",
            embedding_dimensions=1024,
            embedding_normalize=True,
            embedding_model_options_json="{}",
            index_schema_version="v1",
        )
        values.update(overrides)
        return IngestionProfile(**values)
    return create


@pytest.fixture
def canonical_fixture_dir():
    from pathlib import Path
    candidates = list((Path(__file__).parent / "data" / "canonical-documents").glob("*/extracted-document.json"))
    if len(candidates) != 1:
        raise RuntimeError("Expected exactly one canonical document fixture.")
    return candidates[0].parent


@pytest.fixture
def executable_profile(profile_factory):
    return profile_factory(chunker_type="page-aware-recursive-character")

########################################################################

########################################################################
