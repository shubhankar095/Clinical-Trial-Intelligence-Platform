import hashlib
import json
from dataclasses import fields as dataclass_fields
from datetime import datetime, timezone

import pytest
from botocore.exceptions import ClientError

from exceptions.extraction_manifest import ManifestLoadError, ManifestLocationError, ManifestNotFoundError
from models.ingestion_manifest import IngestionFailureManifest, IngestionSuccessManifest
from models.extraction_manifest import ExtractionSuccessManifest
from models.storage_location import StorageLocation
from storage.s3_ingestion_manifest_store import IngestionManifestWriteError, S3IngestionManifestStore
from storage.s3_text_store import S3TextStore


pytestmark = pytest.mark.unit


class _FakeS3:
    def __init__(self, *, response=None, result="text", error=None):
        self.response = response if response is not None else {}
        self.result = result
        self.error = error
        self.uploads = []
        self.downloads = []

    def upload_text(self, **kwargs):
        self.uploads.append(kwargs)
        if self.error:
            raise self.error
        return self.response

    def download_text(self, **kwargs):
        self.downloads.append(kwargs)
        if self.error:
            raise self.error
        return self.result

    def object_exists(self, **kwargs):
        return True


def _success_manifest():
    return IngestionSuccessManifest(
        event_type="INGESTION_COMPLETED",
        manifest_schema_version="ingestion-success-v1",
        processing_status="SUCCESS",
        document_id="d" * 64,
        ingestion_id="ingestion-1",
        ingestion_profile_id="profile-1",
        processing_schema_version="extraction-v1",
        ingestion_schema_version="ingestion-v1",
        index_schema_version="v1",
        source_bucket="source",
        source_key="source.pdf",
        source_version_id="source-version",
        canonical_bucket="canonical",
        canonical_key="canonical.json",
        canonical_version_id=None,
        canonical_sha256=None,
        index_destination="index",
        index_record_count=1,
        chunk_count=1,
        embedding_provider="bedrock",
        embedding_model_id="model",
        embedding_dimensions=1,
        embedding_normalized=True,
        completed_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )


def _failure_manifest():
    return IngestionFailureManifest(
        event_type="INGESTION_FAILED",
        manifest_schema_version="ingestion-failure-v1",
        processing_status="FAILED",
        document_id="d" * 64,
        ingestion_id="ingestion-1",
        ingestion_profile_id="profile-1",
        processing_schema_version="extraction-v1",
        ingestion_schema_version="ingestion-v1",
        manifest_bucket="canonical",
        manifest_key="canonical/_SUCCESS.json",
        manifest_version_id=None,
        error_type="PermanentIngestionError",
        error_message="failed",
        failed_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )


def _client_error(code, status=None):
    response = {"Error": {"Code": code}}
    if status is not None:
        response["ResponseMetadata"] = {"HTTPStatusCode": status}
    return ClientError(response, "GetObject")


def test_s3_text_store_success_and_client_error_translation(monkeypatch):
    monkeypatch.setattr("storage.s3_text_store.S3Service", _FakeS3)
    service = _FakeS3(result="canonical text")
    store = S3TextStore(service)
    location = StorageLocation(bucket="canonical", key="doc.json", version_id="v1")
    assert store.load_text(location) == "canonical text"
    assert service.downloads == [
        {"bucket": "canonical", "key": "doc.json", "version_id": "v1"}
    ]

    for error, expected in (
        (_client_error("NoSuchKey"), ManifestNotFoundError),
        (_client_error("Unknown", 404), ManifestNotFoundError),
        (_client_error("AccessDenied", 403), ManifestLoadError),
        (UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid"), ManifestLoadError),
    ):
        with pytest.raises(expected):
            S3TextStore(_FakeS3(error=error)).load_text(location)

    with pytest.raises(TypeError):
        store.load_text(None)
    with pytest.raises(TypeError):
        S3TextStore(object())


def test_s3_manifest_store_writes_canonical_payload_and_checksums(monkeypatch):
    monkeypatch.setattr("storage.s3_ingestion_manifest_store.S3Service", _FakeS3)
    service = _FakeS3(response={"VersionId": " v1 ", "ETag": '"abc"'})
    store = S3IngestionManifestStore(bucket=" results ", prefix="/my/results/", s3_service=service)
    result = store.write_success(_success_manifest())
    upload = service.uploads[0]
    content = upload["content"]
    assert json.loads(content)["processing_status"] == "SUCCESS"
    assert result.bucket == "results"
    assert result.key == "my/results/ingestion-1/_SUCCESS.json"
    assert result.version_id == "v1"
    assert result.etag == "abc"
    assert result.content_length == len(content.encode("utf-8"))
    assert result.checksum_sha256 == hashlib.sha256(content.encode("utf-8")).hexdigest()
    assert upload["content_type"] == "application/json"
    assert upload["metadata"]["content-sha256"] == result.checksum_sha256
    assert store.build_failure_key("ingestion-1") == "my/results/ingestion-1/_FAILED.json"
    assert store.success_manifest_exists("ingestion-1") is True


def test_s3_manifest_store_failure_write_and_validation(monkeypatch):
    monkeypatch.setattr("storage.s3_ingestion_manifest_store.S3Service", _FakeS3)
    store = S3IngestionManifestStore(bucket="bucket", s3_service=_FakeS3(response={}))
    result = store.write_failure(_failure_manifest())
    assert result.version_id is None
    assert result.etag is None
    assert result.key.endswith("/_FAILED.json")

    error = OSError("offline")
    failing = S3IngestionManifestStore(bucket="bucket", s3_service=_FakeS3(error=error))
    with pytest.raises(IngestionManifestWriteError) as raised:
        failing.write_failure(_failure_manifest())
    assert raised.value.__cause__ is error

    invalid_response = S3IngestionManifestStore(
        bucket="bucket",
        s3_service=_FakeS3(response={"VersionId": 1}),
    )
    with pytest.raises(IngestionManifestWriteError):
        invalid_response.write_success(_success_manifest())

    for kwargs in (
        {"bucket": " "},
        {"bucket": 3},
        {"bucket": "bucket", "prefix": "///"},
        {"bucket": "bucket", "prefix": 3},
        {"bucket": "bucket", "prefix": "a//b"},
        {"bucket": "bucket", "prefix": "a\\b"},
        {"bucket": "bucket", "s3_service": object()},
    ):
        with pytest.raises((TypeError, ValueError)):
            S3IngestionManifestStore(**kwargs)
    with pytest.raises(ValueError):
        store.build_success_key("a/b")
    with pytest.raises(TypeError):
        store.write_success(object())
    with pytest.raises(TypeError):
        store.write_failure(object())


def test_manifest_models_normalize_and_validate_required_fields():
    success = _success_manifest()
    assert success.to_payload()["completed_at"] == "2024-01-01T00:00:00+00:00"
    success_values = {
        item.name: getattr(success, item.name) for item in dataclass_fields(success)
    }
    with_optional_values = IngestionSuccessManifest(
        **(success_values | {"canonical_version_id": " version ", "canonical_sha256": " digest "})
    )
    assert with_optional_values.canonical_version_id == "version"
    assert with_optional_values.canonical_sha256 == "digest"
    failure = _failure_manifest()
    assert failure.to_payload()["failed_at"] == "2024-01-01T00:00:00+00:00"

    for kwargs in (
        {"event_type": "wrong"},
        {"manifest_schema_version": "wrong"},
        {"processing_status": "FAILED"},
        {"index_record_count": -1},
        {"chunk_count": -1},
        {"embedding_dimensions": 0},
        {"embedding_dimensions": True},
        {"embedding_normalized": 1},
        {"index_record_count": 0},
        {"canonical_version_id": " "},
    ):
        fields = {field: getattr(success, field) for field in success.__dataclass_fields__}
        fields.update(kwargs)
        with pytest.raises((TypeError, ValueError)):
            IngestionSuccessManifest(**fields)

    for kwargs in (
        {"event_type": "wrong"},
        {"manifest_schema_version": "wrong"},
        {"processing_status": "SUCCESS"},
        {"error_message": " "},
        {"manifest_version_id": " "},
        {"failed_at": datetime(2024, 1, 1)},
    ):
        fields = {field: getattr(failure, field) for field in failure.__dataclass_fields__}
        fields.update(kwargs)
        with pytest.raises((TypeError, ValueError)):
            IngestionFailureManifest(**fields)

    success_values = {item.name: getattr(success, item.name) for item in dataclass_fields(success)}
    for changes, error in (
        ({"document_id": None}, TypeError),
        ({"canonical_version_id": 1}, TypeError),
        ({"index_record_count": True}, TypeError),
        ({"completed_at": "2024-01-01"}, TypeError),
        ({"completed_at": datetime(2024, 1, 1)}, ValueError),
    ):
        with pytest.raises(error):
            IngestionSuccessManifest(**(success_values | changes))

    failure_values = {item.name: getattr(failure, item.name) for item in dataclass_fields(failure)}
    for changes, error in (
        ({"manifest_bucket": None}, TypeError),
        ({"manifest_version_id": 1}, TypeError),
        ({"failed_at": "2024-01-01"}, TypeError),
        ({"failed_at": datetime(2024, 1, 1)}, ValueError),
    ):
        with pytest.raises(error):
            IngestionFailureManifest(**(failure_values | changes))


def test_extraction_manifest_model_rejects_non_mapping_additional_fields():
    manifest = ExtractionSuccessManifest(
        document_id="d" * 64,
        source_bucket="source",
        source_key="source.pdf",
        source_version_id="version",
        processing_schema_version="extraction-v1",
        canonical_bucket="canonical",
        canonical_key="canonical.json",
        completed_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        processing_status="SUCCESS",
    )
    with pytest.raises(TypeError):
        ExtractionSuccessManifest(
            document_id=manifest.document_id,
            source_bucket=manifest.source_bucket,
            source_key=manifest.source_key,
            source_version_id=manifest.source_version_id,
            processing_schema_version=manifest.processing_schema_version,
            canonical_bucket=manifest.canonical_bucket,
            canonical_key=manifest.canonical_key,
            completed_at=manifest.completed_at,
            processing_status=manifest.processing_status,
            additional_fields=[],
        )


def test_s3_text_store_rejects_missing_bucket():
    store = object.__new__(S3TextStore)
    store.s3_service = _FakeS3()
    location = object.__new__(StorageLocation)
    object.__setattr__(location, "bucket", "")
    object.__setattr__(location, "key", "doc")
    object.__setattr__(location, "version_id", None)
    with pytest.raises(ManifestLocationError):
        store.load_text(location)
