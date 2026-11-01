from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StorageLocation:
    """
    Identify an object in a storage implementation.

    For Amazon S3:
        bucket contains the S3 bucket name.
        key contains the S3 object key.
        version_id optionally identifies an exact
        object version.

    For local storage:
        bucket is normally empty.
        key contains a path relative to the local
        store's configured base directory.
        version_id is unused.
    """

    bucket: str
    key: str
    version_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(
            self.bucket,
            str,
        ):
            raise TypeError(
                "Storage location bucket must "
                "be a string."
            )

        if not isinstance(
            self.key,
            str,
        ):
            raise TypeError(
                "Storage location key must "
                "be a string."
            )

        normalized_bucket = (
            self.bucket.strip()
        )

        normalized_key = (
            self.key.strip()
        )

        if not normalized_key:
            raise ValueError(
                "Storage location key must "
                "not be empty."
            )

        normalized_version_id = (
            self.version_id
        )

        if (
            normalized_version_id
            is not None
            and not isinstance(
                normalized_version_id,
                str,
            )
        ):
            raise TypeError(
                "Storage location version_id "
                "must be a string or None."
            )

        if (
            normalized_version_id
            is not None
        ):
            normalized_version_id = (
                normalized_version_id.strip()
            )

            if not normalized_version_id:
                raise ValueError(
                    "Storage location version_id "
                    "must not be blank when supplied."
                )

        object.__setattr__(
            self,
            "bucket",
            normalized_bucket,
        )

        object.__setattr__(
            self,
            "key",
            normalized_key,
        )

        object.__setattr__(
            self,
            "version_id",
            normalized_version_id,
        )