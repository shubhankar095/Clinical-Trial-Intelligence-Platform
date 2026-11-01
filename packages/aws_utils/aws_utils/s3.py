import tempfile

from pathlib import Path
from typing import Any

from botocore.exceptions import ClientError

from aws_utils.client import get_client


class S3Service:
    """
    Shared Amazon S3 transport adapter.

    Object naming, serialization, and application
    contracts belong to the calling application.
    """

    def __init__(
        self,
        *,
        region_name: str | None = None,
        client: Any | None = None,
    ):
        if region_name is not None and not isinstance(region_name, str):
            raise TypeError("region_name must be a string or None.")

        normalized_region = (
            region_name.strip()
            if region_name is not None
            else None
        )

        if (
            region_name is not None
            and not normalized_region
        ):
            raise ValueError(
                "region_name must not be blank "
                "when supplied."
            )

        self.region_name = normalized_region
        self._client = client

    @property
    def client(
        self,
    ) -> Any:
        """
        Lazily construct the Amazon S3 client.
        """
        if self._client is None:
            self._client = get_client(
                "s3",
                region_name=self.region_name,
            )

        return self._client

    def upload_text(
        self,
        bucket: str,
        key: str,
        content: str,
        content_type: str = "application/json",
        metadata: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Upload one UTF-8 text object and return the
        Amazon S3 put_object response.
        """
        normalized_bucket = (
            self._normalize_required_string(
                value=bucket,
                field_name="bucket",
            )
        )

        normalized_key = (
            self._normalize_required_string(
                value=key,
                field_name="key",
            )
        )

        normalized_content_type = (
            self._normalize_required_string(
                value=content_type,
                field_name="content_type",
            )
        )

        if not isinstance(
            content,
            str,
        ):
            raise TypeError(
                "content must be a string."
            )

        request: dict[str, Any] = {
            "Bucket": normalized_bucket,
            "Key": normalized_key,
            "Body": content.encode(
                "utf-8"
            ),
            "ContentType": (
                normalized_content_type
            ),
        }

        if metadata is not None:
            request["Metadata"] = (
                self._normalize_metadata(
                    metadata
                )
            )

        response = self.client.put_object(
            **request
        )

        return self._require_response(
            response=response,
            operation="upload text",
        )

    def download_text(
        self,
        bucket: str,
        key: str,
        version_id: str | None = None,
    ) -> str:
        """
        Download one Amazon S3 object as UTF-8 text.
        """
        request: dict[str, Any] = {
            "Bucket": (
                self._normalize_required_string(
                    value=bucket,
                    field_name="bucket",
                )
            ),
            "Key": (
                self._normalize_required_string(
                    value=key,
                    field_name="key",
                )
            ),
        }

        normalized_version_id = (
            self._normalize_optional_string(
                value=version_id,
                field_name="version_id",
            )
        )

        if normalized_version_id is not None:
            request["VersionId"] = (
                normalized_version_id
            )

        response = self.client.get_object(
            **request
        )

        body = response.get(
            "Body"
        )

        if body is None:
            raise RuntimeError(
                "Amazon S3 get_object response "
                "does not contain a body."
            )

        try:
            body_value = body.read()
        except AttributeError as exception:
            raise RuntimeError(
                "Amazon S3 object body is not "
                "readable."
            ) from exception

        if not isinstance(
            body_value,
            bytes,
        ):
            raise RuntimeError(
                "Amazon S3 object body must be "
                "bytes."
            )

        return body_value.decode(
            "utf-8"
        )

    def download_file(
        self,
        bucket: str,
        key: str,
        version_id: str | None = None,
    ) -> str:
        """
        Download one Amazon S3 object to a temporary
        local file and return the file path.
        """
        normalized_bucket = (
            self._normalize_required_string(
                value=bucket,
                field_name="bucket",
            )
        )

        normalized_key = (
            self._normalize_required_string(
                value=key,
                field_name="key",
            )
        )

        normalized_version_id = (
            self._normalize_optional_string(
                value=version_id,
                field_name="version_id",
            )
        )

        suffix = (
            "."
            + normalized_key.rsplit(
                ".",
                1,
            )[-1]
            if "." in normalized_key
            else ""
        )

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix,
        ) as temporary_file:
            file_path = temporary_file.name

        try:
            if normalized_version_id is not None:
                self.client.download_file(
                    normalized_bucket,
                    normalized_key,
                    file_path,
                    ExtraArgs={
                        "VersionId": (
                            normalized_version_id
                        ),
                    },
                )
            else:
                self.client.download_file(
                    normalized_bucket,
                    normalized_key,
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
        metadata: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Upload one binary object and return the
        Amazon S3 put_object response.
        """
        if not isinstance(
            content,
            bytes,
        ):
            raise TypeError(
                "content must be bytes."
            )

        request: dict[str, Any] = {
            "Bucket": (
                self._normalize_required_string(
                    value=bucket,
                    field_name="bucket",
                )
            ),
            "Key": (
                self._normalize_required_string(
                    value=key,
                    field_name="key",
                )
            ),
            "Body": content,
            "ContentType": (
                self._normalize_required_string(
                    value=content_type,
                    field_name="content_type",
                )
            ),
        }

        if metadata is not None:
            request["Metadata"] = (
                self._normalize_metadata(
                    metadata
                )
            )

        response = self.client.put_object(
            **request
        )

        return self._require_response(
            response=response,
            operation="upload bytes",
        )

    def delete_object(
        self,
        bucket: str,
        key: str,
    ) -> dict[str, Any]:
        """
        Delete one Amazon S3 object.
        """
        response = self.client.delete_object(
            Bucket=(
                self._normalize_required_string(
                    value=bucket,
                    field_name="bucket",
                )
            ),
            Key=(
                self._normalize_required_string(
                    value=key,
                    field_name="key",
                )
            ),
        )

        return self._require_response(
            response=response,
            operation="delete object",
        )

    def object_exists(
        self,
        bucket: str,
        key: str,
    ) -> bool:
        """
        Return whether an Amazon S3 object exists.
        """
        normalized_bucket = (
            self._normalize_required_string(
                value=bucket,
                field_name="bucket",
            )
        )

        normalized_key = (
            self._normalize_required_string(
                value=key,
                field_name="key",
            )
        )

        try:
            self.client.head_object(
                Bucket=normalized_bucket,
                Key=normalized_key,
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

    @staticmethod
    def _normalize_metadata(
        metadata: dict[str, str],
    ) -> dict[str, str]:
        """
        Validate and normalize Amazon S3 user
        metadata.
        """
        if not isinstance(
            metadata,
            dict,
        ):
            raise TypeError(
                "metadata must be a dictionary."
            )

        normalized_metadata: dict[
            str,
            str,
        ] = {}

        for key, value in metadata.items():
            if not isinstance(
                key,
                str,
            ):
                raise TypeError(
                    "Amazon S3 metadata keys must "
                    "be strings."
                )

            if not isinstance(
                value,
                str,
            ):
                raise TypeError(
                    "Amazon S3 metadata values "
                    "must be strings."
                )

            normalized_key = key.strip()
            normalized_value = value.strip()

            if not normalized_key:
                raise ValueError(
                    "Amazon S3 metadata keys must "
                    "not be blank."
                )

            if not normalized_value:
                raise ValueError(
                    "Amazon S3 metadata values "
                    "must not be blank."
                )

            normalized_metadata[
                normalized_key
            ] = normalized_value

        return normalized_metadata

    @staticmethod
    def _require_response(
        *,
        response: Any,
        operation: str,
    ) -> dict[str, Any]:
        """
        Require one boto3 response dictionary.
        """
        if not isinstance(
            response,
            dict,
        ):
            raise RuntimeError(
                "Amazon S3 "
                f"{operation} response must be "
                "a dictionary."
            )

        return response

    @staticmethod
    def _normalize_required_string(
        *,
        value: str,
        field_name: str,
    ) -> str:
        if not isinstance(
            value,
            str,
        ):
            raise TypeError(
                f"{field_name} must be a string."
            )

        normalized_value = value.strip()

        if not normalized_value:
            raise ValueError(
                f"{field_name} must not be blank."
            )

        return normalized_value

    @staticmethod
    def _normalize_optional_string(
        *,
        value: str | None,
        field_name: str,
    ) -> str | None:
        if value is None:
            return None

        if not isinstance(
            value,
            str,
        ):
            raise TypeError(
                f"{field_name} must be a string "
                "or None."
            )

        normalized_value = value.strip()

        if not normalized_value:
            raise ValueError(
                f"{field_name} must not be blank "
                "when supplied."
            )

        return normalized_value