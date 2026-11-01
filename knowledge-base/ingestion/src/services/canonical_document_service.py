from exceptions.canonical_document import CanonicalDocumentLoadError, CanonicalDocumentNotFoundError
from exceptions.extraction_manifest import ManifestLoadError, ManifestNotFoundError
from models.canonical_document import CanonicalDocument
from models.extraction_manifest import ExtractionSuccessManifest
from models.storage_location import StorageLocation
from services.canonical_document_parser import CanonicalDocumentParser
from services.canonical_document_validator import CanonicalDocumentValidator
from storage.base_text_store import BaseTextStore


class CanonicalDocumentService:
    """Load and validate the S3 canonical document declared by a manifest."""

    def __init__(
        self,
        text_store: BaseTextStore,
        parser: CanonicalDocumentParser | None = None,
        validator: CanonicalDocumentValidator | None = None,
    ):
        if not isinstance(text_store, BaseTextStore):
            raise TypeError("text_store must implement BaseTextStore.")
        self.text_store = text_store
        self.parser = parser or CanonicalDocumentParser()
        self.validator = validator or CanonicalDocumentValidator()

    def build_location(self, manifest: ExtractionSuccessManifest) -> StorageLocation:
        if not isinstance(manifest, ExtractionSuccessManifest):
            raise TypeError("manifest must be an ExtractionSuccessManifest.")
        version_id = manifest.additional_fields.get("canonical_version_id")
        if version_id is not None and (not isinstance(version_id, str) or not version_id.strip()):
            raise CanonicalDocumentLoadError("Manifest canonical_version_id must be a nonblank string.")
        return StorageLocation(
            bucket=manifest.canonical_bucket,
            key=manifest.canonical_key,
            version_id=version_id.strip() if isinstance(version_id, str) else None,
        )

    def load_and_validate(self, manifest: ExtractionSuccessManifest) -> CanonicalDocument:
        try:
            text = self.text_store.load_text(self.build_location(manifest))
        except ManifestNotFoundError as exception:
            raise CanonicalDocumentNotFoundError(
                "Canonical document was not found at the manifest location."
            ) from exception
        except ManifestLoadError as exception:
            raise CanonicalDocumentLoadError("Canonical document could not be loaded.") from exception
        document = self.parser.parse(text)
        return self.validator.validate(document=document, manifest=manifest)
