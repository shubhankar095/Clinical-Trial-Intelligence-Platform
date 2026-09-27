import pytest


pytestmark = pytest.mark.aws


def test_upload_scales_worker_processes_message_and_drains_queue(
    data_dir,
    aws_deployment,
    aws_test_helpers,
):
    aws_test_helpers.wait_for_queue_to_drain(
        timeout_seconds=180
    )

    aws_test_helpers.wait_for_dlq_to_be_empty(
        timeout_seconds=60
    )

    (
        aws_test_helpers
        .wait_for_service_to_scale_to_zero(
            timeout_seconds=1800
        )
    )

    (
        source_key,
        source_version_id,
        _,
    ) = (
        aws_test_helpers
        .upload_document(
            data_dir
            / "minimal_text.pdf"
        )
    )

    scaled_counts = (
        aws_test_helpers
        .wait_for_service_capacity(
            minimum_desired=1,
            timeout_seconds=900,
        )
    )

    assert (
        scaled_counts["desired"] >= 1
        or scaled_counts["running"] >= 1
    )

    (
        document_id,
        canonical_key,
        payload,
    ) = (
        aws_test_helpers
        .wait_for_canonical_document(
            source_key=source_key,
            source_version_id=(
                source_version_id
            ),
            timeout_seconds=900,
        )
    )

    assert (
        payload["processing_status"]
        == "SUCCESS"
    )

    assert (
        payload["document_id"]
        == document_id
    )

    assert (
        payload["source_key"]
        == source_key
    )

    assert (
        payload["source_version_id"]
        == source_version_id
    )

    assert (
        payload[
            "processing_schema_version"
        ]
        == (
            aws_deployment
            .processing_schema_version
        )
    )

    assert (
        canonical_key
        == (
            "canonical-documents/"
            f"{document_id}/"
            "extracted-document.json"
        )
    )

    (
        manifest_key,
        manifest,
    ) = (
        aws_test_helpers
        .wait_for_success_manifest(
            document_id=document_id,
            timeout_seconds=300,
        )
    )

    assert (
        manifest_key
        == (
            "canonical-documents/"
            f"{document_id}/"
            "_SUCCESS.json"
        )
    )

    assert (
        manifest["processing_status"]
        == "SUCCESS"
    )

    assert (
        manifest["canonical_key"]
        == canonical_key
    )

    registry_item = (
        aws_test_helpers
        .wait_for_registry_status(
            document_id=document_id,
            expected_status="COMPLETED",
            timeout_seconds=300,
        )
    )

    assert (
        registry_item["status"]["S"]
        == "COMPLETED"
    )

    assert (
        registry_item[
            "source_version_id"
        ]["S"]
        == source_version_id
    )

    assert (
        "lease_expires_at"
        not in registry_item
    )

    aws_test_helpers.wait_for_queue_to_drain(
        timeout_seconds=180
    )

    dlq_counts = (
        aws_test_helpers.queue_counts(
            aws_test_helpers.dlq_url()
        )
    )

    assert dlq_counts == (
        0,
        0,
    )

    final_counts = (
        aws_test_helpers
        .wait_for_service_to_scale_to_zero(
            timeout_seconds=1800
        )
    )

    assert (
        final_counts["status"]
        == "ACTIVE"
    )

    assert final_counts["desired"] == 0
    assert final_counts["running"] == 0
    assert final_counts["pending"] == 0