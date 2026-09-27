from pathlib import Path

import pytest

from models.document import ClinicalDocument
from processors import pdf_processor as pdf_processor_module
from processors.pdf_processor import PDFProcessor


pytestmark = pytest.mark.integration

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


class RecordingAssetStore:
    """
    In-memory replacement for S3AssetStore used by
    local integration tests.
    """

    def __init__(
        self,
        bucket_name,
    ):
        self.bucket_name = bucket_name
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
            f"integration/{document.document_id}/"
            f"images/{image_id}.{extension}"
        )

        self.saved_images.append(
            {
                "document": document,
                "image_id": image_id,
                "image_bytes": image_bytes,
                "extension": extension,
                "key": key,
            }
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
    """
    In-memory replacement for S3TableStore used by
    local integration tests.
    """

    def __init__(
        self,
        bucket_name,
    ):
        self.bucket_name = bucket_name
        self.saved_tables = []
        self.deleted_tables = []

    def save_table(
        self,
        document,
        table_id,
        rows,
    ):
        key = (
            f"integration/{document.document_id}/"
            f"tables/{table_id}.json"
        )

        self.saved_tables.append(
            {
                "document": document,
                "table_id": table_id,
                "rows": rows,
                "key": key,
            }
        )

        return key

    def delete_table(
        self,
        key,
    ):
        self.deleted_tables.append(
            key
        )


class FakeOCRProcessor:
    """
    Deterministic OCR replacement.

    This class does not call Amazon Textract.
    """

    def __init__(
        self,
        text,
    ):
        self.text = text
        self.calls = []

    def extract_text(
        self,
        image_bytes,
    ):
        self.calls.append(
            image_bytes
        )

        return self.text


@pytest.fixture
def processor_factory(
    monkeypatch,
):
    """
    Create a real PDFProcessor with in-memory stores
    and an optional fake OCR processor.
    """

    monkeypatch.setattr(
        pdf_processor_module,
        "S3AssetStore",
        RecordingAssetStore,
    )

    monkeypatch.setattr(
        pdf_processor_module,
        "S3TableStore",
        RecordingTableStore,
    )

    def create(
        *,
        ocr_processor=None,
        min_words_per_page=2,
        min_quality_score=0.1,
    ):
        return PDFProcessor(
            ocr_processor=ocr_processor,
            pages_to_read="all",
            min_words_per_page=(
                min_words_per_page
            ),
            min_quality_score=(
                min_quality_score
            ),
        )

    return create


def build_document(
    file_name,
):
    path = DATA_DIR / file_name

    assert path.is_file(), (
        f"Missing integration fixture: {path}"
    )

    return ClinicalDocument(
        document_id=(
            f"integration-{path.stem}"
        ),
        file_name=path.name,
        file_format="pdf",
        source_bucket="local-fixtures",
        source_key=(
            f"tests/data/{path.name}"
        ),
        local_file_path=str(path),
    )


def test_minimal_text_pdf_extracts_real_native_text(
    processor_factory,
):
    processor = processor_factory()

    document = build_document(
        "minimal_text.pdf"
    )

    result = processor.process(
        document
    )

    assert (
        result.processing_status
        == "SUCCESS"
    )

    assert result.error_message is None
    assert result.page_count == 1
    assert result.ocr_page_count == 0
    assert result.image_count == 0
    assert result.table_count == 0

    assert (
        "Clinical Trial Extraction Fixture"
        in result.raw_text
    )

    assert (
        "Study ID: TEST001"
        in result.raw_text
    )

    assert (
        "native searchable text"
        in result.raw_text
    )

    page = result.pages[0]

    assert page.page_number == 1

    assert (
        page.extraction_method
        == "TEXT"
    )

    assert (
        page.ocr_applied
        is False
    )

    assert (
        result.raw_text[
            page.start_offset:
            page.end_offset
        ]
        == page.text
    )


def test_scanned_pdf_uses_fake_ocr_without_aws(
    processor_factory,
):
    expected_text = (
        "SCANNED PROTOCOL PAGE\n"
        "Study ID: TEST-SCAN-001\n"
        "Locally supplied OCR text"
    )

    fake_ocr = FakeOCRProcessor(
        expected_text
    )

    processor = processor_factory(
        ocr_processor=fake_ocr,
        min_words_per_page=5,
        min_quality_score=0.6,
    )

    document = build_document(
        "scanned_page.pdf"
    )

    result = processor.process(
        document
    )

    assert (
        result.processing_status
        == "SUCCESS"
    )

    assert result.page_count == 1
    assert result.ocr_page_count == 1
    assert result.raw_text == expected_text

    assert len(
        fake_ocr.calls
    ) == 1

    assert (
        fake_ocr.calls[0]
        .startswith(b"\x89PNG")
    )

    page = result.pages[0]

    assert (
        page.requires_ocr
        is True
    )

    assert (
        page.ocr_applied
        is True
    )

    assert (
        page.extraction_method
        == "OCR"
    )

    assert page.text == expected_text

    assert (
        result.raw_text[
            page.start_offset:
            page.end_offset
        ]
        == page.text
    )

    # The scanned page contains an embedded raster
    # image. The in-memory store captures it instead
    # of uploading it to S3.
    assert result.image_count == 1

    assert len(
        processor.asset_store
        .saved_images
    ) == 1

    assert (
        processor.asset_store
        .saved_images[0][
            "image_bytes"
        ]
    )


def test_table_pdf_discovers_real_vector_table(
    processor_factory,
):
    processor = processor_factory()

    document = build_document(
        "table_document.pdf"
    )

    result = processor.process(
        document
    )

    assert (
        result.processing_status
        == "SUCCESS"
    )

    assert result.page_count == 1
    assert result.ocr_page_count == 0
    assert result.table_count == 1

    assert len(
        result.tables
    ) == 1

    assert len(
        processor.table_store
        .saved_tables
    ) == 1

    table = result.tables[0]

    saved = (
        processor.table_store
        .saved_tables[0]
    )

    assert (
        table.table_id
        == "table-1-1"
    )

    assert table.page_number == 1
    assert table.row_count == 4
    assert table.column_count == 3

    assert (
        saved["table_id"]
        == "table-1-1"
    )

    assert saved["rows"] == [
        [
            "Visit",
            "Day",
            "Assessment",
        ],
        [
            "Screening",
            "-14 to -1",
            "Eligibility",
        ],
        [
            "Baseline",
            "0",
            "Randomization",
        ],
        [
            "Follow-up",
            "28",
            "Safety review",
        ],
    ]

    assert (
        "Participant Visit Schedule"
        in result.raw_text
    )

    assert (
        result.raw_text[
            result.pages[0].start_offset:
            result.pages[0].end_offset
        ]
        == result.pages[0].text
    )