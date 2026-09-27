import threading

from utils.logger import get_logger


logger = get_logger(__name__)


class MessageVisibilityHeartbeat:
    """
    Periodically extend the visibility lease for
    one actively processed SQS message.
    """

    def __init__(
        self,
        consumer,
        receipt_handle: str,
        heartbeat_seconds: int,
        extension_seconds: int,
    ):
        self.consumer = consumer
        self.receipt_handle = (
            receipt_handle
        )

        self.heartbeat_seconds = (
            heartbeat_seconds
        )

        self.extension_seconds = (
            extension_seconds
        )

        self._stop_event = (
            threading.Event()
        )

        self._thread = None
        self._failed = False

    @property
    def failed(self) -> bool:
        return self._failed

    def start(self) -> None:
        if (
            self._thread is not None
            and self._thread.is_alive()
        ):
            return

        self._thread = threading.Thread(
            target=self._run,
            name=(
                "sqs-visibility-heartbeat"
            ),
            daemon=True,
        )

        self._thread.start()

        logger.info(
            "SQS visibility heartbeat started.",
            extra={
                "event": (
                    "message_visibility_"
                    "heartbeat_started"
                ),
                "heartbeat_seconds": (
                    self.heartbeat_seconds
                ),
                "extension_seconds": (
                    self.extension_seconds
                ),
            },
        )

    def _run(self) -> None:
        while not self._stop_event.wait(
            self.heartbeat_seconds
        ):
            try:
                (
                    self.consumer
                    .change_message_visibility(
                        receipt_handle=(
                            self.receipt_handle
                        ),
                        visibility_timeout=(
                            self.extension_seconds
                        ),
                    )
                )

                logger.info(
                    "SQS message visibility "
                    "lease extended.",
                    extra={
                        "event": (
                            "message_visibility_"
                            "extended"
                        ),
                        "extension_seconds": (
                            self.extension_seconds
                        ),
                    },
                )

            except Exception:
                self._failed = True

                logger.exception(
                    "Failed to extend SQS "
                    "message visibility.",
                    extra={
                        "event": (
                            "message_visibility_"
                            "extension_failed"
                        ),
                    },
                )

                return

    def stop(self) -> None:
        self._stop_event.set()

        if self._thread is not None:
            self._thread.join(
                timeout=5,
            )

        logger.info(
            "SQS visibility heartbeat stopped.",
            extra={
                "event": (
                    "message_visibility_"
                    "heartbeat_stopped"
                ),
                "heartbeat_failed": (
                    self._failed
                ),
            },
        )