import pytest
from services.canonical_document_parser import CanonicalDocumentParser
from services.canonical_document_validator import CanonicalDocumentValidator
from services.extraction_manifest_parser import ExtractionManifestParser

pytestmark = [pytest.mark.contract, pytest.mark.local]


def test_committed_canonical_document_is_self_consistent(canonical_fixture_dir):
    manifest = ExtractionManifestParser().parse(
        (canonical_fixture_dir / "_SUCCESS.json").read_text()
    )
    document = CanonicalDocumentParser().parse(
        (canonical_fixture_dir / "extracted-document.json").read_text()
    )
    validated = CanonicalDocumentValidator().validate(document, manifest)
    assert validated.document_id == canonical_fixture_dir.name
    assert validated.page_count == len(validated.pages)
    assert validated.table_count == len(validated.tables)
    for page in validated.pages:
        assert validated.raw_text[page.start_offset:page.end_offset] == page.text
