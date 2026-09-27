import pytest

from events.base_event_consumer import (
    BaseEventConsumer,
)


pytestmark = pytest.mark.unit


class ConcreteEventConsumer(
    BaseEventConsumer
):

    def receive_message(
        self,
    ):
        return BaseEventConsumer.receive_message(
            self
        )

    def delete_message(
        self,
        receipt_handle,
    ):
        return BaseEventConsumer.delete_message(
            self,
            receipt_handle,
        )

    def change_message_visibility(
        self,
        receipt_handle,
        visibility_timeout,
    ):
        return (
            BaseEventConsumer
            .change_message_visibility(
                self,
                receipt_handle,
                visibility_timeout,
            )
        )


def test_base_receive_message_returns_none():
    consumer = ConcreteEventConsumer()

    assert consumer.receive_message() is None


def test_base_delete_message_returns_none():
    consumer = ConcreteEventConsumer()

    assert (
        consumer.delete_message(
            "receipt-123"
        )
        is None
    )


def test_base_change_message_visibility_returns_none():
    consumer = ConcreteEventConsumer()

    assert (
        consumer.change_message_visibility(
            receipt_handle="receipt-123",
            visibility_timeout=600,
        )
        is None
    )