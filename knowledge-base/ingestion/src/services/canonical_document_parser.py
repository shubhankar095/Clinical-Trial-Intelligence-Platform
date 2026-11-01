import json

from json import JSONDecodeError
from typing import Any

from exceptions.canonical_document import (
    CanonicalDocumentFieldError,
    CanonicalDocumentJsonError,
)
from models.canonical_document import (
    CanonicalDocument,
    CanonicalDocumentImage,
    CanonicalDocumentMetadata,
    CanonicalDocumentPage,
    CanonicalDocumentTable,
)


class CanonicalDocumentParser:
    """
    Parse extraction-v1 canonical-document JSON
    into immutable typed models.

    This parser validates JSON structure and field
    types. Cross-field and business-contract
    validation belongs in CanonicalDocumentValidator.
    """

    DOCUMENT_STRING_FIELDS = (
        "document_id",
        "file_name",
        "file_format",
        "source_bucket",
        "source_key",
        "source_version_id",
        "canonical_bucket",
        "canonical_key",
        "processing_schema_version",
        "processing_status",
    )

    DOCUMENT_INTEGER_FIELDS = (
        "page_count",
        "ocr_page_count",
        "image_count",
        "table_count",
    )

    DOCUMENT_LIST_FIELDS = (
        "pages",
        "images",
        "tables",
        "warnings",
    )

    DOCUMENT_KNOWN_FIELDS = frozenset(
        {
            *DOCUMENT_STRING_FIELDS,
            *DOCUMENT_INTEGER_FIELDS,
            *DOCUMENT_LIST_FIELDS,
            "metadata",
            "raw_text",
            "already_processed",
            "error_message",
        }
    )

    METADATA_FIELDS = frozenset(
        {
            "study_id",
            "document_type",
            "version",
            "sponsor",
            "phase",
        }
    )

    PAGE_FIELDS = frozenset(
        {
            "page_number",
            "text",
            "start_offset",
            "end_offset",
            "word_count",
            "quality_score",
            "requires_ocr",
            "ocr_applied",
            "extraction_method",
        }
    )

    IMAGE_FIELDS = frozenset(
        {
            "image_id",
            "page_number",
            "extension",
            "s3_key",
            "width",
            "height",
        }
    )

    TABLE_FIELDS = frozenset(
        {
            "table_id",
            "page_number",
            "s3_key",
            "row_count",
            "column_count",
            "title",
        }
    )

    def parse(
        self,
        document_text: str,
    ) -> CanonicalDocument:
        """
        Parse canonical-document JSON into a typed
        immutable domain object.
        """
        if not isinstance(
            document_text,
            str,
        ):
            raise CanonicalDocumentJsonError(
                "Canonical document content "
                "must be text."
            )

        try:
            payload = json.loads(
                document_text
            )

        except JSONDecodeError as exception:
            raise CanonicalDocumentJsonError(
                "Canonical document is not "
                "valid JSON."
            ) from exception

        if not isinstance(
            payload,
            dict,
        ):
            raise CanonicalDocumentJsonError(
                "Canonical document top-level "
                "JSON value must be an object."
            )

        string_fields = {
            field_name: (
                self._require_nonblank_string(
                    payload=payload,
                    field_name=field_name,
                    context="canonical document",
                )
            )
            for field_name
            in self.DOCUMENT_STRING_FIELDS
        }

        integer_fields = {
            field_name: (
                self._require_integer(
                    payload=payload,
                    field_name=field_name,
                    context="canonical document",
                )
            )
            for field_name
            in self.DOCUMENT_INTEGER_FIELDS
        }

        raw_text = self._require_string(
            payload=payload,
            field_name="raw_text",
            context="canonical document",
        )

        metadata_payload = self._require_object(
            payload=payload,
            field_name="metadata",
            context="canonical document",
        )

        metadata = self._parse_metadata(
            metadata_payload
        )

        pages_payload = self._require_list(
            payload=payload,
            field_name="pages",
            context="canonical document",
        )

        pages = tuple(
            self._parse_page(
                page_payload=page_payload,
                item_index=item_index,
            )
            for item_index, page_payload
            in enumerate(
                pages_payload,
                start=1,
            )
        )

        images_payload = self._require_list(
            payload=payload,
            field_name="images",
            context="canonical document",
        )

        images = tuple(
            self._parse_image(
                image_payload=image_payload,
                item_index=item_index,
            )
            for item_index, image_payload
            in enumerate(
                images_payload,
                start=1,
            )
        )

        tables_payload = self._require_list(
            payload=payload,
            field_name="tables",
            context="canonical document",
        )

        tables = tuple(
            self._parse_table(
                table_payload=table_payload,
                item_index=item_index,
            )
            for item_index, table_payload
            in enumerate(
                tables_payload,
                start=1,
            )
        )

        warnings_payload = self._require_list(
            payload=payload,
            field_name="warnings",
            context="canonical document",
        )

        warnings = tuple(
            self._parse_warning(
                warning=warning,
                item_index=item_index,
            )
            for item_index, warning
            in enumerate(
                warnings_payload,
                start=1,
            )
        )

        already_processed = (
            self._require_boolean(
                payload=payload,
                field_name=(
                    "already_processed"
                ),
                context="canonical document",
            )
        )

        error_message = (
            self._require_optional_string(
                payload=payload,
                field_name="error_message",
                context="canonical document",
            )
        )

        additional_fields = {
            key: value
            for key, value
            in payload.items()
            if (
                key
                not in self
                .DOCUMENT_KNOWN_FIELDS
            )
        }

        return CanonicalDocument(
            document_id=string_fields[
                "document_id"
            ],
            file_name=string_fields[
                "file_name"
            ],
            file_format=string_fields[
                "file_format"
            ],
            source_bucket=string_fields[
                "source_bucket"
            ],
            source_key=string_fields[
                "source_key"
            ],
            source_version_id=(
                string_fields[
                    "source_version_id"
                ]
            ),
            canonical_bucket=(
                string_fields[
                    "canonical_bucket"
                ]
            ),
            canonical_key=string_fields[
                "canonical_key"
            ],
            processing_schema_version=(
                string_fields[
                    "processing_schema_version"
                ]
            ),
            processing_status=(
                string_fields[
                    "processing_status"
                ]
            ),
            metadata=metadata,
            raw_text=raw_text,
            pages=pages,
            page_count=integer_fields[
                "page_count"
            ],
            ocr_page_count=integer_fields[
                "ocr_page_count"
            ],
            images=images,
            image_count=integer_fields[
                "image_count"
            ],
            tables=tables,
            table_count=integer_fields[
                "table_count"
            ],
            warnings=warnings,
            already_processed=(
                already_processed
            ),
            error_message=error_message,
            additional_fields=(
                additional_fields
            ),
        )

    def _parse_metadata(
        self,
        metadata_payload: dict[str, Any],
    ) -> CanonicalDocumentMetadata:
        """
        Parse nullable clinical metadata.
        """
        metadata_values = {
            field_name: (
                self._require_optional_string(
                    payload=metadata_payload,
                    field_name=field_name,
                    context=(
                        "canonical document "
                        "metadata"
                    ),
                )
            )
            for field_name
            in self.METADATA_FIELDS
        }

        additional_fields = {
            key: value
            for key, value
            in metadata_payload.items()
            if key not in self.METADATA_FIELDS
        }

        return CanonicalDocumentMetadata(
            study_id=metadata_values[
                "study_id"
            ],
            document_type=metadata_values[
                "document_type"
            ],
            version=metadata_values[
                "version"
            ],
            sponsor=metadata_values[
                "sponsor"
            ],
            phase=metadata_values[
                "phase"
            ],
            additional_fields=(
                additional_fields
            ),
        )

    def _parse_page(
        self,
        page_payload: Any,
        item_index: int,
    ) -> CanonicalDocumentPage:
        """
        Parse one canonical page.
        """
        context = (
            "canonical page "
            f"{item_index}"
        )

        if not isinstance(
            page_payload,
            dict,
        ):
            raise CanonicalDocumentFieldError(
                f"{context} must be an object."
            )

        additional_fields = {
            key: value
            for key, value
            in page_payload.items()
            if key not in self.PAGE_FIELDS
        }

        return CanonicalDocumentPage(
            page_number=self._require_integer(
                payload=page_payload,
                field_name="page_number",
                context=context,
            ),
            text=self._require_string(
                payload=page_payload,
                field_name="text",
                context=context,
            ),
            start_offset=(
                self._require_integer(
                    payload=page_payload,
                    field_name="start_offset",
                    context=context,
                )
            ),
            end_offset=self._require_integer(
                payload=page_payload,
                field_name="end_offset",
                context=context,
            ),
            word_count=self._require_integer(
                payload=page_payload,
                field_name="word_count",
                context=context,
            ),
            quality_score=(
                self._require_number(
                    payload=page_payload,
                    field_name="quality_score",
                    context=context,
                )
            ),
            requires_ocr=(
                self._require_boolean(
                    payload=page_payload,
                    field_name="requires_ocr",
                    context=context,
                )
            ),
            ocr_applied=(
                self._require_boolean(
                    payload=page_payload,
                    field_name="ocr_applied",
                    context=context,
                )
            ),
            extraction_method=(
                self._require_nonblank_string(
                    payload=page_payload,
                    field_name=(
                        "extraction_method"
                    ),
                    context=context,
                )
            ),
            additional_fields=(
                additional_fields
            ),
        )

    def _parse_image(
        self,
        image_payload: Any,
        item_index: int,
    ) -> CanonicalDocumentImage:
        """
        Parse one canonical image reference.
        """
        context = (
            "canonical image "
            f"{item_index}"
        )

        if not isinstance(
            image_payload,
            dict,
        ):
            raise CanonicalDocumentFieldError(
                f"{context} must be an object."
            )

        additional_fields = {
            key: value
            for key, value
            in image_payload.items()
            if key not in self.IMAGE_FIELDS
        }

        return CanonicalDocumentImage(
            image_id=(
                self._require_nonblank_string(
                    payload=image_payload,
                    field_name="image_id",
                    context=context,
                )
            ),
            page_number=(
                self._require_integer(
                    payload=image_payload,
                    field_name="page_number",
                    context=context,
                )
            ),
            extension=(
                self._require_nonblank_string(
                    payload=image_payload,
                    field_name="extension",
                    context=context,
                )
            ),
            s3_key=(
                self._require_nonblank_string(
                    payload=image_payload,
                    field_name="s3_key",
                    context=context,
                )
            ),
            width=self._require_integer(
                payload=image_payload,
                field_name="width",
                context=context,
            ),
            height=self._require_integer(
                payload=image_payload,
                field_name="height",
                context=context,
            ),
            additional_fields=(
                additional_fields
            ),
        )

    def _parse_table(
        self,
        table_payload: Any,
        item_index: int,
    ) -> CanonicalDocumentTable:
        """
        Parse one canonical table reference.
        """
        context = (
            "canonical table "
            f"{item_index}"
        )

        if not isinstance(
            table_payload,
            dict,
        ):
            raise CanonicalDocumentFieldError(
                f"{context} must be an object."
            )

        additional_fields = {
            key: value
            for key, value
            in table_payload.items()
            if key not in self.TABLE_FIELDS
        }

        return CanonicalDocumentTable(
            table_id=(
                self._require_nonblank_string(
                    payload=table_payload,
                    field_name="table_id",
                    context=context,
                )
            ),
            page_number=(
                self._require_integer(
                    payload=table_payload,
                    field_name="page_number",
                    context=context,
                )
            ),
            s3_key=(
                self._require_nonblank_string(
                    payload=table_payload,
                    field_name="s3_key",
                    context=context,
                )
            ),
            row_count=(
                self._require_integer(
                    payload=table_payload,
                    field_name="row_count",
                    context=context,
                )
            ),
            column_count=(
                self._require_integer(
                    payload=table_payload,
                    field_name="column_count",
                    context=context,
                )
            ),
            title=(
                self._require_optional_string(
                    payload=table_payload,
                    field_name="title",
                    context=context,
                )
            ),
            additional_fields=(
                additional_fields
            ),
        )

    def _parse_warning(
        self,
        warning: Any,
        item_index: int,
    ) -> str:
        """
        Parse one extraction warning.
        """
        if not isinstance(
            warning,
            str,
        ):
            raise CanonicalDocumentFieldError(
                "Canonical document warning "
                f"{item_index} must be a string."
            )

        normalized_warning = (
            warning.strip()
        )

        if not normalized_warning:
            raise CanonicalDocumentFieldError(
                "Canonical document warning "
                f"{item_index} must not be blank."
            )

        return normalized_warning

    def _require_object(
        self,
        payload: dict[str, Any],
        field_name: str,
        context: str,
    ) -> dict[str, Any]:
        value = self._require_field(
            payload=payload,
            field_name=field_name,
            context=context,
        )

        if not isinstance(
            value,
            dict,
        ):
            raise CanonicalDocumentFieldError(
                f"{context} field "
                f"'{field_name}' must be "
                "an object."
            )

        return value

    def _require_list(
        self,
        payload: dict[str, Any],
        field_name: str,
        context: str,
    ) -> list:
        value = self._require_field(
            payload=payload,
            field_name=field_name,
            context=context,
        )

        if not isinstance(
            value,
            list,
        ):
            raise CanonicalDocumentFieldError(
                f"{context} field "
                f"'{field_name}' must be "
                "a list."
            )

        return value

    def _require_string(
        self,
        payload: dict[str, Any],
        field_name: str,
        context: str,
    ) -> str:
        """
        Return exact text without trimming it.

        This is important for raw_text and page text
        because offsets depend on exact characters.
        """
        value = self._require_field(
            payload=payload,
            field_name=field_name,
            context=context,
        )

        if not isinstance(
            value,
            str,
        ):
            raise CanonicalDocumentFieldError(
                f"{context} field "
                f"'{field_name}' must be "
                "a string."
            )

        return value

    def _require_nonblank_string(
        self,
        payload: dict[str, Any],
        field_name: str,
        context: str,
    ) -> str:
        value = self._require_string(
            payload=payload,
            field_name=field_name,
            context=context,
        )

        normalized_value = (
            value.strip()
        )

        if not normalized_value:
            raise CanonicalDocumentFieldError(
                f"{context} field "
                f"'{field_name}' must not "
                "be blank."
            )

        return normalized_value

    def _require_optional_string(
        self,
        payload: dict[str, Any],
        field_name: str,
        context: str,
    ) -> str | None:
        value = self._require_field(
            payload=payload,
            field_name=field_name,
            context=context,
        )

        if value is None:
            return None

        if not isinstance(
            value,
            str,
        ):
            raise CanonicalDocumentFieldError(
                f"{context} field "
                f"'{field_name}' must be "
                "a string or null."
            )

        normalized_value = (
            value.strip()
        )

        return (
            normalized_value
            if normalized_value
            else None
        )

    def _require_integer(
        self,
        payload: dict[str, Any],
        field_name: str,
        context: str,
    ) -> int:
        value = self._require_field(
            payload=payload,
            field_name=field_name,
            context=context,
        )

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
            raise CanonicalDocumentFieldError(
                f"{context} field "
                f"'{field_name}' must be "
                "an integer."
            )

        return value

    def _require_number(
        self,
        payload: dict[str, Any],
        field_name: str,
        context: str,
    ) -> float:
        value = self._require_field(
            payload=payload,
            field_name=field_name,
            context=context,
        )

        if (
            not isinstance(
                value,
                (int, float),
            )
            or isinstance(
                value,
                bool,
            )
        ):
            raise CanonicalDocumentFieldError(
                f"{context} field "
                f"'{field_name}' must be "
                "a number."
            )

        return float(
            value
        )

    def _require_boolean(
        self,
        payload: dict[str, Any],
        field_name: str,
        context: str,
    ) -> bool:
        value = self._require_field(
            payload=payload,
            field_name=field_name,
            context=context,
        )

        if not isinstance(
            value,
            bool,
        ):
            raise CanonicalDocumentFieldError(
                f"{context} field "
                f"'{field_name}' must be "
                "a boolean."
            )

        return value

    def _require_field(
        self,
        payload: dict[str, Any],
        field_name: str,
        context: str,
    ) -> Any:
        if field_name not in payload:
            raise CanonicalDocumentFieldError(
                f"{context} is missing required "
                f"field '{field_name}'."
            )

        return payload[
            field_name
        ]