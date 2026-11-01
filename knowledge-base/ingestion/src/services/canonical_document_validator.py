import math
import re
from utils.logger import get_logger
from exceptions.canonical_document import (
    CanonicalDocumentContentError,
    CanonicalDocumentFieldError,
    CanonicalDocumentIdentityMismatchError,
    EmptyCanonicalDocumentError,
    UnsupportedCanonicalSchemaError,
)
from models.canonical_document import (
    CanonicalDocument,
)
from models.extraction_manifest import (
    ExtractionSuccessManifest,
)

logger = get_logger(__name__)

class CanonicalDocumentValidator:
    """
    Validate a canonical extraction-v1 document
    against its authoritative success manifest.
    """

    SUPPORTED_PROCESSING_SCHEMA = (
        "extraction-v1"
    )

    SUCCESS_STATUS = "SUCCESS"

    DOCUMENT_ID_PATTERN = re.compile(
        r"^[0-9a-f]{64}$"
    )

    SUPPORTED_EXTRACTION_METHODS = {
        "TEXT",
        "OCR",
    }

    def validate(
        self,
        document: CanonicalDocument,
        manifest: ExtractionSuccessManifest,
    ) -> CanonicalDocument:
        if not isinstance(
            document,
            CanonicalDocument,
        ):
            raise TypeError(
                "document must be a "
                "CanonicalDocument."
            )

        if not isinstance(
            manifest,
            ExtractionSuccessManifest,
        ):
            raise TypeError(
                "manifest must be an "
                "ExtractionSuccessManifest."
            )

        self._validate_schema(
            document
        )

        self._validate_status(
            document
        )

        self._validate_identity(
            document=document,
            manifest=manifest,
        )

        self._validate_document_id(
            document.document_id
        )

        self._validate_content(
            document
        )

        self._validate_pages(
            document
        )

        self._validate_counts(
            document
        )

        self._validate_images(
            document
        )

        self._validate_tables(
            document
        )

        return document

    def _validate_schema(
        self,
        document: CanonicalDocument,
    ) -> None:
        if (
            document.processing_schema_version
            != self.SUPPORTED_PROCESSING_SCHEMA
        ):
            raise UnsupportedCanonicalSchemaError(
                "Unsupported canonical document "
                "processing schema "
                f"'{document.processing_schema_version}'."
            )

    def _validate_status(
        self,
        document: CanonicalDocument,
    ) -> None:
        if (
            document.processing_status
            != self.SUCCESS_STATUS
        ):
            raise CanonicalDocumentFieldError(
                "Canonical document "
                "processing_status must be "
                "exactly 'SUCCESS'."
            )

        if document.error_message is not None:
            raise CanonicalDocumentContentError(
                "Successful canonical document "
                "must not contain an error_message."
            )

    def _validate_identity(
        self,
        document: CanonicalDocument,
        manifest: ExtractionSuccessManifest,
    ) -> None:
        expected_identity = {
            "document_id": (
                manifest.document_id
            ),
            "source_bucket": (
                manifest.source_bucket
            ),
            "source_key": (
                manifest.source_key
            ),
            "source_version_id": (
                manifest.source_version_id
            ),
            "processing_schema_version": (
                manifest
                .processing_schema_version
            ),
            "canonical_bucket": (
                manifest.canonical_bucket
            ),
            "canonical_key": (
                manifest.canonical_key
            ),
            "processing_status": (
                manifest.processing_status
            ),
        }

        actual_identity = {
            "document_id": (
                document.document_id
            ),
            "source_bucket": (
                document.source_bucket
            ),
            "source_key": (
                document.source_key
            ),
            "source_version_id": (
                document.source_version_id
            ),
            "processing_schema_version": (
                document
                .processing_schema_version
            ),
            "canonical_bucket": (
                document.canonical_bucket
            ),
            "canonical_key": (
                document.canonical_key
            ),
            "processing_status": (
                document.processing_status
            ),
        }

        if actual_identity != expected_identity:
            mismatched_fields = sorted(
                field_name
                for field_name
                in expected_identity
                if (
                    actual_identity[field_name]
                    != expected_identity[
                        field_name
                    ]
                )
            )

            raise (
                CanonicalDocumentIdentityMismatchError(
                    "Canonical document identity "
                    "does not match the extraction "
                    "success manifest. Mismatched "
                    "fields: "
                    f"{', '.join(mismatched_fields)}."
                )
            )

    def _validate_document_id(
        self,
        document_id: str,
    ) -> None:
        if not self.DOCUMENT_ID_PATTERN.fullmatch(
            document_id
        ):
            raise CanonicalDocumentFieldError(
                "Canonical document document_id "
                "must be a 64-character lowercase "
                "SHA-256 hexadecimal value."
            )

    def _validate_content(
        self,
        document: CanonicalDocument,
    ) -> None:
        if not document.raw_text.strip():
            raise EmptyCanonicalDocumentError(
                "Canonical document contains no "
                "usable extracted text."
            )

        if not document.file_name.strip():
            raise CanonicalDocumentFieldError(
                "Canonical document file_name "
                "must not be blank."
            )

        if not document.file_format.strip():
            raise CanonicalDocumentFieldError(
                "Canonical document file_format "
                "must not be blank."
            )

        if document.file_format.lower() != "pdf":
            raise CanonicalDocumentFieldError(
                "Canonical document file_format "
                "must be 'pdf' for extraction-v1."
            )

    def _validate_pages(
        self,
        document: CanonicalDocument,
    ) -> None:
        if not document.pages:
            raise CanonicalDocumentContentError(
                "Canonical document must contain "
                "at least one page."
            )

        raw_text_length = len(
            document.raw_text
        )

        previous_end_offset = None

        for expected_page_number, page in enumerate(
            document.pages,
            start=1,
        ):
            if (
                page.page_number
                != expected_page_number
            ):
                raise CanonicalDocumentContentError(
                    "Canonical page numbers must "
                    "begin at 1 and remain "
                    "contiguous."
                )

            if page.start_offset < 0:
                raise CanonicalDocumentContentError(
                    "Canonical page start_offset "
                    "must not be negative."
                )

            if (
                page.end_offset
                < page.start_offset
            ):
                raise CanonicalDocumentContentError(
                    "Canonical page end_offset "
                    "must be greater than or equal "
                    "to start_offset."
                )

            if page.end_offset > raw_text_length:
                raise CanonicalDocumentContentError(
                    "Canonical page end_offset "
                    "exceeds raw_text length."
                )

            if (
                previous_end_offset is not None
                and page.start_offset
                < previous_end_offset
            ):
                raise CanonicalDocumentContentError(
                    "Canonical page offsets must "
                    "not overlap or move backward."
                )

            page_slice = document.raw_text[
                page.start_offset:
                page.end_offset
            ]

            if page_slice != page.text:
                logger.warning(
                    "Canonical page text differs "
                    "from its raw_text offset "
                    "slice.",
                    extra={
                        "event": (
                            "canonical_page_text_"
                            "mismatch"
                        ),
                        "document_id": (
                            document.document_id
                        ),
                        "page_number": (
                            page.page_number
                        ),
                        "start_offset": (
                            page.start_offset
                        ),
                        "end_offset": (
                            page.end_offset
                        ),
                        "page_text_length": len(
                            page.text
                        ),
                        "raw_text_slice_length": (
                            len(page_slice)
                        ),
                    },
                )

            expected_word_count = len(
                page.text.split()
            )

            if (
                page.word_count
                != expected_word_count
            ):
                logger.warning(
                    "Canonical page word count "
                    "differs from the ingestion "
                    "calculation.",
                    extra={
                        "event": (
                            "canonical_page_word_"
                            "count_mismatch"
                        ),
                        "document_id": (
                            document.document_id
                        ),
                        "page_number": (
                            page.page_number
                        ),
                        "declared_word_count": (
                            page.word_count
                        ),
                        "calculated_word_count": (
                            expected_word_count
                        ),
                    },
                )

            if not math.isfinite(
                page.quality_score
            ):
                raise CanonicalDocumentContentError(
                    "Canonical page quality_score "
                    "must be finite."
                )

            if not (
                0.0
                <= page.quality_score
                <= 1.0
            ):
                logger.warning(
                    "Canonical page quality score "
                    "is outside the expected range.",
                    extra={
                        "event": (
                            "canonical_page_quality_"
                            "score_out_of_range"
                        ),
                        "document_id": (
                            document.document_id
                        ),
                        "page_number": (
                            page.page_number
                        ),
                        "quality_score": (
                            page.quality_score
                        ),
                        "expected_minimum": 0.0,
                        "expected_maximum": 1.0,
                    },
                )

            if (
                page.extraction_method
                not in self
                .SUPPORTED_EXTRACTION_METHODS
            ):
                raise CanonicalDocumentContentError(
                    "Canonical page contains an "
                    "unsupported extraction_method "
                    f"'{page.extraction_method}'."
                )

            expected_ocr_applied = (
                page.extraction_method
                == "OCR"
            )

            if (
                page.ocr_applied
                != expected_ocr_applied
            ):
                logger.warning(
                    "Canonical page OCR flag "
                    "differs from the expected "
                    "extraction-method behavior.",
                    extra={
                        "event": (
                            "canonical_page_ocr_"
                            "method_mismatch"
                        ),
                        "document_id": (
                            document.document_id
                        ),
                        "page_number": (
                            page.page_number
                        ),
                        "extraction_method": (
                            page.extraction_method
                        ),
                        "ocr_applied": (
                            page.ocr_applied
                        ),
                    },
                )
            
            previous_end_offset = page.end_offset

    def _validate_counts(
        self,
        document: CanonicalDocument,
    ) -> None:
        if document.page_count < 0:
            raise CanonicalDocumentContentError(
                "Canonical page_count must not "
                "be negative."
            )

        if document.ocr_page_count < 0:
            raise CanonicalDocumentContentError(
                "Canonical ocr_page_count must "
                "not be negative."
            )

        if document.image_count < 0:
            raise CanonicalDocumentContentError(
                "Canonical image_count must not "
                "be negative."
            )

        if document.table_count < 0:
            raise CanonicalDocumentContentError(
                "Canonical table_count must not "
                "be negative."
            )

        if (
            document.page_count
            != len(document.pages)
        ):
            raise CanonicalDocumentContentError(
                "Canonical page_count does not "
                "match the number of pages."
            )

        expected_ocr_page_count = sum(
            1
            for page in document.pages
            if page.ocr_applied
        )

        if (
            document.ocr_page_count
            != expected_ocr_page_count
        ):
            raise CanonicalDocumentContentError(
                "Canonical ocr_page_count does "
                "not match pages with OCR applied."
            )

        if (
            document.image_count
            != len(document.images)
        ):
            raise CanonicalDocumentContentError(
                "Canonical image_count does not "
                "match the number of images."
            )

        if (
            document.table_count
            != len(document.tables)
        ):
            raise CanonicalDocumentContentError(
                "Canonical table_count does not "
                "match the number of tables."
            )

    def _validate_images(
        self,
        document: CanonicalDocument,
    ) -> None:
        page_numbers = {
            page.page_number
            for page in document.pages
        }

        image_ids = set()
        image_keys = set()

        for image in document.images:
            if image.image_id in image_ids:
                raise CanonicalDocumentContentError(
                    "Canonical image IDs must "
                    "be unique."
                )

            if image.s3_key in image_keys:
                raise CanonicalDocumentContentError(
                    "Canonical image S3 keys must "
                    "be unique."
                )

            if (
                image.page_number
                not in page_numbers
            ):
                raise CanonicalDocumentContentError(
                    "Canonical image references "
                    "an unknown page."
                )

            if (
                image.width <= 0
                or image.height <= 0
            ):
                raise CanonicalDocumentContentError(
                    "Canonical image dimensions "
                    "must be greater than zero."
                )

            image_ids.add(
                image.image_id
            )

            image_keys.add(
                image.s3_key
            )

    def _validate_tables(
        self,
        document: CanonicalDocument,
    ) -> None:
        page_numbers = {
            page.page_number
            for page in document.pages
        }

        table_ids = set()
        table_keys = set()

        for table in document.tables:
            if table.table_id in table_ids:
                raise CanonicalDocumentContentError(
                    "Canonical table IDs must "
                    "be unique."
                )

            if table.s3_key in table_keys:
                raise CanonicalDocumentContentError(
                    "Canonical table S3 keys must "
                    "be unique."
                )

            if (
                table.page_number
                not in page_numbers
            ):
                raise CanonicalDocumentContentError(
                    "Canonical table references "
                    "an unknown page."
                )

            if table.row_count < 0:
                raise CanonicalDocumentContentError(
                    "Canonical table row_count "
                    "must not be negative."
                )

            if table.column_count < 0:
                raise CanonicalDocumentContentError(
                    "Canonical table column_count "
                    "must not be negative."
                )

            table_ids.add(
                table.table_id
            )

            table_keys.add(
                table.s3_key
            )