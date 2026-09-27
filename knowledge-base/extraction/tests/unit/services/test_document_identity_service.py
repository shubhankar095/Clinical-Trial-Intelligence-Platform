import hashlib
import json

import pytest

from services.document_identity_service import (
    DocumentIdentityService,
)


pytestmark = pytest.mark.unit


@pytest.fixture
def service():
    return DocumentIdentityService()


def test_create_document_id_is_deterministic(
    service,
):
    first = service.create_document_id(
        source_bucket="raw-bucket",
        source_key=(
            "documents/TEST001/"
            "protocols/sample.pdf"
        ),
        source_version_id="version-1",
        processing_schema_version=(
            "extraction-v1"
        ),
    )

    second = service.create_document_id(
        source_bucket="raw-bucket",
        source_key=(
            "documents/TEST001/"
            "protocols/sample.pdf"
        ),
        source_version_id="version-1",
        processing_schema_version=(
            "extraction-v1"
        ),
    )

    assert first == second
    assert len(first) == 64


def test_create_document_id_uses_expected_payload(
    service,
):
    payload = {
        "processing_schema_version": (
            "extraction-v1"
        ),
        "source_bucket": "raw-bucket",
        "source_key": (
            "documents/TEST001/"
            "protocols/sample.pdf"
        ),
        "source_version_id": "version-1",
    }

    serialized = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    expected = hashlib.sha256(
        serialized.encode(
            "utf-8"
        )
    ).hexdigest()

    actual = service.create_document_id(
        source_bucket="raw-bucket",
        source_key=(
            "documents/TEST001/"
            "protocols/sample.pdf"
        ),
        source_version_id="version-1",
        processing_schema_version=(
            "extraction-v1"
        ),
    )

    assert actual == expected


def test_leading_and_trailing_spaces_are_removed(
    service,
):
    stripped = service.create_document_id(
        source_bucket="raw-bucket",
        source_key="documents/sample.pdf",
        source_version_id="version-1",
        processing_schema_version=(
            "extraction-v1"
        ),
    )

    padded = service.create_document_id(
        source_bucket=" raw-bucket ",
        source_key=(
            " documents/sample.pdf "
        ),
        source_version_id=" version-1 ",
        processing_schema_version=(
            " extraction-v1 "
        ),
    )

    assert padded == stripped


@pytest.mark.parametrize(
    (
        "field_name",
        "arguments",
        "message",
    ),
    [
        (
            "source_bucket",
            {
                "source_bucket": " ",
                "source_key": (
                    "documents/sample.pdf"
                ),
                "source_version_id": (
                    "version-1"
                ),
                "processing_schema_version": (
                    "extraction-v1"
                ),
            },
            "source_bucket",
        ),
        (
            "source_key",
            {
                "source_bucket": "raw-bucket",
                "source_key": " ",
                "source_version_id": (
                    "version-1"
                ),
                "processing_schema_version": (
                    "extraction-v1"
                ),
            },
            "source_key",
        ),
        (
            "source_version_id",
            {
                "source_bucket": "raw-bucket",
                "source_key": (
                    "documents/sample.pdf"
                ),
                "source_version_id": " ",
                "processing_schema_version": (
                    "extraction-v1"
                ),
            },
            "source_version_id",
        ),
        (
            "processing_schema_version",
            {
                "source_bucket": "raw-bucket",
                "source_key": (
                    "documents/sample.pdf"
                ),
                "source_version_id": (
                    "version-1"
                ),
                "processing_schema_version": (
                    " "
                ),
            },
            "processing_schema_version",
        ),
    ],
)
def test_empty_identity_component_is_rejected(
    service,
    field_name,
    arguments,
    message,
):
    del field_name

    with pytest.raises(
        ValueError,
        match=message,
    ):
        service.create_document_id(
            **arguments
        )


def test_different_version_produces_different_identity(
    service,
):
    first = service.create_document_id(
        source_bucket="raw-bucket",
        source_key="documents/sample.pdf",
        source_version_id="version-1",
        processing_schema_version=(
            "extraction-v1"
        ),
    )

    second = service.create_document_id(
        source_bucket="raw-bucket",
        source_key="documents/sample.pdf",
        source_version_id="version-2",
        processing_schema_version=(
            "extraction-v1"
        ),
    )

    assert first != second


def test_different_schema_produces_different_identity(
    service,
):
    first = service.create_document_id(
        source_bucket="raw-bucket",
        source_key="documents/sample.pdf",
        source_version_id="version-1",
        processing_schema_version=(
            "extraction-v1"
        ),
    )

    second = service.create_document_id(
        source_bucket="raw-bucket",
        source_key="documents/sample.pdf",
        source_version_id="version-1",
        processing_schema_version=(
            "extraction-v2"
        ),
    )

    assert first != second


def test_unicode_identity_is_supported(
    service,
):
    result = service.create_document_id(
        source_bucket="raw-bucket",
        source_key=(
            "documents/試験001/"
            "protocols/café.pdf"
        ),
        source_version_id="version-日本語",
        processing_schema_version=(
            "extraction-v1"
        ),
    )

    assert len(result) == 64