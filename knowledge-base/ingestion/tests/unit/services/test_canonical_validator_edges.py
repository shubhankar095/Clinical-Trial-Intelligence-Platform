from dataclasses import replace

import pytest

from exceptions.canonical_document import (
    CanonicalDocumentContentError,
    CanonicalDocumentFieldError,
    CanonicalDocumentIdentityMismatchError,
)
from models.canonical_document import CanonicalDocumentImage, CanonicalDocumentTable
from services.canonical_document_parser import CanonicalDocumentParser
from services.canonical_document_validator import CanonicalDocumentValidator
from services.extraction_manifest_parser import ExtractionManifestParser


pytestmark = pytest.mark.unit


def _objects(directory):
    manifest = ExtractionManifestParser().parse((directory / "_SUCCESS.json").read_text())
    document = CanonicalDocumentParser().parse(
        (directory / "extracted-document.json").read_text()
    )
    return manifest, document


def test_canonical_validator_checks_pages_and_metadata_identity(canonical_fixture_dir):
    manifest, document = _objects(canonical_fixture_dir)
    validator = CanonicalDocumentValidator()
    first = document.pages[0]
    invalid_pages = (
        replace(first, page_number=0),
        replace(first, start_offset=-1),
        replace(first, end_offset=first.start_offset - 1),
        replace(first, end_offset=len(document.raw_text) + 1),
        replace(first, quality_score=float("nan")),
        replace(first, extraction_method="OTHER"),
    )
    for page in invalid_pages:
        with pytest.raises(CanonicalDocumentContentError):
            validator.validate(replace(document, pages=(page, *document.pages[1:])), manifest)

    for page in (
        replace(first, text="different"),
        replace(first, word_count=-1),
        replace(first, quality_score=2.0),
        replace(first, extraction_method="OCR", ocr_applied=False),
    ):
        validator.validate(replace(document, pages=(page, *document.pages[1:])), manifest)

    with pytest.raises(CanonicalDocumentIdentityMismatchError):
        validator.validate(document, replace(manifest, source_key="different"))
    invalid_id = "z" * 64
    with pytest.raises(CanonicalDocumentFieldError):
        validator.validate(
            replace(document, document_id=invalid_id),
            replace(manifest, document_id=invalid_id),
        )

    pages = list(document.pages)
    if len(pages) > 1:
        pages[1] = replace(pages[1], start_offset=pages[0].end_offset - 1)
        with pytest.raises(CanonicalDocumentContentError, match="overlap"):
            validator.validate(replace(document, pages=tuple(pages)), manifest)


def test_canonical_validator_checks_counts_and_image_references(canonical_fixture_dir):
    manifest, document = _objects(canonical_fixture_dir)
    validator = CanonicalDocumentValidator()
    for field in ("page_count", "ocr_page_count", "image_count", "table_count"):
        with pytest.raises(CanonicalDocumentContentError):
            validator.validate(replace(document, **{field: -1}), manifest)
    for field in ("page_count", "ocr_page_count", "image_count", "table_count"):
        current = getattr(document, field)
        with pytest.raises(CanonicalDocumentContentError):
            validator.validate(replace(document, **{field: current + 1}), manifest)

    valid_image = CanonicalDocumentImage(
        image_id="image-1",
        page_number=1,
        extension="png",
        s3_key="images/one.png",
        width=10,
        height=20,
    )
    valid_doc = replace(document, images=(valid_image,), image_count=1)
    assert validator.validate(valid_doc, manifest) is valid_doc
    invalid_images = (
        (valid_image, replace(valid_image, image_id="image-1", s3_key="images/two.png")),
        (valid_image, replace(valid_image, image_id="image-2", s3_key="images/one.png")),
        (replace(valid_image, page_number=999),),
        (replace(valid_image, width=0),),
        (replace(valid_image, height=-1),),
    )
    for images in invalid_images:
        with pytest.raises(CanonicalDocumentContentError):
            validator.validate(
                replace(document, images=images, image_count=len(images)),
                manifest,
            )


def test_canonical_validator_checks_table_references(canonical_fixture_dir):
    manifest, document = _objects(canonical_fixture_dir)
    validator = CanonicalDocumentValidator()
    table = CanonicalDocumentTable(
        table_id="table-1",
        page_number=1,
        s3_key="tables/one.json",
        row_count=0,
        column_count=1,
    )
    valid_doc = replace(document, tables=(table,), table_count=1)
    assert validator.validate(valid_doc, manifest) is valid_doc
    invalid_tables = (
        (table, replace(table, table_id="table-1", s3_key="tables/two.json")),
        (table, replace(table, table_id="table-2", s3_key="tables/one.json")),
        (replace(table, page_number=999),),
        (replace(table, row_count=-1),),
        (replace(table, column_count=-1),),
    )
    for tables in invalid_tables:
        with pytest.raises(CanonicalDocumentContentError):
            validator.validate(
                replace(document, tables=tables, table_count=len(tables)),
                manifest,
            )
