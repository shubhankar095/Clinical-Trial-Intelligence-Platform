import pytest
from ingestion_events.sqs_event_consumer import SQSEventConsumer
pytestmark=[pytest.mark.integration,pytest.mark.local]

def test_receive_release_redeliver_and_acknowledge(local_resources):
    client=local_resources["sqs_client"]; url=local_resources["queue_url"]
    client.send_message(QueueUrl=url,MessageBody='{"event":"test"}')
    consumer=SQSEventConsumer(queue_url=url,wait_time_seconds=1,visibility_timeout_seconds=30,
        maximum_messages=1,sqs_service=local_resources["sqs_service"])
    first=consumer.receive_messages()[0]
    consumer.release_message(first)
    second=consumer.receive_messages()[0]
    assert second.message_id == first.message_id
    assert second.approximate_receive_count >= 2
    consumer.acknowledge_message(second)
    assert consumer.receive_messages() == ()
