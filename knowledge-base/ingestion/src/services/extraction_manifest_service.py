from services.extraction_manifest_parser import (
    ExtractionManifestParser,
)
from services.extraction_manifest_validator import (
    ExtractionManifestValidator,
)
from models.extraction_manifest import (
    ExtractionSuccessManifest,
)
from models.storage_location import (
    StorageLocation,
)
from storage.base_text_store import (
    BaseTextStore,
)


class ExtractionManifestService:
    """
    Load, parse, and validate an extraction success
    manifest.

    This service is the public application boundary
    for the first ingestion milestone.
    """

    def __init__(
        self,
        text_store: BaseTextStore,
        parser: (
            ExtractionManifestParser
            | None
        ) = None,
        validator: (
            ExtractionManifestValidator
            | None
        ) = None,
    ):
        self.text_store = text_store

        self.parser = (
            parser
            or ExtractionManifestParser()
        )

        self.validator = (
            validator
            or ExtractionManifestValidator()
        )

    def load_and_validate(
        self,
        location: StorageLocation,
    ) -> ExtractionSuccessManifest:
        manifest_text = (
            self.text_store.load_text(
                location
            )
        )

        manifest = self.parser.parse(
            manifest_text
        )

        return self.validator.validate(
            manifest=manifest,
            location=location,
        )