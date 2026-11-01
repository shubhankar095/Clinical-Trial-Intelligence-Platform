import json
import pytest
from models.storage_location import StorageLocation
from services.extraction_manifest_service import ExtractionManifestService
from services.canonical_document_service import CanonicalDocumentService
from tests.fakes.pipeline import InMemoryTextStore

pytestmark = [pytest.mark.component, pytest.mark.local]


def test_real_services_load_and_validate_committed_extraction_output(canonical_fixture_dir):
    manifest_json = (canonical_fixture_dir / "_SUCCESS.json").read_text()
    canonical_json = (canonical_fixture_dir / "extracted-document.json").read_text()
    raw = json.loads(manifest_json)
    manifest_location = StorageLocation(
        bucket=raw["canonical_bucket"],
        key=f"canonical-documents/{raw['document_id']}/_SUCCESS.json",
        version_id=None,
    )
    canonical_location = (
        raw["canonical_bucket"],
        raw["canonical_key"],
        None,
    )
    store = InMemoryTextStore(
        {
            (manifest_location.bucket, manifest_location.key, None): manifest_json,
            canonical_location: canonical_json,
        }
    )
    manifest = ExtractionManifestService(store).load_and_validate(manifest_location)
    document = CanonicalDocumentService(store).load_and_validate(manifest)
    assert document.document_id == manifest.document_id
    assert document.raw_text
    assert len(store.loads) == 2
