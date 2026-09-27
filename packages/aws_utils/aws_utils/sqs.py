from aws_utils.client import get_client


class SQSService:

    def __init__(self):

        self._client = None

    @property
    def client(self):

        if self._client is None:
            self._client = get_client("sqs")

        return self._client

    def receive_message(
        self,
        queue_url: str,
    ) -> dict:

        return self.client.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=20,
            AttributeNames=[
                "ApproximateReceiveCount",
            ],
        )

    def delete_message(
        self,
        queue_url: str,
        receipt_handle: str,
    ) -> None:

        self.client.delete_message(
            QueueUrl=queue_url,
            ReceiptHandle=receipt_handle,
        )

    def change_message_visibility(
        self,
        queue_url: str,
        receipt_handle: str,
        visibility_timeout: int,
    ) -> None:

        self.client.change_message_visibility(
            QueueUrl=queue_url,
            ReceiptHandle=receipt_handle,
            VisibilityTimeout=visibility_timeout,
        )

    