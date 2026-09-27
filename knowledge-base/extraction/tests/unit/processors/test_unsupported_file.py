import pytest

from models.document import (
    ClinicalDocument,
)
from processors.unsupported_file import (
    UnsupportedFileProcessor,
)


pytestmark = pytest.mark.unit


@pytest.fixture
def document():
    return ClinicalDocument(
        document_id="document-123",
        file_name="sample.docx",
        file_format="docx",
        source_bucket="raw-bucket",
        source_key=(
            "documents/TEST001/"
            "protocols/sample.docx"
        ),
        processing_status="PENDING",
    )


def test_constructor_stores_extension():
    processor = (
        UnsupportedFileProcessor(
            "docx"
        )
    )

    assert (
        processor.extension
        == "docx"
    )


def test_process_returns_same_document(
    document,
):
    processor = (
        UnsupportedFileProcessor(
            "docx"
        )
    )

    result = processor.process(
        document
    )

    assert result is document


def test_process_marks_document_failed(
    document,
):
    processor = (
        UnsupportedFileProcessor(
            "docx"
        )
    )

    result = processor.process(
        document
    )

    assert (
        result.processing_status
        == "FAILED"
    )


def test_process_sets_error_message(
    document,
):
    processor = (
        UnsupportedFileProcessor(
            "docx"
        )
    )

    result = processor.process(
        document
    )

    assert result.error_message

    assert (
        "docx"
        in result.error_message.lower()
    )


def test_process_does_not_create_extracted_content(
    document,
):
    processor = (
        UnsupportedFileProcessor(
            "docx"
        )
    )

    result = processor.process(
        document
    )

    assert result.raw_text == ""
    assert result.pages == []
    assert result.images == []
    assert result.tables == []
    assert result.page_count == 0
    assert result.ocr_page_count == 0
    assert result.image_count == 0
    assert result.table_count == 0


@pytest.mark.parametrize(
    "extension",
    [
        "docx",
        "txt",
        "csv",
        "xlsx",
    ],
)
def test_error_message_contains_requested_extension(
    document,
    extension,
):
    processor = (
        UnsupportedFileProcessor(
            extension
        )
    )

    result = processor.process(
        document
    )

    assert (
        extension
        in result.error_message.lower()
    )