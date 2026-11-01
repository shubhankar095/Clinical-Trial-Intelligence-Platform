from datetime import datetime, timezone
import json
import pytest
from exceptions.extraction_manifest import ManifestNotFoundError
from models.ingestion_manifest import IngestionSuccessManifest
from models.storage_location import StorageLocation
from storage.s3_ingestion_manifest_store import S3IngestionManifestStore
from storage.s3_text_store import S3TextStore
pytestmark=[pytest.mark.integration,pytest.mark.local]

def test_s3_text_store_and_success_manifest(local_resources):
    bucket=local_resources["bucket"]
    local_resources["s3_client"].put_object(Bucket=bucket,Key="input.json",Body=b'{"ok":true}')
    assert S3TextStore(local_resources["s3_service"]).load_text(StorageLocation(bucket,"input.json")) == '{"ok":true}'
    manifest=IngestionSuccessManifest(event_type="INGESTION_COMPLETED",manifest_schema_version="ingestion-success-v1",
      processing_status="SUCCESS",document_id="d"*64,ingestion_id="i"*64,ingestion_profile_id="p"*64,
      processing_schema_version="extraction-v1",ingestion_schema_version="ingestion-v1",index_schema_version="v1",
      source_bucket="source",source_key="key",source_version_id="v1",canonical_bucket=bucket,canonical_key="input.json",
      canonical_version_id=None,canonical_sha256=None,index_destination="opensearch://index",index_record_count=1,
      chunk_count=1,embedding_provider="test",embedding_model_id="deterministic",embedding_dimensions=3,
      embedding_normalized=False,completed_at=datetime.now(timezone.utc))
    stored=S3IngestionManifestStore(bucket=bucket,s3_service=local_resources["s3_service"]).write_success(manifest)
    body=local_resources["s3_client"].get_object(Bucket=bucket,Key=stored.key)["Body"].read()
    assert json.loads(body)["processing_status"] == "SUCCESS"
    for key in (stored.key,"input.json"): local_resources["s3_client"].delete_object(Bucket=bucket,Key=key)

def test_missing_s3_object_is_translated(local_resources):
    with pytest.raises(ManifestNotFoundError):
      S3TextStore(local_resources["s3_service"]).load_text(StorageLocation(local_resources["bucket"],"missing"))
