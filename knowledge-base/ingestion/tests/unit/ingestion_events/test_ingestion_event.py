import json
from datetime import timezone
import pytest
from ingestion_events.ingestion_event import IngestionEventParser, IngestionEventJsonError, IngestionEventFieldError, UnsupportedIngestionEventError, IngestionEventIdentityError
pytestmark=pytest.mark.unit
DOC="a"*64
KEY=f"canonical-documents/{DOC}/_SUCCESS.json"
def payload(**changes):
    p={"event_type":"EXTRACTION_COMPLETED","event_version":"1","document_id":DOC,"processing_schema_version":"extraction-v1","manifest_bucket":"bucket","manifest_key":KEY,"manifest_version_id":"v1","occurred_at":"2026-10-19T12:30:00Z"}; p.update(changes); return p
def parse(p): return IngestionEventParser().parse(json.dumps(p))

def test_parses_valid_event():
    e=parse(payload()); assert e.document_id==DOC and e.manifest_key==KEY and e.occurred_at.tzinfo==timezone.utc

def test_optional_version_may_be_missing():
    p=payload(); p.pop("manifest_version_id"); assert parse(p).manifest_version_id is None

@pytest.mark.parametrize("body", ["", " ", "bad", "[]", "null"])
def test_rejects_invalid_json_or_shape(body):
    with pytest.raises(IngestionEventJsonError): IngestionEventParser().parse(body)

@pytest.mark.parametrize("field", ["event_type","event_version","document_id","processing_schema_version","manifest_bucket","manifest_key","occurred_at"])
def test_requires_fields(field):
    p=payload(); p.pop(field)
    with pytest.raises(IngestionEventFieldError): parse(p)

@pytest.mark.parametrize("field", ["event_type","event_version","document_id","processing_schema_version","manifest_bucket","manifest_key","occurred_at"])
def test_rejects_blank_fields(field):
    with pytest.raises(IngestionEventFieldError): parse(payload(**{field:" "}))

@pytest.mark.parametrize("event_type", ["OTHER","EXTRACTION_FAILED"])
def test_rejects_event_type(event_type):
    with pytest.raises(UnsupportedIngestionEventError): parse(payload(event_type=event_type))

def test_rejects_event_version():
    with pytest.raises(UnsupportedIngestionEventError): parse(payload(event_version="2"))

def test_rejects_schema():
    with pytest.raises(UnsupportedIngestionEventError): parse(payload(processing_schema_version="v2"))

@pytest.mark.parametrize("doc", ["a"*63,"A"*64,"g"*64,"x"])
def test_rejects_document_id(doc):
    with pytest.raises(IngestionEventFieldError): parse(payload(document_id=doc))

def test_rejects_manifest_identity_mismatch():
    with pytest.raises(IngestionEventIdentityError): parse(payload(manifest_key=f"canonical-documents/{'b'*64}/_SUCCESS.json"))

@pytest.mark.parametrize("body", [None, 1])
def test_rejects_non_string_body(body):
    with pytest.raises(IngestionEventJsonError):
        IngestionEventParser().parse(body)

@pytest.mark.parametrize("bucket", ["bucket name", "bucket/path", r"bucket\path", "https://bucket"])
def test_rejects_malformed_bucket_names(bucket):
    with pytest.raises(IngestionEventFieldError):
        parse(payload(manifest_bucket=bucket))

def test_rejects_uri_scheme_after_path_delimiters_are_checked():
    class UrlBucket(str):
        def __contains__(self, value):
            if value in {"/", "\\"}:
                return False
            return super().__contains__(value)

    with pytest.raises(IngestionEventFieldError, match="URI scheme"):
        IngestionEventParser()._validate_bucket_name(UrlBucket("https://bucket"))

@pytest.mark.parametrize("key", [f"/canonical-documents/{DOC}/_SUCCESS.json", f"canonical-documents\\{DOC}\\_SUCCESS.json"])
def test_rejects_unsafe_manifest_key_format(key):
    with pytest.raises(IngestionEventFieldError):
        parse(payload(manifest_key=key))

@pytest.mark.parametrize("value", [None, 1, [], {}])
def test_required_fields_must_be_strings(value):
    with pytest.raises(IngestionEventFieldError):
        parse(payload(event_type=value))

@pytest.mark.parametrize("value", [1, [], {}])
def test_optional_version_must_be_string_or_null(value):
    with pytest.raises(IngestionEventFieldError):
        parse(payload(manifest_version_id=value))

@pytest.mark.parametrize("value", ["", " "])
def test_optional_version_must_not_be_blank(value):
    with pytest.raises(IngestionEventFieldError):
        parse(payload(manifest_version_id=value))

def test_timestamp_normalizes_lowercase_z_and_offsets():
    assert parse(payload(occurred_at="2026-10-19T14:30:00z")).occurred_at.hour == 14
    assert parse(payload(occurred_at="2026-10-19T14:30:00+02:00")).occurred_at.hour == 12

@pytest.mark.parametrize("timestamp", ["bad","2026-10-19T12:00:00"])
def test_rejects_invalid_or_naive_time(timestamp):
    with pytest.raises(IngestionEventFieldError): parse(payload(occurred_at=timestamp))
