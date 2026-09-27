import pytest

from models.document import (
    ClinicalDocument,
)
from storage.s3_asset_store import (
    S3AssetStore,
)
from storage.s3_document_store import (
    S3DocumentStore,
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
            "Clinical@Protocol#V1.pdf"
        ),
        file_format="pdf",
    )


def test_document_key_is_independent_of_file_name(
    document,
):
    store = S3DocumentStore(
        "canonical-bucket"
    )

    first_key = store.build_object_key(
        document
    )

    document.file_name = (
        "Completely Different.pdf"
    )

    second_key = store.build_object_key(
        document
    )

    assert first_key == second_key
    assert first_key == (
        "canonical-documents/"
        "document-123/"
        "extracted-document.json"
    )


def test_document_id_prevents_folder_collision():
    first = ClinicalDocument(
        document_id="document-1",
        file_name="same.pdf",
        file_format="pdf",
    )

    second = ClinicalDocument(
        document_id="document-2",
        file_name="same.pdf",
        file_format="pdf",
    )

    store = S3DocumentStore(
        "canonical-bucket"
    )

    first_key = (
        store.build_object_key(
            first
        )
    )

    second_key = (
        store.build_object_key(
            second
        )
    )

    assert first_key != second_key
    assert "document-1" in first_key
    assert "document-2" in second_key


def test_asset_and_table_keys_share_document_prefix(
    document,
):
    asset_store = S3AssetStore(
        "canonical-bucket"
    )

    table_store = S3TableStore(
        "canonical-bucket"
    )

    image_key = (
        asset_store
        .build_image_key(
            document=document,
            image_id="image-1-1",
            extension="png",
        )
    )

    table_key = (
        table_store
        .build_table_key(
            document=document,
            table_id="table-1-1",
        )
    )

    expected_prefix = (
        "canonical-documents/"
        "document-123/"
    )

    assert image_key.startswith(
        expected_prefix
    )
    assert table_key.startswith(
        expected_prefix
    )


def test_generated_document_key_stays_within_s3_key_limit(
    document,
):
    document.document_id = (
        "a" * 64
    )

    store = S3DocumentStore(
        "canonical-bucket"
    )

    key = store.build_object_key(
        document
    )

    assert (
        len(
            key.encode(
                "utf-8"
            )
        )
        <= 1024
    )


def test_generated_image_key_stays_within_s3_key_limit(
    document,
):
    document.document_id = (
        "a" * 64
    )

    store = S3AssetStore(
        "canonical-bucket"
    )

    key = store.build_image_key(
        document=document,
        image_id="image-9999-9999",
        extension="png",
    )

    assert (
        len(
            key.encode(
                "utf-8"
            )
        )
        <= 1024
    )


def test_generated_table_key_stays_within_s3_key_limit(
    document,
):
    document.document_id = (
        "a" * 64
    )

    store = S3TableStore(
        "canonical-bucket"
    )

    key = store.build_table_key(
        document=document,
        table_id="table-9999-9999",
    )

    assert (
        len(
            key.encode(
                "utf-8"
            )
        )
        <= 1024
    )


@pytest.mark.parametrize(
    "store_type",
    [
        "document",
        "asset",
        "table",
    ],
)
def test_empty_document_id_is_rejected(
    document,
    store_type,
):
    document.document_id = ""

    if store_type == "document":
        store = S3DocumentStore(
            "canonical-bucket"
        )

        with pytest.raises(
            ValueError,
            match="document.document_id",
        ):
            store.build_object_key(
                document
            )

    elif store_type == "asset":
        store = S3AssetStore(
            "canonical-bucket"
        )

        with pytest.raises(
            ValueError,
            match="document.document_id",
        ):
            store.build_image_key(
                document=document,
                image_id="image-1-1",
                extension="png",
            )

    else:
        store = S3TableStore(
            "canonical-bucket"
        )

        with pytest.raises(
            ValueError,
            match="document.document_id",
        ):
            store.build_table_key(
                document=document,
                table_id="table-1-1",
            )