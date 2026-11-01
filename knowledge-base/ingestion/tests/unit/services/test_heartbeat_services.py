import pytest

from exceptions.processing import ProcessingOwnershipLostError, RetryableIngestionError
from ingestion_events.sqs_event_consumer import SQSMessage, SQSEventConsumer
from repositories.processing_registry import ProcessingClaim, ProcessingClaimLostError, ProcessingRegistry
from services.message_visibility_heartbeat import MessageVisibilityHeartbeat
from services.processing_claim_heartbeat import ProcessingClaimHeartbeat


pytestmark = pytest.mark.unit


class _SequenceEvent:
    def __init__(self, values):
        self.values = iter(values)

    def wait(self, _timeout):
        return next(self.values, True)

    def set(self):
        pass


def _message():
    return SQSMessage(
        message_id="message",
        receipt_handle="private",
        body="{}",
        approximate_receive_count=1,
        sent_timestamp_milliseconds=None,
        attributes={},
        message_attributes={},
    )


def _consumer(change=None):
    consumer = object.__new__(SQSEventConsumer)
    consumer.change_message_visibility = change or (lambda *args, **kwargs: None)
    return consumer


def _claim():
    return ProcessingClaim(
        ingestion_id="ingestion",
        owner_token="owner",
        attempt_count=1,
        claimed_at="2024-01-01T00:00:00+00:00",
        lease_expires_at=100,
    )


def _registry(renew=None):
    registry = object.__new__(ProcessingRegistry)
    registry.lease_seconds = 10
    registry.renew_claim = renew or (lambda claim: claim.lease_expires_at + 10)
    return registry


def test_message_visibility_heartbeat_validation_and_clean_lifecycle():
    with pytest.raises(TypeError):
        MessageVisibilityHeartbeat(consumer=object(), message=_message(), heartbeat_seconds=1, extension_seconds=2)
    with pytest.raises(TypeError):
        MessageVisibilityHeartbeat(consumer=_consumer(), message=object(), heartbeat_seconds=1, extension_seconds=2)
    for heartbeat, extension, exception in (
        (True, 2, TypeError),
        (0, 2, ValueError),
        (1, 0, ValueError),
        (1, 43201, ValueError),
        (2, 2, ValueError),
    ):
        with pytest.raises(exception):
            MessageVisibilityHeartbeat(
                consumer=_consumer(),
                message=_message(),
                heartbeat_seconds=heartbeat,
                extension_seconds=extension,
            )

    heartbeat = MessageVisibilityHeartbeat(
        consumer=_consumer(), message=_message(), heartbeat_seconds=5, extension_seconds=10
    )
    assert not heartbeat.is_running
    assert not heartbeat.heartbeat_failed
    assert heartbeat.failure_exception is None
    heartbeat.stop()
    heartbeat.start()
    assert heartbeat.is_running
    with pytest.raises(RuntimeError, match="already been started"):
        heartbeat.start()
    heartbeat.stop()
    heartbeat.stop()
    assert not heartbeat.is_running
    heartbeat.raise_for_failure()


def test_message_visibility_heartbeat_renews_and_reports_failure():
    calls = []
    heartbeat = MessageVisibilityHeartbeat(
        consumer=_consumer(lambda message, **kwargs: calls.append((message, kwargs))),
        message=_message(),
        heartbeat_seconds=1,
        extension_seconds=4,
    )
    heartbeat._stop_event = _SequenceEvent([False, True])
    heartbeat._run()
    assert len(calls) == 1
    assert calls[0][1] == {"visibility_timeout_seconds": 4}

    error = RuntimeError("visibility unavailable")
    failing = MessageVisibilityHeartbeat(
        consumer=_consumer(lambda *_args, **_kwargs: (_ for _ in ()).throw(error)),
        message=_message(),
        heartbeat_seconds=1,
        extension_seconds=4,
    )
    failing._stop_event = _SequenceEvent([False])
    failing._run()
    assert failing.heartbeat_failed
    assert failing.failure_exception is error
    with pytest.raises(RetryableIngestionError) as raised:
        failing.raise_for_failure()
    assert raised.value.__cause__ is error


def test_message_visibility_stop_times_out_for_live_thread(monkeypatch):
    class StuckThread:
        def __init__(self, **kwargs):
            self.alive = False

        def start(self):
            self.alive = True

        def is_alive(self):
            return self.alive

        def join(self, timeout=None):
            self.timeout = timeout

    monkeypatch.setattr("services.message_visibility_heartbeat.threading.Thread", StuckThread)
    heartbeat = MessageVisibilityHeartbeat(
        consumer=_consumer(), message=_message(), heartbeat_seconds=1, extension_seconds=2
    )
    heartbeat.start()
    with pytest.raises(RetryableIngestionError, match="did not stop"):
        heartbeat.stop()


def test_message_visibility_stop_skips_join_when_called_by_heartbeat_thread(monkeypatch):
    class CurrentThread:
        name = "heartbeat-test"

        def is_alive(self):
            return False

    heartbeat = MessageVisibilityHeartbeat(
        consumer=_consumer(), message=_message(), heartbeat_seconds=1, extension_seconds=2
    )
    current = CurrentThread()
    heartbeat._thread = current
    monkeypatch.setattr("services.message_visibility_heartbeat.threading.current_thread", lambda: current)
    heartbeat.stop()
    assert heartbeat._stopped


def test_claim_heartbeat_validation_and_clean_lifecycle():
    with pytest.raises(TypeError):
        ProcessingClaimHeartbeat(registry=object(), claim=_claim(), heartbeat_seconds=1)
    with pytest.raises(TypeError):
        ProcessingClaimHeartbeat(registry=_registry(), claim=object(), heartbeat_seconds=1)
    for seconds, exception in ((True, TypeError), (0, ValueError), (10, ValueError)):
        with pytest.raises(exception):
            ProcessingClaimHeartbeat(registry=_registry(), claim=_claim(), heartbeat_seconds=seconds)

    heartbeat = ProcessingClaimHeartbeat(registry=_registry(), claim=_claim(), heartbeat_seconds=1)
    assert heartbeat.claim == _claim()
    assert not heartbeat.is_running
    assert heartbeat.failure_exception is None
    heartbeat.stop()
    heartbeat.start()
    assert heartbeat.is_running
    with pytest.raises(RuntimeError, match="already been started"):
        heartbeat.start()
    heartbeat.stop()
    heartbeat.stop()
    assert not heartbeat.is_running
    heartbeat.raise_for_failure()


def test_claim_heartbeat_renews_and_maps_failures():
    heartbeat = ProcessingClaimHeartbeat(
        registry=_registry(), claim=_claim(), heartbeat_seconds=1
    )
    heartbeat._stop_event = _SequenceEvent([False, True])
    heartbeat._run()
    assert heartbeat.claim.lease_expires_at == 110

    lost_registry = _registry(lambda _claim: (_ for _ in ()).throw(ProcessingClaimLostError("lost")))
    lost = ProcessingClaimHeartbeat(registry=lost_registry, claim=_claim(), heartbeat_seconds=1)
    lost._stop_event = _SequenceEvent([False])
    lost._run()
    with pytest.raises(ProcessingOwnershipLostError) as raised:
        lost.raise_for_failure()
    assert isinstance(raised.value.__cause__, ProcessingClaimLostError)

    error = OSError("db offline")
    failed_registry = _registry(lambda _claim: (_ for _ in ()).throw(error))
    failed = ProcessingClaimHeartbeat(registry=failed_registry, claim=_claim(), heartbeat_seconds=1)
    failed._stop_event = _SequenceEvent([False])
    failed._run()
    with pytest.raises(RetryableIngestionError) as raised:
        failed.raise_for_failure()
    assert raised.value.__cause__ is error


def test_claim_heartbeat_stop_times_out_for_live_thread(monkeypatch):
    class StuckThread:
        def __init__(self, **kwargs):
            self.alive = False

        def start(self):
            self.alive = True

        def is_alive(self):
            return self.alive

        def join(self, timeout=None):
            self.timeout = timeout

    monkeypatch.setattr("services.processing_claim_heartbeat.threading.Thread", StuckThread)
    heartbeat = ProcessingClaimHeartbeat(registry=_registry(), claim=_claim(), heartbeat_seconds=1)
    heartbeat.start()
    with pytest.raises(RetryableIngestionError, match="did not stop"):
        heartbeat.stop()


def test_claim_heartbeat_stop_skips_join_when_called_by_heartbeat_thread(monkeypatch):
    class CurrentThread:
        def is_alive(self):
            return False

    heartbeat = ProcessingClaimHeartbeat(
        registry=_registry(), claim=_claim(), heartbeat_seconds=1
    )
    current = CurrentThread()
    heartbeat._thread = current
    monkeypatch.setattr("services.processing_claim_heartbeat.threading.current_thread", lambda: current)
    heartbeat.stop()
    assert heartbeat._stopped
