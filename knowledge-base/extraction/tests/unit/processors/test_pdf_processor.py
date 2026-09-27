from unittest.mock import Mock, call

import pytest

from models.document import (
    ClinicalDocument,
    DocumentImage,
    DocumentTable,
)
from processors.pdf_processor import PDFProcessor


pytestmark = pytest.mark.unit


class FakeTableFinder:
    def __init__(self, tables=None):
        self.tables = tables or []


class FakePage:
    def __init__(self, text):
        self.text = text

    def get_text(self):
        return self.text

    def get_images(self, full=True):
        return []

    def find_tables(self):
        return FakeTableFinder()


class FakePDF:
    def __init__(self, pages):
        self.pages = pages

    def __len__(self):
        return len(self.pages)

    def __iter__(self):
        return iter(self.pages)

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception, traceback):
        return False


class FakeOCRProcessor:
    def __init__(self, text="OCR extracted text", exception=None):
        self.text = text
        self.exception = exception
        self.calls = []

    def extract_text(self, image_bytes):
        self.calls.append(image_bytes)
        if self.exception:
            raise self.exception
        return self.text


class FakePixmap:
    def __init__(self, png_bytes=b"rendered-page"):
        self.png_bytes = png_bytes
        self.formats = []

    def tobytes(self, image_format):
        self.formats.append(image_format)
        return self.png_bytes


class FakeImageParent:
    def __init__(self, image_details_by_xref=None, exceptions_by_xref=None):
        self.image_details_by_xref = image_details_by_xref or {}
        self.exceptions_by_xref = exceptions_by_xref or {}
        self.calls = []

    def extract_image(self, xref):
        self.calls.append(xref)
        if xref in self.exceptions_by_xref:
            raise self.exceptions_by_xref[xref]
        return self.image_details_by_xref[xref]


class FakeImagePage:
    def __init__(self, image_references, parent):
        self.image_references = image_references
        self.parent = parent

    def get_images(self, full=True):
        assert full is True
        return self.image_references


class FakeExtractedTable:
    def __init__(self, rows=None, exception=None):
        self.rows = rows if rows is not None else []
        self.exception = exception
        self.extract_calls = 0

    def extract(self):
        self.extract_calls += 1
        if self.exception:
            raise self.exception
        return self.rows


class FakeTablePage:
    def __init__(self, tables=None, exception=None):
        self.tables = tables or []
        self.exception = exception
        self.find_calls = 0

    def find_tables(self):
        self.find_calls += 1
        if self.exception:
            raise self.exception
        return FakeTableFinder(self.tables)


@pytest.fixture
def processor():
    return PDFProcessor(
        ocr_processor=None,
        pages_to_read="all",
        min_words_per_page=2,
        min_quality_score=0.6,
    )


@pytest.fixture
def clinical_document(tmp_path):
    source_file = tmp_path / "sample.pdf"
    source_file.write_bytes(b"fake-pdf")
    return ClinicalDocument(
        document_id="document-123",
        file_name="sample.pdf",
        file_format="pdf",
        source_bucket="raw-bucket",
        source_key="documents/TEST001/protocols/sample.pdf",
        local_file_path=str(source_file),
    )


def patch_pdf(monkeypatch, processor, fake_pdf):
    monkeypatch.setattr(
        "processors.pdf_processor.pymupdf.open",
        lambda path: fake_pdf,
    )
    monkeypatch.setattr(processor, "_extract_images", lambda **kwargs: [])
    monkeypatch.setattr(processor, "_extract_tables", lambda **kwargs: [])


# Text quality and page limits

def test_empty_text_has_zero_quality(processor):
    assert processor.quality_score("") == 0.0


def test_whitespace_only_text_has_zero_quality(processor):
    assert processor.quality_score("   \n\t") == 0.0


def test_alphanumeric_text_has_full_quality(processor):
    assert processor.quality_score("ABC123") == 1.0


def test_quality_score_counts_non_alphanumeric_characters(processor):
    assert processor.quality_score("AB!!") == 0.5


def test_low_density_text_requires_ocr(processor):
    assert processor.requires_ocr("one two") is True


def test_empty_text_requires_ocr(processor):
    assert processor.requires_ocr("") is True


def test_low_quality_text_requires_ocr(processor):
    assert processor.requires_ocr("word1 word2 word3 !!!!!!!!!!") is True


def test_good_text_does_not_require_ocr(processor):
    assert processor.requires_ocr("alpha beta gamma delta") is False


def test_all_pages_returns_total_page_count(processor):
    processor.pages_to_read = "all"
    assert processor._get_page_limit(8) == 8


def test_numeric_page_limit_is_applied(processor):
    processor.pages_to_read = "3"
    assert processor._get_page_limit(8) == 3


def test_page_limit_is_capped_at_total_pages(processor):
    processor.pages_to_read = "20"
    assert processor._get_page_limit(8) == 8


@pytest.mark.parametrize("page_limit", ["0", "-1", "-10"])
def test_non_positive_page_limit_is_rejected(processor, page_limit):
    processor.pages_to_read = page_limit
    with pytest.raises(ValueError, match="pages_to_read"):
        processor._get_page_limit(10)


def test_invalid_page_limit_is_rejected(processor):
    processor.pages_to_read = "invalid"
    with pytest.raises(ValueError):
        processor._get_page_limit(10)


# End-to-end processing with fake PDFs

def test_process_extracts_native_text(monkeypatch, processor, clinical_document):
    fake_pdf = FakePDF([
        FakePage("alpha beta gamma"),
        FakePage("delta epsilon zeta"),
    ])
    patch_pdf(monkeypatch, processor, fake_pdf)
    result = processor.process(clinical_document)
    assert result.processing_status == "SUCCESS"
    assert result.page_count == 2
    assert result.ocr_page_count == 0
    assert result.image_count == 0
    assert result.table_count == 0
    assert result.raw_text == "alpha beta gamma\ndelta epsilon zeta"


def test_page_offsets_match_raw_text(monkeypatch, processor, clinical_document):
    fake_pdf = FakePDF([
        FakePage("first page content"),
        FakePage("second page content"),
    ])
    patch_pdf(monkeypatch, processor, fake_pdf)
    result = processor.process(clinical_document)
    assert result.pages[0].start_offset == 0
    for page in result.pages:
        assert result.raw_text[page.start_offset:page.end_offset] == page.text


def test_page_separator_is_reflected_in_offsets(monkeypatch, processor, clinical_document):
    first_text = "first"
    second_text = "second"
    fake_pdf = FakePDF([FakePage(first_text), FakePage(second_text)])
    patch_pdf(monkeypatch, processor, fake_pdf)
    result = processor.process(clinical_document)
    assert result.pages[0].end_offset == len(first_text)
    assert result.pages[1].start_offset == len(first_text) + 1


def test_ocr_is_applied_to_weak_page(monkeypatch, clinical_document):
    ocr_processor = FakeOCRProcessor(text="OCR text with sufficient content")
    processor = PDFProcessor(
        ocr_processor=ocr_processor,
        pages_to_read="all",
        min_words_per_page=5,
        min_quality_score=0.6,
    )
    fake_pdf = FakePDF([FakePage("short")])
    patch_pdf(monkeypatch, processor, fake_pdf)
    monkeypatch.setattr(processor, "_page_to_bytes", lambda page: b"page-image")
    result = processor.process(clinical_document)
    assert result.processing_status == "SUCCESS"
    assert result.ocr_page_count == 1
    assert result.pages[0].ocr_applied is True
    assert result.pages[0].extraction_method == "OCR"
    assert result.pages[0].text == "OCR text with sufficient content"
    assert ocr_processor.calls == [b"page-image"]


def test_ocr_failure_falls_back_to_native_text(monkeypatch, clinical_document):
    ocr_processor = FakeOCRProcessor(exception=RuntimeError("OCR failed"))
    processor = PDFProcessor(
        ocr_processor=ocr_processor,
        pages_to_read="all",
        min_words_per_page=5,
        min_quality_score=0.6,
    )
    native_text = "short"
    fake_pdf = FakePDF([FakePage(native_text)])
    patch_pdf(monkeypatch, processor, fake_pdf)
    monkeypatch.setattr(processor, "_page_to_bytes", lambda page: b"page-image")
    result = processor.process(clinical_document)
    assert result.processing_status == "SUCCESS"
    assert result.ocr_page_count == 0
    assert result.pages[0].text == native_text
    assert result.pages[0].extraction_method == "TEXT"
    assert result.pages[0].ocr_applied is False

def test_empty_ocr_text_falls_back_to_native_text(
    monkeypatch,
    clinical_document,
):
    ocr_processor = FakeOCRProcessor(
        text="   "
    )

    processor = PDFProcessor(
        ocr_processor=ocr_processor,
        pages_to_read="all",
        min_words_per_page=5,
        min_quality_score=0.6,
    )

    native_text = "short"

    fake_pdf = FakePDF(
        [
            FakePage(native_text)
        ]
    )

    patch_pdf(
        monkeypatch,
        processor,
        fake_pdf,
    )

    monkeypatch.setattr(
        processor,
        "_page_to_bytes",
        lambda page: b"page-image",
    )

    result = processor.process(
        clinical_document
    )

    assert (
        result.processing_status
        == "SUCCESS"
    )

    assert (
        result.ocr_page_count
        == 0
    )

    assert (
        result.pages[0].text
        == native_text
    )

    assert (
        result.pages[0]
        .extraction_method
        == "TEXT"
    )

    assert (
        result.pages[0]
        .ocr_applied
        is False
    )

    assert (
        result.pages[0]
        .requires_ocr
        is True
    )

    assert (
        ocr_processor.calls
        == [b"page-image"]
    )
    
def test_no_ocr_processor_keeps_native_text(monkeypatch, clinical_document):
    processor = PDFProcessor(
        ocr_processor=None,
        pages_to_read="all",
        min_words_per_page=5,
        min_quality_score=0.6,
    )
    native_text = "short"
    fake_pdf = FakePDF([FakePage(native_text)])
    patch_pdf(monkeypatch, processor, fake_pdf)
    result = processor.process(clinical_document)
    assert result.processing_status == "SUCCESS"
    assert result.pages[0].requires_ocr is True
    assert result.pages[0].ocr_applied is False
    assert result.pages[0].text == native_text


def test_page_limit_restricts_processed_pages(monkeypatch, clinical_document):
    processor = PDFProcessor(
        ocr_processor=None,
        pages_to_read="1",
        min_words_per_page=1,
        min_quality_score=0.1,
    )
    fake_pdf = FakePDF([
        FakePage("first page text"),
        FakePage("second page text"),
    ])
    patch_pdf(monkeypatch, processor, fake_pdf)
    result = processor.process(clinical_document)
    assert result.page_count == 1
    assert result.raw_text == "first page text"


def test_fatal_failure_marks_document_failed(monkeypatch, processor, clinical_document):
    cleanup_mock = Mock()
    monkeypatch.setattr(
        "processors.pdf_processor.pymupdf.open",
        Mock(side_effect=RuntimeError("Cannot open PDF")),
    )
    monkeypatch.setattr(processor, "_cleanup_uploaded_assets", cleanup_mock)
    result = processor.process(clinical_document)
    assert result.processing_status == "FAILED"
    assert result.raw_text == ""
    assert result.pages == []
    assert result.images == []
    assert result.tables == []
    assert result.error_message == "Cannot open PDF"
    cleanup_mock.assert_called_once_with(image_keys=[], table_keys=[])


# Page rendering

def test_page_to_bytes_renders_page_as_png(monkeypatch, processor):
    pixmap = FakePixmap(png_bytes=b"png-content")
    page = Mock()
    page.get_pixmap.return_value = pixmap
    matrix = object()
    matrix_mock = Mock(return_value=matrix)
    monkeypatch.setattr("processors.pdf_processor.pymupdf.Matrix", matrix_mock)
    result = processor._page_to_bytes(page)
    matrix_mock.assert_called_once_with(2, 2)
    page.get_pixmap.assert_called_once_with(matrix=matrix)
    assert pixmap.formats == ["png"]
    assert result == b"png-content"


# Image extraction

def test_extract_images_uploads_meaningful_image(processor, clinical_document):
    parent = FakeImageParent({
        101: {
            "width": 640,
            "height": 480,
            "image": b"image-content",
            "ext": "jpeg",
        }
    })
    page = FakeImagePage([(101,)], parent)
    processor.asset_store = Mock()
    processor.asset_store.save_image.return_value = (
        "canonical-documents/sample_document-123/images/image-2-1.jpeg"
    )
    images = processor._extract_images(page, 2, clinical_document)
    assert len(images) == 1
    image = images[0]
    assert isinstance(image, DocumentImage)
    assert image.image_id == "image-2-1"
    assert image.page_number == 2
    assert image.extension == "jpeg"
    assert image.width == 640
    assert image.height == 480
    processor.asset_store.save_image.assert_called_once_with(
        document=clinical_document,
        image_id="image-2-1",
        image_bytes=b"image-content",
        extension="jpeg",
    )


@pytest.mark.parametrize("width,height", [(49, 100), (100, 49), (0, 100), (100, 0)])
def test_extract_images_skips_small_images(processor, clinical_document, width, height):
    parent = FakeImageParent({
        101: {
            "width": width,
            "height": height,
            "image": b"small-image",
            "ext": "png",
        }
    })
    page = FakeImagePage([(101,)], parent)
    processor.asset_store = Mock()
    assert processor._extract_images(page, 1, clinical_document) == []
    processor.asset_store.save_image.assert_not_called()


def test_extract_images_accepts_minimum_meaningful_dimensions(processor, clinical_document):
    parent = FakeImageParent({
        101: {
            "width": 50,
            "height": 50,
            "image": b"image-content",
            "ext": "png",
        }
    })
    page = FakeImagePage([(101,)], parent)
    processor.asset_store = Mock()
    processor.asset_store.save_image.return_value = "image-key"
    images = processor._extract_images(page, 1, clinical_document)
    assert len(images) == 1
    assert images[0].width == 50
    assert images[0].height == 50


def test_extract_images_uses_png_when_extension_is_missing(processor, clinical_document):
    parent = FakeImageParent({
        101: {
            "width": 100,
            "height": 100,
            "image": b"image-content",
        }
    })
    page = FakeImagePage([(101,)], parent)
    processor.asset_store = Mock()
    processor.asset_store.save_image.return_value = "image-key"
    images = processor._extract_images(page, 3, clinical_document)
    assert images[0].extension == "png"
    processor.asset_store.save_image.assert_called_once_with(
        document=clinical_document,
        image_id="image-3-1",
        image_bytes=b"image-content",
        extension="png",
    )


def test_extract_images_continues_after_one_image_fails(processor, clinical_document):
    parent = FakeImageParent(
        image_details_by_xref={
            202: {
                "width": 200,
                "height": 100,
                "image": b"second-image",
                "ext": "png",
            }
        },
        exceptions_by_xref={101: RuntimeError("First image failed")},
    )
    page = FakeImagePage([(101,), (202,)], parent)
    processor.asset_store = Mock()
    processor.asset_store.save_image.return_value = "second-image-key"
    images = processor._extract_images(page, 4, clinical_document)
    assert len(images) == 1
    assert images[0].image_id == "image-4-2"
    assert images[0].s3_key == "second-image-key"
    assert parent.calls == [101, 202]


def test_extract_images_continues_after_upload_failure(processor, clinical_document):
    parent = FakeImageParent({
        101: {
            "width": 100,
            "height": 100,
            "image": b"first-image",
            "ext": "png",
        },
        202: {
            "width": 200,
            "height": 200,
            "image": b"second-image",
            "ext": "jpg",
        },
    })
    page = FakeImagePage([(101,), (202,)], parent)
    processor.asset_store = Mock()
    processor.asset_store.save_image.side_effect = [
        RuntimeError("First upload failed"),
        "second-image-key",
    ]
    images = processor._extract_images(page, 1, clinical_document)
    assert len(images) == 1
    assert images[0].image_id == "image-1-2"
    assert images[0].s3_key == "second-image-key"
    assert processor.asset_store.save_image.call_count == 2


# Table extraction

def test_extract_tables_uploads_table(processor, clinical_document):
    rows = [["A", "B"], ["1", "2"]]
    page = FakeTablePage([FakeExtractedTable(rows=rows)])
    processor.table_store = Mock()
    processor.table_store.save_table.return_value = (
        "canonical-documents/sample_document-123/tables/table-2-1.json"
    )
    tables = processor._extract_tables(page, 2, clinical_document)
    assert len(tables) == 1
    table = tables[0]
    assert isinstance(table, DocumentTable)
    assert table.table_id == "table-2-1"
    assert table.page_number == 2
    assert table.row_count == 2
    assert table.column_count == 2
    processor.table_store.save_table.assert_called_once_with(
        document=clinical_document,
        table_id="table-2-1",
        rows=rows,
    )


def test_extract_tables_uses_largest_row_for_column_count(processor, clinical_document):
    page = FakeTablePage([
        FakeExtractedTable(rows=[["A"], ["B", "C", "D"], ["E", "F"]])
    ])
    processor.table_store = Mock()
    processor.table_store.save_table.return_value = "table-key"
    table = processor._extract_tables(page, 1, clinical_document)[0]
    assert table.row_count == 3
    assert table.column_count == 3


def test_extract_tables_handles_empty_rows(processor, clinical_document):
    page = FakeTablePage([FakeExtractedTable(rows=[])])
    processor.table_store = Mock()
    processor.table_store.save_table.return_value = "empty-table-key"
    table = processor._extract_tables(page, 1, clinical_document)[0]
    assert table.row_count == 0
    assert table.column_count == 0


def test_extract_tables_assigns_sequential_ids(processor, clinical_document):
    page = FakeTablePage([
        FakeExtractedTable(rows=[["first"]]),
        FakeExtractedTable(rows=[["second"]]),
    ])
    processor.table_store = Mock()
    processor.table_store.save_table.side_effect = ["first-table-key", "second-table-key"]
    tables = processor._extract_tables(page, 3, clinical_document)
    assert [table.table_id for table in tables] == ["table-3-1", "table-3-2"]


def test_extract_tables_returns_empty_list_when_discovery_fails(processor, clinical_document):
    page = FakeTablePage(exception=RuntimeError("Table discovery failed"))
    processor.table_store = Mock()
    assert processor._extract_tables(page, 1, clinical_document) == []
    processor.table_store.save_table.assert_not_called()


def test_extract_tables_returns_empty_list_when_table_extract_fails(processor, clinical_document):
    page = FakeTablePage([
        FakeExtractedTable(exception=RuntimeError("Table extraction failed"))
    ])
    processor.table_store = Mock()
    assert processor._extract_tables(page, 1, clinical_document) == []
    processor.table_store.save_table.assert_not_called()


def test_extract_tables_returns_previous_tables_when_later_table_fails(processor, clinical_document):
    page = FakeTablePage([
        FakeExtractedTable(rows=[["first"]]),
        FakeExtractedTable(exception=RuntimeError("Second table failed")),
    ])
    processor.table_store = Mock()
    processor.table_store.save_table.return_value = "first-table-key"
    tables = processor._extract_tables(page, 1, clinical_document)
    assert len(tables) == 1
    assert tables[0].table_id == "table-1-1"


def test_extract_tables_returns_empty_list_when_upload_fails(processor, clinical_document):
    page = FakeTablePage([FakeExtractedTable(rows=[["value"]])])
    processor.table_store = Mock()
    processor.table_store.save_table.side_effect = RuntimeError("Table upload failed")
    assert processor._extract_tables(page, 1, clinical_document) == []


# Cleanup

def test_cleanup_images_deletes_every_key(processor):
    processor.asset_store = Mock()
    processor._cleanup_images(["image-key-1", "image-key-2"])
    assert processor.asset_store.delete_image.call_args_list == [
        call("image-key-1"),
        call("image-key-2"),
    ]


def test_cleanup_images_continues_after_delete_failure(processor):
    processor.asset_store = Mock()
    processor.asset_store.delete_image.side_effect = [
        RuntimeError("First deletion failed"),
        None,
    ]
    processor._cleanup_images(["image-key-1", "image-key-2"])
    assert processor.asset_store.delete_image.call_count == 2


def test_cleanup_tables_deletes_every_key(processor):
    processor.table_store = Mock()
    processor._cleanup_tables(["table-key-1", "table-key-2"])
    assert processor.table_store.delete_table.call_args_list == [
        call("table-key-1"),
        call("table-key-2"),
    ]


def test_cleanup_tables_continues_after_delete_failure(processor):
    processor.table_store = Mock()
    processor.table_store.delete_table.side_effect = [
        RuntimeError("First deletion failed"),
        None,
    ]
    processor._cleanup_tables(["table-key-1", "table-key-2"])
    assert processor.table_store.delete_table.call_count == 2


def test_cleanup_uploaded_assets_delegates_to_both_cleanup_methods(monkeypatch, processor):
    cleanup_images = Mock()
    cleanup_tables = Mock()
    monkeypatch.setattr(processor, "_cleanup_images", cleanup_images)
    monkeypatch.setattr(processor, "_cleanup_tables", cleanup_tables)
    processor._cleanup_uploaded_assets(
        image_keys=["image-key"],
        table_keys=["table-key"],
    )
    cleanup_images.assert_called_once_with(["image-key"])
    cleanup_tables.assert_called_once_with(["table-key"])


# Asset tracking and rollback through process()

def test_process_tracks_images_and_tables(monkeypatch, processor, clinical_document):
    fake_pdf = FakePDF([FakePage("alpha beta gamma")])
    image = DocumentImage(
        image_id="image-1-1",
        page_number=1,
        extension="png",
        s3_key="image-key",
        width=100,
        height=100,
    )
    table = DocumentTable(
        table_id="table-1-1",
        page_number=1,
        s3_key="table-key",
        row_count=2,
        column_count=2,
    )
    monkeypatch.setattr(
        "processors.pdf_processor.pymupdf.open",
        lambda path: fake_pdf,
    )
    monkeypatch.setattr(processor, "_extract_images", lambda **kwargs: [image])
    monkeypatch.setattr(processor, "_extract_tables", lambda **kwargs: [table])
    result = processor.process(clinical_document)
    assert result.processing_status == "SUCCESS"
    assert result.images == [image]
    assert result.tables == [table]
    assert result.image_count == 1
    assert result.table_count == 1


def test_fatal_failure_rolls_back_uploaded_assets(monkeypatch, processor, clinical_document):
    class FailingTextPage(FakePage):
        def get_text(self):
            raise RuntimeError("Text extraction failed")

    fake_pdf = FakePDF([FailingTextPage("")])
    image = DocumentImage(
        image_id="image-1-1",
        page_number=1,
        extension="png",
        s3_key="uploaded-image-key",
        width=100,
        height=100,
    )
    table = DocumentTable(
        table_id="table-1-1",
        page_number=1,
        s3_key="uploaded-table-key",
        row_count=1,
        column_count=1,
    )
    cleanup_mock = Mock()
    monkeypatch.setattr(
        "processors.pdf_processor.pymupdf.open",
        lambda path: fake_pdf,
    )
    monkeypatch.setattr(processor, "_extract_images", lambda **kwargs: [image])
    monkeypatch.setattr(processor, "_extract_tables", lambda **kwargs: [table])
    monkeypatch.setattr(processor, "_cleanup_uploaded_assets", cleanup_mock)
    result = processor.process(clinical_document)
    cleanup_mock.assert_called_once_with(
        image_keys=["uploaded-image-key"],
        table_keys=["uploaded-table-key"],
    )
    assert result.processing_status == "FAILED"
    assert result.error_message == "Text extraction failed"
    assert result.raw_text == ""
    assert result.pages == []
    assert result.images == []
    assert result.tables == []
    assert result.page_count == 0
    assert result.ocr_page_count == 0
    assert result.image_count == 0
    assert result.table_count == 0


def test_ocr_failure_adds_warning(
    monkeypatch,
    clinical_document,
):
    ocr_processor = FakeOCRProcessor(
        exception=RuntimeError(
            "OCR unavailable"
        )
    )

    processor = PDFProcessor(
        ocr_processor=ocr_processor,
        pages_to_read="all",
        min_words_per_page=5,
        min_quality_score=0.6,
    )

    fake_pdf = FakePDF(
        [
            FakePage("short")
        ]
    )

    patch_pdf(
        monkeypatch,
        processor,
        fake_pdf,
    )

    monkeypatch.setattr(
        processor,
        "_page_to_bytes",
        lambda page: b"page-image",
    )

    result = processor.process(
        clinical_document
    )

    assert result.warnings == [
        (
            "OCR failed for page 1; "
            "native text was retained."
        )
    ]


def test_empty_ocr_result_adds_warning(
    monkeypatch,
    clinical_document,
):
    ocr_processor = FakeOCRProcessor(
        text="   "
    )

    processor = PDFProcessor(
        ocr_processor=ocr_processor,
        pages_to_read="all",
        min_words_per_page=5,
        min_quality_score=0.6,
    )

    fake_pdf = FakePDF(
        [
            FakePage("short")
        ]
    )

    patch_pdf(
        monkeypatch,
        processor,
        fake_pdf,
    )

    monkeypatch.setattr(
        processor,
        "_page_to_bytes",
        lambda page: b"page-image",
    )

    result = processor.process(
        clinical_document
    )

    assert result.warnings == [
        (
            "OCR failed for page 1; "
            "native text was retained."
        )
    ]


def test_missing_ocr_processor_adds_warning(
    monkeypatch,
    clinical_document,
):
    processor = PDFProcessor(
        ocr_processor=None,
        pages_to_read="all",
        min_words_per_page=5,
        min_quality_score=0.6,
    )

    fake_pdf = FakePDF(
        [
            FakePage("short")
        ]
    )

    patch_pdf(
        monkeypatch,
        processor,
        fake_pdf,
    )

    result = processor.process(
        clinical_document
    )

    assert result.warnings == [
        (
            "Page 1 required OCR, "
            "but no OCR processor "
            "was configured."
        )
    ]


def test_image_failure_adds_warning(
    processor,
    clinical_document,
):
    parent = FakeImageParent(
        exceptions_by_xref={
            101: RuntimeError(
                "Image is corrupted"
            )
        }
    )

    page = FakeImagePage(
        [(101,)],
        parent,
    )

    processor.asset_store = Mock()

    result = processor._extract_images(
        page=page,
        page_number=2,
        document=clinical_document,
    )

    assert result == []

    assert clinical_document.warnings == [
        (
            "One image could not be "
            "extracted from page 2."
        )
    ]


def test_table_discovery_failure_adds_warning(
    processor,
    clinical_document,
):
    page = FakeTablePage(
        exception=RuntimeError(
            "Table detector failed"
        )
    )

    processor.table_store = Mock()

    result = processor._extract_tables(
        page=page,
        page_number=3,
        document=clinical_document,
    )

    assert result == []

    assert clinical_document.warnings == [
        (
            "Table discovery failed "
            "for page 3."
        )
    ]


def test_individual_table_failure_adds_warning(
    processor,
    clinical_document,
):
    page = FakeTablePage(
        [
            FakeExtractedTable(
                exception=RuntimeError(
                    "Table extraction failed"
                )
            )
        ]
    )

    processor.table_store = Mock()

    result = processor._extract_tables(
        page=page,
        page_number=4,
        document=clinical_document,
    )

    assert result == []

    assert clinical_document.warnings == [
        (
            "Table 1 could not be "
            "extracted from page 4."
        )
    ]