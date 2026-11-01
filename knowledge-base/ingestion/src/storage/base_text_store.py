from abc import ABC, abstractmethod

from models.storage_location import (
    StorageLocation,
)


class BaseTextStore(ABC):
    """
    Storage abstraction for loading UTF-8 text.

    Implementations may read from local files,
    Amazon S3, or another object store.
    """

    @abstractmethod
    def load_text(
        self,
        location: StorageLocation,
    ) -> str:
        """
        Load and return UTF-8 text from the supplied
        storage location.
        """
        raise NotImplementedError