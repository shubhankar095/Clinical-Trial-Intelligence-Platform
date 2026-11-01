import pytest
from exceptions.processing import RetryableIngestionError,PermanentIngestionError
from tests.fakes.controlled_failures import ControlledEmbeddingFailure,ControlledIndexFailure
pytestmark=[pytest.mark.resilience,pytest.mark.local]

def test_controlled_embedding_failure_is_deterministic():
    failure=ControlledEmbeddingFailure(RetryableIngestionError("temporary"))
    with pytest.raises(RetryableIngestionError): failure.embed(object())
    assert failure.calls==1

def test_controlled_index_failure_is_deterministic():
    failure=ControlledIndexFailure(PermanentIngestionError("invalid"))
    with pytest.raises(PermanentIngestionError): failure.index_records(ingestion_id="id",records=())
    assert failure.calls==1
