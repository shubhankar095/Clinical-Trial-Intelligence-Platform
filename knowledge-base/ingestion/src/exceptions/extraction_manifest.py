class IngestionInputError(RuntimeError):
    """
    Base exception for errors encountered while
    loading or validating ingestion input.
    """


class ExtractionManifestError(IngestionInputError):
    """
    Base exception for extraction success-manifest
    loading, parsing, and validation failures.
    """


class ManifestLoadError(ExtractionManifestError):
    """
    The extraction manifest could not be loaded
    from its configured storage location.
    """


class ManifestNotFoundError(ManifestLoadError):
    """
    The extraction manifest does not exist at the
    requested storage location.
    """


class ManifestJsonError(ExtractionManifestError):
    """
    The extraction manifest is not valid JSON or
    its top-level JSON value is not an object.
    """


class ManifestFieldError(ExtractionManifestError):
    """
    A required extraction-manifest field is missing,
    has an invalid type, or contains an invalid value.
    """


class ManifestLocationError(ExtractionManifestError):
    """
    The extraction manifest was supplied from an
    invalid or unsafe storage location.
    """


class ManifestIdentityMismatchError(ExtractionManifestError):
    """
    Identity values in the manifest payload do not
    match values derived from the manifest location
    or canonical document location.
    """


class UnsupportedExtractionSchemaError(ExtractionManifestError):
    """
    The manifest references an extraction schema
    that this ingestion version does not support.
    """