import time
from pathlib import Path

import pymupdf
import pytest

from models.document import (
    ClinicalDocument,
)
from processors.pdf_processor import (
    PDFProcessor,
)


pytestmark = pytest.mark.performance


class NullAssetStore:

    def save_image(
        self,
        document,
        image_id,
        image_bytes,
        extension,
    ):
        return (
            f"null/images/"
            f"{image_id}.{extension}"
        )

    def delete_image(
        self,
        key,
    ):
        pass


class NullTableStore:

    def save_table(
        self,
        document,
        table_id,
        rows,
    ):
        return (
            f"null/tables/"
            f"{table_id}.json"
        )

    def delete_table(
        self,
        key,
    ):
        pass


def create_large_text_pdf(
    path: Path,
    page_count: int,
):
    document = pymupdf.open()

    for page_number in range(
        1,
        page_count + 1,
    ):
        page = document.new_page()

        lines = [
            (
                "Clinical Trial "
                f"Protocol Page {page_number}"
            ),
            "Study ID: PERF-001",
            (
                "This page contains "
                "representative clinical "
                "trial content."
            ),
            (
                "The participant attended "
                "the scheduled assessment."
            ),
            (
                "Safety, eligibility, and "
                "treatment data were reviewed."
            ),
        ]

        for line_number, line in enumerate(
            lines,
            start=1,
        ):
            page.insert_text(
                (
                    72,
                    72
                    + (
                        line_number
                        * 24
                    ),
                ),
                line,
                fontsize=11,
            )

    document.save(
        path
    )

    document.close()


def test_fifty_page_pdf_processes_with_consistent_counts(
    tmp_path,
):
    pdf_path = (
        tmp_path / "large.pdf"
    )

    create_large_text_pdf(
        pdf_path,
        page_count=50,
    )

    processor = PDFProcessor(
        ocr_processor=None,
        asset_store=NullAssetStore(),
        table_store=NullTableStore(),
        pages_to_read="all",
        min_words_per_page=2,
        min_quality_score=0.1,
    )

    clinical_document = (
        ClinicalDocument(
            document_id=(
                "performance-document"
            ),
            file_name="large.pdf",
            file_format="pdf",
            source_bucket="local",
            source_key=(
                "documents/PERF001/"
                "protocols/large.pdf"
            ),
            local_file_path=str(
                pdf_path
            ),
        )
    )

    started_at = time.perf_counter()

    result = processor.process(
        clinical_document
    )

    duration_seconds = (
        time.perf_counter()
        - started_at
    )

    assert (
        result.processing_status
        == "SUCCESS"
    )

    assert result.page_count == 50

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

    assert result.raw_text

    assert result.ocr_page_count == 0

    assert result.warnings == []

    assert len(
        result.raw_text
    ) > 5000

    for page in result.pages:
        assert (
            page.extraction_method
            == "TEXT"
        )

        assert (
            page.requires_ocr
            is False
        )

        assert (
            result.raw_text[
                page.start_offset:
                page.end_offset
            ]
            == page.text
        )

    print(
        "Performance result: "
        f"pages={result.page_count}, "
        f"duration_seconds="
        f"{duration_seconds:.3f}, "
        f"raw_text_chars="
        f"{len(result.raw_text)}"
    )