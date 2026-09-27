from aws_utils.client import get_client


class TextractService:

    def __init__(self):

        self._client = None

    @property
    def client(self):

        if self._client is None:
            self._client = get_client(
                "textract"
            )

        return self._client

    def extract_text(
        self,
        image_bytes: bytes,
    ) -> dict:

        return self.client.detect_document_text(
            Document={
                "Bytes": image_bytes
            }
        )