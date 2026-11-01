import pytest
from exceptions.processing import RetryableIngestionError
from services.provider_error_classifier import raise_classified_provider_error
pytestmark=[pytest.mark.resilience,pytest.mark.local]

def test_timeout_is_classified_retryable():
    with pytest.raises(RetryableIngestionError):
        raise_classified_provider_error(RuntimeError("request timeout"),operation="embedding")
