from abc import ABC, abstractmethod

from models.document import ClinicalDocument


class BaseIndexer(ABC):

    @abstractmethod
    def index(
        self,
        document: ClinicalDocument
    ) -> ClinicalDocument:
        pass