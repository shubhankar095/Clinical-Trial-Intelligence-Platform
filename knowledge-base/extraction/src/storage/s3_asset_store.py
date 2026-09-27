from aws_utils.s3 import S3Service
from models.document import (
    ClinicalDocument,
)
from utils.logger import get_logger


logger = get_logger(__name__)


class S3AssetStore:

    def __init__(
        self,
        bucket_name: str,
    ):
        self.bucket_name = bucket_name
        self.s3 = S3Service()

    def build_image_key(
        self,
        document: ClinicalDocument,
        image_id: str,
        extension: str,
    ) -> str:
        if not document.document_id:
            raise ValueError(
                "document.document_id must "
                "not be empty."
            )

        return (
            "canonical-documents/"
            f"{document.document_id}/"
            "images/"
            f"{image_id}.{extension}"
        )

    def save_image(
        self,
        document: ClinicalDocument,
        image_id: str,
        image_bytes: bytes,
        extension: str,
    ) -> str:
        key = self.build_image_key(
            document=document,
            image_id=image_id,
            extension=extension,
        )

        content_type = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "gif": "image/gif",
            "webp": "image/webp",
        }.get(
            extension.lower(),
            "application/octet-stream",
        )

        self.s3.upload_bytes(
            bucket=self.bucket_name,
            key=key,
            content=image_bytes,
            content_type=content_type,
        )

        return key

    def delete_image(
        self,
        key: str,
    ) -> None:
        self.s3.delete_object(
            bucket=self.bucket_name,
            key=key,
        )