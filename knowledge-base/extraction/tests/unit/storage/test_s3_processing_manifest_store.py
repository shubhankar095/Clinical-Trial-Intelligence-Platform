import json
from unittest.mock import Mock

import pytest

from models.document import (
    ClinicalDocument,
)
from models.processing_manifest import (
    ProcessingManifest,
)
from storage import (
    s3_processing_manifest_store,
)
from storage.s3_processing_manifest_store import (
    S3ProcessingManifestStore,
)


pytestmark = pytest.mark.unit


@pytest.fixture
def s3_service():
    return Mock()


@pytest.fixture
def store(
    s3_service,
):
    return S3ProcessingManifestStore(
        bucket_name="canonical-bucket",
        s3_service=s3_service,
    )


@pytest.fixture
def document():
    return ClinicalDocument(
        document_id="document-123",
        file_name="sample.pdf",
        file_format="pdf",
        source_bucket="raw-bucket",
        source_key=(
            "documents/TEST001/"
            "protocols/sample.pdf"
        ),
        source_version_id="version-1",
        processing_schema_version=(
            "extraction-v1"
        ),
        canonical_bucket=(
            "canonical-bucket"
        ),
        canonical_key=(
            "canonical-documents/"
            "document-123/"
            "extracted-document.json"
        ),
        processing_status="SUCCESS",
    )


@pytest.fixture
def manifest():
    return ProcessingManifest(
        document_id="document-123",
        source_bucket="raw-bucket",
        source_key=(
            "documents/TEST001/"
            "protocols/sample.pdf"
        ),
        source_version_id="version-1",
        processing_schema_version=(
            "extraction-v1"
        ),
        canonical_bucket=(
            "canonical-bucket"
        ),
        canonical_key=(
            "canonical-documents/"
            "document-123/"
            "extracted-document.json"
        ),
        completed_at=(
            "2026-09-26T15:39:57+00:00"
        ),
        processing_status="SUCCESS",
    )


def test_constructor_stores_dependencies(
    store,
    s3_service,
):
    assert store.bucket_name == (
        "canonical-bucket"
    )
    assert store.s3 is s3_service


def test_build_object_key(
    store,
):
    assert store.build_object_key(
        "document-123"
    ) == (
        "canonical-documents/"
        "document-123/"
        "_SUCCESS.json"
    )


@pytest.mark.parametrize(
    "document_id",
    [
        "",
        None,
    ],
)
def test_build_object_key_rejects_empty_document_id(
    store,
    document_id,
):
    with pytest.raises(
        ValueError,
        match="document_id",
    ):
        store.build_object_key(
            document_id
        )


def test_exists_delegates_to_s3(
    store,
    s3_service,
):
    s3_service.object_exists.return_value = (
        True
    )

    result = store.exists(
        "document-123"
    )

    assert result is True

    s3_service.object_exists.assert_called_once_with(
        bucket="canonical-bucket",
        key=(
            "canonical-documents/"
            "document-123/"
            "_SUCCESS.json"
        ),
    )


def test_load_downloads_and_deserializes_manifest(
    store,
    s3_service,
    manifest,
):
    s3_service.download_text.return_value = (
        json.dumps(
            {
                "document_id": (
                    manifest.document_id
                ),
                "source_bucket": (
                    manifest.source_bucket
                ),
                "source_key": (
                    manifest.source_key
                ),
                "source_version_id": (
                    manifest.source_version_id
                ),
                "processing_schema_version": (
                    manifest
                    .processing_schema_version
                ),
                "canonical_bucket": (
                    manifest.canonical_bucket
                ),
                "canonical_key": (
                    manifest.canonical_key
                ),
                "completed_at": (
                    manifest.completed_at
                ),
                "processing_status": (
                    manifest.processing_status
                ),
            }
        )
    )

    result = store.load(
        "document-123"
    )

    assert result == manifest

    s3_service.download_text.assert_called_once_with(
        bucket="canonical-bucket",
        key=(
            "canonical-documents/"
            "document-123/"
            "_SUCCESS.json"
        ),
    )


def test_load_propagates_invalid_json(
    store,
    s3_service,
):
    s3_service.download_text.return_value = (
        "{invalid-json"
    )

    with pytest.raises(
        json.JSONDecodeError,
    ):
        store.load(
            "document-123"
        )


def test_validate_accepts_matching_success_manifest(
    store,
    document,
    manifest,
):
    store.validate(
        document=document,
        manifest=manifest,
    )


@pytest.mark.parametrize(
    (
        "field_name",
        "replacement",
    ),
    [
        (
            "document_id",
            "different-document",
        ),
        (
            "source_bucket",
            "different-bucket",
        ),
        (
            "source_key",
            "different-key",
        ),
        (
            "source_version_id",
            "different-version",
        ),
        (
            "processing_schema_version",
            "extraction-v2",
        ),
    ],
)
def test_validate_rejects_identity_mismatch(
    store,
    document,
    manifest,
    field_name,
    replacement,
):
    setattr(
        manifest,
        field_name,
        replacement,
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        store.validate(
            document=document,
            manifest=manifest,
        )


def test_validate_rejects_non_success_status(
    store,
    document,
    manifest,
):
    manifest.processing_status = "FAILED"

    with pytest.raises(
        ValueError,
        match="SUCCESS status",
    ):
        store.validate(
            document=document,
            manifest=manifest,
        )


def test_save_rejects_failed_document(
    store,
    document,
):
    document.processing_status = "FAILED"

    with pytest.raises(
        ValueError,
        match="not successful",
    ):
        store.save(
            document
        )


def test_save_rejects_missing_canonical_key(
    store,
    document,
):
    document.canonical_key = ""

    with pytest.raises(
        ValueError,
        match="canonical_key",
    ):
        store.save(
            document
        )


def test_save_uploads_success_manifest(
    monkeypatch,
    store,
    s3_service,
    document,
):
    fixed_datetime = Mock()
    fixed_datetime.now.return_value.isoformat.return_value = (
        "2026-09-26T15:39:57+00:00"
    )

    monkeypatch.setattr(
        s3_processing_manifest_store,
        "datetime",
        fixed_datetime,
    )

    result = store.save(
        document
    )

    assert result == (
        "canonical-documents/"
        "document-123/"
        "_SUCCESS.json"
    )

    s3_service.upload_text.assert_called_once()

    upload_call = (
        s3_service
        .upload_text
        .call_args
        .kwargs
    )

    assert upload_call["bucket"] == (
        "canonical-bucket"
    )
    assert upload_call["key"] == result

    payload = json.loads(
        upload_call["content"]
    )

    assert payload == {
        "document_id": "document-123",
        "source_bucket": "raw-bucket",
        "source_key": (
            "documents/TEST001/"
            "protocols/sample.pdf"
        ),
        "source_version_id": "version-1",
        "processing_schema_version": (
            "extraction-v1"
        ),
        "canonical_bucket": (
            "canonical-bucket"
        ),
        "canonical_key": (
            "canonical-documents/"
            "document-123/"
            "extracted-document.json"
        ),
        "completed_at": (
            "2026-09-26T15:39:57+00:00"
        ),
        "processing_status": "SUCCESS",
    }


def test_save_propagates_upload_failure(
    store,
    s3_service,
    document,
):
    s3_service.upload_text.side_effect = (
        RuntimeError(
            "S3 upload failed"
        )
    )

    with pytest.raises(
        RuntimeError,
        match="S3 upload failed",
    ):
        store.save(
            document
        )