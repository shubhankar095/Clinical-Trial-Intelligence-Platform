from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest

from exceptions.processing_claim import (
    ProcessingClaimLostError,
    ProcessingClaimUnavailableError,
)
from models.document import (
    ClinicalDocument,
    DocumentImage,
    DocumentTable,
)
from models.processing_manifest import (
    ProcessingManifest,
)
from repositories.processing_registry import (
    ProcessingClaim,
)
from services import document_extraction_service
from services.document_extraction_service import (
    DocumentExtractionService,
)


pytestmark = pytest.mark.component


SOURCE_KEY = (
    "documents/TEST001/"
    "protocols/sample.pdf"
)

CANONICAL_KEY = (
    "canonical-documents/"
    "document-123/"
    "extracted-document.json"
)


class FakeRegistrationService:

    def __init__(
        self,
        document,
        exception=None,
    ):
        self.document = document
        self.exception = exception
        self.calls = []

    def register(
        self,
        bucket_name,
        object_key,
        version_id,
        s3_metadata,
    ):
        self.calls.append(
            {
                "bucket_name": bucket_name,
                "object_key": object_key,
                "version_id": version_id,
                "s3_metadata": s3_metadata,
            }
        )

        if self.exception:
            raise self.exception

        return self.document


class FakeS3Service:

    def __init__(
        self,
        local_file_path,
        download_exception=None,
        delete_exception=None,
    ):
        self.local_file_path = str(
            local_file_path
        )
        self.download_exception = (
            download_exception
        )
        self.delete_exception = (
            delete_exception
        )
        self.download_calls = []
        self.delete_calls = []

    def download_file(
        self,
        bucket,
        key,
        version_id=None,
    ):
        self.download_calls.append(
            {
                "bucket": bucket,
                "key": key,
                "version_id": version_id,
            }
        )

        if self.download_exception:
            raise self.download_exception

        return self.local_file_path

    def delete_object(
        self,
        bucket,
        key,
    ):
        self.delete_calls.append(
            {
                "bucket": bucket,
                "key": key,
            }
        )

        if self.delete_exception:
            raise self.delete_exception


class FakeDocumentStore:

    def __init__(
        self,
        key=CANONICAL_KEY,
        save_exception=None,
    ):
        self.key = key
        self.save_exception = (
            save_exception
        )
        self.build_calls = []
        self.save_calls = []

    def build_object_key(
        self,
        document,
    ):
        self.build_calls.append(
            document
        )

        return self.key

    def save(
        self,
        document,
    ):
        self.save_calls.append(
            document
        )

        if self.save_exception:
            raise self.save_exception

        return self.key


class FakeManifestStore:

    def __init__(
        self,
        *,
        exists_results=None,
        manifest=None,
        save_exception=None,
        load_exception=None,
        validate_exception=None,
    ):
        self.exists_results = list(
            exists_results
            if exists_results is not None
            else [False, False]
        )
        self.manifest = manifest
        self.save_exception = (
            save_exception
        )
        self.load_exception = (
            load_exception
        )
        self.validate_exception = (
            validate_exception
        )

        self.exists_calls = []
        self.load_calls = []
        self.validate_calls = []
        self.save_calls = []

    def exists(
        self,
        document_id,
    ):
        self.exists_calls.append(
            document_id
        )

        if self.exists_results:
            return self.exists_results.pop(
                0
            )

        return False

    def load(
        self,
        document_id,
    ):
        self.load_calls.append(
            document_id
        )

        if self.load_exception:
            raise self.load_exception

        return self.manifest

    def validate(
        self,
        document,
        manifest,
    ):
        self.validate_calls.append(
            {
                "document": document,
                "manifest": manifest,
            }
        )

        if self.validate_exception:
            raise self.validate_exception

    def save(
        self,
        document,
    ):
        self.save_calls.append(
            document
        )

        if self.save_exception:
            raise self.save_exception

        return (
            "canonical-documents/"
            f"{document.document_id}/"
            "_SUCCESS.json"
        )


class FakeProcessingRegistry:

    def __init__(
        self,
        *,
        claim=None,
        acquire_exception=None,
        complete_exception=None,
        release_exception=None,
    ):
        self.claim = (
            claim
            or ProcessingClaim(
                document_id="document-123",
                owner_token="owner-token-123",
                lease_expires_at=1900,
            )
        )
        self.acquire_exception = (
            acquire_exception
        )
        self.complete_exception = (
            complete_exception
        )
        self.release_exception = (
            release_exception
        )

        self.acquire_calls = []
        self.complete_calls = []
        self.release_calls = []

    def acquire(
        self,
        document,
    ):
        self.acquire_calls.append(
            document
        )

        if self.acquire_exception:
            raise self.acquire_exception

        return self.claim

    def mark_completed(
        self,
        claim,
        canonical_key,
    ):
        self.complete_calls.append(
            {
                "claim": claim,
                "canonical_key": (
                    canonical_key
                ),
            }
        )

        if self.complete_exception:
            raise self.complete_exception

    def release(
        self,
        claim,
    ):
        self.release_calls.append(
            claim
        )

        if self.release_exception:
            raise self.release_exception


class FakeProcessor:

    def __init__(
        self,
        result_document=None,
        exception=None,
    ):
        self.result_document = (
            result_document
        )
        self.exception = exception
        self.calls = []

    def process(
        self,
        document,
    ):
        self.calls.append(
            document
        )

        if self.exception:
            raise self.exception

        return (
            self.result_document
            or document
        )


class FakeClaimHeartbeat:

    instances = []
    start_failure = None
    stop_failure = None
    raise_failures = []

    def __init__(
        self,
        processing_registry,
        claim,
        heartbeat_seconds,
    ):
        self.processing_registry = (
            processing_registry
        )
        self.claim = claim
        self.heartbeat_seconds = (
            heartbeat_seconds
        )
        self.start_calls = 0
        self.stop_calls = 0
        self.raise_calls = 0

        self.__class__.instances.append(
            self
        )

    def start(
        self,
    ):
        self.start_calls += 1

        if self.__class__.start_failure:
            raise self.__class__.start_failure

    def stop(
        self,
    ):
        self.stop_calls += 1

        if self.__class__.stop_failure:
            raise self.__class__.stop_failure

    def raise_if_failed(
        self,
    ):
        self.raise_calls += 1

        if self.__class__.raise_failures:
            failure = (
                self.__class__
                .raise_failures
                .pop(0)
            )

            if failure is not None:
                raise failure


@pytest.fixture(autouse=True)
def configure_module(
    monkeypatch,
):
    FakeClaimHeartbeat.instances = []
    FakeClaimHeartbeat.start_failure = None
    FakeClaimHeartbeat.stop_failure = None
    FakeClaimHeartbeat.raise_failures = []

    monkeypatch.setattr(
        document_extraction_service,
        "canonical_document_bucket",
        "canonical-bucket",
    )

    monkeypatch.setattr(
        document_extraction_service,
        "processing_claim_heartbeat_seconds",
        5,
    )

    monkeypatch.setattr(
        document_extraction_service,
        "ProcessingClaimHeartbeat",
        FakeClaimHeartbeat,
    )


@pytest.fixture
def local_source_file(
    tmp_path,
):
    source_file = (
        tmp_path / "sample.pdf"
    )

    source_file.write_bytes(
        b"test-pdf-content"
    )

    return source_file


@pytest.fixture
def pending_document():
    return ClinicalDocument(
        document_id="document-123",
        file_name="sample.pdf",
        file_format="pdf",
        source_bucket="raw-bucket",
        source_key=SOURCE_KEY,
        source_version_id="version-1",
        processing_schema_version=(
            "extraction-v1"
        ),
        processing_status="PENDING",
    )


@pytest.fixture
def successful_document(
    pending_document,
):
    pending_document.raw_text = (
        "Extracted document text"
    )
    pending_document.page_count = 2
    pending_document.ocr_page_count = 1
    pending_document.processing_status = (
        "SUCCESS"
    )
    pending_document.error_message = None

    return pending_document


@pytest.fixture
def failed_document(
    pending_document,
):
    pending_document.processing_status = (
        "FAILED"
    )
    pending_document.error_message = (
        "Processor could not extract "
        "the document"
    )

    return pending_document


@pytest.fixture
def success_manifest():
    return ProcessingManifest(
        document_id="document-123",
        source_bucket="raw-bucket",
        source_key=SOURCE_KEY,
        source_version_id="version-1",
        processing_schema_version=(
            "extraction-v1"
        ),
        canonical_bucket=(
            "canonical-bucket"
        ),
        canonical_key=CANONICAL_KEY,
        completed_at=(
            "2026-09-26T15:39:57+00:00"
        ),
        processing_status="SUCCESS",
    )


def build_service(
    *,
    document,
    local_source_file,
    document_store=None,
    manifest_store=None,
    processing_registry=None,
    s3_service=None,
    registration_exception=None,
):
    registration_service = (
        FakeRegistrationService(
            document=document,
            exception=(
                registration_exception
            ),
        )
    )

    s3_service = (
        s3_service
        or FakeS3Service(
            local_file_path=(
                local_source_file
            )
        )
    )

    document_store = (
        document_store
        or FakeDocumentStore()
    )

    manifest_store = (
        manifest_store
        or FakeManifestStore()
    )

    processing_registry = (
        processing_registry
        or FakeProcessingRegistry()
    )

    service = DocumentExtractionService(
        registration_service=(
            registration_service
        ),
        s3_service=s3_service,
        document_store=document_store,
        manifest_store=manifest_store,
        processing_registry=(
            processing_registry
        ),
    )

    return (
        service,
        registration_service,
        s3_service,
        document_store,
        manifest_store,
        processing_registry,
    )


def process_document(
    service,
    *,
    s3_metadata=None,
):
    return service.process_document(
        bucket_name="raw-bucket",
        object_key=SOURCE_KEY,
        version_id="version-1",
        s3_metadata=(
            s3_metadata
            if s3_metadata is not None
            else {}
        ),
    )


def configure_processor(
    monkeypatch,
    processor,
):
    monkeypatch.setattr(
        document_extraction_service,
        "get_processor",
        lambda extension: processor,
    )


def test_successful_document_completes_full_lifecycle(
    monkeypatch,
    successful_document,
    local_source_file,
):
    processor = FakeProcessor(
        result_document=successful_document
    )

    (
        service,
        registration_service,
        s3_service,
        document_store,
        manifest_store,
        processing_registry,
    ) = build_service(
        document=successful_document,
        local_source_file=(
            local_source_file
        ),
    )

    configure_processor(
        monkeypatch,
        processor,
    )

    result = process_document(
        service
    )

    assert result is successful_document
    assert result.processing_status == (
        "SUCCESS"
    )
    assert result.canonical_bucket == (
        "canonical-bucket"
    )
    assert result.canonical_key == (
        CANONICAL_KEY
    )
    assert result.local_file_path == ""

    assert registration_service.calls == [
        {
            "bucket_name": "raw-bucket",
            "object_key": SOURCE_KEY,
            "version_id": "version-1",
            "s3_metadata": {},
        }
    ]

    assert s3_service.download_calls == [
        {
            "bucket": "raw-bucket",
            "key": SOURCE_KEY,
            "version_id": "version-1",
        }
    ]

    assert (
        document_store.build_calls
        == [result]
    )
    assert (
        document_store.save_calls
        == [result]
    )
    assert (
        manifest_store.save_calls
        == [result]
    )
    assert (
        processing_registry.acquire_calls
        == [result]
    )
    assert (
        processing_registry.complete_calls
        == [
            {
                "claim": (
                    processing_registry.claim
                ),
                "canonical_key": (
                    CANONICAL_KEY
                ),
            }
        ]
    )
    assert (
        processing_registry.release_calls
        == []
    )

    assert len(
        FakeClaimHeartbeat.instances
    ) == 1

    heartbeat = (
        FakeClaimHeartbeat.instances[0]
    )

    assert heartbeat.start_calls == 1
    assert heartbeat.stop_calls >= 1
    assert heartbeat.raise_calls >= 3
    assert heartbeat.heartbeat_seconds == 5
    assert (
        local_source_file.exists()
        is False
    )


def test_exact_source_version_is_downloaded(
    monkeypatch,
    successful_document,
    local_source_file,
):
    processor = FakeProcessor(
        result_document=successful_document
    )

    (
        service,
        _,
        s3_service,
        _,
        _,
        _,
    ) = build_service(
        document=successful_document,
        local_source_file=(
            local_source_file
        ),
    )

    configure_processor(
        monkeypatch,
        processor,
    )

    process_document(
        service
    )

    assert s3_service.download_calls == [
        {
            "bucket": "raw-bucket",
            "key": SOURCE_KEY,
            "version_id": "version-1",
        }
    ]


def test_failed_processor_result_is_not_persisted(
    monkeypatch,
    failed_document,
    local_source_file,
):
    processor = FakeProcessor(
        result_document=failed_document
    )

    (
        service,
        _,
        _,
        document_store,
        manifest_store,
        processing_registry,
    ) = build_service(
        document=failed_document,
        local_source_file=(
            local_source_file
        ),
    )

    configure_processor(
        monkeypatch,
        processor,
    )

    result = process_document(
        service
    )

    assert result is failed_document
    assert result.processing_status == (
        "FAILED"
    )
    assert document_store.build_calls == []
    assert document_store.save_calls == []
    assert manifest_store.save_calls == []
    assert (
        processing_registry.complete_calls
        == []
    )
    assert (
        processing_registry.release_calls
        == [processing_registry.claim]
    )
    assert (
        local_source_file.exists()
        is False
    )


def test_processor_exception_is_propagated_and_claim_released(
    monkeypatch,
    pending_document,
    local_source_file,
):
    processor = FakeProcessor(
        exception=RuntimeError(
            "Processor crashed"
        )
    )

    (
        service,
        _,
        _,
        document_store,
        manifest_store,
        processing_registry,
    ) = build_service(
        document=pending_document,
        local_source_file=(
            local_source_file
        ),
    )

    configure_processor(
        monkeypatch,
        processor,
    )

    with pytest.raises(
        RuntimeError,
        match="Processor crashed",
    ):
        process_document(
            service
        )

    assert document_store.save_calls == []
    assert manifest_store.save_calls == []
    assert (
        processing_registry.release_calls
        == [processing_registry.claim]
    )
    assert (
        local_source_file.exists()
        is False
    )
    assert (
        pending_document.local_file_path
        == ""
    )


def test_download_failure_is_propagated_and_claim_released(
    pending_document,
    local_source_file,
):
    s3_service = FakeS3Service(
        local_file_path=local_source_file,
        download_exception=RuntimeError(
            "S3 download failed"
        ),
    )

    processing_registry = (
        FakeProcessingRegistry()
    )

    (
        service,
        _,
        _,
        document_store,
        manifest_store,
        _,
    ) = build_service(
        document=pending_document,
        local_source_file=(
            local_source_file
        ),
        s3_service=s3_service,
        processing_registry=(
            processing_registry
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="S3 download failed",
    ):
        process_document(
            service
        )

    assert document_store.save_calls == []
    assert manifest_store.save_calls == []
    assert (
        processing_registry.release_calls
        == [processing_registry.claim]
    )


def test_registration_failure_prevents_claim_and_download(
    pending_document,
    local_source_file,
):
    processing_registry = (
        FakeProcessingRegistry()
    )

    (
        service,
        _,
        s3_service,
        document_store,
        manifest_store,
        _,
    ) = build_service(
        document=pending_document,
        local_source_file=(
            local_source_file
        ),
        processing_registry=(
            processing_registry
        ),
        registration_exception=ValueError(
            "Invalid document path"
        ),
    )

    with pytest.raises(
        ValueError,
        match="Invalid document path",
    ):
        process_document(
            service
        )

    assert s3_service.download_calls == []
    assert document_store.save_calls == []
    assert manifest_store.exists_calls == []
    assert (
        processing_registry.acquire_calls
        == []
    )


def test_claim_unavailable_is_propagated_without_download(
    pending_document,
    local_source_file,
):
    processing_registry = (
        FakeProcessingRegistry(
            acquire_exception=(
                ProcessingClaimUnavailableError(
                    "Claim already owned"
                )
            )
        )
    )

    (
        service,
        _,
        s3_service,
        _,
        manifest_store,
        _,
    ) = build_service(
        document=pending_document,
        local_source_file=(
            local_source_file
        ),
        processing_registry=(
            processing_registry
        ),
    )

    with pytest.raises(
        ProcessingClaimUnavailableError,
        match="Claim already owned",
    ):
        process_document(
            service
        )

    assert s3_service.download_calls == []
    assert manifest_store.save_calls == []
    assert (
        processing_registry.release_calls
        == []
    )


def test_canonical_save_failure_cleans_assets_and_releases_claim(
    monkeypatch,
    successful_document,
    local_source_file,
):
    successful_document.images = [
        DocumentImage(
            image_id="image-1-1",
            page_number=1,
            extension="png",
            s3_key=(
                "canonical-documents/"
                "document-123/"
                "images/image-1-1.png"
            ),
            width=100,
            height=200,
        )
    ]

    successful_document.tables = [
        DocumentTable(
            table_id="table-1-1",
            page_number=1,
            s3_key=(
                "canonical-documents/"
                "document-123/"
                "tables/table-1-1.json"
            ),
            row_count=2,
            column_count=3,
        )
    ]

    successful_document.image_count = 1
    successful_document.table_count = 1

    processor = FakeProcessor(
        result_document=successful_document
    )

    document_store = FakeDocumentStore(
        save_exception=RuntimeError(
            "Canonical save failed"
        )
    )

    (
        service,
        _,
        s3_service,
        _,
        manifest_store,
        processing_registry,
    ) = build_service(
        document=successful_document,
        local_source_file=(
            local_source_file
        ),
        document_store=document_store,
    )

    configure_processor(
        monkeypatch,
        processor,
    )

    with pytest.raises(
        RuntimeError,
        match="Canonical save failed",
    ):
        process_document(
            service
        )

    assert s3_service.delete_calls == [
        {
            "bucket": "canonical-bucket",
            "key": (
                "canonical-documents/"
                "document-123/"
                "images/image-1-1.png"
            ),
        },
        {
            "bucket": "canonical-bucket",
            "key": (
                "canonical-documents/"
                "document-123/"
                "tables/table-1-1.json"
            ),
        },
    ]

    assert successful_document.images == []
    assert successful_document.tables == []
    assert successful_document.image_count == 0
    assert successful_document.table_count == 0
    assert (
        successful_document.processing_status
        == "FAILED"
    )
    assert (
        successful_document.error_message
        == "Canonical document save failed."
    )

    assert manifest_store.save_calls == []
    assert (
        processing_registry.complete_calls
        == []
    )
    assert (
        processing_registry.release_calls
        == [processing_registry.claim]
    )


def test_asset_cleanup_failure_does_not_hide_save_failure(
    monkeypatch,
    successful_document,
    local_source_file,
):
    successful_document.images = [
        DocumentImage(
            image_id="image-1-1",
            page_number=1,
            extension="png",
            s3_key=(
                "canonical-documents/"
                "document-123/"
                "images/image-1-1.png"
            ),
            width=100,
            height=200,
        )
    ]
    successful_document.image_count = 1

    processor = FakeProcessor(
        result_document=successful_document
    )

    document_store = FakeDocumentStore(
        save_exception=RuntimeError(
            "Original save failure"
        )
    )

    s3_service = FakeS3Service(
        local_file_path=local_source_file,
        delete_exception=RuntimeError(
            "Cleanup deletion failed"
        ),
    )

    (
        service,
        _,
        _,
        _,
        _,
        processing_registry,
    ) = build_service(
        document=successful_document,
        local_source_file=(
            local_source_file
        ),
        document_store=document_store,
        s3_service=s3_service,
    )

    configure_processor(
        monkeypatch,
        processor,
    )

    with pytest.raises(
        RuntimeError,
        match="Original save failure",
    ):
        process_document(
            service
        )

    assert len(
        s3_service.delete_calls
    ) == 1
    assert (
        processing_registry.release_calls
        == [processing_registry.claim]
    )


def test_manifest_save_failure_prevents_completion(
    monkeypatch,
    successful_document,
    local_source_file,
):
    processor = FakeProcessor(
        result_document=successful_document
    )

    manifest_store = FakeManifestStore(
        save_exception=RuntimeError(
            "Manifest save failed"
        )
    )

    (
        service,
        _,
        _,
        document_store,
        _,
        processing_registry,
    ) = build_service(
        document=successful_document,
        local_source_file=(
            local_source_file
        ),
        manifest_store=manifest_store,
    )

    configure_processor(
        monkeypatch,
        processor,
    )

    with pytest.raises(
        RuntimeError,
        match="Manifest save failed",
    ):
        process_document(
            service
        )

    assert (
        document_store.save_calls
        == [successful_document]
    )
    assert (
        processing_registry.complete_calls
        == []
    )
    assert (
        processing_registry.release_calls
        == [processing_registry.claim]
    )


def test_claim_completion_failure_is_propagated(
    monkeypatch,
    successful_document,
    local_source_file,
):
    processor = FakeProcessor(
        result_document=successful_document
    )

    processing_registry = (
        FakeProcessingRegistry(
            complete_exception=(
                ProcessingClaimLostError(
                    "Claim expired"
                )
            )
        )
    )

    (
        service,
        _,
        _,
        document_store,
        manifest_store,
        _,
    ) = build_service(
        document=successful_document,
        local_source_file=(
            local_source_file
        ),
        processing_registry=(
            processing_registry
        ),
    )

    configure_processor(
        monkeypatch,
        processor,
    )

    with pytest.raises(
        ProcessingClaimLostError,
        match="Claim expired",
    ):
        process_document(
            service
        )

    assert (
        document_store.save_calls
        == [successful_document]
    )
    assert (
        manifest_store.save_calls
        == [successful_document]
    )
    assert (
        processing_registry.release_calls
        == [processing_registry.claim]
    )


def test_heartbeat_failure_prevents_canonical_persistence(
    monkeypatch,
    successful_document,
    local_source_file,
):
    processor = FakeProcessor(
        result_document=successful_document
    )

    FakeClaimHeartbeat.raise_failures = [
        ProcessingClaimLostError(
            "Claim renewal failed"
        )
    ]

    (
        service,
        _,
        _,
        document_store,
        manifest_store,
        processing_registry,
    ) = build_service(
        document=successful_document,
        local_source_file=(
            local_source_file
        ),
    )

    configure_processor(
        monkeypatch,
        processor,
    )

    with pytest.raises(
        ProcessingClaimLostError,
        match="Claim renewal failed",
    ):
        process_document(
            service
        )

    assert document_store.save_calls == []
    assert manifest_store.save_calls == []
    assert (
        processing_registry.complete_calls
        == []
    )
    assert (
        processing_registry.release_calls
        == [processing_registry.claim]
    )


def test_existing_manifest_skips_download_and_reconciles_registry(
    pending_document,
    success_manifest,
    local_source_file,
):
    manifest_store = FakeManifestStore(
        exists_results=[True],
        manifest=success_manifest,
    )

    (
        service,
        _,
        s3_service,
        document_store,
        _,
        processing_registry,
    ) = build_service(
        document=pending_document,
        local_source_file=(
            local_source_file
        ),
        manifest_store=manifest_store,
    )

    result = process_document(
        service
    )

    assert result is pending_document
    assert result.already_processed is True
    assert result.processing_status == (
        "SUCCESS"
    )
    assert result.canonical_bucket == (
        "canonical-bucket"
    )
    assert result.canonical_key == (
        CANONICAL_KEY
    )

    assert s3_service.download_calls == []
    assert document_store.save_calls == []
    assert (
        manifest_store.load_calls
        == ["document-123"]
    )
    assert len(
        manifest_store.validate_calls
    ) == 1
    assert (
        processing_registry.complete_calls
        == [
            {
                "claim": (
                    processing_registry.claim
                ),
                "canonical_key": (
                    CANONICAL_KEY
                ),
            }
        ]
    )
    assert (
        processing_registry.release_calls
        == []
    )
    assert (
        FakeClaimHeartbeat.instances
        == []
    )


def test_existing_manifest_with_registry_contention_still_returns_success(
    pending_document,
    success_manifest,
    local_source_file,
):
    manifest_store = FakeManifestStore(
        exists_results=[True],
        manifest=success_manifest,
    )

    processing_registry = (
        FakeProcessingRegistry(
            acquire_exception=(
                ProcessingClaimUnavailableError(
                    "Registry record exists"
                )
            )
        )
    )

    (
        service,
        _,
        s3_service,
        document_store,
        _,
        _,
    ) = build_service(
        document=pending_document,
        local_source_file=(
            local_source_file
        ),
        manifest_store=manifest_store,
        processing_registry=(
            processing_registry
        ),
    )

    result = process_document(
        service
    )

    assert result.already_processed is True
    assert result.processing_status == (
        "SUCCESS"
    )
    assert s3_service.download_calls == []
    assert document_store.save_calls == []
    assert (
        processing_registry.complete_calls
        == []
    )
    assert (
        processing_registry.release_calls
        == []
    )


def test_manifest_appearing_after_claim_is_used(
    pending_document,
    success_manifest,
    local_source_file,
):
    manifest_store = FakeManifestStore(
        exists_results=[
            False,
            True,
        ],
        manifest=success_manifest,
    )

    (
        service,
        _,
        s3_service,
        document_store,
        _,
        processing_registry,
    ) = build_service(
        document=pending_document,
        local_source_file=(
            local_source_file
        ),
        manifest_store=manifest_store,
    )

    result = process_document(
        service
    )

    assert result.already_processed is True
    assert result.processing_status == (
        "SUCCESS"
    )
    assert s3_service.download_calls == []
    assert document_store.save_calls == []
    assert (
        processing_registry.complete_calls
        == [
            {
                "claim": (
                    processing_registry.claim
                ),
                "canonical_key": (
                    CANONICAL_KEY
                ),
            }
        ]
    )
    assert (
        processing_registry.release_calls
        == []
    )

    heartbeat = (
        FakeClaimHeartbeat.instances[0]
    )
    assert heartbeat.start_calls == 1
    assert heartbeat.stop_calls >= 1
    assert heartbeat.raise_calls == 1


def test_manifest_validation_failure_is_propagated(
    pending_document,
    success_manifest,
    local_source_file,
):
    manifest_store = FakeManifestStore(
        exists_results=[True],
        manifest=success_manifest,
        validate_exception=ValueError(
            "Manifest identity mismatch"
        ),
    )

    (
        service,
        _,
        s3_service,
        _,
        _,
        processing_registry,
    ) = build_service(
        document=pending_document,
        local_source_file=(
            local_source_file
        ),
        manifest_store=manifest_store,
    )

    with pytest.raises(
        ValueError,
        match="Manifest identity mismatch",
    ):
        process_document(
            service
        )

    assert s3_service.download_calls == []
    assert (
        processing_registry.acquire_calls
        == []
    )


def test_reconciliation_completion_failure_releases_claim(
    pending_document,
    success_manifest,
    local_source_file,
):
    manifest_store = FakeManifestStore(
        exists_results=[True],
        manifest=success_manifest,
    )

    processing_registry = (
        FakeProcessingRegistry(
            complete_exception=RuntimeError(
                "Registry completion failed"
            )
        )
    )

    (
        service,
        _,
        _,
        _,
        _,
        _,
    ) = build_service(
        document=pending_document,
        local_source_file=(
            local_source_file
        ),
        manifest_store=manifest_store,
        processing_registry=(
            processing_registry
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="Registry completion failed",
    ):
        process_document(
            service
        )

    assert (
        processing_registry.release_calls
        == [processing_registry.claim]
    )


def test_release_failure_does_not_hide_processor_result(
    monkeypatch,
    failed_document,
    local_source_file,
):
    processor = FakeProcessor(
        result_document=failed_document
    )

    processing_registry = (
        FakeProcessingRegistry(
            release_exception=RuntimeError(
                "Claim release failed"
            )
        )
    )

    (
        service,
        _,
        _,
        _,
        _,
        _,
    ) = build_service(
        document=failed_document,
        local_source_file=(
            local_source_file
        ),
        processing_registry=(
            processing_registry
        ),
    )

    configure_processor(
        monkeypatch,
        processor,
    )

    result = process_document(
        service
    )

    assert result.processing_status == (
        "FAILED"
    )
    assert len(
        processing_registry.release_calls
    ) == 1


def test_temporary_file_delete_failure_is_ignored(
    monkeypatch,
    successful_document,
    local_source_file,
):
    processor = FakeProcessor(
        result_document=successful_document
    )

    (
        service,
        _,
        _,
        document_store,
        _,
        _,
    ) = build_service(
        document=successful_document,
        local_source_file=(
            local_source_file
        ),
    )

    configure_processor(
        monkeypatch,
        processor,
    )

    def fail_to_delete(
        self,
        missing_ok=False,
    ):
        del self
        del missing_ok

        raise OSError(
            "Temporary file is locked"
        )

    monkeypatch.setattr(
        document_extraction_service.Path,
        "unlink",
        fail_to_delete,
    )

    result = process_document(
        service
    )

    assert result.processing_status == (
        "SUCCESS"
    )
    assert result.local_file_path == ""
    assert (
        local_source_file.exists()
        is True
    )
    assert (
        document_store.save_calls
        == [result]
    )


def test_process_skips_cleanup_when_processor_clears_path(
    monkeypatch,
    successful_document,
    local_source_file,
):
    class ClearingProcessor:

        def process(
            self,
            document,
        ):
            document.processing_status = (
                "SUCCESS"
            )
            document.local_file_path = ""

            return document

    (
        service,
        _,
        _,
        document_store,
        _,
        _,
    ) = build_service(
        document=successful_document,
        local_source_file=(
            local_source_file
        ),
    )

    configure_processor(
        monkeypatch,
        ClearingProcessor(),
    )

    result = process_document(
        service
    )

    assert result.processing_status == (
        "SUCCESS"
    )
    assert result.local_file_path == ""
    assert (
        local_source_file.exists()
        is True
    )
    assert (
        document_store.save_calls
        == [result]
    )


def test_processor_is_selected_using_registered_format(
    monkeypatch,
    successful_document,
    local_source_file,
):
    processor = FakeProcessor(
        result_document=successful_document
    )

    selected_extensions = []

    def select_processor(
        extension,
    ):
        selected_extensions.append(
            extension
        )

        return processor

    (
        service,
        _,
        _,
        _,
        _,
        _,
    ) = build_service(
        document=successful_document,
        local_source_file=(
            local_source_file
        ),
    )

    monkeypatch.setattr(
        document_extraction_service,
        "get_processor",
        select_processor,
    )

    process_document(
        service
    )

    assert selected_extensions == [
        "pdf"
    ]


def test_delete_canonical_object_ignores_empty_key(
    successful_document,
    local_source_file,
):
    s3_service = FakeS3Service(
        local_file_path=local_source_file
    )

    (
        service,
        _,
        _,
        _,
        _,
        _,
    ) = build_service(
        document=successful_document,
        local_source_file=(
            local_source_file
        ),
        s3_service=s3_service,
    )

    service._delete_canonical_object(
        object_key="",
        asset_type="image",
    )

    assert s3_service.delete_calls == []



def test_reconciliation_release_failure_does_not_hide_completion_failure(
    pending_document,
    success_manifest,
    local_source_file,
):
    manifest_store = FakeManifestStore(
        exists_results=[True],
        manifest=success_manifest,
    )

    processing_registry = (
        FakeProcessingRegistry(
            complete_exception=RuntimeError(
                "Registry completion failed"
            ),
            release_exception=RuntimeError(
                "Registry release failed"
            ),
        )
    )

    (
        service,
        _,
        _,
        _,
        _,
        _,
    ) = build_service(
        document=pending_document,
        local_source_file=(
            local_source_file
        ),
        manifest_store=manifest_store,
        processing_registry=(
            processing_registry
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="Registry completion failed",
    ):
        process_document(
            service
        )

    assert (
        processing_registry.complete_calls
        == [
            {
                "claim": (
                    processing_registry.claim
                ),
                "canonical_key": (
                    CANONICAL_KEY
                ),
            }
        ]
    )

    assert (
        processing_registry.release_calls
        == [processing_registry.claim]
    )


def test_heartbeat_stop_failure_is_propagated_before_completion(
    monkeypatch,
    successful_document,
    local_source_file,
):
    processor = FakeProcessor(
        result_document=successful_document
    )

    class FirstStopFailingHeartbeat:

        instances = []

        def __init__(
            self,
            processing_registry,
            claim,
            heartbeat_seconds,
        ):
            self.processing_registry = (
                processing_registry
            )
            self.claim = claim
            self.heartbeat_seconds = (
                heartbeat_seconds
            )
            self.start_calls = 0
            self.stop_calls = 0
            self.raise_calls = 0

            self.__class__.instances.append(
                self
            )

        def start(
            self,
        ):
            self.start_calls += 1

        def raise_if_failed(
            self,
        ):
            self.raise_calls += 1

        def stop(
            self,
        ):
            self.stop_calls += 1

            if self.stop_calls == 1:
                raise RuntimeError(
                    "Heartbeat stop failed"
                )

    monkeypatch.setattr(
        document_extraction_service,
        "ProcessingClaimHeartbeat",
        FirstStopFailingHeartbeat,
    )

    (
        service,
        _,
        _,
        document_store,
        manifest_store,
        processing_registry,
    ) = build_service(
        document=successful_document,
        local_source_file=(
            local_source_file
        ),
    )

    configure_processor(
        monkeypatch,
        processor,
    )

    with pytest.raises(
        RuntimeError,
        match="Heartbeat stop failed",
    ):
        process_document(
            service
        )

    assert (
        document_store.save_calls
        == [successful_document]
    )

    assert (
        manifest_store.save_calls
        == [successful_document]
    )

    assert (
        processing_registry.complete_calls
        == []
    )

    assert (
        processing_registry.release_calls
        == [processing_registry.claim]
    )

    assert len(
        FirstStopFailingHeartbeat.instances
    ) == 1

    heartbeat = (
        FirstStopFailingHeartbeat
        .instances[0]
    )

    assert heartbeat.start_calls == 1
    assert heartbeat.stop_calls == 2

    assert (
        successful_document.local_file_path
        == ""
    )

    assert (
        local_source_file.exists()
        is False
    )