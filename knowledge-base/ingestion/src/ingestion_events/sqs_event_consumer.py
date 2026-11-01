from dataclasses import dataclass
from types import MappingProxyType
from typing import (
    Any,
    Mapping,
)

from botocore.exceptions import (
    BotoCoreError,
    ClientError,
)

from aws_utils.sqs import (
    SQSService,
)
from utils.logger import get_logger


logger = get_logger(__name__)


class SQSConsumerError(
    RuntimeError
):
    """
    Base exception for Ingestion SQS operations.
    """


class SQSReceiveError(
    SQSConsumerError
):
    """
    Messages could not be received or the Amazon SQS
    response was invalid.
    """


class SQSDeleteError(
    SQSConsumerError
):
    """
    A completed message could not be deleted.
    """


class SQSVisibilityError(
    SQSConsumerError
):
    """
    A message visibility timeout could not be
    changed.
    """


@dataclass(
    frozen=True,
    slots=True,
)
class SQSMessage:
    """
    Immutable representation of one received Amazon
    SQS message.

    The receipt handle must never be logged because
    the handle temporarily authorizes deletion and
    visibility changes for the message.
    """

    message_id: str
    receipt_handle: str
    body: str

    approximate_receive_count: int

    sent_timestamp_milliseconds: (
        int
        | None
    )

    attributes: Mapping[
        str,
        str,
    ]

    message_attributes: Mapping[
        str,
        Any,
    ]

    def __post_init__(
        self,
    ) -> None:
        object.__setattr__(
            self,
            "attributes",
            MappingProxyType(
                dict(
                    self.attributes
                )
            ),
        )

        object.__setattr__(
            self,
            "message_attributes",
            MappingProxyType(
                dict(
                    self.message_attributes
                )
            ),
        )


class SQSEventConsumer:
    """
    Application-level Amazon SQS adapter for the
    Ingestion worker.

    Business event parsing remains separate in
    IngestionEventParser.
    """

    def __init__(
        self,
        *,
        queue_url: str,
        wait_time_seconds: int = 20,
        visibility_timeout_seconds: int = 900,
        maximum_messages: int = 1,
        sqs_service: SQSService | None = None,
    ):
        self.queue_url = (
            self._normalize_required_string(
                value=queue_url,
                field_name="queue_url",
            )
        )

        self._validate_integer_range(
            value=wait_time_seconds,
            field_name="wait_time_seconds",
            minimum=0,
            maximum=20,
        )

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

        self._validate_integer_range(
            value=maximum_messages,
            field_name="maximum_messages",
            minimum=1,
            maximum=10,
        )

        if (
            sqs_service is not None
            and not isinstance(
                sqs_service,
                SQSService,
            )
        ):
            raise TypeError(
                "sqs_service must be an "
                "SQSService or None."
            )

        self.wait_time_seconds = (
            wait_time_seconds
        )

        self.visibility_timeout_seconds = (
            visibility_timeout_seconds
        )

        self.maximum_messages = (
            maximum_messages
        )

        self.sqs_service = (
            sqs_service
            or SQSService()
        )

    def receive_messages(
        self,
    ) -> tuple[SQSMessage, ...]:
        """
        Long-poll the configured queue.

        An empty tuple is a valid result when no
        messages are currently available.
        """
        try:
            response = (
                self.sqs_service
                .receive_messages(
                    queue_url=self.queue_url,
                    maximum_messages=(
                        self.maximum_messages
                    ),
                    wait_time_seconds=(
                        self.wait_time_seconds
                    ),
                    visibility_timeout_seconds=(
                        self
                        .visibility_timeout_seconds
                    ),
                    attribute_names=["All"],
                    message_attribute_names=[
                        "All",
                    ],
                )
            )
        except (
            BotoCoreError,
            ClientError,
        ) as exception:
            raise SQSReceiveError(
                "Messages could not be received "
                "from the Ingestion queue."
            ) from exception

        if not isinstance(
            response,
            dict,
        ):
            raise SQSReceiveError(
                "Amazon SQS receive response must "
                "be a dictionary."
            )

        raw_messages = response.get(
            "Messages",
            [],
        )

        if not isinstance(
            raw_messages,
            list,
        ):
            raise SQSReceiveError(
                "Amazon SQS Messages response must "
                "be a list."
            )

        messages = tuple(
            self._parse_message(
                raw_message
            )
            for raw_message
            in raw_messages
        )

        if messages:
            logger.info(
                "Received Ingestion message(s).",
                extra={
                    "event": (
                        "ingestion_messages_"
                        "received"
                    ),
                    "message_count": len(
                        messages
                    ),
                },
            )

        return messages

    def acknowledge_message(
        self,
        message: SQSMessage,
    ) -> None:
        """
        Delete one successfully completed message.
        """
        self._validate_message(
            message
        )

        try:
            self.sqs_service.delete_message(
                queue_url=self.queue_url,
                receipt_handle=(
                    message.receipt_handle
                ),
            )
        except (
            BotoCoreError,
            ClientError,
        ) as exception:
            raise SQSDeleteError(
                "Completed Ingestion message could "
                "not be acknowledged."
            ) from exception

        logger.info(
            "Ingestion message acknowledged.",
            extra={
                "event": (
                    "ingestion_message_"
                    "acknowledged"
                ),
                "message_id": (
                    message.message_id
                ),
                "approximate_receive_count": (
                    message
                    .approximate_receive_count
                ),
            },
        )

    def change_message_visibility(
        self,
        message: SQSMessage,
        *,
        visibility_timeout_seconds: int,
    ) -> None:
        """
        Change one received message's visibility
        timeout.
        """
        self._validate_message(
            message
        )

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

        try:
            (
                self.sqs_service
                .change_message_visibility(
                    queue_url=self.queue_url,
                    receipt_handle=(
                        message.receipt_handle
                    ),
                    visibility_timeout=(
                        visibility_timeout_seconds
                    ),
                )
            )
        except (
            BotoCoreError,
            ClientError,
        ) as exception:
            raise SQSVisibilityError(
                "Ingestion message visibility "
                "could not be changed."
            ) from exception

    def release_message(
        self,
        message: SQSMessage,
    ) -> None:
        """
        Immediately return an unstarted message to
        the queue during graceful shutdown.
        """
        self.change_message_visibility(
            message,
            visibility_timeout_seconds=0,
        )

        logger.info(
            "Released unstarted Ingestion message.",
            extra={
                "event": (
                    "ingestion_unstarted_message_"
                    "released"
                ),
                "message_id": (
                    message.message_id
                ),
                "approximate_receive_count": (
                    message
                    .approximate_receive_count
                ),
            },
        )

    def _parse_message(
        self,
        raw_message: Any,
    ) -> SQSMessage:
        if not isinstance(
            raw_message,
            dict,
        ):
            raise SQSReceiveError(
                "Amazon SQS message must be a "
                "dictionary."
            )

        message_id = (
            self._read_required_string(
                payload=raw_message,
                field_name="MessageId",
            )
        )

        receipt_handle = (
            self._read_required_string(
                payload=raw_message,
                field_name="ReceiptHandle",
            )
        )

        body = self._read_required_string(
            payload=raw_message,
            field_name="Body",
            allow_blank=True,
        )

        attributes_value = raw_message.get(
            "Attributes",
            {},
        )

        if not isinstance(
            attributes_value,
            dict,
        ):
            raise SQSReceiveError(
                "Amazon SQS message Attributes "
                "must be a dictionary."
            )

        attributes = {
            str(key): str(value)
            for (
                key,
                value,
            )
            in attributes_value.items()
        }

        message_attributes = (
            raw_message.get(
                "MessageAttributes",
                {},
            )
        )

        if not isinstance(
            message_attributes,
            dict,
        ):
            raise SQSReceiveError(
                "Amazon SQS MessageAttributes "
                "must be a dictionary."
            )

        receive_count = (
            self._parse_integer_attribute(
                value=attributes.get(
                    "ApproximateReceiveCount",
                    "1",
                ),
                field_name=(
                    "ApproximateReceiveCount"
                ),
                minimum=1,
            )
        )

        sent_timestamp = None

        if "SentTimestamp" in attributes:
            sent_timestamp = (
                self._parse_integer_attribute(
                    value=attributes[
                        "SentTimestamp"
                    ],
                    field_name=(
                        "SentTimestamp"
                    ),
                    minimum=0,
                )
            )

        return SQSMessage(
            message_id=message_id,
            receipt_handle=receipt_handle,
            body=body,
            approximate_receive_count=(
                receive_count
            ),
            sent_timestamp_milliseconds=(
                sent_timestamp
            ),
            attributes=attributes,
            message_attributes=(
                message_attributes
            ),
        )

    @staticmethod
    def _validate_message(
        message: SQSMessage,
    ) -> None:
        if not isinstance(
            message,
            SQSMessage,
        ):
            raise TypeError(
                "message must be an SQSMessage."
            )

    @staticmethod
    def _read_required_string(
        *,
        payload: dict[str, Any],
        field_name: str,
        allow_blank: bool = False,
    ) -> str:
        value = payload.get(
            field_name
        )

        if not isinstance(
            value,
            str,
        ):
            raise SQSReceiveError(
                "Amazon SQS field "
                f"'{field_name}' must be a string."
            )

        if (
            not allow_blank
            and not value.strip()
        ):
            raise SQSReceiveError(
                "Amazon SQS field "
                f"'{field_name}' must not be blank."
            )

        return value

    @staticmethod
    def _parse_integer_attribute(
        *,
        value: str,
        field_name: str,
        minimum: int,
    ) -> int:
        try:
            parsed_value = int(
                value
            )
        except (
            TypeError,
            ValueError,
        ) as exception:
            raise SQSReceiveError(
                "Amazon SQS attribute "
                f"'{field_name}' must contain an "
                "integer."
            ) from exception

        if parsed_value < minimum:
            raise SQSReceiveError(
                "Amazon SQS attribute "
                f"'{field_name}' must be at least "
                f"{minimum}."
            )

        return parsed_value

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