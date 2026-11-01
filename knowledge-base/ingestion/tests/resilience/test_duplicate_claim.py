import pytest
pytestmark=[pytest.mark.resilience,pytest.mark.local]

def test_duplicate_claim_is_rejected_by_stateful_test_double():
    claims=set()
    def acquire(value):
        if value in claims:return False
        claims.add(value);return True
    assert acquire("generation") is True
    assert acquire("generation") is False
