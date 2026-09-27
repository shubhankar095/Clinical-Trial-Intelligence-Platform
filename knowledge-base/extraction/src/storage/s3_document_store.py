from aws_utils.s3 import S3Service
from models.document import (
    ClinicalDocument,
)
from storage.base_document_store import (
    BaseDocumentStore,
)
from storage.document_serializer import (
    DocumentSerializer,
)
from utils.logger import get_logger


logger = get_logger(__name__)


class S3DocumentStore(
    BaseDocumentStore
):

    def __init__(
        self,
        bucket_name: str,
    ):
        self.bucket_name = bucket_name
        self.s3 = S3Service()

    def save(
        self,
        document: ClinicalDocument,
    ) -> str:
        object_key = (
            self.build_object_key(
                document
            )
        )

        payload = (
            DocumentSerializer.serialize(
                document
            )
        )

        self.s3.upload_text(
            bucket=self.bucket_name,
            key=object_key,
            content=payload,
        )

        logger.info(
            "Saved canonical document.",
            extra={
                "event": (
                    "canonical_document_saved"
                ),
                "document_id": (
                    document.document_id
                ),
                "canonical_bucket": (
                    self.bucket_name
                ),
                "canonical_key": object_key,
            },
        )

        return object_key

    def build_object_key(
        self,
        document: ClinicalDocument,
    ) -> str:
        if not document.document_id:
            raise ValueError(
                "document.document_id must "
                "not be empty."
            )

        return (
            "canonical-documents/"
            f"{document.document_id}/"
            "extracted-document.json"
        )