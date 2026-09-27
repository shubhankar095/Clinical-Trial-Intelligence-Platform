class ProcessingClaimUnavailableError(
    RuntimeError
):
    """
    Another worker currently owns an active
    processing claim for the document.
    """


class ProcessingClaimLostError(
    RuntimeError
):
    """
    The worker no longer owns the processing
    claim it previously acquired.
    """