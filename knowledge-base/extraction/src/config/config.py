import os

environment = os.getenv("ENVIRONMENT","dev")
pages_to_read = os.getenv("PAGES_TO_READ","all")
min_words_per_page = int(os.getenv("MIN_WORDS_PER_PAGE","20"))
min_quality_score = float(os.getenv("MIN_QUALITY_SCORE", "0.6"))
canonical_document_bucket = os.getenv("CANONICAL_DOCUMENT_BUCKET","")
document_uploaded_queue_url = os.getenv("DOCUMENT_UPLOADED_QUEUE_URL","")
processing_schema_version = os.getenv("PROCESSING_SCHEMA_VERSION", "extraction-v1")
sqs_visibility_extension_seconds = int(os.getenv("SQS_VISIBILITY_EXTENSION_SECONDS", "600"))
sqs_visibility_heartbeat_seconds = int(os.getenv("SQS_VISIBILITY_HEARTBEAT_SECONDS", "180"))
processing_registry_table = os.getenv("PROCESSING_REGISTRY_TABLE", "")
processing_claim_lease_seconds = int(os.getenv("PROCESSING_CLAIM_LEASE_SECONDS", "1800"))
processing_claim_heartbeat_seconds = int(os.getenv("PROCESSING_CLAIM_HEARTBEAT_SECONDS", "300"))

def validate_runtime_config() -> None:
    """
    Validate configuration required to run
    the extraction worker.
    """

    missing_settings = []

    if not canonical_document_bucket:
        missing_settings.append("CANONICAL_DOCUMENT_BUCKET")

    if not document_uploaded_queue_url:
        missing_settings.append("DOCUMENT_UPLOADED_QUEUE_URL")

    if not processing_registry_table:
        missing_settings.append("PROCESSING_REGISTRY_TABLE")

    if missing_settings:
        settings = ", ".join(missing_settings)

        raise RuntimeError(
            "Missing required environment "
            f"configuration: {settings}"
        )

    if min_words_per_page < 0:
        raise ValueError(
            "MIN_WORDS_PER_PAGE must be "
            "zero or greater."
        )

    if not (
        0.0
        <= min_quality_score
        <= 1.0
    ):
        raise ValueError(
            "MIN_QUALITY_SCORE must be "
            "between 0.0 and 1.0."
        )

    if (
        sqs_visibility_extension_seconds
        <= 0
    ):
        raise ValueError(
            "SQS_VISIBILITY_EXTENSION_SECONDS "
            "must be greater than zero."
        )

    if sqs_visibility_extension_seconds > 43200 :
        raise ValueError(
            "SQS_VISIBILITY_EXTENSION_SECONDS "
            "cannot exceed 43200 seconds."
        )

    if sqs_visibility_heartbeat_seconds <= 0 :
        raise ValueError(
            "SQS_VISIBILITY_HEARTBEAT_SECONDS "
            "must be greater than zero."
        )

    if sqs_visibility_heartbeat_seconds >= sqs_visibility_extension_seconds :
        raise ValueError(
            "SQS_VISIBILITY_HEARTBEAT_SECONDS "
            "must be less than "
            "SQS_VISIBILITY_EXTENSION_SECONDS."
        )

    if not processing_schema_version.strip():
        raise ValueError(
            "PROCESSING_SCHEMA_VERSION must "
            "not be empty."
        )

    if processing_claim_lease_seconds <= 0:
        raise ValueError(
            "PROCESSING_CLAIM_LEASE_SECONDS "
            "must be greater than zero."
            )

    if (
        processing_claim_lease_seconds
        <= sqs_visibility_extension_seconds
    ):
        raise ValueError(
            "PROCESSING_CLAIM_LEASE_SECONDS "
            "must be greater than "
            "SQS_VISIBILITY_EXTENSION_SECONDS."
        )

    if processing_claim_heartbeat_seconds <= 0:
        raise ValueError(
            "PROCESSING_CLAIM_HEARTBEAT_SECONDS "
            "must be greater than zero."
        )

    if (
        processing_claim_heartbeat_seconds
        >= processing_claim_lease_seconds
    ):
        raise ValueError(
            "PROCESSING_CLAIM_HEARTBEAT_SECONDS "
            "must be less than "
            "PROCESSING_CLAIM_LEASE_SECONDS."
        )

    if pages_to_read.lower() != "all":
        try:
            page_limit = int(
                pages_to_read
            )

        except ValueError as exception:
            raise ValueError(
                "PAGES_TO_READ must be "
                "'all' or a positive integer."
            ) from exception

        if page_limit < 1:
            raise ValueError(
                "PAGES_TO_READ must be "
                "'all' or a positive integer."
            )


study_document_types = {
    "protocols": "PROTOCOL",
    "monitoring": "MONITORING",
    "csr": "CSR",
    "sap": "SAP",
    "ib": "IB",
    "tmf": "TMF",
}


shared_document_types = {
    "sop": "SOP",
    "regulations": "REGULATION",
    "guidances": "GUIDANCE",
    "templates": "TEMPLATE",
}
