import signal
import threading

from types import FrameType
from typing import Any

from utils.logger import get_logger


logger = get_logger(__name__)


class ShutdownController:
    """
    Coordinate graceful Ingestion worker shutdown.

    Signal handlers only set a thread-safe flag. The
    worker performs all queue and storage actions in
    normal execution context.
    """

    SUPPORTED_SIGNALS = (
        signal.SIGTERM,
        signal.SIGINT,
    )

    def __init__(
        self,
    ):
        self._shutdown_event = (
            threading.Event()
        )

        self._lock = threading.Lock()

        self._signal_number: (
            int
            | None
        ) = None

        self._handlers_installed = False

        self._previous_handlers: dict[
            signal.Signals,
            Any,
        ] = {}

    @property
    def shutdown_requested(
        self,
    ) -> bool:
        return (
            self._shutdown_event
            .is_set()
        )

    @property
    def signal_number(
        self,
    ) -> int | None:
        with self._lock:
            return self._signal_number

    def install_signal_handlers(
        self,
    ) -> None:
        """
        Install SIGTERM and SIGINT handlers.

        Python only permits this from the main
        thread.
        """
        if (
            threading.current_thread()
            is not threading.main_thread()
        ):
            raise RuntimeError(
                "Signal handlers must be installed "
                "from the main thread."
            )

        with self._lock:
            if self._handlers_installed:
                return

            for signal_value in (
                self.SUPPORTED_SIGNALS
            ):
                self._previous_handlers[
                    signal_value
                ] = signal.getsignal(
                    signal_value
                )

                signal.signal(
                    signal_value,
                    self._handle_signal,
                )

            self._handlers_installed = True

        logger.info(
            "Ingestion shutdown signal handlers "
            "installed.",
            extra={
                "event": (
                    "ingestion_shutdown_handlers_"
                    "installed"
                ),
            },
        )

    def restore_signal_handlers(
        self,
    ) -> None:
        """
        Restore the previously configured handlers.
        """
        if (
            threading.current_thread()
            is not threading.main_thread()
        ):
            raise RuntimeError(
                "Signal handlers must be restored "
                "from the main thread."
            )

        with self._lock:
            if not self._handlers_installed:
                return

            previous_handlers = dict(
                self._previous_handlers
            )

            self._previous_handlers.clear()
            self._handlers_installed = False

        for (
            signal_value,
            previous_handler,
        ) in previous_handlers.items():
            signal.signal(
                signal_value,
                previous_handler,
            )

    def request_shutdown(
        self,
        signal_number: int | None = None,
    ) -> None:
        """
        Request shutdown programmatically or from a
        signal handler.

        The operation is idempotent. The first signal
        number is retained.
        """
        first_request = False

        with self._lock:
            if not self._shutdown_event.is_set():
                first_request = True

                if signal_number is not None:
                    self._signal_number = int(
                        signal_number
                    )

                self._shutdown_event.set()

        if first_request:
            logger.warning(
                "Ingestion worker shutdown "
                "requested. The worker will stop "
                "receiving new messages after the "
                "current message completes.",
                extra={
                    "event": (
                        "ingestion_shutdown_"
                        "requested"
                    ),
                    "signal": signal_number,
                },
            )

    def wait(
        self,
        timeout: float | None = None,
    ) -> bool:
        """
        Wait for shutdown or for the optional timeout.

        Return True when shutdown was requested.
        """
        if (
            timeout is not None
            and timeout < 0
        ):
            raise ValueError(
                "timeout must be zero or greater."
            )

        return self._shutdown_event.wait(
            timeout
        )

    def _handle_signal(
        self,
        signal_number: int,
        frame: FrameType | None,
    ) -> None:
        del frame

        self.request_shutdown(
            signal_number=signal_number
        )