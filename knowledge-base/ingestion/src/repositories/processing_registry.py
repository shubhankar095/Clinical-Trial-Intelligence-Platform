import time
import uuid

from dataclasses import dataclass
from datetime import (
    datetime,
    timezone,
)
from enum import Enum
from typing import Any

from botocore.exceptions import (
    BotoCoreError,
    ClientError,
)

from aws_utils.dynamodb import (
    DynamoDBService,
)
from utils.logger import get_logger


logger = get_logger(__name__)


class ProcessingRegistryError(
    RuntimeError
):
    """
    Base processing-registry exception.
    """


class ProcessingRegistryWriteError(
    ProcessingRegistryError
):
    """
    A DynamoDB registry write failed.
    """


class ProcessingClaimLostError(
    ProcessingRegistryError
):
    """
    The current worker no longer owns the active
    processing claim.
    """


class ClaimDisposition(
    str,
    Enum,
):
    """
    Result of one claim-acquisition request.
    """

    ACQUIRED = "ACQUIRED"
    COMPLETED = "COMPLETED"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(
    frozen=True,
    slots=True,
)
class ProcessingClaim:
    """
    One successfully acquired processing claim.
    """

    ingestion_id: str
    owner_token: str

    attempt_count: int

    claimed_at: str
    lease_expires_at: int


@dataclass(
    frozen=True,
    slots=True,
)
class ClaimResult:
    """
    Outcome of one processing-claim request.
    """

    disposition: ClaimDisposition

    claim: ProcessingClaim | None = None

    existing_record: (
        dict[str, Any]
        | None
    ) = None


class ProcessingRegistry:
    """
    DynamoDB-backed distributed Ingestion registry.

    A claim can be acquired when:

    - No record exists.
    - A previous record is FAILED.
    - A PROCESSING lease has expired.

    A COMPLETED record is never reclaimed.
    """

    STATUS_PROCESSING = "PROCESSING"
    STATUS_COMPLETED = "COMPLETED"
    STATUS_FAILED = "FAILED"

    def __init__(
        self,
        *,
        table_name: str,
        lease_seconds: int,
        record_ttl_days: int,
        dynamodb_service: (
            DynamoDBService
            | None
        ) = None,
        clock: Any | None = None,
    ):
        self.table_name = (
            self._normalize_required_string(
                value=table_name,
                field_name="table_name",
            )
        )

        self._validate_positive_integer(
            value=lease_seconds,
            field_name="lease_seconds",
        )

        self._validate_positive_integer(
            value=record_ttl_days,
            field_name="record_ttl_days",
        )

        if (
            dynamodb_service is not None
            and not isinstance(
                dynamodb_service,
                DynamoDBService,
            )
        ):
            raise TypeError(
                "dynamodb_service must be a "
                "DynamoDBService or None."
            )

        self.lease_seconds = lease_seconds

        self.record_ttl_days = (
            record_ttl_days
        )

        self.dynamodb_service = (
            dynamodb_service
            or DynamoDBService()
        )

        self._clock = clock or time.time

    def acquire_claim(
        self,
        *,
        ingestion_id: str,
        document_id: str,
        ingestion_profile_id: str,
        manifest_bucket: str,
        manifest_key: str,
        manifest_version_id: (
            str
            | None
        ),
    ) -> ClaimResult:
        """
        Atomically acquire a processing claim.
        """
        ingestion_id = (
            self._normalize_required_string(
                value=ingestion_id,
                field_name="ingestion_id",
            )
        )

        document_id = (
            self._normalize_required_string(
                value=document_id,
                field_name="document_id",
            )
        )

        ingestion_profile_id = (
            self._normalize_required_string(
                value=ingestion_profile_id,
                field_name=(
                    "ingestion_profile_id"
                ),
            )
        )

        manifest_bucket = (
            self._normalize_required_string(
                value=manifest_bucket,
                field_name="manifest_bucket",
            )
        )

        manifest_key = (
            self._normalize_required_string(
                value=manifest_key,
                field_name="manifest_key",
            )
        )

        manifest_version_id = (
            self._normalize_optional_string(
                value=manifest_version_id,
                field_name=(
                    "manifest_version_id"
                ),
            )
        )

        current_epoch = self._now_epoch()

        claimed_at = self._to_timestamp(
            current_epoch
        )

        lease_expires_at = (
            current_epoch
            + self.lease_seconds
        )

        ttl = (
            current_epoch
            + self.record_ttl_days
            * 86_400
        )

        owner_token = str(
            uuid.uuid4()
        )

        values = {
            ":processing": {
                "S": self.STATUS_PROCESSING,
            },
            ":failed": {
                "S": self.STATUS_FAILED,
            },
            ":document_id": {
                "S": document_id,
            },
            ":profile_id": {
                "S": ingestion_profile_id,
            },
            ":owner_token": {
                "S": owner_token,
            },
            ":manifest_bucket": {
                "S": manifest_bucket,
            },
            ":manifest_key": {
                "S": manifest_key,
            },
            ":claimed_at": {
                "S": claimed_at,
            },
            ":lease_expires_at": {
                "N": str(
                    lease_expires_at
                ),
            },
            ":current_epoch": {
                "N": str(
                    current_epoch
                ),
            },
            ":ttl": {
                "N": str(
                    ttl
                ),
            },
            ":zero": {
                "N": "0",
            },
            ":one": {
                "N": "1",
            },
        }

        set_parts = [
            "document_id = :document_id",
            (
                "ingestion_profile_id = "
                ":profile_id"
            ),
            "#status = :processing",
            "owner_token = :owner_token",
            (
                "manifest_bucket = "
                ":manifest_bucket"
            ),
            "manifest_key = :manifest_key",
            "claimed_at = :claimed_at",
            "heartbeat_at = :claimed_at",
            "updated_at = :claimed_at",
            (
                "lease_expires_at = "
                ":lease_expires_at"
            ),
            "#ttl = :ttl",
            (
                "attempt_count = "
                "if_not_exists("
                "attempt_count, :zero"
                ") + :one"
            ),
        ]

        remove_parts = [
            "completed_at",
            "failed_at",
            "error_type",
            "error_message",
            "index_destination",
            "index_record_count",
            "chunk_count",
            "success_manifest_bucket",
            "success_manifest_key",
            "success_manifest_version_id",
        ]

        if manifest_version_id is None:
            remove_parts.append(
                "manifest_version_id"
            )
        else:
            values[
                ":manifest_version_id"
            ] = {
                "S": manifest_version_id,
            }

            set_parts.append(
                "manifest_version_id = "
                ":manifest_version_id"
            )

        try:
            response = (
                self.dynamodb_service
                .update_item(
                    table_name=(
                        self.table_name
                    ),
                    key={
                        "ingestion_id": {
                            "S": ingestion_id,
                        },
                    },
                    condition_expression=(
                        "attribute_not_exists("
                        "ingestion_id"
                        ") OR #status = :failed "
                        "OR ("
                        "#status = :processing "
                        "AND lease_expires_at "
                        "< :current_epoch"
                        ")"
                    ),
                    update_expression=(
                        "SET "
                        + ", ".join(set_parts)
                        + " REMOVE "
                        + ", ".join(
                            remove_parts
                        )
                    ),
                    expression_attribute_names={
                        "#status": "status",
                        "#ttl": "ttl",
                    },
                    expression_attribute_values=(
                        values
                    ),
                    return_values="ALL_NEW",
                )
            )
        except ClientError as exception:
            if self._is_conditional_failure(
                exception
            ):
                existing_record = (
                    self.get_record(
                        ingestion_id
                    )
                )

                if (
                    existing_record
                    and existing_record.get(
                        "status"
                    )
                    == self.STATUS_COMPLETED
                ):
                    return ClaimResult(
                        disposition=(
                            ClaimDisposition
                            .COMPLETED
                        ),
                        existing_record=(
                            existing_record
                        ),
                    )

                return ClaimResult(
                    disposition=(
                        ClaimDisposition
                        .UNAVAILABLE
                    ),
                    existing_record=(
                        existing_record
                    ),
                )

            raise ProcessingRegistryWriteError(
                "Ingestion processing claim could "
                "not be acquired."
            ) from exception

        except BotoCoreError as exception:
            raise ProcessingRegistryWriteError(
                "Ingestion processing claim could "
                "not be acquired."
            ) from exception

        attributes = response.get(
            "Attributes",
            {},
        )

        record = self._deserialize_item(
            attributes
        )

        attempt_count = record.get(
            "attempt_count"
        )

        if (
            not isinstance(
                attempt_count,
                int,
            )
            or attempt_count <= 0
        ):
            raise ProcessingRegistryWriteError(
                "Processing claim response did not "
                "contain a valid attempt_count."
            )

        claim = ProcessingClaim(
            ingestion_id=ingestion_id,
            owner_token=owner_token,
            attempt_count=attempt_count,
            claimed_at=claimed_at,
            lease_expires_at=(
                lease_expires_at
            ),
        )

        logger.info(
            "Ingestion processing claim acquired.",
            extra={
                "event": (
                    "ingestion_processing_claim_"
                    "acquired"
                ),
                "ingestion_id": ingestion_id,
                "document_id": document_id,
                "ingestion_profile_id": (
                    ingestion_profile_id
                ),
                "attempt_count": (
                    attempt_count
                ),
                "lease_expires_at": (
                    lease_expires_at
                ),
            },
        )

        return ClaimResult(
            disposition=(
                ClaimDisposition.ACQUIRED
            ),
            claim=claim,
            existing_record=record,
        )

    def renew_claim(
        self,
        claim: ProcessingClaim,
    ) -> int:
        """
        Renew one active processing claim.
        """
        self._validate_claim(
            claim
        )

        current_epoch = self._now_epoch()

        timestamp = self._to_timestamp(
            current_epoch
        )

        lease_expires_at = (
            current_epoch
            + self.lease_seconds
        )

        self._owned_update(
            claim=claim,
            update_expression=(
                "SET heartbeat_at = :timestamp, "
                "updated_at = :timestamp, "
                "lease_expires_at = "
                ":lease_expires_at"
            ),
            values={
                ":processing": {
                    "S": self.STATUS_PROCESSING,
                },
                ":owner_token": {
                    "S": claim.owner_token,
                },
                ":timestamp": {
                    "S": timestamp,
                },
                ":lease_expires_at": {
                    "N": str(
                        lease_expires_at
                    ),
                },
            },
            failure_message=(
                "Ingestion processing claim could "
                "not be renewed."
            ),
        )

        return lease_expires_at

    def mark_completed(
        self,
        claim: ProcessingClaim,
        *,
        index_destination: str,
        index_record_count: int,
        chunk_count: int,
        success_manifest_bucket: str,
        success_manifest_key: str,
        success_manifest_version_id: (
            str
            | None
        ) = None,
    ) -> None:
        """
        Mark an owned claim COMPLETED.
        """
        self._validate_claim(
            claim
        )

        index_destination = (
            self._normalize_required_string(
                value=index_destination,
                field_name=(
                    "index_destination"
                ),
            )
        )

        success_manifest_bucket = (
            self._normalize_required_string(
                value=success_manifest_bucket,
                field_name=(
                    "success_manifest_bucket"
                ),
            )
        )

        success_manifest_key = (
            self._normalize_required_string(
                value=success_manifest_key,
                field_name=(
                    "success_manifest_key"
                ),
            )
        )

        success_manifest_version_id = (
            self._normalize_optional_string(
                value=(
                    success_manifest_version_id
                ),
                field_name=(
                    "success_manifest_version_id"
                ),
            )
        )

        self._validate_nonnegative_integer(
            value=index_record_count,
            field_name=(
                "index_record_count"
            ),
        )

        self._validate_nonnegative_integer(
            value=chunk_count,
            field_name="chunk_count",
        )

        timestamp = self._to_timestamp(
            self._now_epoch()
        )

        values = {
            ":processing": {
                "S": self.STATUS_PROCESSING,
            },
            ":completed": {
                "S": self.STATUS_COMPLETED,
            },
            ":owner_token": {
                "S": claim.owner_token,
            },
            ":timestamp": {
                "S": timestamp,
            },
            ":destination": {
                "S": index_destination,
            },
            ":record_count": {
                "N": str(
                    index_record_count
                ),
            },
            ":chunk_count": {
                "N": str(
                    chunk_count
                ),
            },
            ":manifest_bucket": {
                "S": (
                    success_manifest_bucket
                ),
            },
            ":manifest_key": {
                "S": success_manifest_key,
            },
        }

        set_parts = [
            "#status = :completed",
            "completed_at = :timestamp",
            "updated_at = :timestamp",
            (
                "index_destination = "
                ":destination"
            ),
            (
                "index_record_count = "
                ":record_count"
            ),
            "chunk_count = :chunk_count",
            (
                "success_manifest_bucket = "
                ":manifest_bucket"
            ),
            (
                "success_manifest_key = "
                ":manifest_key"
            ),
        ]

        remove_parts = [
            "lease_expires_at",
            "heartbeat_at",
            "failed_at",
            "error_type",
            "error_message",
        ]

        if (
            success_manifest_version_id
            is None
        ):
            remove_parts.append(
                "success_manifest_version_id"
            )
        else:
            values[
                ":manifest_version_id"
            ] = {
                "S": (
                    success_manifest_version_id
                ),
            }

            set_parts.append(
                "success_manifest_version_id = "
                ":manifest_version_id"
            )

        self._owned_update(
            claim=claim,
            update_expression=(
                "SET "
                + ", ".join(set_parts)
                + " REMOVE "
                + ", ".join(remove_parts)
            ),
            values=values,
            failure_message=(
                "Ingestion processing claim could "
                "not be marked complete."
            ),
        )

        logger.info(
            "Ingestion processing claim marked "
            "complete.",
            extra={
                "event": (
                    "ingestion_processing_claim_"
                    "completed"
                ),
                "ingestion_id": (
                    claim.ingestion_id
                ),
                "chunk_count": chunk_count,
                "index_record_count": (
                    index_record_count
                ),
                "index_destination": (
                    index_destination
                ),
            },
        )

    def mark_failed(
        self,
        claim: ProcessingClaim,
        *,
        error_type: str,
        error_message: str,
    ) -> None:
        """
        Mark an owned claim permanently FAILED.
        """
        self._validate_claim(
            claim
        )

        error_type = (
            self._normalize_required_string(
                value=error_type,
                field_name="error_type",
            )
        )

        error_message = (
            self._normalize_required_string(
                value=error_message,
                field_name="error_message",
            )
        )

        timestamp = self._to_timestamp(
            self._now_epoch()
        )

        self._owned_update(
            claim=claim,
            update_expression=(
                "SET #status = :failed, "
                "failed_at = :timestamp, "
                "updated_at = :timestamp, "
                "error_type = :error_type, "
                "error_message = :error_message "
                "REMOVE lease_expires_at, "
                "heartbeat_at"
            ),
            values={
                ":processing": {
                    "S": self.STATUS_PROCESSING,
                },
                ":failed": {
                    "S": self.STATUS_FAILED,
                },
                ":owner_token": {
                    "S": claim.owner_token,
                },
                ":timestamp": {
                    "S": timestamp,
                },
                ":error_type": {
                    "S": error_type,
                },
                ":error_message": {
                    "S": error_message,
                },
            },
            failure_message=(
                "Ingestion processing claim could "
                "not be marked failed."
            ),
        )

        logger.warning(
            "Ingestion processing claim marked "
            "failed.",
            extra={
                "event": (
                    "ingestion_processing_claim_"
                    "failed"
                ),
                "ingestion_id": (
                    claim.ingestion_id
                ),
                "error_type": error_type,
            },
        )

    def get_record(
        self,
        ingestion_id: str,
    ) -> dict[str, Any] | None:
        """
        Read one strongly consistent registry record.
        """
        ingestion_id = (
            self._normalize_required_string(
                value=ingestion_id,
                field_name="ingestion_id",
            )
        )

        try:
            item = (
                self.dynamodb_service
                .get_item(
                    table_name=(
                        self.table_name
                    ),
                    key={
                        "ingestion_id": {
                            "S": ingestion_id,
                        },
                    },
                    consistent_read=True,
                )
            )
        except (
            BotoCoreError,
            ClientError,
        ) as exception:
            raise ProcessingRegistryError(
                "Ingestion processing record could "
                "not be read."
            ) from exception

        if item is None:
            return None

        return self._deserialize_item(
            item
        )

    def _owned_update(
        self,
        *,
        claim: ProcessingClaim,
        update_expression: str,
        values: dict[
            str,
            dict[str, Any],
        ],
        failure_message: str,
    ) -> None:
        try:
            (
                self.dynamodb_service
                .update_item(
                    table_name=(
                        self.table_name
                    ),
                    key={
                        "ingestion_id": {
                            "S": (
                                claim.ingestion_id
                            ),
                        },
                    },
                    update_expression=(
                        update_expression
                    ),
                    condition_expression=(
                        "#status = :processing "
                        "AND owner_token = "
                        ":owner_token"
                    ),
                    expression_attribute_names={
                        "#status": "status",
                    },
                    expression_attribute_values=(
                        values
                    ),
                    return_values="NONE",
                )
            )
        except ClientError as exception:
            if self._is_conditional_failure(
                exception
            ):
                raise ProcessingClaimLostError(
                    "The Ingestion processing "
                    "claim is no longer owned by "
                    "this worker."
                ) from exception

            raise ProcessingRegistryWriteError(
                failure_message
            ) from exception

        except BotoCoreError as exception:
            raise ProcessingRegistryWriteError(
                failure_message
            ) from exception

    @staticmethod
    def _deserialize_item(
        item: dict[
            str,
            dict[str, Any],
        ],
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}

        for (
            field_name,
            field_value,
        ) in item.items():
            if not isinstance(
                field_value,
                dict,
            ):
                continue

            if "S" in field_value:
                result[field_name] = (
                    field_value["S"]
                )
            elif "N" in field_value:
                number_value = (
                    field_value["N"]
                )

                try:
                    result[field_name] = int(
                        number_value
                    )
                except ValueError:
                    result[field_name] = float(
                        number_value
                    )
            elif "BOOL" in field_value:
                result[field_name] = (
                    field_value["BOOL"]
                )
            elif (
                field_value.get("NULL")
                is True
            ):
                result[field_name] = None
            else:
                result[field_name] = (
                    field_value
                )

        return result

    def _now_epoch(
        self,
    ) -> int:
        return int(
            self._clock()
        )

    @staticmethod
    def _to_timestamp(
        epoch_seconds: int,
    ) -> str:
        return datetime.fromtimestamp(
            epoch_seconds,
            tz=timezone.utc,
        ).isoformat()

    @staticmethod
    def _is_conditional_failure(
        exception: ClientError,
    ) -> bool:
        return (
            exception.response
            .get(
                "Error",
                {},
            )
            .get(
                "Code"
            )
            == (
                "ConditionalCheckFailedException"
            )
        )

    @staticmethod
    def _validate_claim(
        claim: ProcessingClaim,
    ) -> None:
        if not isinstance(
            claim,
            ProcessingClaim,
        ):
            raise TypeError(
                "claim must be a ProcessingClaim."
            )

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

        value = value.strip()

        if not value:
            raise ValueError(
                f"{field_name} must not be blank."
            )

        return value

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

        value = value.strip()

        if not value:
            raise ValueError(
                f"{field_name} must not be blank "
                "when supplied."
            )

        return value

    @staticmethod
    def _validate_positive_integer(
        *,
        value: int,
        field_name: str,
    ) -> None:
        if (
            not isinstance(
                value,
                int,
            )
            or isinstance(
                value,
                bool,
            )
        ):
            raise TypeError(
                f"{field_name} must be an integer."
            )

        if value <= 0:
            raise ValueError(
                f"{field_name} must be greater "
                "than zero."
            )

    @staticmethod
    def _validate_nonnegative_integer(
        *,
        value: int,
        field_name: str,
    ) -> None:
        if (
            not isinstance(
                value,
                int,
            )
            or isinstance(
                value,
                bool,
            )
        ):
            raise TypeError(
                f"{field_name} must be an integer."
            )

        if value < 0:
            raise ValueError(
                f"{field_name} must be zero or "
                "greater."
            )