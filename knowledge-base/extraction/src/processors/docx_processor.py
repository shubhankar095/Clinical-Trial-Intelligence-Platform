#from docx import Document
from utils.logger import get_logger
from models.document import ClinicalDocument
from processors.base_processor import BaseProcessor

logger = get_logger(__name__)

class DOCXProcessor(BaseProcessor):

    def process(self, document: ClinicalDocument) -> ClinicalDocument:

        self.logger.info(f"Processing DOCX: {document.file_name}")

        try:
            #doc = Document(document.s3_key)

            #for paragraph in doc.paragraphs:

            extracted_text = """
            Monitoring Summary
            Site Findings...
            """

            document.raw_text = extracted_text
            document.processing_status = "SUCCESS"

            return document

        except Exception as ex:

            document.processing_status = "FAILED"
            document.error_message = str(ex)

            return document