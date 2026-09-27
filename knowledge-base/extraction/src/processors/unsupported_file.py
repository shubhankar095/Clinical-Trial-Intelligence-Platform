from models.document import ClinicalDocument
from processors.base_processor import BaseProcessor


class UnsupportedFileProcessor(BaseProcessor):

    def __init__(self, extension: str):
        super().__init__()
        self.extension = extension

    def process(self, document: ClinicalDocument) -> ClinicalDocument:

        document.processing_status = "FAILED"
        document.error_message = (
            f"The file type '.{self.extension}' is not currently supported by this version. "
            f"Please consider converting it to a supported format like .pdf."
        )

        return document