from __future__ import annotations
import pytest
from repositories.processing_registry import ClaimDisposition, ProcessingRegistry
pytestmark=[pytest.mark.integration,pytest.mark.local]

def registry(resources, now=1_700_000_000):
    return ProcessingRegistry(table_name=resources["table"], lease_seconds=900,
        record_ttl_days=90, dynamodb_service=resources["dynamodb_service"], clock=lambda: now)

def acquire(value, ingestion_id="ingestion-1"):
    return value.acquire_claim(ingestion_id=ingestion_id, document_id="d"*64,
        ingestion_profile_id="p"*64, manifest_bucket="canonical",
        manifest_key=f"canonical-documents/{'d'*64}/_SUCCESS.json", manifest_version_id=None)

def test_real_dynamodb_accepts_claim_expression_and_stores_ttl(local_resources):
    result=acquire(registry(local_resources))
    assert result.disposition is ClaimDisposition.ACQUIRED
    item=local_resources["dynamodb_client"].get_item(TableName=local_resources["table"],
        Key={"ingestion_id":{"S":"ingestion-1"}},ConsistentRead=True)["Item"]
    assert item["status"]["S"] == "PROCESSING"
    assert item["ttl"]["N"] == str(1_700_000_000 + 90*86_400)

def test_duplicate_active_claim_is_unavailable(local_resources):
    value=registry(local_resources)
    assert acquire(value,"ingestion-2").disposition is ClaimDisposition.ACQUIRED
    assert acquire(value,"ingestion-2").disposition is ClaimDisposition.UNAVAILABLE

def test_expired_claim_is_reacquired(local_resources):
    assert acquire(registry(local_resources),"ingestion-3").claim.attempt_count == 1
    result=acquire(registry(local_resources,1_700_000_901),"ingestion-3")
    assert result.disposition is ClaimDisposition.ACQUIRED
    assert result.claim.attempt_count == 2

def test_claim_can_be_renewed_completed_and_recognized(local_resources):
    value=registry(local_resources); result=acquire(value,"ingestion-4"); claim=result.claim
    assert value.renew_claim(claim)==1_700_000_900
    value.mark_completed(claim,index_destination="opensearch://index",index_record_count=1,
        chunk_count=1,success_manifest_bucket=local_resources["bucket"],
        success_manifest_key="ingestion-results/ingestion-4/_SUCCESS.json")
    assert acquire(value,"ingestion-4").disposition is ClaimDisposition.COMPLETED
