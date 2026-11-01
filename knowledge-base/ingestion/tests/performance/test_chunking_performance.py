import json,time,pytest
from services.canonical_document_parser import CanonicalDocumentParser
from tests.helpers.canonical_document_builder import expand_canonical_payload
pytestmark=[pytest.mark.performance,pytest.mark.local]

def test_generated_large_canonical_payload_parses_within_budget(canonical_fixture_dir):
    payload=json.loads((canonical_fixture_dir/"extracted-document.json").read_text())
    expanded=expand_canonical_payload(payload,copies=10)
    started=time.perf_counter();document=CanonicalDocumentParser().parse(json.dumps(expanded));elapsed=time.perf_counter()-started
    assert document.page_count==payload["page_count"]*10
    assert elapsed<2.0
