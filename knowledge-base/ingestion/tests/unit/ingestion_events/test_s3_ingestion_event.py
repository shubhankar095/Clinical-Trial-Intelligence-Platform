import json
from urllib.parse import quote_plus
import pytest
from exceptions.ingestion_event import IgnorableIngestionEvent
from ingestion_events.ingestion_event import IngestionEventFieldError, IngestionEventJsonError
from ingestion_events.s3_ingestion_event import S3IngestionEventParser
pytestmark=pytest.mark.unit
DOC="a"*64; KEY=f"canonical-documents/{DOC}/_SUCCESS.json"
def payload(key=KEY, event_name="ObjectCreated:Put", source="aws:s3", version="v1"):
    obj={"key":key};
    if version is not ...: obj["versionId"]=version
    return {"Records":[{"eventSource":source,"eventName":event_name,"eventTime":"2026-10-19T12:30:00Z","s3":{"bucket":{"name":"bucket"},"object":obj}}]}
def parse(p): return S3IngestionEventParser().parse(json.dumps(p))

def test_parses_s3_event():
    e=parse(payload()); assert e.document_id==DOC and e.manifest_version_id=="v1"

def test_decodes_key(): assert parse(payload(quote_plus(KEY, safe=""))).manifest_key==KEY

def test_version_is_optional(): assert parse(payload(version=...)).manifest_version_id is None

def test_ignores_test_event():
    with pytest.raises(IgnorableIngestionEvent): parse({"Event":"s3:TestEvent"})

@pytest.mark.parametrize("body", ["", "bad", "[]", "null"])
def test_rejects_invalid_body(body):
    with pytest.raises(IngestionEventJsonError): S3IngestionEventParser().parse(body)

@pytest.mark.parametrize("records", [None, [], [{},{}]])
def test_requires_one_record(records):
    with pytest.raises(IngestionEventFieldError): parse({"Records":records})

def test_requires_s3_source():
    with pytest.raises(IngestionEventFieldError): parse(payload(source="aws:sns"))

def test_requires_object_created():
    with pytest.raises(IngestionEventFieldError): parse(payload(event_name="ObjectRemoved:Delete"))

@pytest.mark.parametrize("details", [None, [], "invalid"])
def test_requires_s3_details_object(details):
    p=payload(); p["Records"][0]["s3"]=details
    with pytest.raises(IngestionEventFieldError): parse(p)

@pytest.mark.parametrize(
    "bucket,obj",
    [
        (None, {"key": KEY}),
        ({}, None),
        ([], {"key": KEY}),
        ({"name": "bucket"}, []),
    ],
)
def test_requires_bucket_and_object_objects(bucket, obj):
    p=payload(); p["Records"][0]["s3"]={"bucket":bucket,"object":obj}
    with pytest.raises(IngestionEventFieldError): parse(p)

@pytest.mark.parametrize("name", [None, "", " "])
def test_requires_nonblank_bucket_name(name):
    p=payload(); p["Records"][0]["s3"]["bucket"]["name"]=name
    with pytest.raises(IngestionEventFieldError): parse(p)

@pytest.mark.parametrize("key", [None, "", " "])
def test_requires_nonblank_object_key(key):
    p=payload(); p["Records"][0]["s3"]["object"]["key"]=key
    with pytest.raises(IngestionEventFieldError): parse(p)

@pytest.mark.parametrize("key", ["bad", f"canonical-documents/{DOC}/wrong.json", f"canonical-documents/{'A'*64}/_SUCCESS.json"])
def test_rejects_bad_key(key):
    with pytest.raises(IngestionEventFieldError): parse(payload(key))

@pytest.mark.parametrize("version", [1, " "])
def test_rejects_invalid_object_version(version):
    with pytest.raises(IngestionEventFieldError): parse(payload(version=version))

@pytest.mark.parametrize("timestamp", [None, 1, " ", "invalid", "2026-10-19T12:30:00"])
def test_rejects_invalid_event_time(timestamp):
    p=payload(); p["Records"][0]["eventTime"]=timestamp
    with pytest.raises(IngestionEventFieldError): parse(p)
