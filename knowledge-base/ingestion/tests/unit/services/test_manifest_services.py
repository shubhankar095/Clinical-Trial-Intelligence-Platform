import json

import pytest

from exceptions.extraction_manifest import (
    ManifestJsonError,
    ManifestLoadError,
    ManifestNotFoundError,
)
from models.storage_location import StorageLocation
from services.canonical_document_service import CanonicalDocumentService
from services.extraction_manifest_service import ExtractionManifestService
from storage.base_text_store import BaseTextStore


pytestmark = pytest.mark.unit


class _TextStore(BaseTextStore):
    def __init__(self, values):
        self.values = values
        self.locations = []

    def load_text(self, location):
        self.locations.append(location)
        value = self.values[(location.bucket, location.key)]
        if isinstance(value, Exception):
            raise value
        return value


def test_extraction_manifest_service_loads_parses_and_validates(canonical_fixture_dir):
    manifest_text = (canonical_fixture_dir / "_SUCCESS.json").read_text()
    canonical_bucket = json.loads(manifest_text)["canonical_bucket"]
    document_id = canonical_fixture_dir.name
    location = StorageLocation(
        bucket=canonical_bucket,
        key=f"canonical-documents/{document_id}/_SUCCESS.json",
        version_id=None,
    )
    store = _TextStore({(canonical_bucket, location.key): manifest_text})

    manifest = ExtractionManifestService(store).load_and_validate(location)

    assert manifest.document_id == document_id
    assert store.locations == [location]


@pytest.mark.parametrize(
    ("stored_value", "expected_exception"),
    [
        (ManifestNotFoundError("missing"), ManifestNotFoundError),
        (ManifestLoadError("unavailable"), ManifestLoadError),
        ("not valid json", ManifestJsonError),
    ],
)
def test_extraction_manifest_service_propagates_load_and_parse_errors(
    canonical_fixture_dir,
    stored_value,
    expected_exception,
):
    document_id = canonical_fixture_dir.name
    location = StorageLocation(
        bucket="canonical",
        key=f"canonical-documents/{document_id}/_SUCCESS.json",
        version_id=None,
    )
    store = _TextStore({("canonical", location.key): stored_value})

    with pytest.raises(expected_exception):
        ExtractionManifestService(store).load_and_validate(location)


def test_canonical_document_service_loads_and_validates(canonical_fixture_dir):
    manifest_text = (canonical_fixture_dir / "_SUCCESS.json").read_text()
    document_text = (canonical_fixture_dir / "extracted-document.json").read_text()
    document_id = canonical_fixture_dir.name
    canonical_bucket = json.loads(manifest_text)["canonical_bucket"]
    manifest_location = StorageLocation(
        bucket=canonical_bucket,
        key=f"canonical-documents/{document_id}/_SUCCESS.json",
        version_id=None,
    )
    manifest = ExtractionManifestService(
        _TextStore({(canonical_bucket, manifest_location.key): manifest_text})
    ).load_and_validate(manifest_location)
    document_location = (manifest.canonical_bucket, manifest.canonical_key)
    store = _TextStore({document_location: document_text})

    document = CanonicalDocumentService(store).load_and_validate(manifest)

    assert document.document_id == manifest.document_id
    assert store.locations[0].bucket == manifest.canonical_bucket
    assert store.locations[0].key == manifest.canonical_key
