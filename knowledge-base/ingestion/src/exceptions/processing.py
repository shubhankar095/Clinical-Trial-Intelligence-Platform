class IngestionProcessingError(RuntimeError):
    """Base exception for classified Ingestion processing failures."""


class RetryableIngestionError(IngestionProcessingError):
    """A temporary dependency or transport failure that SQS should retry."""


class PermanentIngestionError(IngestionProcessingError):
    """A document-specific failure that will not succeed with unchanged input."""


class IngestionConfigurationError(IngestionProcessingError):
    """A deployment, credential, permission, or endpoint configuration failure."""


class ProcessingOwnershipLostError(RetryableIngestionError):
    """The current worker no longer owns the distributed processing claim."""
