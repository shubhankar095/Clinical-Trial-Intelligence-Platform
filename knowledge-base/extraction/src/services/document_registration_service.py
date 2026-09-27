from pathlib import Path

from config.config import (
    processing_schema_version,
    shared_document_types,
    study_document_types,
)

from models.document import (
    ClinicalDocument,
    DocumentMetadata,
)
from services.document_identity_service import (
    DocumentIdentityService,
)
from utils.logger import get_logger


logger = get_logger(__name__)


class DocumentRegistrationService:

    def __init__(
        self,
        identity_service=None,
    ):
        self.identity_service = (
            identity_service
            or DocumentIdentityService()
        )

    def register(
        self,
        bucket_name: str,
        object_key: str,
        version_id: str,
        s3_metadata: dict,
    ) -> ClinicalDocument:
        self._validate_path(
            object_key
        )

        if not version_id:
            raise ValueError(
                "S3 source version ID is "
                "required for document "
                "registration."
            )

        logger.info(
            f"Validated document path: "
            f"{object_key}"
        )

        file_name = Path(
            object_key
        ).name

        file_format = (
            Path(
                object_key
            )
            .suffix
            .replace(
                ".",
                "",
            )
            .lower()
        )

        path_metadata = (
            self._extract_metadata_from_path(
                object_key
            )
        )

        metadata = DocumentMetadata(
            study_id=(
                s3_metadata.get(
                    "study_id"
                )
                or path_metadata[
                    "study_id"
                ]
            ),
            document_type=(
                s3_metadata.get(
                    "document_type"
                )
                or path_metadata[
                    "document_type"
                ]
            ),
            version=s3_metadata.get(
                "version"
            ),
            sponsor=s3_metadata.get(
                "sponsor"
            ),
            phase=s3_metadata.get(
                "phase"
            ),
        )

        document_id = (
            self.identity_service
            .create_document_id(
                source_bucket=(
                    bucket_name
                ),
                source_key=object_key,
                source_version_id=(
                    version_id
                ),
                processing_schema_version=(
                    processing_schema_version
                ),
            )
        )

        logger.info(
            "Derived document identity "
            "and metadata.",
            extra={
                "event": (
                    "document_registered"
                ),
                "document_id": (
                    document_id
                ),
                "source_bucket": (
                    bucket_name
                ),
                "source_key": object_key,
                "source_version_id": (
                    version_id
                ),
                "processing_schema_version": (
                    processing_schema_version
                ),
                "study_id": (
                    metadata.study_id
                ),
                "document_type": (
                    metadata.document_type
                ),
            },
        )

        return ClinicalDocument(
            document_id=document_id,
            file_name=file_name,
            file_format=file_format,
            source_bucket=bucket_name,
            source_key=object_key,
            source_version_id=(
                version_id
            ),
            processing_schema_version=(
                processing_schema_version
            ),
            metadata=metadata,
        )

    def _extract_metadata_from_path(
        self,
        object_key: str,
    ) -> dict:
        path_parts = (
            object_key.split("/")
        )

        metadata = {
            "study_id": None,
            "document_type": None,
        }

        if len(path_parts) < 3:
            return metadata

        root_folder = path_parts[0]

        if root_folder != "documents":
            return metadata

        second_level = path_parts[1]
        category = (
            path_parts[2].lower()
        )

        if (
            second_level.lower()
            == "shared"
        ):
            metadata[
                "document_type"
            ] = (
                shared_document_types
                .get(
                    category
                )
            )

        else:
            metadata[
                "study_id"
            ] = (
                second_level.upper()
            )

            metadata[
                "document_type"
            ] = (
                study_document_types
                .get(
                    category
                )
            )

        return metadata

    def _validate_path(
        self,
        object_key: str,
    ) -> None:
        path_parts = (
            object_key.split("/")
        )

        if len(path_parts) < 4:
            raise ValueError(
                f"Invalid document path: "
                f"'{object_key}'. "
                f"Expected structure: "
                f"documents/<study>/"
                f"<document-type>/file"
            )

        if any(
            not path_part.strip()
            for path_part
            in path_parts[:4]
        ):
            raise ValueError(
                f"Invalid document path: "
                f"'{object_key}'. "
                f"Path components cannot "
                f"be empty."
            )

        file_name = path_parts[-1]

        if not Path(
            file_name
        ).suffix:
            raise ValueError(
                f"Invalid document file: "
                f"'{file_name}'. "
                f"A file extension is "
                f"required."
            )

        if (
            path_parts[0]
            != "documents"
        ):
            raise ValueError(
                f"Invalid root folder in "
                f"'{object_key}'. "
                f"Expected 'documents/'."
            )

        if (
            path_parts[1].lower()
            == "shared"
        ):
            if (
                path_parts[2].lower()
                not in shared_document_types
            ):
                raise ValueError(
                    f"Unsupported shared "
                    f"document category "
                    f"'{path_parts[2]}'."
                )

        else:
            if (
                path_parts[2].lower()
                not in study_document_types
            ):
                raise ValueError(
                    f"Unsupported study "
                    f"document category "
                    f"'{path_parts[2]}'."
                )