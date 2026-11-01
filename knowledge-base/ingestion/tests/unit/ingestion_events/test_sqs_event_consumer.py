from dataclasses import FrozenInstanceError
from types import MappingProxyType
from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError

from aws_utils.sqs import SQSService
from ingestion_events.sqs_event_consumer import (
    SQSDeleteError,
    SQSEventConsumer,
    SQSMessage,
    SQSReceiveError,
    SQSVisibilityError,
)

pytestmark = pytest.mark.unit
QUEUE_URL = "https://sqs.ap-south-1.amazonaws.com/123456789012/ingestion"


def aws_error() -> ClientError:
    return ClientError(
        {"Error": {"Code": "ServiceUnavailable", "Message": "temporary"}},
        "TestOperation",
    )


def raw_message(**changes):
    value = {
        "MessageId": "message-1",
        "ReceiptHandle": "secret-receipt",
        "Body": '{"event":"test"}',
        "Attributes": {
            "ApproximateReceiveCount": "2",
            "SentTimestamp": "1700000000000",
            "Custom": 123,
        },
        "MessageAttributes": {
            "source": {"StringValue": "extraction", "DataType": "String"}
        },
    }
    value.update(changes)
    return value


def create_consumer(response=None):
    client = Mock()
    client.receive_message.return_value = (
        {"Messages": [raw_message()]} if response is None else response
    )
    service = SQSService(region_name="ap-south-1", client=client)
    consumer = SQSEventConsumer(
        queue_url=f" {QUEUE_URL} ",
        wait_time_seconds=10,
        visibility_timeout_seconds=120,
        maximum_messages=3,
        sqs_service=service,
    )
    return consumer, client


def create_message():
    return SQSMessage(
        message_id="message-1",
        receipt_handle="secret-receipt",
        body="body",
        approximate_receive_count=2,
        sent_timestamp_milliseconds=1700000000000,
        attributes={"ApproximateReceiveCount": "2"},
        message_attributes={"source": {"StringValue": "extraction"}},
    )


def test_message_is_frozen_and_mappings_are_immutable():
    attributes = {"a": "1"}
    message_attributes = {"b": {"StringValue": "2"}}
    message = SQSMessage("id", "receipt", "body", 1, None, attributes, message_attributes)
    attributes["a"] = "changed"
    assert isinstance(message.attributes, MappingProxyType)
    assert isinstance(message.message_attributes, MappingProxyType)
    assert message.attributes["a"] == "1"
    with pytest.raises(TypeError):
        message.attributes["x"] = "y"  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        message.body = "changed"  # type: ignore[misc]


def test_constructor_normalizes_and_stores_configuration():
    consumer, _ = create_consumer()
    assert consumer.queue_url == QUEUE_URL
    assert consumer.wait_time_seconds == 10
    assert consumer.visibility_timeout_seconds == 120
    assert consumer.maximum_messages == 3
    assert isinstance(consumer.sqs_service, SQSService)


@pytest.mark.parametrize("queue_url", [None, 1])
def test_constructor_requires_string_queue_url(queue_url):
    with pytest.raises(TypeError):
        SQSEventConsumer(queue_url=queue_url)  # type: ignore[arg-type]


@pytest.mark.parametrize("queue_url", ["", " ", "\n"])
def test_constructor_rejects_blank_queue_url(queue_url):
    with pytest.raises(ValueError):
        SQSEventConsumer(queue_url=queue_url)


@pytest.mark.parametrize(
    "field,value",
    [
        ("wait_time_seconds", -1), ("wait_time_seconds", 21),
        ("visibility_timeout_seconds", -1), ("visibility_timeout_seconds", 43201),
        ("maximum_messages", 0), ("maximum_messages", 11),
    ],
)
def test_constructor_rejects_out_of_range_integers(field, value):
    with pytest.raises(ValueError):
        SQSEventConsumer(queue_url=QUEUE_URL, **{field: value})


@pytest.mark.parametrize("field", ["wait_time_seconds", "visibility_timeout_seconds", "maximum_messages"])
def test_constructor_rejects_non_integer_values(field):
    with pytest.raises(TypeError):
        SQSEventConsumer(queue_url=QUEUE_URL, **{field: True})


def test_constructor_rejects_invalid_service():
    with pytest.raises(TypeError, match="sqs_service"):
        SQSEventConsumer(queue_url=QUEUE_URL, sqs_service=object())  # type: ignore[arg-type]


def test_receive_messages_parses_response_and_calls_transport():
    consumer, client = create_consumer()
    messages = consumer.receive_messages()
    assert len(messages) == 1
    message = messages[0]
    assert message.message_id == "message-1"
    assert message.receipt_handle == "secret-receipt"
    assert message.body == '{"event":"test"}'
    assert message.approximate_receive_count == 2
    assert message.sent_timestamp_milliseconds == 1700000000000
    assert message.attributes["Custom"] == "123"
    client.receive_message.assert_called_once_with(
        QueueUrl=QUEUE_URL,
        MaxNumberOfMessages=3,
        WaitTimeSeconds=10,
        AttributeNames=["All"],
        MessageAttributeNames=["All"],
        VisibilityTimeout=120,
    )


@pytest.mark.parametrize("response", [{}, {"Messages": []}])
def test_receive_messages_allows_no_messages(response):
    consumer, _ = create_consumer(response)
    assert consumer.receive_messages() == ()


@pytest.mark.parametrize("response", [None, [], "invalid", 1])
def test_receive_messages_requires_dictionary(response):
    consumer, client = create_consumer({})
    client.receive_message.return_value = response
    with pytest.raises(SQSReceiveError, match="dictionary"):
        consumer.receive_messages()


def test_receive_messages_requires_message_list():
    consumer, _ = create_consumer({"Messages": {}})
    with pytest.raises(SQSReceiveError, match="must be a list"):
        consumer.receive_messages()


def test_receive_messages_wraps_aws_error():
    consumer, client = create_consumer()
    client.receive_message.side_effect = aws_error()
    with pytest.raises(SQSReceiveError, match="could not be received"):
        consumer.receive_messages()


@pytest.mark.parametrize("value", [None, [], "message", 1])
def test_parse_message_requires_dictionary(value):
    consumer, _ = create_consumer()
    with pytest.raises(SQSReceiveError, match="must be a dictionary"):
        consumer._parse_message(value)  # type: ignore[arg-type]


@pytest.mark.parametrize("field", ["MessageId", "ReceiptHandle"])
def test_parse_message_requires_nonblank_identity_fields(field):
    consumer, _ = create_consumer()
    value = raw_message(**{field: " "})
    with pytest.raises(SQSReceiveError, match=field):
        consumer._parse_message(value)


def test_parse_message_allows_blank_body():
    consumer, _ = create_consumer()
    message = consumer._parse_message(raw_message(Body=""))
    assert message.body == ""


@pytest.mark.parametrize("field", ["MessageId", "ReceiptHandle", "Body"])
def test_parse_message_requires_string_fields(field):
    consumer, _ = create_consumer()
    with pytest.raises(SQSReceiveError, match=field):
        consumer._parse_message(raw_message(**{field: None}))


@pytest.mark.parametrize("field", ["Attributes", "MessageAttributes"])
def test_parse_message_requires_mapping_fields(field):
    consumer, _ = create_consumer()
    with pytest.raises(SQSReceiveError, match=field):
        consumer._parse_message(raw_message(**{field: []}))


def test_parse_message_defaults_optional_fields():
    consumer, _ = create_consumer()
    value = raw_message()
    value.pop("Attributes")
    value.pop("MessageAttributes")
    message = consumer._parse_message(value)
    assert message.approximate_receive_count == 1
    assert message.sent_timestamp_milliseconds is None
    assert dict(message.attributes) == {}
    assert dict(message.message_attributes) == {}


@pytest.mark.parametrize(
    "attributes",
    [
        {"ApproximateReceiveCount": "bad"},
        {"ApproximateReceiveCount": "0"},
        {"SentTimestamp": "bad"},
        {"SentTimestamp": "-1"},
    ],
)
def test_parse_message_rejects_invalid_integer_attributes(attributes):
    consumer, _ = create_consumer()
    with pytest.raises(SQSReceiveError):
        consumer._parse_message(raw_message(Attributes=attributes))


def test_acknowledge_message_deletes_message():
    consumer, client = create_consumer()
    message = create_message()
    consumer.acknowledge_message(message)
    client.delete_message.assert_called_once_with(
        QueueUrl=QUEUE_URL,
        ReceiptHandle="secret-receipt",
    )


def test_acknowledge_message_validates_type():
    consumer, _ = create_consumer()
    with pytest.raises(TypeError, match="SQSMessage"):
        consumer.acknowledge_message(object())  # type: ignore[arg-type]


def test_acknowledge_message_wraps_aws_error():
    consumer, client = create_consumer()
    client.delete_message.side_effect = aws_error()
    with pytest.raises(SQSDeleteError, match="could not be acknowledged"):
        consumer.acknowledge_message(create_message())


def test_change_visibility_calls_transport():
    consumer, client = create_consumer()
    consumer.change_message_visibility(create_message(), visibility_timeout_seconds=45)
    client.change_message_visibility.assert_called_once_with(
        QueueUrl=QUEUE_URL,
        ReceiptHandle="secret-receipt",
        VisibilityTimeout=45,
    )


@pytest.mark.parametrize("value", [-1, 43201])
def test_change_visibility_rejects_range(value):
    consumer, _ = create_consumer()
    with pytest.raises(ValueError):
        consumer.change_message_visibility(create_message(), visibility_timeout_seconds=value)


def test_change_visibility_wraps_aws_error():
    consumer, client = create_consumer()
    client.change_message_visibility.side_effect = aws_error()
    with pytest.raises(SQSVisibilityError, match="could not be changed"):
        consumer.change_message_visibility(create_message(), visibility_timeout_seconds=45)


def test_release_message_sets_visibility_to_zero():
    consumer, client = create_consumer()
    consumer.release_message(create_message())
    client.change_message_visibility.assert_called_once_with(
        QueueUrl=QUEUE_URL,
        ReceiptHandle="secret-receipt",
        VisibilityTimeout=0,
    )
