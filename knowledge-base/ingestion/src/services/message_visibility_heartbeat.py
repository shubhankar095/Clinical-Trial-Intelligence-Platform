import threading

from ingestion_events.sqs_event_consumer import SQSMessage, SQSEventConsumer
from exceptions.processing import RetryableIngestionError
from utils.logger import get_logger

logger = get_logger(__name__)


class MessageVisibilityHeartbeat:
    """Periodically extend SQS visibility while one message is being processed."""

    def __init__(
        self,
        *,
        consumer: SQSEventConsumer,
        message: SQSMessage,
        heartbeat_seconds: int,
        extension_seconds: int,
    ):
        if not isinstance(consumer, SQSEventConsumer):
            raise TypeError("consumer must be an SQSEventConsumer.")
        if not isinstance(message, SQSMessage):
            raise TypeError("message must be an SQSMessage.")
        self._positive(heartbeat_seconds, "heartbeat_seconds")
        self._positive(extension_seconds, "extension_seconds")
        if extension_seconds > 43_200:
            raise ValueError("extension_seconds must not exceed 43200.")
        if heartbeat_seconds >= extension_seconds:
            raise ValueError("heartbeat_seconds must be less than extension_seconds.")

        self.consumer = consumer
        self.message = message
        self.heartbeat_seconds = heartbeat_seconds
        self.extension_seconds = extension_seconds
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._failure_exception: BaseException | None = None
        self._stopped = False

    @property
    def is_running(self) -> bool:
        with self._lock:
            return bool(self._thread and self._thread.is_alive())

    @property
    def heartbeat_failed(self) -> bool:
        with self._lock:
            return self._failure_exception is not None

    @property
    def failure_exception(self) -> BaseException | None:
        with self._lock:
            return self._failure_exception

    def start(self) -> None:
        with self._lock:
            if self._thread is not None:
                raise RuntimeError("Message visibility heartbeat has already been started.")
            self._thread = threading.Thread(
                target=self._run,
                name="ingestion-message-visibility-heartbeat",
                daemon=True,
            )
            thread = self._thread
        thread.start()
        logger.info(
            "Ingestion SQS visibility heartbeat started.",
            extra={
                "event": "ingestion_message_visibility_heartbeat_started",
                "message_id": self.message.message_id,
                "heartbeat_seconds": self.heartbeat_seconds,
                "extension_seconds": self.extension_seconds,
            },
        )

    def stop(self) -> None:
        """Idempotently stop and fully join the heartbeat before message finalization."""
        with self._lock:
            thread = self._thread
            if thread is None or self._stopped:
                return
        self._stop_event.set()
        if thread is not threading.current_thread():
            thread.join(timeout=self.heartbeat_seconds + 5)
        if thread.is_alive():
            raise RetryableIngestionError(
                "Message visibility heartbeat thread did not stop."
            )
        with self._lock:
            self._stopped = True
        logger.info(
            "Ingestion SQS visibility heartbeat stopped.",
            extra={
                "event": "ingestion_message_visibility_heartbeat_stopped",
                "message_id": self.message.message_id,
                "heartbeat_failed": self.heartbeat_failed,
            },
        )

    def raise_for_failure(self) -> None:
        exception = self.failure_exception
        if exception is not None:
            raise RetryableIngestionError(
                "The Ingestion SQS visibility heartbeat failed."
            ) from exception

    def _run(self) -> None:
        while not self._stop_event.wait(self.heartbeat_seconds):
            try:
                self.consumer.change_message_visibility(
                    self.message,
                    visibility_timeout_seconds=self.extension_seconds,
                )
            except BaseException as exception:
                with self._lock:
                    self._failure_exception = exception
                logger.exception(
                    "Ingestion SQS visibility heartbeat failed.",
                    extra={
                        "event": "ingestion_message_visibility_heartbeat_failed",
                        "message_id": self.message.message_id,
                    },
                )
                self._stop_event.set()
                return

    @staticmethod
    def _positive(value: int, name: str) -> None:
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(f"{name} must be an integer.")
        if value <= 0:
            raise ValueError(f"{name} must be greater than zero.")
