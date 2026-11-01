import time,pytest
from services.canonical_document_parser import CanonicalDocumentParser
pytestmark=[pytest.mark.performance,pytest.mark.local]

def test_canonical_fixture_parses_within_local_budget(canonical_fixture_dir):
    value=(canonical_fixture_dir/"extracted-document.json").read_text()
    started=time.perf_counter()
    for _ in range(20): CanonicalDocumentParser().parse(value)
    assert time.perf_counter()-started < 2.0
