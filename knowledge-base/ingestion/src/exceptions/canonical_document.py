from exceptions.extraction_manifest import IngestionInputError


class CanonicalDocumentError(IngestionInputError):
    """
    Base exception for canonical-document loading,
    parsing, and validation failures.
    """


class CanonicalDocumentLoadError(CanonicalDocumentError):
    """
    The canonical document could not be loaded from
    its configured storage location.
    """


class CanonicalDocumentNotFoundError(CanonicalDocumentLoadError):
    """
    The canonical document does not exist at the
    location declared by the extraction manifest.
    """


class CanonicalDocumentJsonError(CanonicalDocumentError):
    """
    The canonical document is not valid JSON or its
    top-level JSON value is not an object.
    """


class CanonicalDocumentFieldError(CanonicalDocumentError):
    """
    A required canonical-document field is missing,
    has an invalid type, or contains an invalid
    value.
    """


class CanonicalDocumentIdentityMismatchError(CanonicalDocumentError):
    """
    Canonical-document identity values do not match
    the authoritative extraction success manifest.
    """


class CanonicalDocumentContentError(CanonicalDocumentError):
    """
    Canonical text, page offsets, counts, or other
    content relationships are inconsistent.
    """


class EmptyCanonicalDocumentError(CanonicalDocumentContentError):
    """
    The canonical document contains no usable text
    for ingestion.
    """


class UnsupportedCanonicalSchemaError(CanonicalDocumentError):
    """
    The canonical document references an extraction
    schema that this ingestion version does not
    support.
    """