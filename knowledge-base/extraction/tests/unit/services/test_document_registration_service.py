from unittest.mock import Mock

import pytest

from services.document_registration_service import (
    DocumentRegistrationService,
)


pytestmark = pytest.mark.unit


@pytest.fixture
def identity_service():
    service = Mock()
    service.create_document_id.return_value = (
        "document-123"
    )
    return service


@pytest.fixture
def service(
    identity_service,
):
    return DocumentRegistrationService(
        identity_service=identity_service
    )


def register_document(
    service,
    *,
    object_key=(
        "documents/TEST001/"
        "protocols/sample.pdf"
    ),
    version_id="version-1",
    s3_metadata=None,
):
    return service.register(
        bucket_name="raw-bucket",
        object_key=object_key,
        version_id=version_id,
        s3_metadata=(
            s3_metadata
            if s3_metadata is not None
            else {}
        ),
    )


def test_registers_study_document(
    service,
    identity_service,
):
    document = register_document(
        service
    )

    assert document.document_id == (
        "document-123"
    )
    assert document.file_name == "sample.pdf"
    assert document.file_format == "pdf"
    assert document.source_bucket == (
        "raw-bucket"
    )
    assert document.source_key == (
        "documents/TEST001/"
        "protocols/sample.pdf"
    )
    assert document.source_version_id == (
        "version-1"
    )
    assert document.processing_schema_version
    assert document.metadata.study_id == (
        "TEST001"
    )
    assert (
        document.metadata.document_type
        == "PROTOCOL"
    )

    (
        identity_service
        .create_document_id
        .assert_called_once_with(
            source_bucket="raw-bucket",
            source_key=(
                "documents/TEST001/"
                "protocols/sample.pdf"
            ),
            source_version_id="version-1",
            processing_schema_version=(
                document
                .processing_schema_version
            ),
        )
    )


def test_study_id_is_converted_to_uppercase(
    service,
):
    document = register_document(
        service,
        object_key=(
            "documents/test001/"
            "protocols/sample.pdf"
        ),
    )

    assert document.metadata.study_id == (
        "TEST001"
    )


def test_registers_shared_document(
    service,
):
    document = register_document(
        service,
        object_key=(
            "documents/shared/"
            "sop/sample.pdf"
        ),
    )

    assert document.metadata.study_id is None
    assert (
        document.metadata.document_type
        == "SOP"
    )


def test_s3_metadata_overrides_path_metadata(
    service,
):
    document = register_document(
        service,
        s3_metadata={
            "study_id": "OVERRIDE001",
            "document_type": "CSR",
            "version": "3",
            "sponsor": "Sponsor A",
            "phase": "III",
        },
    )

    assert document.metadata.study_id == (
        "OVERRIDE001"
    )
    assert (
        document.metadata.document_type
        == "CSR"
    )
    assert document.metadata.version == "3"
    assert (
        document.metadata.sponsor
        == "Sponsor A"
    )
    assert document.metadata.phase == "III"


def test_path_metadata_is_used_when_s3_metadata_is_empty(
    service,
):
    document = register_document(
        service,
        object_key=(
            "documents/TEST001/"
            "monitoring/sample.pdf"
        ),
        s3_metadata={
            "study_id": "",
            "document_type": None,
        },
    )

    assert document.metadata.study_id == (
        "TEST001"
    )
    assert (
        document.metadata.document_type
        == "MONITORING"
    )


def test_file_extension_is_normalized_to_lowercase(
    service,
):
    document = register_document(
        service,
        object_key=(
            "documents/TEST001/"
            "protocols/SAMPLE.PDF"
        ),
    )

    assert document.file_format == "pdf"


@pytest.mark.parametrize(
    "version_id",
    [
        "",
        None,
    ],
)
def test_missing_version_id_is_rejected(
    service,
    identity_service,
    version_id,
):
    with pytest.raises(
        ValueError,
        match="version ID is required",
    ):
        register_document(
            service,
            version_id=version_id,
        )

    (
        identity_service
        .create_document_id
        .assert_not_called()
    )


def test_rejects_short_path(
    service,
):
    with pytest.raises(
        ValueError,
        match="Invalid document path",
    ):
        register_document(
            service,
            object_key="documents/sample.pdf",
        )


@pytest.mark.parametrize(
    "object_key",
    [
        (
            "documents//"
            "protocols/sample.pdf"
        ),
        (
            "documents/TEST001//"
            "sample.pdf"
        ),
        (
            "/TEST001/"
            "protocols/sample.pdf"
        ),
    ],
)
def test_rejects_empty_path_component(
    service,
    object_key,
):
    with pytest.raises(
        ValueError,
        match="Path components cannot be empty",
    ):
        register_document(
            service,
            object_key=object_key,
        )


def test_rejects_file_without_extension(
    service,
):
    with pytest.raises(
        ValueError,
        match="A file extension is required",
    ):
        register_document(
            service,
            object_key=(
                "documents/TEST001/"
                "protocols/sample"
            ),
        )


def test_rejects_invalid_root_folder(
    service,
):
    with pytest.raises(
        ValueError,
        match="Invalid root folder",
    ):
        register_document(
            service,
            object_key=(
                "uploads/TEST001/"
                "protocols/sample.pdf"
            ),
        )


def test_rejects_unsupported_study_category(
    service,
):
    with pytest.raises(
        ValueError,
        match=(
            "Unsupported study document category"
        ),
    ):
        register_document(
            service,
            object_key=(
                "documents/TEST001/"
                "unsupported/sample.pdf"
            ),
        )


def test_rejects_unsupported_shared_category(
    service,
):
    with pytest.raises(
        ValueError,
        match=(
            "Unsupported shared document category"
        ),
    ):
        register_document(
            service,
            object_key=(
                "documents/shared/"
                "unsupported/sample.pdf"
            ),
        )


@pytest.mark.parametrize(
    (
        "category",
        "expected_type",
    ),
    [
        (
            "protocols",
            "PROTOCOL",
        ),
        (
            "monitoring",
            "MONITORING",
        ),
        (
            "csr",
            "CSR",
        ),
        (
            "sap",
            "SAP",
        ),
        (
            "ib",
            "IB",
        ),
        (
            "tmf",
            "TMF",
        ),
    ],
)
def test_supported_study_categories(
    service,
    category,
    expected_type,
):
    document = register_document(
        service,
        object_key=(
            f"documents/TEST001/"
            f"{category}/sample.pdf"
        ),
    )

    assert (
        document.metadata.document_type
        == expected_type
    )


@pytest.mark.parametrize(
    (
        "category",
        "expected_type",
    ),
    [
        (
            "sop",
            "SOP",
        ),
        (
            "regulations",
            "REGULATION",
        ),
        (
            "guidances",
            "GUIDANCE",
        ),
        (
            "templates",
            "TEMPLATE",
        ),
    ],
)
def test_supported_shared_categories(
    service,
    category,
    expected_type,
):
    document = register_document(
        service,
        object_key=(
            f"documents/shared/"
            f"{category}/sample.pdf"
        ),
    )

    assert (
        document.metadata.document_type
        == expected_type
    )


def test_extract_metadata_returns_empty_for_short_path(
    service,
):
    result = (
        service
        ._extract_metadata_from_path(
            "documents/sample.pdf"
        )
    )

    assert result == {
        "study_id": None,
        "document_type": None,
    }


def test_extract_metadata_returns_empty_for_invalid_root(
    service,
):
    result = (
        service
        ._extract_metadata_from_path(
            "uploads/TEST001/"
            "protocols/sample.pdf"
        )
    )

    assert result == {
        "study_id": None,
        "document_type": None,
    }


def test_extract_metadata_handles_shared_path_without_category(
    service,
):
    result = (
        service
        ._extract_metadata_from_path(
            "documents/shared"
        )
    )

    assert result == {
        "study_id": None,
        "document_type": None,
    }


def test_identity_service_failure_is_propagated(
    service,
    identity_service,
):
    identity_service.create_document_id.side_effect = (
        RuntimeError(
            "Identity generation failed"
        )
    )

    with pytest.raises(
        RuntimeError,
        match="Identity generation failed",
    ):
        register_document(
            service
        )