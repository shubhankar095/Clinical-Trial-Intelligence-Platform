from abc import (
    ABC,
    abstractmethod,
)

from models.index_record import (
    IndexRecord,
)


class BaseIndexer(ABC):
    """
    Common interface for index persistence adapters.

    Implementations may write records to local
    storage, OpenSearch, or another search system.
    """

    @abstractmethod
    def index_records(
        self,
        *,
        ingestion_id: str,
        records: tuple[
            IndexRecord,
            ...,
        ],
    ) -> str:
        """
        Persist index records and return a
        destination description.
        """
        raise NotImplementedError