from unittest.mock import Mock

import pytest

from models.document import (
    ClinicalDocument,
)
from storage.s3_asset_store import (
    S3AssetStore,
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
    asset_store = S3AssetStore(
        "canonical-bucket"
    )
    asset_store.s3 = Mock()

    return asset_store


def test_constructor_stores_bucket_name(
    store,
):
    assert store.bucket_name == (
        "canonical-bucket"
    )


def test_build_image_key(
    store,
    document,
):
    result = store.build_image_key(
        document=document,
        image_id="image-2-1",
        extension="png",
    )

    assert result == (
        "canonical-documents/"
        "document-123/"
        "images/image-2-1.png"
    )


@pytest.mark.parametrize(
    "document_id",
    [
        "",
        None,
    ],
)
def test_build_image_key_rejects_empty_document_id(
    store,
    document,
    document_id,
):
    document.document_id = document_id

    with pytest.raises(
        ValueError,
        match="document.document_id",
    ):
        store.build_image_key(
            document=document,
            image_id="image-1-1",
            extension="png",
        )


@pytest.mark.parametrize(
    (
        "extension",
        "expected_content_type",
    ),
    [
        (
            "jpg",
            "image/jpeg",
        ),
        (
            "jpeg",
            "image/jpeg",
        ),
        (
            "png",
            "image/png",
        ),
        (
            "gif",
            "image/gif",
        ),
        (
            "webp",
            "image/webp",
        ),
        (
            "PNG",
            "image/png",
        ),
        (
            "unknown",
            "application/octet-stream",
        ),
    ],
)
def test_save_image_uses_expected_content_type(
    store,
    document,
    extension,
    expected_content_type,
):
    image_bytes = b"image-data"

    result = store.save_image(
        document=document,
        image_id="image-1-1",
        image_bytes=image_bytes,
        extension=extension,
    )

    expected_key = (
        "canonical-documents/"
        "document-123/"
        "images/"
        f"image-1-1.{extension}"
    )

    store.s3.upload_bytes.assert_called_once_with(
        bucket="canonical-bucket",
        key=expected_key,
        content=image_bytes,
        content_type=(
            expected_content_type
        ),
    )

    assert result == expected_key


def test_save_image_propagates_upload_failure(
    store,
    document,
):
    store.s3.upload_bytes.side_effect = (
        RuntimeError(
            "Image upload failed"
        )
    )

    with pytest.raises(
        RuntimeError,
        match="Image upload failed",
    ):
        store.save_image(
            document=document,
            image_id="image-1-1",
            image_bytes=b"image-data",
            extension="png",
        )


def test_delete_image(
    store,
):
    store.delete_image(
        "canonical-documents/"
        "document-123/"
        "images/image.png"
    )

    store.s3.delete_object.assert_called_once_with(
        bucket="canonical-bucket",
        key=(
            "canonical-documents/"
            "document-123/"
            "images/image.png"
        ),
    )


def test_delete_image_propagates_failure(
    store,
):
    store.s3.delete_object.side_effect = (
        RuntimeError(
            "Image deletion failed"
        )
    )

    with pytest.raises(
        RuntimeError,
        match="Image deletion failed",
    ):
        store.delete_image(
            "canonical-documents/"
            "document-123/"
            "images/image.png"
        )