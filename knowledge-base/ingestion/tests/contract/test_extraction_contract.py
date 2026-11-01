import pytest
from models.storage_location import StorageLocation
from services.extraction_manifest_parser import ExtractionManifestParser
from services.extraction_manifest_validator import ExtractionManifestValidator

pytestmark = [pytest.mark.contract, pytest.mark.local]


def test_committed_success_manifest_matches_ingestion_contract(canonical_fixture_dir):
    manifest = ExtractionManifestParser().parse(
        (canonical_fixture_dir / "_SUCCESS.json").read_text()
    )
    location = StorageLocation(
        bucket=manifest.canonical_bucket,
        key=f"canonical-documents/{manifest.document_id}/_SUCCESS.json",
        version_id=None,
    )
    validated = ExtractionManifestValidator().validate(
        manifest=manifest,
        location=location,
    )
    assert validated.document_id == canonical_fixture_dir.name
    assert validated.processing_schema_version == "extraction-v1"
