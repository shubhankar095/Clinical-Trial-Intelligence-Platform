from aws_utils.sqs import SQSService
from events.base_event_consumer import BaseEventConsumer


class SQSEventConsumer(BaseEventConsumer):

    def __init__(
        self,
        queue_url: str
    ):

        self.queue_url = queue_url

        self.sqs = SQSService()

    def receive_message(self):

        return self.sqs.receive_message(
            self.queue_url
        )

    def delete_message(
        self,
        receipt_handle: str
    ):

        self.sqs.delete_message(
            self.queue_url,
            receipt_handle
        )

    def change_message_visibility(
        self,
        receipt_handle: str,
        visibility_timeout: int,
    ) -> None:
        self.sqs.change_message_visibility(
            queue_url=self.queue_url,
            receipt_handle=receipt_handle,
            visibility_timeout=visibility_timeout,
        )