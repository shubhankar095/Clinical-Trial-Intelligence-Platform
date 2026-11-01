from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from exceptions.extraction_manifest import IngestionInputError
from exceptions.ingestion_event import IgnorableIngestionEvent
from exceptions.processing import (
    IngestionConfigurationError,
    PermanentIngestionError,
    RetryableIngestionError,
)
from ingestion_events.ingestion_event import IngestionEventError
from models.document import DocumentChunk
from models.ingestion_manifest import IngestionFailureManifest
from models.storage_location import StorageLocation
from repositories.processing_registry import (
    ClaimDisposition,
    ClaimResult,
    ProcessingClaim,
)
from services.canonical_document_parser import CanonicalDocumentParser
from services.extraction_manifest_parser import ExtractionManifestParser
from services.ingestion_identity_service import IngestionIdentityService
from storage.s3_ingestion_manifest_store import StoredIngestionManifest
from workers.ingestion_worker import IngestionWorker, MessageDisposition


pytestmark = pytest.mark.unit


class _Visibility:
    def __init__(self, *, failure=None, **_kwargs):
        self.failure = failure
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def raise_for_failure(self):
        if self.failure:
            raise self.failure


class _ClaimHeartbeat:
    def __init__(self, *, claim, **_kwargs):
        self.claim = claim
        self.started = False
        self.stopped = False
        self.failure = None

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def raise_for_failure(self):
        if self.failure:
            raise self.failure


def _worker():
    worker = object.__new__(IngestionWorker)
    worker.event_consumer = SimpleNamespace(
        acknowledge_message=lambda _message: None,
        release_message=lambda _message: None,
    )
    worker.event_parser = SimpleNamespace(parse=lambda _body: None)
    worker.manifest_service = SimpleNamespace(load_and_validate=lambda _location: None)
    worker.canonical_document_service = SimpleNamespace(load_and_validate=lambda _manifest: None)
    worker.identity_service = SimpleNamespace(create_ingestion_identity=lambda **_kwargs: None)
    worker.processing_registry = SimpleNamespace(acquire_claim=lambda **_kwargs: None)
    worker.result_store = SimpleNamespace()
    worker.shutdown_controller = SimpleNamespace(
        shutdown_requested=True,
        install_signal_handlers=lambda: None,
        restore_signal_handlers=lambda: None,
    )
    worker.embedding_service = SimpleNamespace(close=lambda: None)
    return worker


def _domain(canonical_fixture_dir, profile_factory):
    manifest = ExtractionManifestParser().parse(
        (canonical_fixture_dir / "_SUCCESS.json").read_text()
    )
    document = CanonicalDocumentParser().parse(
        (canonical_fixture_dir / "extracted-document.json").read_text()
    )
    profile = profile_factory()
    identity = IngestionIdentityService().create_ingestion_identity(
        document, manifest, profile
    )
    claim = ProcessingClaim(
        ingestion_id=identity.ingestion_id,
        owner_token="owner",
        attempt_count=1,
        claimed_at="2024-01-01T00:00:00+00:00",
        lease_expires_at=100,
    )
    location = StorageLocation(
        bucket="canonical",
        key=f"canonical-documents/{document.document_id}/_SUCCESS.json",
        version_id=None,
    )
    event = SimpleNamespace(
        manifest_bucket=location.bucket,
        manifest_key=location.key,
        manifest_version_id=location.version_id,
    )
    return manifest, document, profile, identity, claim, location, event


def test_process_message_handles_dispositions_and_retryable_errors(monkeypatch):
    import workers.ingestion_worker as worker_module

    message = SimpleNamespace(message_id="message", body="{}")
    worker = _worker()
    worker.event_consumer.acknowledged = []
    worker.event_consumer.released = []
    worker.event_consumer.acknowledge_message = worker.event_consumer.acknowledged.append
    worker.event_consumer.release_message = worker.event_consumer.released.append
    created = []

    def heartbeat(**kwargs):
        value = _Visibility(**kwargs)
        created.append(value)
        return value

    monkeypatch.setattr(worker_module, "MessageVisibilityHeartbeat", heartbeat)
    worker._route_message = lambda *_args: MessageDisposition.ACKNOWLEDGE
    worker._process_message(message)
    assert worker.event_consumer.acknowledged == [message]
    assert created[-1].started and created[-1].stopped

    worker._route_message = lambda *_args: MessageDisposition.RELEASE
    worker._process_message(message)
    assert worker.event_consumer.released == [message]

    for error in (
        IngestionConfigurationError("configuration"),
        RetryableIngestionError("retry"),
        RuntimeError("unexpected"),
    ):
        worker._route_message = lambda *_args, error=error: (_ for _ in ()).throw(error)
        worker._process_message(message)
    assert worker.event_consumer.acknowledged == [message]
    assert worker.event_consumer.released == [message]


def test_route_message_maps_parse_input_and_claim_outcomes(
    canonical_fixture_dir, profile_factory, monkeypatch
):
    import workers.ingestion_worker as worker_module

    monkeypatch.setattr(worker_module, "MessageVisibilityHeartbeat", _Visibility)
    manifest, document, profile, identity, claim, location, event = _domain(
        canonical_fixture_dir, profile_factory
    )
    worker = _worker()
    worker.ingestion_profile = profile
    worker.event_parser.parse = lambda _body: event
    worker.manifest_service.load_and_validate = lambda _location: manifest
    worker.canonical_document_service.load_and_validate = lambda _manifest: document
    worker.identity_service.create_ingestion_identity = lambda **_kwargs: identity
    visibility = _Visibility()

    worker.event_parser.parse = lambda _body: (_ for _ in ()).throw(IgnorableIngestionEvent())
    message = SimpleNamespace(body="{}", message_id="message")
    assert worker._route_message(message, visibility) == MessageDisposition.ACKNOWLEDGE
    worker.event_parser.parse = lambda _body: (_ for _ in ()).throw(IngestionEventError())
    assert worker._route_message(message, visibility) == MessageDisposition.RETRY
    worker.event_parser.parse = lambda _body: event

    worker.manifest_service.load_and_validate = lambda _location: (_ for _ in ()).throw(
        IngestionInputError("invalid input")
    )
    assert worker._route_message(message, visibility) == MessageDisposition.RETRY
    worker.manifest_service.load_and_validate = lambda _location: manifest
    worker.canonical_document_service.load_and_validate = lambda _manifest: document

    worker.processing_registry.acquire_claim = lambda **_kwargs: ClaimResult(
        disposition=ClaimDisposition.COMPLETED
    )
    assert worker._route_message(message, visibility) == MessageDisposition.ACKNOWLEDGE
    worker.processing_registry.acquire_claim = lambda **_kwargs: ClaimResult(
        disposition=ClaimDisposition.UNAVAILABLE
    )
    assert worker._route_message(message, visibility) == MessageDisposition.RELEASE
    worker.processing_registry.acquire_claim = lambda **_kwargs: ClaimResult(
        disposition=ClaimDisposition.ACQUIRED
    )
    with pytest.raises(RetryableIngestionError, match="claim is missing"):
        worker._route_message(message, visibility)

    worker.processing_registry.acquire_claim = lambda **_kwargs: ClaimResult(
        disposition=ClaimDisposition.ACQUIRED, claim=claim
    )
    worker._process_claimed = lambda **_kwargs: MessageDisposition.ACKNOWLEDGE
    assert worker._route_message(message, visibility) == MessageDisposition.ACKNOWLEDGE


def test_process_claimed_success_and_failure_paths(
    canonical_fixture_dir, profile_factory, monkeypatch
):
    import workers.ingestion_worker as worker_module

    monkeypatch.setattr(worker_module, "ProcessingClaimHeartbeat", _ClaimHeartbeat)
    manifest, document, profile, identity, claim, location, _event = _domain(
        canonical_fixture_dir, profile_factory
    )
    worker = _worker()
    worker.processing_registry.mark_completed = lambda *args, **kwargs: None
    worker.processing_registry.mark_failed = lambda *args, **kwargs: None
    worker.ingestion_profile = profile
    worker.result_store.write_success = lambda _manifest: StoredIngestionManifest(
        bucket="results",
        key="ingestion/_SUCCESS.json",
        version_id=None,
        etag=None,
        checksum_sha256="hash",
        content_length=10,
    )
    failures = []
    worker.result_store.write_failure = failures.append
    chunk = DocumentChunk(
        chunk_id="chunk",
        ingestion_id=identity.ingestion_id,
        ingestion_profile_id=identity.ingestion_profile_id,
        document_id=document.document_id,
        chunk_index=0,
        text="text",
        start_offset=0,
        end_offset=4,
        start_page=1,
        end_page=1,
        character_count=4,
    )
    record = object()
    worker._execute_pipeline = lambda *_args: ((chunk,), (record,), "index")
    visibility = _Visibility()
    assert worker._process_claimed(
        manifest=manifest,
        document=document,
        identity=identity,
        claim=claim,
        location=location,
        visibility=visibility,
        started_at=0,
    ) == MessageDisposition.ACKNOWLEDGE

    worker._execute_pipeline = lambda *_args: (_ for _ in ()).throw(
        PermanentIngestionError("bad document")
    )
    assert worker._process_claimed(
        manifest=manifest,
        document=document,
        identity=identity,
        claim=claim,
        location=location,
        visibility=visibility,
        started_at=0,
    ) == MessageDisposition.ACKNOWLEDGE
    assert isinstance(failures[0], IngestionFailureManifest)
    assert failures[0].error_message == "bad document"

    worker._execute_pipeline = lambda *_args: (_ for _ in ()).throw(
        RetryableIngestionError("temporary")
    )
    with pytest.raises(RetryableIngestionError):
        worker._process_claimed(
            manifest=manifest,
            document=document,
            identity=identity,
            claim=claim,
            location=location,
            visibility=visibility,
            started_at=0,
        )


def test_execute_pipeline_and_success_manifest(canonical_fixture_dir, profile_factory):
    manifest, document, profile, identity, claim, location, _event = _domain(
        canonical_fixture_dir, profile_factory
    )
    worker = _worker()
    worker.ingestion_profile = profile
    chunk = object()
    embedded = object()
    record = object()
    worker.chunking_service = SimpleNamespace(
        chunk_document=lambda **_kwargs: (chunk,)
    )
    worker.embedding_service = SimpleNamespace(
        embed_chunks=lambda **_kwargs: (embedded,)
    )
    worker.index_record_service = SimpleNamespace(
        create_records=lambda **_kwargs: (record,)
    )
    worker.indexing_service = SimpleNamespace(
        index_records=lambda **_kwargs: "destination"
    )
    assert worker._execute_pipeline(document, identity) == ((chunk,), (record,), "destination")

    result = worker._success_manifest(manifest, identity, (chunk,), (record,), "destination")
    assert result.document_id == identity.document_id
    assert result.index_record_count == result.chunk_count == 1
    assert result.index_destination == "destination"
    assert result.completed_at.tzinfo == timezone.utc
    assert worker._build_profile().ingestion_schema_version


def test_run_releases_on_shutdown_and_always_closes():
    class Controller:
        def __init__(self):
            self.states = iter((False, True, True))
            self.restored = False

        @property
        def shutdown_requested(self):
            return next(self.states)

        def install_signal_handlers(self):
            pass

        def restore_signal_handlers(self):
            self.restored = True

    message = object()
    controller = Controller()
    worker = _worker()
    worker.shutdown_controller = controller
    worker.event_consumer.receive_messages = lambda: (message,)
    released = []
    worker.event_consumer.release_message = released.append
    closed = []
    worker.embedding_service.close = lambda: closed.append(True)
    worker.run()
    assert released == [message]
    assert closed == [True]
    assert controller.restored


def test_run_processes_messages_until_shutdown_and_restores_after_close_error():
    class Controller:
        def __init__(self):
            self.states = iter((False, False, True))
            self.restored = False

        @property
        def shutdown_requested(self):
            return next(self.states)

        def install_signal_handlers(self):
            pass

        def restore_signal_handlers(self):
            self.restored = True

    controller = Controller()
    worker = _worker()
    worker.shutdown_controller = controller
    message = object()
    responses = iter(((message,),))
    worker.event_consumer.receive_messages = lambda: next(responses)
    processed = []
    worker._process_message = processed.append

    def fail_close():
        raise RuntimeError("close failed")

    worker.embedding_service.close = fail_close
    with pytest.raises(RuntimeError, match="close failed"):
        worker.run()
    assert processed == [message]
    assert controller.restored
