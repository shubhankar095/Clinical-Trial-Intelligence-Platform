import json
from unittest.mock import Mock

import pytest

from models.document import (
    ClinicalDocument,
)
from storage.s3_document_store import (
    S3DocumentStore,
)


pytestmark = pytest.mark.unit


@pytest.fixture
def document():
    return ClinicalDocument(
        document_id="document-123",
        file_name=(
            "Clinical Protocol V1.pdf"
        ),
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
def store():
    document_store = (
        S3DocumentStore(
            "canonical-bucket"
        )
    )

    document_store.s3 = Mock()

    return document_store


def test_constructor_stores_bucket_name(
    store,
):
    assert store.bucket_name == (
        "canonical-bucket"
    )


def test_build_object_key(
    store,
    document,
):
    result = store.build_object_key(
        document
    )

    assert result == (
        "canonical-documents/"
        "document-123/"
        "extracted-document.json"
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
    document,
    document_id,
):
    document.document_id = document_id

    with pytest.raises(
        ValueError,
        match="document.document_id",
    ):
        store.build_object_key(
            document
        )


def test_save_uploads_serialized_document(
    store,
    document,
):
    result = store.save(
        document
    )

    expected_key = (
        "canonical-documents/"
        "document-123/"
        "extracted-document.json"
    )

    (
        store.s3
        .upload_text
        .assert_called_once()
    )

    upload_call = (
        store.s3
        .upload_text
        .call_args
        .kwargs
    )

    assert upload_call["bucket"] == (
        "canonical-bucket"
    )
    assert upload_call["key"] == (
        expected_key
    )

    payload = json.loads(
        upload_call["content"]
    )

    assert payload["document_id"] == (
        "document-123"
    )
    assert payload["source_version_id"] == (
        "version-1"
    )
    assert (
        payload["processing_schema_version"]
        == "extraction-v1"
    )
    assert (
        payload["processing_status"]
        == "SUCCESS"
    )
    assert (
        payload["canonical_key"]
        == document.canonical_key
    )
    assert "local_file_path" not in payload

    assert result == expected_key


def test_save_uses_key_derived_from_document_id(
    store,
    document,
):
    document.file_name = (
        "A Completely Different Name.pdf"
    )

    result = store.save(
        document
    )

    assert result == (
        "canonical-documents/"
        "document-123/"
        "extracted-document.json"
    )


def test_save_propagates_upload_failure(
    store,
    document,
):
    store.s3.upload_text.side_effect = (
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