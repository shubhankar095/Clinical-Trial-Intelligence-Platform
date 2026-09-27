from unittest.mock import Mock

import pytest

from services import (
    message_visibility_heartbeat,
)
from services.message_visibility_heartbeat import (
    MessageVisibilityHeartbeat,
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
    ):
        self.target = target
        self.name = name
        self.daemon = daemon
        self.start_calls = 0
        self.join_calls = []
        self.alive = False

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
def consumer():
    return Mock()


@pytest.fixture
def heartbeat(
    consumer,
):
    return MessageVisibilityHeartbeat(
        consumer=consumer,
        receipt_handle="receipt-123",
        heartbeat_seconds=180,
        extension_seconds=600,
    )


def test_constructor_initializes_state(
    heartbeat,
    consumer,
):
    assert heartbeat.consumer is consumer
    assert heartbeat.receipt_handle == (
        "receipt-123"
    )
    assert heartbeat.heartbeat_seconds == 180
    assert heartbeat.extension_seconds == 600
    assert heartbeat.failed is False
    assert heartbeat._thread is None


def test_start_creates_daemon_thread(
    monkeypatch,
    heartbeat,
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
        message_visibility_heartbeat
        .threading,
        "Thread",
        thread_factory,
    )

    heartbeat.start()

    assert len(created_threads) == 1

    thread = created_threads[0]

    assert thread.target == heartbeat._run
    assert thread.name == (
        "sqs-visibility-heartbeat"
    )
    assert thread.daemon is True
    assert thread.start_calls == 1


def test_start_is_idempotent_when_alive(
    heartbeat,
):
    thread = Mock()
    thread.is_alive.return_value = True

    heartbeat._thread = thread

    heartbeat.start()

    thread.is_alive.assert_called_once_with()


def test_run_extends_message_visibility(
    heartbeat,
    consumer,
):
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

    (
        consumer
        .change_message_visibility
        .assert_called_once_with(
            receipt_handle="receipt-123",
            visibility_timeout=600,
        )
    )

    assert stop_event.wait_calls == [
        180,
        180,
    ]
    assert heartbeat.failed is False


def test_run_records_visibility_failure(
    heartbeat,
    consumer,
):
    consumer.change_message_visibility.side_effect = (
        RuntimeError(
            "SQS unavailable"
        )
    )

    heartbeat._stop_event = (
        ControlledStopEvent(
            [False]
        )
    )

    heartbeat._run()

    assert heartbeat.failed is True


def test_stop_sets_event_without_thread(
    heartbeat,
):
    stop_event = Mock()
    heartbeat._stop_event = stop_event

    heartbeat.stop()

    stop_event.set.assert_called_once_with()


def test_stop_joins_existing_thread(
    heartbeat,
):
    stop_event = Mock()
    thread = Mock()

    heartbeat._stop_event = stop_event
    heartbeat._thread = thread

    heartbeat.stop()

    stop_event.set.assert_called_once_with()
    thread.join.assert_called_once_with(
        timeout=5
    )


def test_failed_property_reflects_internal_state(
    heartbeat,
):
    assert heartbeat.failed is False

    heartbeat._failed = True

    assert heartbeat.failed is True