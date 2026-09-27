import json

import pytest


pytestmark = pytest.mark.aws


def assert_common_document_fields(
    *,
    result,
    aws_deployment,
):
    payload = result["payload"]

    source_key = result["source_key"]
    source_version_id = (
        result["source_version_id"]
    )
    document_id = result["document_id"]
    canonical_key = (
        result["canonical_key"]
    )

    assert (
        payload["processing_status"]
        == "SUCCESS"
    )

    assert payload["error_message"] is None

    assert (
        payload["document_id"]
        == document_id
    )

    assert (
        payload["source_bucket"]
        == aws_deployment.raw_bucket
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
        payload["canonical_bucket"]
        == aws_deployment.canonical_bucket
    )

    assert (
        payload["canonical_key"]
        == canonical_key
    )

    assert (
        canonical_key
        == (
            "canonical-documents/"
            f"{document_id}/"
            "extracted-document.json"
        )
    )

    assert payload["file_format"] == "pdf"

    assert (
        payload["metadata"]["study_id"]
        == "AWSTEST001"
    )

    assert (
        payload["metadata"][
            "document_type"
        ]
        == "PROTOCOL"
    )

    assert payload["page_count"] >= 1

    assert (
        payload["page_count"]
        == len(payload["pages"])
    )

    assert (
        payload["ocr_page_count"]
        <= payload["page_count"]
    )

    assert (
        payload["image_count"]
        == len(payload["images"])
    )

    assert (
        payload["table_count"]
        == len(payload["tables"])
    )

    assert payload["raw_text"].strip()

    assert payload["already_processed"] is False

    for page in payload["pages"]:
        assert (
            payload["raw_text"][
                page["start_offset"]:
                page["end_offset"]
            ]
            == page["text"]
        )


def assert_success_manifest(
    *,
    result,
    aws_deployment,
):
    manifest = result["manifest"]

    expected_manifest_key = (
        "canonical-documents/"
        f"{result['document_id']}/"
        "_SUCCESS.json"
    )

    assert (
        result["manifest_key"]
        == expected_manifest_key
    )

    assert (
        manifest["document_id"]
        == result["document_id"]
    )

    assert (
        manifest["source_bucket"]
        == aws_deployment.raw_bucket
    )

    assert (
        manifest["source_key"]
        == result["source_key"]
    )

    assert (
        manifest["source_version_id"]
        == result["source_version_id"]
    )

    assert (
        manifest[
            "processing_schema_version"
        ]
        == (
            aws_deployment
            .processing_schema_version
        )
    )

    assert (
        manifest["canonical_bucket"]
        == aws_deployment.canonical_bucket
    )

    assert (
        manifest["canonical_key"]
        == result["canonical_key"]
    )

    assert (
        manifest["processing_status"]
        == "SUCCESS"
    )

    assert manifest["completed_at"]


def assert_completed_registry(
    *,
    result,
    aws_deployment,
):
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

    assert "updated_at" in item
    assert "completed_at" in item
    assert "ttl" in item

    assert "lease_expires_at" not in item

    assert int(
        item["completed_at"]["N"]
    ) > 0

    assert int(
        item["updated_at"]["N"]
    ) > 0

    assert int(
        item["ttl"]["N"]
    ) > int(
        item["completed_at"]["N"]
    )


def assert_successful_processing(
    *,
    result,
    aws_deployment,
):
    assert_common_document_fields(
        result=result,
        aws_deployment=aws_deployment,
    )

    assert_success_manifest(
        result=result,
        aws_deployment=aws_deployment,
    )

    assert_completed_registry(
        result=result,
        aws_deployment=aws_deployment,
    )


def test_native_text_pdf_is_processed(
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

    assert_successful_processing(
        result=result,
        aws_deployment=aws_deployment,
    )

    payload = result["payload"]

    assert (
        result["canonical_key"]
        .endswith(
            "extracted-document.json"
        )
    )

    assert payload["ocr_page_count"] == 0

    assert (
        "Clinical Trial Extraction Fixture"
        in payload["raw_text"]
    )

    assert (
        "Study ID: TEST001"
        in payload["raw_text"]
    )


def test_scanned_pdf_uses_textract_ocr(
    data_dir,
    aws_deployment,
    aws_test_helpers,
    s3_client,
):
    result = (
        aws_test_helpers
        .process_document(
            data_dir
            / "scanned_page.pdf"
        )
    )

    assert_successful_processing(
        result=result,
        aws_deployment=aws_deployment,
    )

    payload = result["payload"]

    assert payload["ocr_page_count"] >= 1

    assert any(
        page["ocr_applied"]
        for page in payload["pages"]
    )

    assert any(
        (
            page["extraction_method"]
            == "OCR"
        )
        for page in payload["pages"]
    )

    assert payload["image_count"] >= 1

    image = payload["images"][0]

    response = s3_client.head_object(
        Bucket=(
            aws_deployment
            .canonical_bucket
        ),
        Key=image["s3_key"],
    )

    assert response["ContentLength"] > 0

    assert (
        response["ContentType"]
        .startswith(
            "image/"
        )
    )

    assert image["s3_key"].startswith(
        (
            "canonical-documents/"
            f"{result['document_id']}/"
            "images/"
        )
    )


def test_table_pdf_creates_table_asset(
    data_dir,
    aws_deployment,
    aws_test_helpers,
    s3_client,
):
    result = (
        aws_test_helpers
        .process_document(
            data_dir
            / "table_document.pdf"
        )
    )

    assert_successful_processing(
        result=result,
        aws_deployment=aws_deployment,
    )

    payload = result["payload"]

    assert payload["table_count"] >= 1

    table = payload["tables"][0]

    assert table["row_count"] == 4
    assert table["column_count"] == 3

    assert table["s3_key"].startswith(
        (
            "canonical-documents/"
            f"{result['document_id']}/"
            "tables/"
        )
    )

    response = s3_client.get_object(
        Bucket=(
            aws_deployment
            .canonical_bucket
        ),
        Key=table["s3_key"],
    )

    rows = json.loads(
        response["Body"]
        .read()
        .decode(
            "utf-8"
        )
    )

    assert rows[0] == [
        "Visit",
        "Day",
        "Assessment",
    ]

    assert len(rows) == 4