import pytest

from models.canonical_document import (
    CanonicalDocumentImage,
    CanonicalDocumentMetadata,
    CanonicalDocumentPage,
    CanonicalDocumentTable,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "constructor,values",
    [
        (CanonicalDocumentMetadata, {}),
        (
            CanonicalDocumentPage,
            {
                "page_number": 1,
                "text": "page",
                "start_offset": 0,
                "end_offset": 4,
                "word_count": 1,
                "quality_score": 1.0,
                "requires_ocr": False,
                "ocr_applied": False,
                "extraction_method": "native",
            },
        ),
        (
            CanonicalDocumentImage,
            {
                "image_id": "image-1",
                "page_number": 1,
                "extension": "png",
                "s3_key": "images/1.png",
                "width": 10,
                "height": 10,
            },
        ),
        (
            CanonicalDocumentTable,
            {
                "table_id": "table-1",
                "page_number": 1,
                "s3_key": "tables/1.json",
                "row_count": 1,
                "column_count": 1,
            },
        ),
    ],
)
def test_additional_fields_must_be_mapping(constructor, values):
    with pytest.raises(TypeError, match="Expected a mapping"):
        constructor(**values, additional_fields=None)
