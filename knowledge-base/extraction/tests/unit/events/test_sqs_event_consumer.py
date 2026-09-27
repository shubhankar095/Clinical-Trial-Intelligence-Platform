from unittest.mock import Mock

import pytest

from events.sqs_event_consumer import (
    SQSEventConsumer,
)


pytestmark = pytest.mark.unit


@pytest.fixture
def queue_url():
    return (
        "https://example.invalid/"
        "extraction-queue"
    )


@pytest.fixture
def consumer(
    queue_url,
):
    event_consumer = (
        SQSEventConsumer(
            queue_url
        )
    )

    event_consumer.sqs = Mock()

    return event_consumer


def test_constructor_stores_queue_url(
    queue_url,
):
    consumer = SQSEventConsumer(
        queue_url
    )

    assert (
        consumer.queue_url
        == queue_url
    )


def test_receive_message_delegates_to_sqs(
    consumer,
):
    expected_response = {
        "Messages": [
            {
                "MessageId": (
                    "message-123"
                ),
                "ReceiptHandle": (
                    "receipt-123"
                ),
                "Body": "{}",
            }
        ]
    }

    (
        consumer.sqs
        .receive_message
        .return_value
    ) = expected_response

    result = consumer.receive_message()

    (
        consumer.sqs
        .receive_message
        .assert_called_once_with(
            consumer.queue_url
        )
    )

    assert result == expected_response


def test_receive_message_returns_empty_response(
    consumer,
):
    (
        consumer.sqs
        .receive_message
        .return_value
    ) = {}

    result = consumer.receive_message()

    assert result == {}


def test_receive_message_propagates_failure(
    consumer,
):
    (
        consumer.sqs
        .receive_message
        .side_effect
    ) = RuntimeError(
        "SQS receive failed"
    )

    with pytest.raises(
        RuntimeError,
        match="SQS receive failed",
    ):
        consumer.receive_message()


def test_delete_message_delegates_to_sqs(
    consumer,
):
    consumer.delete_message(
        "receipt-123"
    )

    (
        consumer.sqs
        .delete_message
        .assert_called_once_with(
            consumer.queue_url,
            "receipt-123",
        )
    )


def test_delete_message_propagates_failure(
    consumer,
):
    (
        consumer.sqs
        .delete_message
        .side_effect
    ) = RuntimeError(
        "SQS delete failed"
    )

    with pytest.raises(
        RuntimeError,
        match="SQS delete failed",
    ):
        consumer.delete_message(
            "receipt-123"
        )


def test_change_message_visibility_delegates_to_sqs(
    consumer,
):
    consumer.change_message_visibility(
        receipt_handle="receipt-123",
        visibility_timeout=600,
    )

    (
        consumer.sqs
        .change_message_visibility
        .assert_called_once_with(
            queue_url=(
                consumer.queue_url
            ),
            receipt_handle=(
                "receipt-123"
            ),
            visibility_timeout=600,
        )
    )


def test_change_message_visibility_accepts_zero_timeout(
    consumer,
):
    consumer.change_message_visibility(
        receipt_handle="receipt-123",
        visibility_timeout=0,
    )

    (
        consumer.sqs
        .change_message_visibility
        .assert_called_once_with(
            queue_url=(
                consumer.queue_url
            ),
            receipt_handle=(
                "receipt-123"
            ),
            visibility_timeout=0,
        )
    )


def test_change_message_visibility_propagates_failure(
    consumer,
):
    (
        consumer.sqs
        .change_message_visibility
        .side_effect
    ) = RuntimeError(
        "SQS visibility change failed"
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "SQS visibility change failed"
        ),
    ):
        consumer.change_message_visibility(
            receipt_handle="receipt-123",
            visibility_timeout=600,
        )