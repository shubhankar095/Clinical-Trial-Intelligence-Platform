from unittest.mock import patch
import pytest
from chunkers.chunker_factory import ChunkerFactory
pytestmark=pytest.mark.unit

def test_creates_recursive_chunker(profile_factory) -> None:
    profile=profile_factory(chunker_type="page-aware-recursive-character")
    with patch("chunkers.chunker_factory.RecursiveCharacterChunker") as chunker_class:
        result=ChunkerFactory.create(profile)
    assert result is chunker_class.return_value
    chunker_class.assert_called_once_with()

def test_rejects_unknown_chunker(profile_factory) -> None:
    profile = profile_factory(chunker_type="unknown")
    with pytest.raises(ValueError, match="Unsupported chunker_type 'unknown'"):
        ChunkerFactory.create(profile)


def test_rejects_non_profile() -> None:
    with pytest.raises(TypeError, match="profile must be an IngestionProfile"):
        ChunkerFactory.create(None)  # type: ignore[arg-type]
