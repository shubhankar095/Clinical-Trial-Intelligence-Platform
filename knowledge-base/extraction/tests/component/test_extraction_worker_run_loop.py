import signal
from unittest.mock import Mock

import pytest

from workers import extraction_worker
from workers.extraction_worker import (
    ExtractionWorker,
)


pytestmark = pytest.mark.component


class FakeExtractionService:

    pass


class EmptyQueueConsumer:

    def __init__(
        self,
    ):
        self.worker = None
        self.receive_calls = 0

    def receive_message(
        self,
    ):
        self.receive_calls += 1

        self.worker.shutdown_requested = (
            True
        )

        return {
            "Messages": [],
        }

    def delete_message(
        self,
        receipt_handle,
    ):
        raise AssertionError(
            "No message should be deleted"
        )


class SingleBatchConsumer:

    def __init__(
        self,
        messages,
    ):
        self.messages = messages
        self.worker = None
        self.receive_calls = 0

    def receive_message(
        self,
    ):
        self.receive_calls += 1

        return {
            "Messages": self.messages,
        }

    def delete_message(
        self,
        receipt_handle,
    ):
        pass


class RecoveringConsumer:

    def __init__(
        self,
    ):
        self.worker = None
        self.receive_calls = 0

    def receive_message(
        self,
    ):
        self.receive_calls += 1

        if self.receive_calls == 1:
            raise RuntimeError(
                "Temporary SQS failure"
            )

        self.worker.shutdown_requested = (
            True
        )

        return {
            "Messages": [],
        }

    def delete_message(
        self,
        receipt_handle,
    ):
        pass


class AlwaysFailingConsumer:

    def __init__(
        self,
    ):
        self.worker = None
        self.receive_calls = 0

    def receive_message(
        self,
    ):
        self.receive_calls += 1

        if self.receive_calls >= 3:
            self.worker.shutdown_requested = (
                True
            )

        raise RuntimeError(
            "SQS unavailable"
        )

    def delete_message(
        self,
        receipt_handle,
    ):
        pass


def build_worker(
    consumer,
):
    worker = ExtractionWorker(
        consumer=consumer,
        extraction_service=(
            FakeExtractionService()
        ),
    )

    consumer.worker = worker

    return worker


def test_request_shutdown_sets_shutdown_flag():
    consumer = EmptyQueueConsumer()

    worker = build_worker(
        consumer
    )

    assert (
        worker.shutdown_requested
        is False
    )

    worker._request_shutdown(
        signal.SIGTERM,
        None,
    )

    assert (
        worker.shutdown_requested
        is True
    )


def test_repeated_shutdown_request_is_idempotent():
    consumer = EmptyQueueConsumer()

    worker = build_worker(
        consumer
    )

    worker._request_shutdown(
        signal.SIGTERM,
        None,
    )

    worker._request_shutdown(
        signal.SIGINT,
        None,
    )

    assert (
        worker.shutdown_requested
        is True
    )


def test_register_signal_handlers(
    monkeypatch,
):
    consumer = EmptyQueueConsumer()

    worker = build_worker(
        consumer
    )

    registered_handlers = {}

    def fake_signal(
        signum,
        handler,
    ):
        registered_handlers[
            signum
        ] = handler

    monkeypatch.setattr(
        extraction_worker.signal,
        "signal",
        fake_signal,
    )

    worker._register_signal_handlers()

    assert (
        registered_handlers[
            signal.SIGTERM
        ]
        == worker._request_shutdown
    )

    assert (
        registered_handlers[
            signal.SIGINT
        ]
        == worker._request_shutdown
    )


def test_run_stops_after_empty_queue_when_shutdown_requested(
    monkeypatch,
):
    consumer = EmptyQueueConsumer()

    worker = build_worker(
        consumer
    )

    monkeypatch.setattr(
        worker,
        "_register_signal_handlers",
        Mock(),
    )

    worker.run()

    assert (
        consumer.receive_calls
        == 1
    )

    assert (
        worker.shutdown_requested
        is True
    )


def test_run_processes_all_messages_in_batch(
    monkeypatch,
):
    messages = [
        {
            "MessageId": "message-1",
            "ReceiptHandle": (
                "receipt-1"
            ),
            "Body": "{}",
        },
        {
            "MessageId": "message-2",
            "ReceiptHandle": (
                "receipt-2"
            ),
            "Body": "{}",
        },
    ]

    consumer = SingleBatchConsumer(
        messages
    )

    worker = build_worker(
        consumer
    )

    processed_messages = []

    def process_message(
        message,
    ):
        processed_messages.append(
            message["MessageId"]
        )

        if len(processed_messages) == 2:
            worker.shutdown_requested = (
                True
            )

    monkeypatch.setattr(
        worker,
        "_register_signal_handlers",
        Mock(),
    )

    monkeypatch.setattr(
        worker,
        "_process_message",
        process_message,
    )

    worker.run()

    assert processed_messages == [
        "message-1",
        "message-2",
    ]


def test_run_does_not_start_remaining_messages_after_shutdown(
    monkeypatch,
):
    messages = [
        {
            "MessageId": "message-1",
            "ReceiptHandle": (
                "receipt-1"
            ),
            "Body": "{}",
        },
        {
            "MessageId": "message-2",
            "ReceiptHandle": (
                "receipt-2"
            ),
            "Body": "{}",
        },
    ]

    consumer = SingleBatchConsumer(
        messages
    )

    worker = build_worker(
        consumer
    )

    processed_messages = []

    def process_message(
        message,
    ):
        processed_messages.append(
            message["MessageId"]
        )

        worker.shutdown_requested = (
            True
        )

    monkeypatch.setattr(
        worker,
        "_register_signal_handlers",
        Mock(),
    )

    monkeypatch.setattr(
        worker,
        "_process_message",
        process_message,
    )

    worker.run()

    assert processed_messages == [
        "message-1"
    ]


def test_receive_failure_uses_exponential_backoff(
    monkeypatch,
):
    consumer = RecoveringConsumer()

    worker = build_worker(
        consumer
    )

    sleep_calls = []

    monkeypatch.setattr(
        worker,
        "_register_signal_handlers",
        Mock(),
    )

    monkeypatch.setattr(
        extraction_worker.time,
        "sleep",
        lambda seconds: (
            sleep_calls.append(
                seconds
            )
        ),
    )

    worker.run()

    assert (
        consumer.receive_calls
        == 2
    )

    assert sleep_calls == [2]


def test_successful_receive_resets_failure_count(
    monkeypatch,
):
    class FailThenSucceedThenFailConsumer:

        def __init__(
            self,
        ):
            self.worker = None
            self.receive_calls = 0

        def receive_message(
            self,
        ):
            self.receive_calls += 1

            if self.receive_calls == 1:
                raise RuntimeError(
                    "First failure"
                )

            if self.receive_calls == 2:
                return {
                    "Messages": [],
                }

            self.worker.shutdown_requested = (
                True
            )

            raise RuntimeError(
                "Second failure"
            )

        def delete_message(
            self,
            receipt_handle,
        ):
            pass

    consumer = (
        FailThenSucceedThenFailConsumer()
    )

    worker = build_worker(
        consumer
    )

    sleep_calls = []

    monkeypatch.setattr(
        worker,
        "_register_signal_handlers",
        Mock(),
    )

    monkeypatch.setattr(
        extraction_worker.time,
        "sleep",
        lambda seconds: (
            sleep_calls.append(
                seconds
            )
        ),
    )

    worker.run()

    assert sleep_calls == [
        2,
        2,
    ]


def test_receive_backoff_increases_exponentially(
    monkeypatch,
):
    consumer = AlwaysFailingConsumer()

    worker = build_worker(
        consumer
    )

    sleep_calls = []

    monkeypatch.setattr(
        worker,
        "_register_signal_handlers",
        Mock(),
    )

    monkeypatch.setattr(
        extraction_worker.time,
        "sleep",
        lambda seconds: (
            sleep_calls.append(
                seconds
            )
        ),
    )

    worker.run()

    assert sleep_calls == [
        2,
        4,
        8,
    ]


def test_run_registers_signal_handlers(
    monkeypatch,
):
    consumer = EmptyQueueConsumer()

    worker = build_worker(
        consumer
    )

    register_mock = Mock()

    monkeypatch.setattr(
        worker,
        "_register_signal_handlers",
        register_mock,
    )

    worker.run()

    register_mock.assert_called_once_with()


class LongFailingConsumer:

    def __init__(
        self,
    ):
        self.worker = None
        self.receive_calls = 0

    def receive_message(
        self,
    ):
        self.receive_calls += 1

        if self.receive_calls >= 7:
            self.worker.shutdown_requested = (
                True
            )

        raise RuntimeError(
            "SQS remains unavailable"
        )

    def delete_message(
        self,
        receipt_handle,
    ):
        pass


def test_receive_backoff_reaches_and_holds_sixty_second_cap(
    monkeypatch,
):
    consumer = LongFailingConsumer()

    worker = build_worker(
        consumer
    )

    sleep_calls = []

    monkeypatch.setattr(
        worker,
        "_register_signal_handlers",
        Mock(),
    )

    monkeypatch.setattr(
        extraction_worker.time,
        "sleep",
        lambda seconds: (
            sleep_calls.append(
                seconds
            )
        ),
    )

    worker.run()

    assert sleep_calls == [
        2,
        4,
        8,
        16,
        32,
        60,
        60,
    ]