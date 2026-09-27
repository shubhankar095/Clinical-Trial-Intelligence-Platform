import json

from aws_utils.s3 import S3Service
from models.document import (
    ClinicalDocument,
)
from utils.logger import get_logger


logger = get_logger(__name__)


class S3TableStore:

    def __init__(
        self,
        bucket_name: str,
    ):
        self.bucket_name = bucket_name
        self.s3 = S3Service()

    def build_table_key(
        self,
        document: ClinicalDocument,
        table_id: str,
    ) -> str:
        if not document.document_id:
            raise ValueError(
                "document.document_id must "
                "not be empty."
            )

        return (
            "canonical-documents/"
            f"{document.document_id}/"
            "tables/"
            f"{table_id}.json"
        )

    def save_table(
        self,
        document: ClinicalDocument,
        table_id: str,
        rows: list,
    ) -> str:
        key = self.build_table_key(
            document=document,
            table_id=table_id,
        )

        self.s3.upload_text(
            bucket=self.bucket_name,
            key=key,
            content=json.dumps(
                rows,
                indent=2,
                ensure_ascii=False,
            ),
        )

        return key

    def delete_table(
        self,
        key: str,
    ) -> None:
        self.s3.delete_object(
            bucket=self.bucket_name,
            key=key,
        )