from abc import ABC, abstractmethod
from utils.logger import get_logger
from models.document import ClinicalDocument

class BaseProcessor(ABC):

    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)

    @abstractmethod
    def process(self, document: ClinicalDocument) -> ClinicalDocument:
        """
        All processors must implement this method.
        """
        pass