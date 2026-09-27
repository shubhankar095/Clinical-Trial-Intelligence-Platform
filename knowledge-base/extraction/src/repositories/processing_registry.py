import time

from dataclasses import dataclass
from uuid import uuid4

from botocore.exceptions import (
    ClientError,
)

from aws_utils.dynamodb import (
    DynamoDBService,
)
from exceptions.processing_claim import (
    ProcessingClaimLostError,
    ProcessingClaimUnavailableError,
)
from models.document import (
    ClinicalDocument,
)
from utils.logger import get_logger


logger = get_logger(__name__)


@dataclass(frozen=True)
class ProcessingClaim:
    document_id: str
    owner_token: str
    lease_expires_at: int


class ProcessingRegistry:

    def __init__(
        self,
        table_name: str,
        lease_seconds: int,
        dynamodb_service=None,
    ):
        if not table_name.strip():
            raise ValueError(
                "Processing registry table "
                "name must not be empty."
            )

        if lease_seconds <= 0:
            raise ValueError(
                "Processing claim lease "
                "must be greater than zero."
            )

        self.table_name = table_name
        self.lease_seconds = (
            lease_seconds
        )

        self.dynamodb = (
            dynamodb_service
            or DynamoDBService()
        )

    def _key(
        self,
        document_id: str,
    ) -> dict:
        return {
            "document_id": {
                "S": document_id,
            },
        }

    def _is_conditional_failure(
        self,
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
            == "ConditionalCheckFailedException"
        )

    def acquire(
        self,
        document: ClinicalDocument,
    ) -> ProcessingClaim:
        now = int(
            time.time()
        )

        lease_expires_at = (
            now
            + self.lease_seconds
        )

        owner_token = str(
            uuid4()
        )

        item = {
            "document_id": {
                "S": document.document_id,
            },
            "owner_token": {
                "S": owner_token,
            },
            "status": {
                "S": "PROCESSING",
            },
            "source_bucket": {
                "S": document.source_bucket,
            },
            "source_key": {
                "S": document.source_key,
            },
            "source_version_id": {
                "S": (
                    document.source_version_id
                ),
            },
            "processing_schema_version": {
                "S": (
                    document
                    .processing_schema_version
                ),
            },
            "claimed_at": {
                "N": str(
                    now
                ),
            },
            "updated_at": {
                "N": str(
                    now
                ),
            },
            "lease_expires_at": {
                "N": str(
                    lease_expires_at
                ),
            },
            "ttl": {
                "N": str(
                    lease_expires_at
                    + 86400
                ),
            },
        }

        try:
            self.dynamodb.put_item(
                table_name=self.table_name,
                item=item,
                condition_expression=(
                    "attribute_not_exists("
                    "#document_id"
                    ") OR "
                    "#lease_expires_at < :now"
                ),
                expression_attribute_names={
                    "#document_id": (
                        "document_id"
                    ),
                    "#lease_expires_at": (
                        "lease_expires_at"
                    ),
                },
                expression_attribute_values={
                    ":now": {
                        "N": str(
                            now
                        ),
                    },
                },
            )

        except ClientError as exception:
            if self._is_conditional_failure(
                exception
            ):
                logger.info(
                    "Processing claim is "
                    "currently owned by another "
                    "worker.",
                    extra={
                        "event": (
                            "processing_claim_"
                            "unavailable"
                        ),
                        "document_id": (
                            document.document_id
                        ),
                    },
                )

                raise (
                    ProcessingClaimUnavailableError(
                        "A different worker owns "
                        "an active processing claim "
                        f"for document "
                        f"{document.document_id}."
                    )
                ) from exception

            raise

        logger.info(
            "Processing claim acquired.",
            extra={
                "event": (
                    "processing_claim_acquired"
                ),
                "document_id": (
                    document.document_id
                ),
                "lease_expires_at": (
                    lease_expires_at
                ),
            },
        )

        return ProcessingClaim(
            document_id=(
                document.document_id
            ),
            owner_token=owner_token,
            lease_expires_at=(
                lease_expires_at
            ),
        )

    def renew(
        self,
        claim: ProcessingClaim,
    ) -> ProcessingClaim:
        """
        Extend an active processing claim owned by
        the supplied worker token.
        """
        now = int(time.time())

        lease_expires_at = (
            now
            + self.lease_seconds
        )

        try:
            self.dynamodb.update_item(
                table_name=self.table_name,
                key=self._key(
                    claim.document_id
                ),
                update_expression=(
                    "SET #lease_expires_at = "
                    ":lease_expires_at, "
                    "#updated_at = :now, "
                    "#ttl = :ttl"
                ),
                condition_expression=(
                    "#owner_token = :owner_token "
                    "AND #status = :processing "
                    "AND #lease_expires_at >= :now"
                ),
                expression_attribute_names={
                    "#owner_token": (
                        "owner_token"
                    ),
                    "#status": "status",
                    "#lease_expires_at": (
                        "lease_expires_at"
                    ),
                    "#updated_at": (
                        "updated_at"
                    ),
                    "#ttl": "ttl",
                },
                expression_attribute_values={
                    ":owner_token": {
                        "S": claim.owner_token,
                    },
                    ":processing": {
                        "S": "PROCESSING",
                    },
                    ":lease_expires_at": {
                        "N": str(
                            lease_expires_at
                        ),
                    },
                    ":now": {
                        "N": str(
                            now
                        ),
                    },
                    ":ttl": {
                        "N": str(
                            lease_expires_at
                            + 86400
                        ),
                    },
                },
            )

        except ClientError as exception:
            if self._is_conditional_failure(
                exception
            ):
                raise ProcessingClaimLostError(
                    "Processing claim ownership was lost "
                    "or the claim expired before renewal."
                ) from exception

            raise

        logger.info(
            "Processing claim renewed.",
            extra={
                "event": (
                    "processing_claim_renewed"
                ),
                "document_id": (
                    claim.document_id
                ),
                "lease_expires_at": (
                    lease_expires_at
                ),
            },
        )

        return ProcessingClaim(
            document_id=(
                claim.document_id
            ),
            owner_token=(
                claim.owner_token
            ),
            lease_expires_at=(
                lease_expires_at
            ),
        )

    def mark_completed(
        self,
        claim: ProcessingClaim,
        canonical_key: str,
    ) -> None:
        now = int(
            time.time()
        )

        try:
            self.dynamodb.update_item(
                table_name=self.table_name,
                key=self._key(
                    claim.document_id
                ),
                update_expression=(
                    "SET #status = :completed, "
                    "#canonical_key = :canonical_key, "
                    "#updated_at = :now, "
                    "#completed_at = :now, "
                    "#ttl = :ttl "
                    "REMOVE #lease_expires_at"
                ),
                condition_expression=(
                    "#owner_token = :owner_token "
                    "AND #status = :processing "
                    "AND #lease_expires_at >= :now"
                ),
                expression_attribute_names={
                    "#status": "status",
                    "#owner_token": (
                        "owner_token"
                    ),
                    "#canonical_key": (
                        "canonical_key"
                    ),
                    "#updated_at": (
                        "updated_at"
                    ),
                    "#completed_at": (
                        "completed_at"
                    ),
                    "#ttl": "ttl",
                    "#lease_expires_at": (
                        "lease_expires_at"
                    ),
                },
                expression_attribute_values={
                    ":completed": {
                        "S": "COMPLETED",
                    },
                    ":processing": {
                        "S": "PROCESSING",
                    },
                    ":owner_token": {
                        "S": claim.owner_token,
                    },
                    ":canonical_key": {
                        "S": canonical_key,
                    },
                    ":now": {
                        "N": str(
                            now
                        ),
                    },
                    ":ttl": {
                        "N": str(
                            now
                            + 2592000
                        ),
                    },
                },
            )

        except ClientError as exception:
            if self._is_conditional_failure(
                exception
            ):
                raise ProcessingClaimLostError(
                    "Processing claim ownership was lost "
                    "or the claim expired before completion."
                ) from exception

            raise

        logger.info(
            "Processing claim marked complete.",
            extra={
                "event": (
                    "processing_claim_completed"
                ),
                "document_id": (
                    claim.document_id
                ),
                "canonical_key": canonical_key,
            },
        )

    def release(
        self,
        claim: ProcessingClaim,
    ) -> None:
        try:
            self.dynamodb.delete_item(
                table_name=self.table_name,
                key=self._key(
                    claim.document_id
                ),
                condition_expression=(
                    "#owner_token = :owner_token "
                    "AND #status = :processing"
                ),
                expression_attribute_names={
                    "#owner_token": (
                        "owner_token"
                    ),
                    "#status": "status",
                },
                expression_attribute_values={
                    ":owner_token": {
                        "S": claim.owner_token,
                    },
                    ":processing": {
                        "S": "PROCESSING",
                    },
                },
            )

        except ClientError as exception:
            if self._is_conditional_failure(
                exception
            ):
                logger.warning(
                    "Processing claim could not "
                    "be released because this "
                    "worker no longer owns it.",
                    extra={
                        "event": (
                            "processing_claim_"
                            "release_skipped"
                        ),
                        "document_id": (
                            claim.document_id
                        ),
                    },
                )

                return

            raise

        logger.info(
            "Processing claim released.",
            extra={
                "event": (
                    "processing_claim_released"
                ),
                "document_id": (
                    claim.document_id
                ),
            },
        )