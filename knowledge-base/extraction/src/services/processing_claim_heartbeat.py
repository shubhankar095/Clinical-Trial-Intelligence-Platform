import threading

from exceptions.processing_claim import (
    ProcessingClaimLostError,
)
from utils.logger import get_logger


logger = get_logger(__name__)


class ProcessingClaimHeartbeat:
    """
    Periodically renew a DynamoDB processing
    claim while document processing is active.
    """

    def __init__(
        self,
        processing_registry,
        claim,
        heartbeat_seconds: int,
    ):
        if heartbeat_seconds <= 0:
            raise ValueError(
                "Claim heartbeat interval must "
                "be greater than zero."
            )

        self.processing_registry = (
            processing_registry
        )
        self.claim = claim
        self.heartbeat_seconds = (
            heartbeat_seconds
        )

        self._stop_event = threading.Event()
        self._thread = None
        self._failure = None
        self._stopped = False

    @property
    def failed(self) -> bool:
        return self._failure is not None

    @property
    def failure(self):
        return self._failure

    def start(self) -> None:
        if (
            self._thread is not None
            and self._thread.is_alive()
        ):
            return

        self._thread = threading.Thread(
            target=self._run,
            name=(
                "processing-claim-heartbeat"
            ),
            daemon=True,
        )

        self._thread.start()

        logger.info(
            "Processing claim heartbeat started.",
            extra={
                "event": (
                    "processing_claim_heartbeat_"
                    "started"
                ),
                "document_id": (
                    self.claim.document_id
                ),
                "heartbeat_seconds": (
                    self.heartbeat_seconds
                ),
            },
        )

    def _run(self) -> None:
        while not self._stop_event.wait(
            self.heartbeat_seconds
        ):
            try:
                self.claim = (
                    self.processing_registry
                    .renew(
                        self.claim
                    )
                )

            except Exception as exception:
                self._failure = exception

                logger.exception(
                    "Processing claim heartbeat "
                    "failed.",
                    extra={
                        "event": (
                            "processing_claim_"
                            "heartbeat_failed"
                        ),
                        "document_id": (
                            self.claim.document_id
                        ),
                        "ownership_lost": (
                            isinstance(
                                exception,
                                ProcessingClaimLostError,
                            )
                        ),
                    },
                )

                return

    def raise_if_failed(self) -> None:
        if self._failure is None:
            return

        if isinstance(
            self._failure,
            ProcessingClaimLostError,
        ):
            raise ProcessingClaimLostError(
                "Processing claim ownership was "
                "lost during document processing."
            ) from self._failure

        raise RuntimeError(
            "Processing claim renewal failed "
            "during document processing."
        ) from self._failure

    def stop(self) -> None:
        if self._stopped:
            return

        self._stopped = True
        self._stop_event.set()

        if self._thread is not None:
            self._thread.join(
                timeout=10,
            )

            if self._thread.is_alive():
                self._failure = RuntimeError(
                    "Processing claim heartbeat "
                    "did not stop cleanly."
                )

        logger.info(
            "Processing claim heartbeat stopped.",
            extra={
                "event": (
                    "processing_claim_heartbeat_"
                    "stopped"
                ),
                "document_id": (
                    self.claim.document_id
                ),
                "heartbeat_failed": (
                    self.failed
                ),
            },
        )