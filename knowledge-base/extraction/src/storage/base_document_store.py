from abc import ABC, abstractmethod
from models.document import ClinicalDocument


class BaseDocumentStore(ABC):

    @abstractmethod
    def save(
        self,
        document: ClinicalDocument
    ) -> str:
        pass