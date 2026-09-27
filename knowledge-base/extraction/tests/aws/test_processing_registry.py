import time

import pytest


pytestmark = pytest.mark.aws


def test_successful_processing_creates_completed_registry_record(
    data_dir,
    aws_deployment,
    aws_test_helpers,
):
    result = (
        aws_test_helpers
        .process_document(
            data_dir
            / "minimal_text.pdf"
        )
    )

    item = result["registry_item"]

    assert (
        item["document_id"]["S"]
        == result["document_id"]
    )

    assert (
        item["status"]["S"]
        == "COMPLETED"
    )

    assert (
        item["source_bucket"]["S"]
        == aws_deployment.raw_bucket
    )

    assert (
        item["source_key"]["S"]
        == result["source_key"]
    )

    assert (
        item["source_version_id"]["S"]
        == result["source_version_id"]
    )

    assert (
        item[
            "processing_schema_version"
        ]["S"]
        == (
            aws_deployment
            .processing_schema_version
        )
    )

    assert (
        item["canonical_key"]["S"]
        == result["canonical_key"]
    )

    assert "claimed_at" in item
    assert "updated_at" in item
    assert "completed_at" in item
    assert "ttl" in item
    assert "owner_token" in item

    assert "lease_expires_at" not in item

    claimed_at = int(
        item["claimed_at"]["N"]
    )

    updated_at = int(
        item["updated_at"]["N"]
    )

    completed_at = int(
        item["completed_at"]["N"]
    )

    ttl = int(
        item["ttl"]["N"]
    )

    assert claimed_at > 0

    assert (
        updated_at
        >= claimed_at
    )

    assert (
        completed_at
        >= claimed_at
    )

    assert ttl > completed_at

    assert ttl > int(
        time.time()
    )


def test_registry_record_matches_success_manifest(
    data_dir,
    aws_deployment,
    aws_test_helpers,
):
    result = (
        aws_test_helpers
        .process_document(
            data_dir
            / "table_document.pdf"
        )
    )

    item = result["registry_item"]
    manifest = result["manifest"]
    payload = result["payload"]

    assert (
        item["document_id"]["S"]
        == manifest["document_id"]
        == payload["document_id"]
    )

    assert (
        item["source_bucket"]["S"]
        == manifest["source_bucket"]
        == payload["source_bucket"]
        == aws_deployment.raw_bucket
    )

    assert (
        item["source_key"]["S"]
        == manifest["source_key"]
        == payload["source_key"]
    )

    assert (
        item["source_version_id"]["S"]
        == manifest[
            "source_version_id"
        ]
        == payload[
            "source_version_id"
        ]
    )

    assert (
        item[
            "processing_schema_version"
        ]["S"]
        == manifest[
            "processing_schema_version"
        ]
        == payload[
            "processing_schema_version"
        ]
        == (
            aws_deployment
            .processing_schema_version
        )
    )

    assert (
        item["canonical_key"]["S"]
        == manifest["canonical_key"]
        == payload["canonical_key"]
    )

    assert (
        item["status"]["S"]
        == "COMPLETED"
    )

    assert (
        manifest["processing_status"]
        == "SUCCESS"
    )

    assert (
        payload["processing_status"]
        == "SUCCESS"
    )

    assert (
        "lease_expires_at"
        not in item
    )