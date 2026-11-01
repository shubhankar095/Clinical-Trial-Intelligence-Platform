from typing import NoReturn

from botocore.exceptions import BotoCoreError, ClientError

from exceptions.processing import (
    IngestionConfigurationError,
    IngestionProcessingError,
    PermanentIngestionError,
    RetryableIngestionError,
)

RETRYABLE_HTTP_STATUS_CODES = frozenset({408, 425, 429, 500, 502, 503, 504})
CONFIGURATION_HTTP_STATUS_CODES = frozenset({401, 403})
PERMANENT_HTTP_STATUS_CODES = frozenset({400, 404, 405, 409, 413, 415, 422})

RETRYABLE_AWS_ERROR_CODES = frozenset({
    "InternalFailure",
    "InternalServerException",
    "ModelNotReadyException",
    "ModelTimeoutException",
    "PriorRequestNotComplete",
    "ProvisionedThroughputExceededException",
    "RequestLimitExceeded",
    "ServiceUnavailable",
    "ServiceUnavailableException",
    "SlowDown",
    "Throttling",
    "ThrottlingException",
    "TooManyRequestsException",
})

CONFIGURATION_AWS_ERROR_CODES = frozenset({
    "AccessDenied",
    "AccessDeniedException",
    "ExpiredToken",
    "ExpiredTokenException",
    "IncompleteSignature",
    "InvalidClientTokenId",
    "InvalidSignatureException",
    "MissingAuthenticationToken",
    "NotAuthorized",
    "NotAuthorizedException",
    "SignatureDoesNotMatch",
    "UnrecognizedClientException",
})

PERMANENT_AWS_ERROR_CODES = frozenset({
    "ResourceNotFoundException",
    "ValidationException",
})


def raise_classified_provider_error(
    exception: BaseException,
    *,
    operation: str,
) -> NoReturn:
    """Translate provider/transport exceptions into the Ingestion taxonomy."""
    if isinstance(exception, IngestionProcessingError):
        raise exception

    if isinstance(exception, ClientError):
        error = exception.response.get("Error", {})
        code = str(error.get("Code", ""))
        status = exception.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if code in CONFIGURATION_AWS_ERROR_CODES or status in CONFIGURATION_HTTP_STATUS_CODES:
            raise IngestionConfigurationError(
                f"{operation} failed because AWS authorization or credentials are invalid."
            ) from exception
        if code in RETRYABLE_AWS_ERROR_CODES or status in RETRYABLE_HTTP_STATUS_CODES:
            raise RetryableIngestionError(
                f"{operation} failed because the AWS service is temporarily unavailable."
            ) from exception
        if code in PERMANENT_AWS_ERROR_CODES or status in PERMANENT_HTTP_STATUS_CODES:
            raise PermanentIngestionError(
                f"{operation} was rejected by the AWS service."
            ) from exception
        raise RetryableIngestionError(
            f"{operation} failed with an unclassified AWS service error."
        ) from exception

    if isinstance(exception, BotoCoreError):
        raise RetryableIngestionError(
            f"{operation} failed because the AWS transport is temporarily unavailable."
        ) from exception

    status = _status_code(exception)
    if status in CONFIGURATION_HTTP_STATUS_CODES:
        raise IngestionConfigurationError(
            f"{operation} failed because provider authorization is invalid."
        ) from exception
    if status in RETRYABLE_HTTP_STATUS_CODES:
        raise RetryableIngestionError(
            f"{operation} failed because the provider is temporarily unavailable."
        ) from exception
    if status in PERMANENT_HTTP_STATUS_CODES:
        raise PermanentIngestionError(
            f"{operation} was permanently rejected by the provider."
        ) from exception

    name = type(exception).__name__.lower()
    message = str(exception).lower()
    if any(token in name or token in message for token in (
        "timeout", "connection", "temporarily unavailable", "throttl", "too many request"
    )):
        raise RetryableIngestionError(
            f"{operation} failed because of a temporary transport or throttling condition."
        ) from exception
    if any(token in message for token in (
        "unauthorized", "forbidden", "access denied", "signature", "credential"
    )):
        raise IngestionConfigurationError(
            f"{operation} failed because provider authorization or configuration is invalid."
        ) from exception

    raise RetryableIngestionError(
        f"{operation} failed with an unclassified provider error."
    ) from exception


def _status_code(exception: BaseException) -> int | None:
    for attribute in ("status_code", "status"):
        value = getattr(exception, attribute, None)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    info = getattr(exception, "info", None)
    if isinstance(info, dict):
        value = info.get("status")
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return None
