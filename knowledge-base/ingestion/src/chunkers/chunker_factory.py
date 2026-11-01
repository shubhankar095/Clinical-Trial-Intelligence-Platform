from chunkers.base_chunker import (
    BaseChunker,
)
from chunkers.recursive_character_chunker import (
    RecursiveCharacterChunker,
)
from models.ingestion_profile import (
    IngestionProfile,
)


class ChunkerFactory:
    """
    Create the configured chunking strategy.

    Adding a new chunker should require changing
    only this factory and adding the new chunker
    implementation.
    """

    RECURSIVE_CHARACTER_TYPE = (
        "page-aware-recursive-character"
    )

    @classmethod
    def create(
        cls,
        profile: IngestionProfile,
    ) -> BaseChunker:
        if not isinstance(
            profile,
            IngestionProfile,
        ):
            raise TypeError(
                "profile must be an "
                "IngestionProfile."
            )

        if (
            profile.chunker_type
            == cls.RECURSIVE_CHARACTER_TYPE
        ):
            return (
                RecursiveCharacterChunker()
            )

        raise ValueError(
            "Unsupported chunker_type "
            f"'{profile.chunker_type}'."
        )