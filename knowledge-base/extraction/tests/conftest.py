import pytest

from models.document import (
    ClinicalDocument,
    DocumentImage,
    DocumentMetadata,
    DocumentTable,
)


@pytest.fixture
def clinical_document(
    tmp_path,
) -> ClinicalDocument:

    source_file = (
        tmp_path / "sample.pdf"
    )

    source_file.write_bytes(
        b"%PDF-test-content"
    )

    return ClinicalDocument(
        document_id="document-123",
        file_name="sample.pdf",
        file_format="pdf",
        source_bucket="raw-bucket",
        source_key=(
            "documents/TEST001/"
            "protocols/sample.pdf"
        ),
        local_file_path=str(
            source_file
        ),
        metadata=DocumentMetadata(
            study_id="TEST001",
            document_type="PROTOCOL",
            version="1",
        ),
    )


@pytest.fixture
def document_with_assets(
    clinical_document,
) -> ClinicalDocument:

    clinical_document.images = [
        DocumentImage(
            image_id="image-1-1",
            page_number=1,
            extension="png",
            s3_key=(
                "canonical-documents/"
                "sample/images/image-1-1.png"
            ),
            width=100,
            height=100,
        )
    ]

    clinical_document.tables = [
        DocumentTable(
            table_id="table-1-1",
            page_number=1,
            s3_key=(
                "canonical-documents/"
                "sample/tables/table-1-1.json"
            ),
            row_count=2,
            column_count=2,
        )
    ]

    clinical_document.image_count = 1
    clinical_document.table_count = 1

    return clinical_document