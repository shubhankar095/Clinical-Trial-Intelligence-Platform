import json,pytest
pytestmark=[pytest.mark.contract,pytest.mark.local]

def test_table_fixture_paths_match_canonical_references(canonical_fixture_dir):
    payload=json.loads((canonical_fixture_dir/"extracted-document.json").read_text())
    expected={item["s3_key"].split("/")[-1] for item in payload["tables"]}
    actual={path.name for path in (canonical_fixture_dir/"tables").glob("*.json")}
    assert actual==expected
