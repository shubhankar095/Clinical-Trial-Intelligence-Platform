import json
import pytest
from ingestion_events.s3_ingestion_event import S3IngestionEventParser
from tests.helpers.fixture_loader import read_text
pytestmark=[pytest.mark.contract,pytest.mark.local]

def test_native_s3_fixture_routes_to_committed_success_manifest():
    event=S3IngestionEventParser().parse(read_text("events/s3-object-created-success.json"))
    assert event is not None
    assert event.document_id=="5abd56280df8df8fed4df2924e9568d9f730be30d078666e8960fa013afe457e"
    assert event.manifest_key==f"canonical-documents/{event.document_id}/_SUCCESS.json"
    assert event.manifest_version_id=="test-version"
