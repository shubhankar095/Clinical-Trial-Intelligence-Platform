import json

import pytest


pytestmark = pytest.mark.aws


def _find_matching_canonical_documents(
    *,
    aws_deployment,
    aws_test_helpers,
    s3_client,
    source_key,
    source_version_id,
):
    paginator = (
        s3_client
        .get_paginator(
            "list_objects_v2"
        )
    )

    matches = []

    for page in paginator.paginate(
        Bucket=(
            aws_deployment
            .canonical_bucket
        ),
        Prefix=(
            "canonical-documents/"
        ),
    ):
        for item in page.get(
            "Contents",
            [],
        ):
            key = item["Key"]

            if not key.endswith(
                "extracted-document.json"
            ):
                continue

            payload = (
                aws_test_helpers
                .load_json_object(
                    bucket=(
                        aws_deployment
                        .canonical_bucket
                    ),
                    key=key,
                )
            )

            if (
                payload.get(
                    "source_key"
                )
                == source_key
                and payload.get(
                    "source_version_id"
                )
                == source_version_id
            ):
                matches.append(
                    {
                        "key": key,
                        "payload": payload,
                    }
                )

    return matches


def test_duplicate_event_for_same_version_is_idempotent(
    data_dir,
    aws_deployment,
    aws_test_helpers,
    s3_client,
):
    result = (
        aws_test_helpers
        .process_document(
            data_dir
            / "minimal_text.pdf"
        )
    )

    original_payload = (
        result["payload"]
    )

    original_manifest = (
        result["manifest"]
    )

    message_id = (
        aws_test_helpers
        .send_duplicate_s3_event(
            source_key=(
                result["source_key"]
            ),
            source_version_id=(
                result[
                    "source_version_id"
                ]
            ),
        )
    )

    assert message_id

    aws_test_helpers.wait_for_queue_to_drain(
        timeout_seconds=300
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

    canonical_payload = (
        aws_test_helpers
        .load_json_object(
            bucket=(
                aws_deployment
                .canonical_bucket
            ),
            key=(
                result["canonical_key"]
            ),
        )
    )

    manifest = (
        aws_test_helpers
        .load_json_object(
            bucket=(
                aws_deployment
                .canonical_bucket
            ),
            key=(
                result["manifest_key"]
            ),
        )
    )

    assert (
        canonical_payload["document_id"]
        == result["document_id"]
    )

    assert (
        canonical_payload[
            "source_version_id"
        ]
        == result["source_version_id"]
    )

    assert (
        canonical_payload[
            "canonical_key"
        ]
        == result["canonical_key"]
    )

    assert (
        manifest["document_id"]
        == result["document_id"]
    )

    assert (
        manifest["canonical_key"]
        == result["canonical_key"]
    )

    assert (
        canonical_payload
        == original_payload
    )

    assert manifest == original_manifest

    matches = (
        _find_matching_canonical_documents(
            aws_deployment=(
                aws_deployment
            ),
            aws_test_helpers=(
                aws_test_helpers
            ),
            s3_client=s3_client,
            source_key=(
                result["source_key"]
            ),
            source_version_id=(
                result[
                    "source_version_id"
                ]
            ),
        )
    )

    assert len(matches) == 1

    assert (
        matches[0]["key"]
        == result["canonical_key"]
    )

    registry_item = (
        aws_test_helpers
        .wait_for_registry_status(
            document_id=(
                result["document_id"]
            ),
            expected_status=(
                "COMPLETED"
            ),
            timeout_seconds=120,
        )
    )

    assert (
        registry_item["status"]["S"]
        == "COMPLETED"
    )

    assert (
        "lease_expires_at"
        not in registry_item
    )


def test_new_version_of_same_key_creates_new_identity(
    data_dir,
    aws_deployment,
    aws_test_helpers,
):
    source_key = (
        "documents/"
        "AWSTEST001/"
        "protocols/"
        "versioned-document.pdf"
    )

    first_result = (
        aws_test_helpers
        .process_document(
            file_path=(
                data_dir
                / "minimal_text.pdf"
            ),
            source_key=source_key,
        )
    )

    second_result = (
        aws_test_helpers
        .process_document(
            file_path=(
                data_dir
                / "table_document.pdf"
            ),
            source_key=source_key,
        )
    )

    assert (
        first_result["source_key"]
        == second_result["source_key"]
        == source_key
    )

    assert (
        first_result[
            "source_version_id"
        ]
        != second_result[
            "source_version_id"
        ]
    )

    assert (
        first_result["document_id"]
        != second_result["document_id"]
    )

    assert (
        first_result["canonical_key"]
        != second_result["canonical_key"]
    )

    assert (
        first_result["manifest_key"]
        != second_result["manifest_key"]
    )

    assert (
        first_result["payload"][
            "source_version_id"
        ]
        == first_result[
            "source_version_id"
        ]
    )

    assert (
        second_result["payload"][
            "source_version_id"
        ]
        == second_result[
            "source_version_id"
        ]
    )

    assert (
        first_result["payload"][
            "document_id"
        ]
        == first_result["document_id"]
    )

    assert (
        second_result["payload"][
            "document_id"
        ]
        == second_result["document_id"]
    )

    assert (
        first_result["manifest"][
            "processing_status"
        ]
        == "SUCCESS"
    )

    assert (
        second_result["manifest"][
            "processing_status"
        ]
        == "SUCCESS"
    )

    assert (
        first_result["registry_item"][
            "status"
        ]["S"]
        == "COMPLETED"
    )

    assert (
        second_result["registry_item"][
            "status"
        ]["S"]
        == "COMPLETED"
    )

    assert (
        aws_test_helpers.object_exists(
            bucket=(
                aws_deployment
                .canonical_bucket
            ),
            key=(
                first_result[
                    "canonical_key"
                ]
            ),
        )
        is True
    )

    assert (
        aws_test_helpers.object_exists(
            bucket=(
                aws_deployment
                .canonical_bucket
            ),
            key=(
                second_result[
                    "canonical_key"
                ]
            ),
        )
        is True
    )