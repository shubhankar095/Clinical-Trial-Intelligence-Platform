import threading

from exceptions.processing import ProcessingOwnershipLostError, RetryableIngestionError
from repositories.processing_registry import ProcessingClaim, ProcessingClaimLostError, ProcessingRegistry
from utils.logger import get_logger

logger = get_logger(__name__)


class ProcessingClaimHeartbeat:
    """Renew a DynamoDB processing claim until explicitly stopped."""

    def __init__(self, *, registry: ProcessingRegistry, claim: ProcessingClaim, heartbeat_seconds: int):
        if not isinstance(registry, ProcessingRegistry):
            raise TypeError("registry must be a ProcessingRegistry.")
        if not isinstance(claim, ProcessingClaim):
            raise TypeError("claim must be a ProcessingClaim.")
        if not isinstance(heartbeat_seconds, int) or isinstance(heartbeat_seconds, bool):
            raise TypeError("heartbeat_seconds must be an integer.")
        if heartbeat_seconds <= 0 or heartbeat_seconds >= registry.lease_seconds:
            raise ValueError("heartbeat_seconds must be positive and shorter than the lease.")
        self.registry = registry
        self._claim = claim
        self.heartbeat_seconds = heartbeat_seconds
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._failure_exception: BaseException | None = None
        self._stopped = False

    @property
    def claim(self) -> ProcessingClaim:
        with self._lock:
            return self._claim

    @property
    def is_running(self) -> bool:
        with self._lock:
            return bool(self._thread and self._thread.is_alive())

    @property
    def failure_exception(self) -> BaseException | None:
        with self._lock:
            return self._failure_exception

    def start(self) -> None:
        with self._lock:
            if self._thread is not None:
                raise RuntimeError("Processing claim heartbeat has already been started.")
            self._thread = threading.Thread(
                target=self._run,
                name="ingestion-processing-claim-heartbeat",
                daemon=True,
            )
            thread = self._thread
        thread.start()

    def stop(self) -> None:
        """Idempotently stop and fully join before COMPLETED or FAILED is written."""
        with self._lock:
            thread = self._thread
            if thread is None or self._stopped:
                return
        self._stop_event.set()
        if thread is not threading.current_thread():
            thread.join(timeout=self.heartbeat_seconds + 5)
        if thread.is_alive():
            raise RetryableIngestionError(
                "Processing claim heartbeat thread did not stop."
            )
        with self._lock:
            self._stopped = True

    def raise_for_failure(self) -> None:
        exception = self.failure_exception
        if exception is None:
            return
        if isinstance(exception, ProcessingClaimLostError):
            raise ProcessingOwnershipLostError(
                "The Ingestion processing claim was lost during processing."
            ) from exception
        raise RetryableIngestionError("The Ingestion processing claim heartbeat failed.") from exception

    def _run(self) -> None:
        while not self._stop_event.wait(self.heartbeat_seconds):
            try:
                renewed_expiry = self.registry.renew_claim(self.claim)
                current = self.claim
                renewed = ProcessingClaim(
                    ingestion_id=current.ingestion_id,
                    owner_token=current.owner_token,
                    attempt_count=current.attempt_count,
                    claimed_at=current.claimed_at,
                    lease_expires_at=renewed_expiry,
                )
                with self._lock:
                    self._claim = renewed
            except BaseException as exception:
                with self._lock:
                    self._failure_exception = exception
                logger.exception(
                    "Ingestion processing claim heartbeat failed.",
                    extra={
                        "event": "ingestion_processing_claim_heartbeat_failed",
                        "ingestion_id": self.claim.ingestion_id,
                        "claim_lost": isinstance(exception, ProcessingClaimLostError),
                    },
                )
                self._stop_event.set()
                return