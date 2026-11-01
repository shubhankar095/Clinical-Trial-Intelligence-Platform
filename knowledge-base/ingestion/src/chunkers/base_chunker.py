from abc import (
    ABC,
    abstractmethod,
)

from models.canonical_document import (
    CanonicalDocument,
)
from models.document import (
    DocumentChunk,
)
from models.ingestion_profile import (
    IngestionIdentity,
    IngestionProfile,
)


class BaseChunker(ABC):
    """
    Common interface for all text-chunking
    strategies.

    Implementations may use LangChain, custom
    algorithms, token splitters, semantic splitters,
    or section-aware clinical-document logic.
    """

    @abstractmethod
    def chunk(
        self,
        document: CanonicalDocument,
        identity: IngestionIdentity,
        profile: IngestionProfile,
    ) -> tuple[DocumentChunk, ...]:
        """
        Split one canonical document into immutable,
        deterministic chunks.
        """
        raise NotImplementedError

    def _find_page_range(
        self,
        document: CanonicalDocument,
        start_offset: int,
        end_offset: int,
    ) -> tuple[int | None, int | None]:
        """
        Return the first and last canonical pages
        whose source ranges intersect the chunk.

        Page-range intersection is used instead of
        point lookup so page separators or gaps do
        not cause otherwise valid chunks to lose
        their page mapping.
        """
        intersecting_pages = [
            page.page_number
            for page in document.pages
            if (
                page.start_offset
                < end_offset
                and page.end_offset
                > start_offset
            )
        ]

        if not intersecting_pages:
            return None, None

        return (
            intersecting_pages[0],
            intersecting_pages[-1],
        )