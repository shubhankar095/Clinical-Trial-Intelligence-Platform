import json
from dataclasses import replace
from datetime import datetime, tzinfo

import pytest

from exceptions.canonical_document import (
    CanonicalDocumentContentError,
    CanonicalDocumentFieldError,
    CanonicalDocumentIdentityMismatchError,
    CanonicalDocumentJsonError,
    CanonicalDocumentLoadError,
    CanonicalDocumentNotFoundError,
    EmptyCanonicalDocumentError,
    UnsupportedCanonicalSchemaError,
)
from exceptions.extraction_manifest import (
    ManifestFieldError,
    ManifestIdentityMismatchError,
    ManifestJsonError,
    ManifestLoadError,
    ManifestLocationError,
    ManifestNotFoundError,
    UnsupportedExtractionSchemaError,
)
from exceptions.processing import PermanentIngestionError, RetryableIngestionError
from models.canonical_document import CanonicalDocument
from models.document import DocumentChunk
from models.embedded_chunk import EmbeddedChunk
from models.storage_location import StorageLocation
from services.canonical_document_parser import CanonicalDocumentParser
from services.canonical_document_service import CanonicalDocumentService
from services.canonical_document_validator import CanonicalDocumentValidator
from services.chunking_service import ChunkingService
from services.embedding_service import EmbeddingService
from services.extraction_manifest_parser import ExtractionManifestParser
from services.extraction_manifest_validator import ExtractionManifestValidator
from services.indexing_service import IndexingService
from services.ingestion_identity_service import IngestionIdentityService
from chunkers.base_chunker import BaseChunker
from embedders.base_embedder import BaseEmbedder
from indexers.base_indexer import BaseIndexer
from storage.base_text_store import BaseTextStore


pytestmark = pytest.mark.unit


def _fixtures(directory):
    manifest = ExtractionManifestParser().parse(
        (directory / "_SUCCESS.json").read_text()
    )
    document = CanonicalDocumentParser().parse(
        (directory / "extracted-document.json").read_text()
    )
    return manifest, document


def _chunk(identity, document):
    return DocumentChunk(
        chunk_id="chunk-0",
        ingestion_id=identity.ingestion_id,
        ingestion_profile_id=identity.ingestion_profile_id,
        document_id=document.document_id,
        chunk_index=0,
        text=document.raw_text,
        start_offset=0,
        end_offset=len(document.raw_text),
        start_page=1,
        end_page=document.page_count,
        character_count=len(document.raw_text),
    )


class _Chunker(BaseChunker):
    def __init__(self, chunks):
        self.chunks = chunks

    def chunk(self, document, identity, profile):
        return self.chunks


class _Embedder(BaseEmbedder):
    def __init__(self, result):
        self.result = result
        self.closed = False

    def embed(self, chunk):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result

    def close(self):
        self.closed = True


class _Indexer(BaseIndexer):
    def __init__(self, result="index"):
        self.result = result

    def index_records(self, *, ingestion_id, records):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def test_base_text_store_abstract_method():
    class ConcreteStore(BaseTextStore):
        def load_text(self, location):
            return super().load_text(location)

    with pytest.raises(NotImplementedError):
        ConcreteStore().load_text(None)


def test_extraction_manifest_parser_validates_json_shapes():
    parser = ExtractionManifestParser()
    for payload in ("not json", "[]", "null"):
        with pytest.raises(ManifestJsonError):
            parser.parse(payload)
    with pytest.raises(ManifestJsonError):
        parser.parse(None)


def test_extraction_manifest_parser_required_fields_and_timestamp(canonical_fixture_dir):
    raw = json.loads((canonical_fixture_dir / "_SUCCESS.json").read_text())
    parser = ExtractionManifestParser()
    for field in parser.REQUIRED_STRING_FIELDS:
        missing = dict(raw)
        del missing[field]
        with pytest.raises(ManifestFieldError):
            parser.parse(json.dumps(missing))
        invalid = dict(raw, **{field: 1})
        with pytest.raises(ManifestFieldError):
            parser.parse(json.dumps(invalid))
        blank = dict(raw, **{field: "  "})
        with pytest.raises(ManifestFieldError):
            parser.parse(json.dumps(blank))

    for timestamp in ("yesterday", "2024-01-01T00:00:00"):
        with pytest.raises(ManifestFieldError):
            parser.parse(json.dumps(dict(raw, completed_at=timestamp)))

    manifest = parser.parse(json.dumps(dict(raw, completed_at="2024-01-01T00:00:00z", future_field=7)))
    assert manifest.additional_fields["future_field"] == 7


def test_extraction_manifest_validator_rejects_contract_mismatches(canonical_fixture_dir):
    manifest, _ = _fixtures(canonical_fixture_dir)
    location = StorageLocation(
        bucket=manifest.canonical_bucket,
        key=f"canonical-documents/{manifest.document_id}/_SUCCESS.json",
        version_id=None,
    )
    validator = ExtractionManifestValidator(manifest.canonical_bucket)
    assert validator.validate(manifest, location) is manifest

    for key in ("wrong", f"canonical-documents/{manifest.document_id}/wrong.json"):
        with pytest.raises(ManifestLocationError):
            validator.validate(manifest, replace(location, key=key))
    with pytest.raises(ManifestLocationError):
        validator.validate(manifest, replace(location, key="canonical-documents//_SUCCESS.json"))
    with pytest.raises(ManifestFieldError):
        validator.validate(replace(manifest, document_id="x" * 64), location)
    with pytest.raises(ManifestIdentityMismatchError):
        validator.validate(replace(manifest, document_id="a" * 64), location)
    with pytest.raises(ManifestFieldError):
        validator.validate(replace(manifest, processing_status="FAILED"), location)
    with pytest.raises(UnsupportedExtractionSchemaError):
        validator.validate(replace(manifest, processing_schema_version="future"), location)
    with pytest.raises(ManifestIdentityMismatchError):
        ExtractionManifestValidator("other").validate(manifest, location)
    with pytest.raises(ManifestIdentityMismatchError):
        validator.validate(
            replace(manifest, canonical_key="other"),
            location,
        )
    with pytest.raises(ManifestFieldError):
        validator.validate(replace(manifest, completed_at=datetime(2024, 1, 1)), location)
    class NoOffset(tzinfo):
        def utcoffset(self, _dt):
            return None

    with pytest.raises(ManifestFieldError):
        validator.validate(
            replace(manifest, completed_at=datetime(2024, 1, 1, tzinfo=NoOffset())),
            location,
        )
    with pytest.raises(TypeError):
        validator.validate(None, location)
    with pytest.raises(TypeError):
        validator.validate(manifest, None)
    with pytest.raises(ValueError):
        ExtractionManifestValidator(" ")


def test_canonical_parser_rejects_invalid_top_level_and_field_shapes(canonical_fixture_dir):
    parser = CanonicalDocumentParser()
    source = json.loads((canonical_fixture_dir / "extracted-document.json").read_text())
    for payload in ("broken", "[]", "null"):
        with pytest.raises(CanonicalDocumentJsonError):
            parser.parse(payload)
    with pytest.raises(CanonicalDocumentJsonError):
        parser.parse(None)

    for field in parser.DOCUMENT_STRING_FIELDS:
        for value in (None, "  "):
            with pytest.raises(CanonicalDocumentFieldError):
                parser.parse(json.dumps(dict(source, **{field: value})))
    for field in parser.DOCUMENT_INTEGER_FIELDS:
        for value in (True, "1"):
            with pytest.raises(CanonicalDocumentFieldError):
                parser.parse(json.dumps(dict(source, **{field: value})))
    for field, value in (
        ("metadata", []),
        ("pages", {}),
        ("images", {}),
        ("tables", {}),
        ("warnings", {}),
        ("already_processed", 1),
        ("error_message", 1),
        ("raw_text", 1),
    ):
        with pytest.raises(CanonicalDocumentFieldError):
            parser.parse(json.dumps(dict(source, **{field: value})))
    with pytest.raises(CanonicalDocumentFieldError):
        parser.parse(json.dumps({key: value for key, value in source.items() if key != "document_id"}))
    with pytest.raises(CanonicalDocumentFieldError):
        parser.parse(
            json.dumps(
                dict(
                    source,
                    pages=[
                        dict(source["pages"][0], quality_score="not-a-number"),
                        *source["pages"][1:],
                    ],
                )
            )
        )


def test_canonical_parser_nested_records_and_unknown_fields(canonical_fixture_dir):
    parser = CanonicalDocumentParser()
    source = json.loads((canonical_fixture_dir / "extracted-document.json").read_text())
    source["future_document_field"] = True
    source["metadata"]["future_metadata_field"] = "value"
    source["metadata"]["study_id"] = "  "
    source["images"] = [{
        "image_id": "image-1", "page_number": 1, "extension": "png",
        "s3_key": "image.png", "width": 10, "height": 20, "future": 1,
    }]
    source["tables"] = [{
        "table_id": "table-1", "page_number": 1, "s3_key": "table.json",
        "row_count": 1, "column_count": 2, "title": " ",
    }]
    source["warnings"] = [" warning "]
    document = parser.parse(json.dumps(source))
    assert document.additional_fields["future_document_field"] is True
    assert document.metadata.additional_fields["future_metadata_field"] == "value"
    assert document.metadata.study_id is None
    assert document.images[0].additional_fields["future"] == 1
    assert document.tables[0].title is None
    assert document.warnings == ("warning",)

    for field, value in (
        ("pages", [None]),
        ("images", [None]),
        ("tables", [None]),
        ("warnings", [None]),
        ("warnings", [" "]),
    ):
        with pytest.raises(CanonicalDocumentFieldError):
            parser.parse(json.dumps(dict(source, **{field: value})))


def test_canonical_services_validate_load_errors(canonical_fixture_dir):
    manifest, document = _fixtures(canonical_fixture_dir)

    class Store(BaseTextStore):
        def __init__(self, result):
            self.result = result

        def load_text(self, location):
            if isinstance(self.result, Exception):
                raise self.result
            return self.result

    service = CanonicalDocumentService(Store(json.dumps({"unexpected": True})))
    with pytest.raises(CanonicalDocumentFieldError):
        service.load_and_validate(manifest)
    with pytest.raises(CanonicalDocumentLoadError):
        service.build_location(replace(manifest, additional_fields={"canonical_version_id": " "}))

    with pytest.raises(CanonicalDocumentNotFoundError):
        CanonicalDocumentService(Store(ManifestNotFoundError())).load_and_validate(manifest)
    with pytest.raises(CanonicalDocumentLoadError):
        CanonicalDocumentService(Store(ManifestLoadError())).load_and_validate(manifest)

    with pytest.raises(TypeError):
        CanonicalDocumentService(object())
    with pytest.raises(TypeError):
        service.build_location(None)
    assert document.document_id == manifest.document_id


def test_canonical_validator_rejects_primary_contract_fields(canonical_fixture_dir):
    manifest, document = _fixtures(canonical_fixture_dir)
    validator = CanonicalDocumentValidator()
    assert validator.validate(document, manifest) is document
    for invalid, error in (
        (replace(document, processing_schema_version="other"), UnsupportedCanonicalSchemaError),
        (replace(document, processing_status="FAILED"), CanonicalDocumentFieldError),
        (replace(document, error_message="failed"), CanonicalDocumentContentError),
        (replace(document, document_id="not-a-hash"), CanonicalDocumentIdentityMismatchError),
        (replace(document, raw_text=" "), EmptyCanonicalDocumentError),
        (replace(document, file_name=" "), CanonicalDocumentFieldError),
        (replace(document, file_format=" "), CanonicalDocumentFieldError),
        (replace(document, file_format="txt"), CanonicalDocumentFieldError),
        (replace(document, pages=()), CanonicalDocumentContentError),
    ):
        with pytest.raises(error):
            validator.validate(invalid, manifest)
    with pytest.raises(TypeError):
        validator.validate(None, manifest)
    with pytest.raises(TypeError):
        validator.validate(document, None)


def test_chunking_service_checks_all_chunk_invariants(canonical_fixture_dir, profile_factory):
    manifest, document = _fixtures(canonical_fixture_dir)
    profile = profile_factory()
    identity = IngestionIdentityService().create_ingestion_identity(document, manifest, profile)
    good = _chunk(identity, document)
    assert ChunkingService(_Chunker((good,))).chunk_document(document, identity, profile) == (good,)
    invalid_chunks = (
        [],
        (),
        (object(),),
        (replace(good, chunk_index=1),),
        (replace(good, text=" "),),
        (replace(good, start_offset=-1),),
        (replace(good, end_offset=0),),
        (replace(good, end_offset=len(document.raw_text) + 1),),
        (replace(good, text="other"),),
        (replace(good, character_count=1),),
        (replace(good, document_id="other"),),
        (replace(good, ingestion_id="other"),),
        (replace(good, ingestion_profile_id="other"),),
        (good, good),
        (good, replace(good, chunk_index=1)),
    )
    for chunks in invalid_chunks:
        with pytest.raises(PermanentIngestionError):
            ChunkingService(_Chunker(chunks)).chunk_document(document, identity, profile)
    with pytest.raises(TypeError):
        ChunkingService(object())


def test_embedding_service_checks_provider_output(canonical_fixture_dir, profile_factory):
    manifest, document = _fixtures(canonical_fixture_dir)
    profile = profile_factory()
    identity = IngestionIdentityService().create_ingestion_identity(document, manifest, profile)
    chunk = _chunk(identity, document)
    good = EmbeddedChunk(
        chunk=chunk,
        embedding=tuple([0.1] * profile.embedding_dimensions),
        embedding_provider=profile.embedding_provider,
        embedding_model_id=profile.embedding_model_id,
        embedding_dimensions=profile.embedding_dimensions,
        embedding_normalized=profile.embedding_normalize,
    )
    embedder = _Embedder(good)
    service = EmbeddingService(embedder)
    assert service.embed_chunks((chunk,), profile) == (good,)
    service.close()
    assert embedder.closed

    invalid_results = (
        replace(good, chunk=replace(chunk, chunk_id="other")),
        replace(good, embedding_provider="other"),
        replace(good, embedding_model_id="other"),
        replace(good, embedding_dimensions=1),
        replace(good, embedding=(float("nan"),) + good.embedding[1:]),
        replace(good, embedding=(True,) + good.embedding[1:]),
        replace(good, embedding=(0.1,)),
        replace(good, embedding_normalized=not profile.embedding_normalize),
    )
    for result in invalid_results:
        with pytest.raises(PermanentIngestionError):
            EmbeddingService(_Embedder(result)).embed_chunks((chunk,), profile)
    for invalid in ((), []):
        with pytest.raises(ValueError):
            service.embed_chunks(invalid, profile)
    class InconsistentTuple(tuple):
        def __len__(self):
            return 2

        def __iter__(self):
            return iter((chunk,))

    with pytest.raises(PermanentIngestionError, match="count"):
        service.embed_chunks(InconsistentTuple((chunk, chunk)), profile)
    with pytest.raises(TypeError):
        service.embed_chunks((chunk,), object())
    with pytest.raises(TypeError):
        EmbeddingService(object())
    with pytest.raises(RetryableIngestionError):
        EmbeddingService(_Embedder(RuntimeError("embedding unavailable"))).embed_chunks(
            (chunk,), profile
        )

    class WithoutClose(BaseEmbedder):
        def embed(self, supplied_chunk):
            return good

    EmbeddingService(WithoutClose()).close()


def test_indexing_service_validates_and_normalizes_requests():
    with pytest.raises(TypeError):
        IndexingService(object())
    service = IndexingService(_Indexer(" destination "))
    from models.index_record import IndexRecord
    record = IndexRecord(
        index_record_id="record",
        index_schema_version="v1",
        document_id="doc",
        ingestion_id="ingest",
        ingestion_profile_id="profile",
        chunk_id="chunk",
        chunk_index=0,
        text="text",
        character_count=4,
        start_offset=0,
        end_offset=4,
        start_page=None,
        end_page=None,
        embedding=(0.1,),
        embedding_provider="test",
        embedding_model_id="model",
        embedding_dimensions=1,
        embedding_normalized=False,
        input_token_count=None,
        file_name="file",
        file_format="pdf",
        source_bucket="source",
        source_key="source",
        source_version_id="version",
        canonical_bucket="canonical",
        canonical_key="canonical",
        study_id=None,
        document_type=None,
        document_version=None,
        sponsor=None,
        phase=None,
    )
    assert service.index_records(ingestion_id=" ingest ", records=(record,)) == "destination"
    for ingestion_id, records, error in (
        (" ", (record,), ValueError),
        ("ingest", [], TypeError),
        ("ingest", (), PermanentIngestionError),
        ("ingest", (object(),), PermanentIngestionError),
        ("other", (record,), PermanentIngestionError),
        ("ingest", (record, record), PermanentIngestionError),
    ):
        with pytest.raises(error):
            service.index_records(ingestion_id=ingestion_id, records=records)
    for response in (" ", None):
        with pytest.raises(PermanentIngestionError):
            IndexingService(_Indexer(response)).index_records(
                ingestion_id="ingest", records=(record,)
            )
    with pytest.raises(RetryableIngestionError):
        IndexingService(_Indexer(RuntimeError("service unavailable"))).index_records(
            ingestion_id="ingest", records=(record,)
        )
