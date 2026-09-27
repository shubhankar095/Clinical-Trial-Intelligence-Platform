from unittest.mock import Mock

import pytest

from exceptions.processing_claim import (
    ProcessingClaimLostError,
)
from repositories.processing_registry import (
    ProcessingClaim,
)
from services import (
    processing_claim_heartbeat,
)
from services.processing_claim_heartbeat import (
    ProcessingClaimHeartbeat,
)


pytestmark = pytest.mark.unit


class ControlledStopEvent:

    def __init__(
        self,
        wait_results,
    ):
        self.wait_results = iter(
            wait_results
        )
        self.wait_calls = []
        self.set_calls = 0

    def wait(
        self,
        timeout,
    ):
        self.wait_calls.append(
            timeout
        )
        return next(
            self.wait_results
        )

    def set(
        self,
    ):
        self.set_calls += 1


class FakeThread:

    def __init__(
        self,
        *,
        target,
        name,
        daemon,
        alive=False,
    ):
        self.target = target
        self.name = name
        self.daemon = daemon
        self.alive = alive
        self.start_calls = 0
        self.join_calls = []

    def start(
        self,
    ):
        self.start_calls += 1
        self.alive = True

    def is_alive(
        self,
    ):
        return self.alive

    def join(
        self,
        timeout=None,
    ):
        self.join_calls.append(
            timeout
        )


@pytest.fixture
def claim():
    return ProcessingClaim(
        document_id="document-123",
        owner_token="owner-token-123",
        lease_expires_at=1900,
    )


@pytest.fixture
def registry():
    return Mock()


def build_heartbeat(
    registry,
    claim,
    heartbeat_seconds=5,
):
    return ProcessingClaimHeartbeat(
        processing_registry=registry,
        claim=claim,
        heartbeat_seconds=(
            heartbeat_seconds
        ),
    )


@pytest.mark.parametrize(
    "heartbeat_seconds",
    [
        0,
        -1,
        -5,
    ],
)
def test_constructor_rejects_invalid_interval(
    registry,
    claim,
    heartbeat_seconds,
):
    with pytest.raises(
        ValueError,
        match="greater than zero",
    ):
        build_heartbeat(
            registry,
            claim,
            heartbeat_seconds,
        )


def test_constructor_initializes_state(
    registry,
    claim,
):
    heartbeat = build_heartbeat(
        registry,
        claim,
    )

    assert heartbeat.processing_registry is (
        registry
    )
    assert heartbeat.claim is claim
    assert heartbeat.heartbeat_seconds == 5
    assert heartbeat.failed is False
    assert heartbeat.failure is None
    assert heartbeat._thread is None
    assert heartbeat._stopped is False


def test_start_creates_daemon_thread(
    monkeypatch,
    registry,
    claim,
):
    created_threads = []

    def thread_factory(
        *,
        target,
        name,
        daemon,
    ):
        thread = FakeThread(
            target=target,
            name=name,
            daemon=daemon,
        )
        created_threads.append(
            thread
        )
        return thread

    monkeypatch.setattr(
        processing_claim_heartbeat
        .threading,
        "Thread",
        thread_factory,
    )

    heartbeat = build_heartbeat(
        registry,
        claim,
    )

    heartbeat.start()

    assert len(created_threads) == 1

    thread = created_threads[0]

    assert thread.target == heartbeat._run
    assert thread.name == (
        "processing-claim-heartbeat"
    )
    assert thread.daemon is True
    assert thread.start_calls == 1
    assert heartbeat._thread is thread


def test_start_is_idempotent_when_thread_is_alive(
    registry,
    claim,
):
    heartbeat = build_heartbeat(
        registry,
        claim,
    )

    existing_thread = Mock()
    existing_thread.is_alive.return_value = (
        True
    )

    heartbeat._thread = existing_thread

    heartbeat.start()

    existing_thread.is_alive.assert_called_once_with()


def test_run_renews_claim(
    registry,
    claim,
):
    renewed_claim = ProcessingClaim(
        document_id="document-123",
        owner_token="owner-token-123",
        lease_expires_at=2000,
    )

    registry.renew.return_value = (
        renewed_claim
    )

    heartbeat = build_heartbeat(
        registry,
        claim,
    )

    stop_event = ControlledStopEvent(
        [
            False,
            True,
        ]
    )

    heartbeat._stop_event = (
        stop_event
    )

    heartbeat._run()

    registry.renew.assert_called_once_with(
        claim
    )

    assert heartbeat.claim == (
        renewed_claim
    )
    assert stop_event.wait_calls == [
        5,
        5,
    ]
    assert heartbeat.failed is False


def test_run_stores_claim_loss_failure(
    registry,
    claim,
):
    failure = ProcessingClaimLostError(
        "Claim lost"
    )

    registry.renew.side_effect = (
        failure
    )

    heartbeat = build_heartbeat(
        registry,
        claim,
    )

    heartbeat._stop_event = (
        ControlledStopEvent(
            [False]
        )
    )

    heartbeat._run()

    assert heartbeat.failed is True
    assert heartbeat.failure is failure


def test_run_stores_unexpected_failure(
    registry,
    claim,
):
    failure = RuntimeError(
        "DynamoDB unavailable"
    )

    registry.renew.side_effect = (
        failure
    )

    heartbeat = build_heartbeat(
        registry,
        claim,
    )

    heartbeat._stop_event = (
        ControlledStopEvent(
            [False]
        )
    )

    heartbeat._run()

    assert heartbeat.failed is True
    assert heartbeat.failure is failure


def test_raise_if_failed_returns_when_healthy(
    registry,
    claim,
):
    heartbeat = build_heartbeat(
        registry,
        claim,
    )

    heartbeat.raise_if_failed()


def test_raise_if_failed_translates_claim_loss(
    registry,
    claim,
):
    heartbeat = build_heartbeat(
        registry,
        claim,
    )

    original_failure = (
        ProcessingClaimLostError(
            "Original claim loss"
        )
    )

    heartbeat._failure = (
        original_failure
    )

    with pytest.raises(
        ProcessingClaimLostError,
        match=(
            "lost during document processing"
        ),
    ) as exception_info:
        heartbeat.raise_if_failed()

    assert (
        exception_info.value.__cause__
        is original_failure
    )


def test_raise_if_failed_translates_generic_failure(
    registry,
    claim,
):
    heartbeat = build_heartbeat(
        registry,
        claim,
    )

    original_failure = RuntimeError(
        "DynamoDB unavailable"
    )

    heartbeat._failure = (
        original_failure
    )

    with pytest.raises(
        RuntimeError,
        match="renewal failed",
    ) as exception_info:
        heartbeat.raise_if_failed()

    assert (
        exception_info.value.__cause__
        is original_failure
    )


def test_stop_sets_event_and_joins_thread(
    registry,
    claim,
):
    heartbeat = build_heartbeat(
        registry,
        claim,
    )

    stop_event = Mock()
    thread = Mock()
    thread.is_alive.return_value = False

    heartbeat._stop_event = stop_event
    heartbeat._thread = thread

    heartbeat.stop()

    assert heartbeat._stopped is True
    stop_event.set.assert_called_once_with()
    thread.join.assert_called_once_with(
        timeout=10
    )
    thread.is_alive.assert_called_once_with()
    assert heartbeat.failed is False


def test_stop_without_thread_is_safe(
    registry,
    claim,
):
    heartbeat = build_heartbeat(
        registry,
        claim,
    )

    stop_event = Mock()
    heartbeat._stop_event = stop_event

    heartbeat.stop()

    stop_event.set.assert_called_once_with()
    assert heartbeat._stopped is True


def test_stop_is_idempotent(
    registry,
    claim,
):
    heartbeat = build_heartbeat(
        registry,
        claim,
    )

    stop_event = Mock()
    thread = Mock()
    thread.is_alive.return_value = False

    heartbeat._stop_event = stop_event
    heartbeat._thread = thread

    heartbeat.stop()
    heartbeat.stop()

    stop_event.set.assert_called_once_with()
    thread.join.assert_called_once_with(
        timeout=10
    )


def test_stop_records_failure_when_thread_remains_alive(
    registry,
    claim,
):
    heartbeat = build_heartbeat(
        registry,
        claim,
    )

    thread = Mock()
    thread.is_alive.return_value = True

    heartbeat._thread = thread

    heartbeat.stop()

    assert heartbeat.failed is True
    assert isinstance(
        heartbeat.failure,
        RuntimeError,
    )
    assert (
        "did not stop cleanly"
        in str(
            heartbeat.failure
        )
    )