from pathlib import Path

import pymupdf
import pytest

from models.document import (
    ClinicalDocument,
)
from processors.pdf_processor import (
    PDFProcessor,
)


pytestmark = pytest.mark.integration


class RecordingAssetStore:

    def __init__(
        self,
    ):
        self.saved_images = []
        self.deleted_images = []

    def save_image(
        self,
        document,
        image_id,
        image_bytes,
        extension,
    ):
        key = (
            f"test/{document.document_id}/"
            f"images/{image_id}.{extension}"
        )

        self.saved_images.append(
            key
        )

        return key

    def delete_image(
        self,
        key,
    ):
        self.deleted_images.append(
            key
        )


class RecordingTableStore:

    def __init__(
        self,
    ):
        self.saved_tables = []
        self.deleted_tables = []

    def save_table(
        self,
        document,
        table_id,
        rows,
    ):
        key = (
            f"test/{document.document_id}/"
            f"tables/{table_id}.json"
        )

        self.saved_tables.append(
            key
        )

        return key

    def delete_table(
        self,
        key,
    ):
        self.deleted_tables.append(
            key
        )


def build_processor():
    return PDFProcessor(
        ocr_processor=None,
        asset_store=RecordingAssetStore(),
        table_store=RecordingTableStore(),
        pages_to_read="all",
        min_words_per_page=2,
        min_quality_score=0.1,
    )


def build_document(
    path: Path,
):
    return ClinicalDocument(
        document_id=(
            f"failure-{path.stem}"
        ),
        file_name=path.name,
        file_format="pdf",
        source_bucket="local-test",
        source_key=(
            "documents/TEST001/"
            f"protocols/{path.name}"
        ),
        local_file_path=str(path),
    )


def assert_clean_failure(
    result,
):
    assert (
        result.processing_status
        == "FAILED"
    )

    assert result.error_message
    assert result.raw_text == ""
    assert result.pages == []
    assert result.images == []
    assert result.tables == []
    assert result.page_count == 0
    assert result.ocr_page_count == 0
    assert result.image_count == 0
    assert result.table_count == 0


def test_corrupted_pdf_fails_cleanly(
    tmp_path,
):
    source_file = (
        tmp_path / "corrupted.pdf"
    )

    source_file.write_bytes(
        b"This is not a PDF document."
    )

    processor = build_processor()

    result = processor.process(
        build_document(source_file)
    )

    assert_clean_failure(
        result
    )

    assert (
        processor.asset_store
        .saved_images
        == []
    )

    assert (
        processor.table_store
        .saved_tables
        == []
    )


def test_truncated_pdf_returns_consistent_result(
    tmp_path,
):
    valid_file = (
        tmp_path / "valid.pdf"
    )

    truncated_file = (
        tmp_path / "truncated.pdf"
    )

    document = pymupdf.open()

    page = document.new_page()

    page.insert_text(
        (72, 72),
        (
            "Clinical trial "
            "protocol content"
        ),
    )

    document.save(
        valid_file
    )

    document.close()

    original_bytes = (
        valid_file.read_bytes()
    )

    truncated_file.write_bytes(
        original_bytes[
            : max(
                16,
                len(original_bytes) // 4,
            )
        ]
    )

    processor = build_processor()

    result = processor.process(
        build_document(
            truncated_file
        )
    )

    assert result.processing_status in {
        "SUCCESS",
        "FAILED",
    }

    if (
        result.processing_status
        == "FAILED"
    ):
        assert_clean_failure(
            result
        )

        return

    assert result.error_message is None

    assert (
        result.page_count
        == len(result.pages)
    )

    assert (
        result.image_count
        == len(result.images)
    )

    assert (
        result.table_count
        == len(result.tables)
    )

    assert (
        result.ocr_page_count
        <= result.page_count
    )

    for extracted_page in result.pages:
        assert (
            result.raw_text[
                extracted_page.start_offset:
                extracted_page.end_offset
            ]
            == extracted_page.text
        )

def test_password_protected_pdf_fails_without_password(
    tmp_path,
):
    protected_file = (
        tmp_path
        / "password-protected.pdf"
    )

    document = pymupdf.open()

    page = document.new_page()

    page.insert_text(
        (72, 72),
        (
            "Protected clinical "
            "document"
        ),
    )

    document.save(
        protected_file,
        encryption=(
            pymupdf.PDF_ENCRYPT_AES_256
        ),
        owner_pw="owner-password",
        user_pw="user-password",
    )

    document.close()

    processor = build_processor()

    result = processor.process(
        build_document(
            protected_file
        )
    )

    assert_clean_failure(
        result
    )


def test_valid_pdf_with_blank_page_has_defined_result(
    tmp_path,
):
    blank_file = (
        tmp_path / "blank.pdf"
    )

    document = pymupdf.open()

    document.new_page()

    document.save(
        blank_file
    )

    document.close()

    processor = build_processor()

    result = processor.process(
        build_document(
            blank_file
        )
    )

    assert (
        result.processing_status
        == "SUCCESS"
    )

    assert result.page_count == 1
    assert result.raw_text == ""
    assert len(result.pages) == 1

    page = result.pages[0]

    assert page.page_number == 1
    assert page.text == ""
    assert page.requires_ocr is True
    assert page.ocr_applied is False

    assert result.warnings == [
        (
            "Page 1 required OCR, "
            "but no OCR processor "
            "was configured."
        )
    ]