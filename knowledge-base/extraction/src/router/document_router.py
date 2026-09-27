from utils.logger import get_logger
from ocr.textract_ocr import TextractOCR
from processors.pdf_processor import PDFProcessor
from processors.unsupported_file import UnsupportedFileProcessor
from config.config import pages_to_read, min_words_per_page, min_quality_score


logger = get_logger(__name__)


def _create_pdf_processor() -> PDFProcessor:

    return PDFProcessor(
        ocr_processor=TextractOCR(),
        pages_to_read=pages_to_read,
        min_words_per_page=min_words_per_page,
        min_quality_score=min_quality_score,
    )


PROCESSOR_FACTORIES = {
    "pdf": _create_pdf_processor,
}


def get_processor(file_extension: str):

    extension = file_extension.lower().lstrip(".")
    factory = PROCESSOR_FACTORIES.get(extension)

    if factory is None:
        logger.warning(
            f"No processor found for "
            f"'.{extension}' files. "
            f"Using UnsupportedFileProcessor."
        )

        return UnsupportedFileProcessor(extension)

    try:
        processor = factory()
        logger.info(
            f"Processor selected for "
            f"'.{extension}' files: "
            f"{processor.__class__.__name__}"
        )

        return processor

    except Exception:
        logger.exception(
            f"Failed to instantiate processor "
            f"for '.{extension}'."
        )

        raise