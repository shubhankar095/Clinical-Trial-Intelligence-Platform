from botocore.exceptions import ClientError

from aws_utils.s3 import (
    S3Service,
)
from exceptions.extraction_manifest import (
    ManifestLoadError,
    ManifestLocationError,
    ManifestNotFoundError,
)
from models.storage_location import (
    StorageLocation,
)
from storage.base_text_store import (
    BaseTextStore,
)


class S3TextStore(BaseTextStore):
    """
    Load UTF-8 text objects from Amazon S3.

    The storage adapter translates Amazon S3 errors
    into the ingestion storage exception contract.
    """

    NOT_FOUND_ERROR_CODES = frozenset(
        {
            "404",
            "NoSuchKey",
            "NoSuchVersion",
            "NotFound",
        }
    )

    def __init__(
        self,
        s3_service: S3Service | None = None,
    ):
        if (
            s3_service is not None
            and not isinstance(
                s3_service,
                S3Service,
            )
        ):
            raise TypeError(
                "s3_service must be an "
                "S3Service or None."
            )

        self.s3_service = (
            s3_service
            or S3Service()
        )

    def load_text(
        self,
        location: StorageLocation,
    ) -> str:
        if not isinstance(
            location,
            StorageLocation,
        ):
            raise TypeError(
                "location must be a "
                "StorageLocation."
            )

        if not location.bucket:
            raise ManifestLocationError(
                "Amazon S3 storage location "
                "requires a bucket."
            )

        try:
            return (
                self.s3_service
                .download_text(
                    bucket=location.bucket,
                    key=location.key,
                    version_id=(
                        location.version_id
                    ),
                )
            )

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
                in self.NOT_FOUND_ERROR_CODES
                or http_status == 404
            ):
                raise ManifestNotFoundError(
                    "Amazon S3 text object was "
                    "not found at "
                    f"s3://{location.bucket}/"
                    f"{location.key}."
                ) from exception

            raise ManifestLoadError(
                "Amazon S3 text object could not "
                "be loaded from "
                f"s3://{location.bucket}/"
                f"{location.key}."
            ) from exception

        except UnicodeDecodeError as exception:
            raise ManifestLoadError(
                "Amazon S3 object is not valid "
                "UTF-8 text."
            ) from exception