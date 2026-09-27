import json
from unittest.mock import Mock

import pytest

from models.document import (
    ClinicalDocument,
)
from storage.s3_table_store import (
    S3TableStore,
)


pytestmark = pytest.mark.unit


@pytest.fixture
def document():
    return ClinicalDocument(
        document_id="document-123",
        file_name=(
            "Clinical Protocol V1.pdf"
        ),
        file_format="pdf",
    )


@pytest.fixture
def store():
    table_store = S3TableStore(
        "canonical-bucket"
    )

    table_store.s3 = Mock()

    return table_store


def test_constructor_stores_bucket_name(
    store,
):
    assert store.bucket_name == (
        "canonical-bucket"
    )


def test_build_table_key(
    store,
    document,
):
    result = store.build_table_key(
        document=document,
        table_id="table-1-1",
    )

    assert result == (
        "canonical-documents/"
        "document-123/"
        "tables/table-1-1.json"
    )


@pytest.mark.parametrize(
    "document_id",
    [
        "",
        None,
    ],
)
def test_build_table_key_rejects_empty_document_id(
    store,
    document,
    document_id,
):
    document.document_id = document_id

    with pytest.raises(
        ValueError,
        match="document.document_id",
    ):
        store.build_table_key(
            document=document,
            table_id="table-1-1",
        )


def test_save_table_uploads_json(
    store,
    document,
):
    rows = [
        [
            "Column A",
            "Column B",
        ],
        [
            "Value 1",
            "Value 2",
        ],
    ]

    result = store.save_table(
        document=document,
        table_id="table-1-1",
        rows=rows,
    )

    expected_key = (
        "canonical-documents/"
        "document-123/"
        "tables/table-1-1.json"
    )

    (
        store.s3
        .upload_text
        .assert_called_once()
    )

    upload_call = (
        store.s3
        .upload_text
        .call_args
        .kwargs
    )

    assert upload_call["bucket"] == (
        "canonical-bucket"
    )
    assert upload_call["key"] == (
        expected_key
    )
    assert (
        json.loads(
            upload_call["content"]
        )
        == rows
    )
    assert result == expected_key


def test_save_table_preserves_unicode(
    store,
    document,
):
    rows = [
        [
            "Name",
            "Value",
        ],
        [
            "café",
            "日本語",
        ],
    ]

    store.save_table(
        document=document,
        table_id="table-1-1",
        rows=rows,
    )

    uploaded_content = (
        store.s3
        .upload_text
        .call_args
        .kwargs["content"]
    )

    assert (
        json.loads(
            uploaded_content
        )
        == rows
    )

    assert "café" in uploaded_content
    assert "日本語" in uploaded_content


def test_save_table_uses_document_id_not_file_name(
    store,
    document,
):
    document.file_name = (
        "Different Table Source.pdf"
    )

    result = store.save_table(
        document=document,
        table_id="table-3-2",
        rows=[
            [
                "value",
            ]
        ],
    )

    assert result == (
        "canonical-documents/"
        "document-123/"
        "tables/table-3-2.json"
    )


def test_delete_table(
    store,
):
    store.delete_table(
        "canonical-documents/"
        "document-123/"
        "tables/table.json"
    )

    (
        store.s3
        .delete_object
        .assert_called_once_with(
            bucket="canonical-bucket",
            key=(
                "canonical-documents/"
                "document-123/"
                "tables/table.json"
            ),
        )
    )


def test_delete_table_propagates_failure(
    store,
):
    store.s3.delete_object.side_effect = (
        RuntimeError(
            "Table deletion failed"
        )
    )

    with pytest.raises(
        RuntimeError,
        match="Table deletion failed",
    ):
        store.delete_table(
            "canonical-documents/"
            "document-123/"
            "tables/table.json"
        )


def test_save_table_propagates_upload_failure(
    store,
    document,
):
    store.s3.upload_text.side_effect = (
        RuntimeError(
            "Table upload failed"
        )
    )

    with pytest.raises(
        RuntimeError,
        match="Table upload failed",
    ):
        store.save_table(
            document=document,
            table_id="table-1-1",
            rows=[
                [
                    "value",
                ]
            ],
        )