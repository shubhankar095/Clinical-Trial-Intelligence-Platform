from datetime import datetime,timezone
import pytest
from models.ingestion_manifest import IngestionSuccessManifest,IngestionFailureManifest
pytestmark=[pytest.mark.contract,pytest.mark.local]

def test_success_and_failure_manifests_serialize_contract_fields():
    now=datetime(2026,10,20,tzinfo=timezone.utc)
    success=IngestionSuccessManifest(event_type="INGESTION_COMPLETED",manifest_schema_version="ingestion-success-v1",processing_status="SUCCESS",document_id="a"*64,ingestion_id="b"*64,ingestion_profile_id="c"*64,processing_schema_version="extraction-v1",ingestion_schema_version="ingestion-v1",index_schema_version="v1",source_bucket="source",source_key="key",source_version_id="v1",canonical_bucket="canonical",canonical_key="doc.json",canonical_version_id=None,canonical_sha256=None,index_destination="opensearch://index",index_record_count=2,chunk_count=2,embedding_provider="test",embedding_model_id="model",embedding_dimensions=3,embedding_normalized=False,completed_at=now)
    failure=IngestionFailureManifest(event_type="INGESTION_FAILED",manifest_schema_version="ingestion-failure-v1",processing_status="FAILED",document_id="a"*64,ingestion_id="b"*64,ingestion_profile_id="c"*64,processing_schema_version="extraction-v1",ingestion_schema_version="ingestion-v1",manifest_bucket="bucket",manifest_key="key",manifest_version_id=None,error_type="PermanentIngestionError",error_message="invalid canonical document",failed_at=now)
    assert success.to_payload()["index_record_count"]==success.to_payload()["chunk_count"]
    assert failure.to_payload()["processing_status"]=="FAILED"
    assert success.to_payload()["completed_at"].endswith("+00:00")
