from typing import Any

from aws_utils.client import get_client


class SQSService:
    """
    Shared Amazon SQS transport adapter.

    Queue-specific business behavior belongs to the
    calling application. This adapter owns only
    boto3 request construction and execution.
    """

    def __init__(
        self,
        *,
        region_name: str | None = None,
        client: Any | None = None,
    ):
        if (
            region_name is not None
            and not isinstance(
                region_name,
                str,
            )
        ):
            raise TypeError(
                "region_name must be a string or "
                "None."
            )

        normalized_region = (
            region_name.strip()
            if region_name is not None
            else None
        )

        if (
            region_name is not None
            and not normalized_region
        ):
            raise ValueError(
                "region_name must not be blank "
                "when supplied."
            )

        self.region_name = normalized_region
        self._client = client

    @property
    def client(
        self,
    ) -> Any:
        """
        Lazily construct the Amazon SQS client.
        """
        if self._client is None:
            self._client = get_client(
                "sqs",
                region_name=self.region_name,
            )

        return self._client

    def receive_messages(
        self,
        *,
        queue_url: str,
        maximum_messages: int = 1,
        wait_time_seconds: int = 20,
        visibility_timeout_seconds: (
            int
            | None
        ) = None,
        attribute_names: (
            list[str]
            | None
        ) = None,
        message_attribute_names: (
            list[str]
            | None
        ) = None,
    ) -> dict[str, Any]:
        """
        Long-poll an Amazon SQS queue.
        """
        normalized_queue_url = (
            self._normalize_required_string(
                value=queue_url,
                field_name="queue_url",
            )
        )

        self._validate_integer_range(
            value=maximum_messages,
            field_name="maximum_messages",
            minimum=1,
            maximum=10,
        )

        self._validate_integer_range(
            value=wait_time_seconds,
            field_name="wait_time_seconds",
            minimum=0,
            maximum=20,
        )

        if visibility_timeout_seconds is not None:
            self._validate_integer_range(
                value=(
                    visibility_timeout_seconds
                ),
                field_name=(
                    "visibility_timeout_seconds"
                ),
                minimum=0,
                maximum=43_200,
            )

        request: dict[str, Any] = {
            "QueueUrl": normalized_queue_url,
            "MaxNumberOfMessages": (
                maximum_messages
            ),
            "WaitTimeSeconds": (
                wait_time_seconds
            ),
            "AttributeNames": (
                attribute_names
                if attribute_names is not None
                else ["All"]
            ),
            "MessageAttributeNames": (
                message_attribute_names
                if message_attribute_names
                is not None
                else ["All"]
            ),
        }

        if visibility_timeout_seconds is not None:
            request["VisibilityTimeout"] = (
                visibility_timeout_seconds
            )

        return self.client.receive_message(
            **request
        )

    def receive_message(
        self,
        queue_url: str,
    ) -> dict[str, Any]:
        """
        Backward-compatible one-message receive
        operation.
        """
        return self.receive_messages(
            queue_url=queue_url,
            maximum_messages=1,
            wait_time_seconds=20,
            attribute_names=[
                "ApproximateReceiveCount",
            ],
        )

    def delete_message(
        self,
        queue_url: str,
        receipt_handle: str,
    ) -> None:
        """
        Delete one completed Amazon SQS message.
        """
        self.client.delete_message(
            QueueUrl=(
                self._normalize_required_string(
                    value=queue_url,
                    field_name="queue_url",
                )
            ),
            ReceiptHandle=(
                self._normalize_required_string(
                    value=receipt_handle,
                    field_name="receipt_handle",
                )
            ),
        )

    def change_message_visibility(
        self,
        queue_url: str,
        receipt_handle: str,
        visibility_timeout: int,
    ) -> None:
        """
        Change one received message's visibility
        timeout.
        """
        self._validate_integer_range(
            value=visibility_timeout,
            field_name="visibility_timeout",
            minimum=0,
            maximum=43_200,
        )

        self.client.change_message_visibility(
            QueueUrl=(
                self._normalize_required_string(
                    value=queue_url,
                    field_name="queue_url",
                )
            ),
            ReceiptHandle=(
                self._normalize_required_string(
                    value=receipt_handle,
                    field_name="receipt_handle",
                )
            ),
            VisibilityTimeout=(
                visibility_timeout
            ),
        )

    def get_queue_attributes(
        self,
        *,
        queue_url: str,
        attribute_names: (
            list[str]
            | None
        ) = None,
    ) -> dict[str, Any]:
        """
        Return requested queue attributes.
        """
        return self.client.get_queue_attributes(
            QueueUrl=(
                self._normalize_required_string(
                    value=queue_url,
                    field_name="queue_url",
                )
            ),
            AttributeNames=(
                attribute_names
                if attribute_names is not None
                else ["All"]
            ),
        )

    @staticmethod
    def _normalize_required_string(
        *,
        value: str,
        field_name: str,
    ) -> str:
        if not isinstance(
            value,
            str,
        ):
            raise TypeError(
                f"{field_name} must be a string."
            )

        normalized_value = value.strip()

        if not normalized_value:
            raise ValueError(
                f"{field_name} must not be blank."
            )

        return normalized_value

    @staticmethod
    def _validate_integer_range(
        *,
        value: int,
        field_name: str,
        minimum: int,
        maximum: int,
    ) -> None:
        if (
            not isinstance(
                value,
                int,
            )
            or isinstance(
                value,
                bool,
            )
        ):
            raise TypeError(
                f"{field_name} must be an integer."
            )

        if (
            value < minimum
            or value > maximum
        ):
            raise ValueError(
                f"{field_name} must be between "
                f"{minimum} and {maximum}."
            )