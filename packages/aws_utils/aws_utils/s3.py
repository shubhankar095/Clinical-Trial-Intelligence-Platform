import tempfile

from pathlib import Path

from botocore.exceptions import ClientError

from aws_utils.client import get_client


class S3Service:

    def __init__(self):
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = get_client(
                "s3"
            )

        return self._client

    def upload_text(
        self,
        bucket: str,
        key: str,
        content: str,
    ) -> None:
        self.client.put_object(
            Bucket=bucket,
            Key=key,
            Body=content.encode(
                "utf-8"
            ),
            ContentType=(
                "application/json"
            ),
        )

    def download_text(
        self,
        bucket: str,
        key: str,
        version_id: str | None = None,
    ) -> str:
        request = {
            "Bucket": bucket,
            "Key": key,
        }

        if version_id:
            request["VersionId"] = (
                version_id
            )

        response = self.client.get_object(
            **request
        )

        return (
            response["Body"]
            .read()
            .decode("utf-8")
        )

    def download_file(
        self,
        bucket: str,
        key: str,
        version_id: str | None = None,
    ) -> str:
        suffix = (
            "." + key.rsplit(
                ".",
                1,
            )[-1]
            if "." in key
            else ""
        )

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix,
        ) as temp_file:
            file_path = temp_file.name

        try:
            if version_id:
                self.client.download_file(
                    bucket,
                    key,
                    file_path,
                    ExtraArgs={
                        "VersionId": (
                            version_id
                        ),
                    },
                )

            else:
                self.client.download_file(
                    bucket,
                    key,
                    file_path,
                )

            return file_path

        except Exception:
            Path(
                file_path
            ).unlink(
                missing_ok=True
            )

            raise

    def upload_bytes(
        self,
        bucket: str,
        key: str,
        content: bytes,
        content_type: str,
    ) -> None:
        self.client.put_object(
            Bucket=bucket,
            Key=key,
            Body=content,
            ContentType=content_type,
        )

    def delete_object(
        self,
        bucket: str,
        key: str,
    ) -> None:
        self.client.delete_object(
            Bucket=bucket,
            Key=key,
        )

    def object_exists(
        self,
        bucket: str,
        key: str,
    ) -> bool:
        try:
            self.client.head_object(
                Bucket=bucket,
                Key=key,
            )

            return True

        except ClientError as exception:
            error = (
                exception.response
                .get(
                    "Error",
                    {},
                )
            )

            error_code = str(
                error.get(
                    "Code",
                    "",
                )
            )

            http_status = (
                exception.response
                .get(
                    "ResponseMetadata",
                    {},
                )
                .get(
                    "HTTPStatusCode"
                )
            )

            if (
                error_code
                in {
                    "404",
                    "NoSuchKey",
                    "NotFound",
                }
                or http_status == 404
            ):
                return False

            raise