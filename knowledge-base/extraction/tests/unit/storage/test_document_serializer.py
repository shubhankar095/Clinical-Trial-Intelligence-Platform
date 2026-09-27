import json

from models.document import (
    ClinicalDocument,
    DocumentImage,
    DocumentMetadata,
    DocumentPage,
    DocumentTable,
)
from storage.document_serializer import (
    DocumentSerializer,
)


def build_document():
    return ClinicalDocument(
        document_id="document-123",
        file_name="sample.pdf",
        file_format="pdf",
        source_bucket="raw-bucket",
        source_key=(
            "documents/TEST001/"
            "protocols/sample.pdf"
        ),
        local_file_path=(
            "/tmp/private-path.pdf"
        ),
        canonical_bucket=(
            "canonical-bucket"
        ),
        canonical_key=(
            "canonical-documents/"
            "sample/extracted-document.json"
        ),
        metadata=DocumentMetadata(
            study_id="TEST001",
            document_type="PROTOCOL",
            version="1",
            sponsor="Sponsor A",
            phase="III",
        ),
        raw_text="Unicode text: café 日本語",
        pages=[
            DocumentPage(
                page_number=1,
                text="Page one",
                start_offset=0,
                end_offset=8,
                word_count=2,
                quality_score=0.9,
                requires_ocr=False,
                ocr_applied=False,
                extraction_method="TEXT",
            )
        ],
        page_count=1,
        ocr_page_count=0,
        image_count=1,
        table_count=1,
        images=[
            DocumentImage(
                image_id="image-1-1",
                page_number=1,
                extension="png",
                s3_key=(
                    "canonical-documents/"
                    "sample/images/"
                    "image-1-1.png"
                ),
                width=100,
                height=200,
            )
        ],
        tables=[
            DocumentTable(
                table_id="table-1-1",
                page_number=1,
                s3_key=(
                    "canonical-documents/"
                    "sample/tables/"
                    "table-1-1.json"
                ),
                row_count=2,
                column_count=3,
                title="Test table",
            )
        ],
        processing_status="SUCCESS",
        error_message=None,
    )


def test_serialize_returns_valid_json():
    document = build_document()

    serialized = (
        DocumentSerializer.serialize(
            document
        )
    )

    payload = json.loads(
        serialized
    )

    assert isinstance(
        payload,
        dict,
    )


def test_serialize_excludes_local_file_path():
    document = build_document()

    payload = json.loads(
        DocumentSerializer.serialize(
            document
        )
    )

    assert (
        "local_file_path"
        not in payload
    )


def test_serialize_preserves_unicode():
    document = build_document()

    serialized = (
        DocumentSerializer.serialize(
            document
        )
    )

    assert "café" in serialized
    assert "日本語" in serialized


def test_serialize_includes_metadata():
    document = build_document()

    payload = json.loads(
        DocumentSerializer.serialize(
            document
        )
    )

    assert payload["metadata"] == {
        "study_id": "TEST001",
        "document_type": "PROTOCOL",
        "version": "1",
        "sponsor": "Sponsor A",
        "phase": "III",
    }


def test_serialize_includes_pages():
    document = build_document()

    payload = json.loads(
        DocumentSerializer.serialize(
            document
        )
    )

    assert len(
        payload["pages"]
    ) == 1

    page = payload["pages"][0]

    assert page["page_number"] == 1
    assert page["text"] == "Page one"
    assert page["start_offset"] == 0
    assert page["end_offset"] == 8
    assert page["word_count"] == 2
    assert page["quality_score"] == 0.9
    assert page["requires_ocr"] is False
    assert page["ocr_applied"] is False

    assert (
        page["extraction_method"]
        == "TEXT"
    )


def test_serialize_includes_images():
    document = build_document()

    payload = json.loads(
        DocumentSerializer.serialize(
            document
        )
    )

    assert len(
        payload["images"]
    ) == 1

    image = payload["images"][0]

    assert (
        image["image_id"]
        == "image-1-1"
    )

    assert image["width"] == 100
    assert image["height"] == 200


def test_serialize_includes_tables():
    document = build_document()

    payload = json.loads(
        DocumentSerializer.serialize(
            document
        )
    )

    assert len(
        payload["tables"]
    ) == 1

    table = payload["tables"][0]

    assert (
        table["table_id"]
        == "table-1-1"
    )

    assert table["row_count"] == 2
    assert table["column_count"] == 3
    assert table["title"] == (
        "Test table"
    )


def test_serialize_includes_processing_status():
    document = build_document()

    payload = json.loads(
        DocumentSerializer.serialize(
            document
        )
    )

    assert (
        payload["processing_status"]
        == "SUCCESS"
    )

    assert (
        payload["error_message"]
        is None
    )