from dataclasses import replace

import pytest

from exceptions.processing import PermanentIngestionError
from models.document import DocumentChunk
from models.embedded_chunk import EmbeddedChunk
from services.canonical_document_parser import CanonicalDocumentParser
from services.extraction_manifest_parser import ExtractionManifestParser
from services.index_record_service import IndexRecordService
from services.ingestion_identity_service import IngestionIdentityService


pytestmark = pytest.mark.unit


def _domain_objects(canonical_fixture_dir, profile_factory, additional_fields=None):
    manifest = ExtractionManifestParser().parse(
        (canonical_fixture_dir / "_SUCCESS.json").read_text()
    )
    document = CanonicalDocumentParser().parse(
        (canonical_fixture_dir / "extracted-document.json").read_text()
    )
    if additional_fields is not None:
        manifest = replace(manifest, additional_fields=additional_fields)
    profile = profile_factory()
    identity = IngestionIdentityService().create_ingestion_identity(
        document, manifest, profile
    )
    chunk = DocumentChunk(
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
    embedded = EmbeddedChunk(
        chunk=chunk,
        embedding=tuple([0.25] * profile.embedding_dimensions),
        embedding_provider=profile.embedding_provider,
        embedding_model_id=profile.embedding_model_id,
        embedding_dimensions=profile.embedding_dimensions,
        embedding_normalized=profile.embedding_normalize,
    )
    return manifest, document, profile, identity, chunk, embedded


def test_identity_service_validates_arguments_and_optional_manifest_values(
    canonical_fixture_dir, profile_factory
):
    manifest, document, profile, identity, *_ = _domain_objects(
        canonical_fixture_dir, profile_factory
    )
    service = IngestionIdentityService()
    assert len(service.create_profile_id(profile)) == 64
    assert identity.canonical_version_id is None
    assert identity.canonical_sha256 is None
    assert service.create_ingestion_identity(document, manifest, profile) == identity

    with pytest.raises(TypeError):
        service.create_profile_id(None)
    with pytest.raises(TypeError):
        service.create_ingestion_identity(None, manifest, profile)
    with pytest.raises(TypeError):
        service.create_ingestion_identity(document, None, profile)
    with pytest.raises(TypeError):
        service.create_ingestion_identity(document, manifest, None)
    with pytest.raises(ValueError):
        service.create_ingestion_identity(
            document, replace(manifest, document_id="other"), profile
        )

    versioned = replace(
        manifest,
        additional_fields={
            "canonical_version_id": " version ",
            "canonical_sha256": " digest ",
        },
    )
    versioned_identity = service.create_ingestion_identity(document, versioned, profile)
    assert versioned_identity.canonical_version_id == "version"
    assert versioned_identity.canonical_sha256 == "digest"

    for fields in (
        {"canonical_version_id": 1},
        {"canonical_version_id": " "},
        {"canonical_sha256": []},
        {"canonical_sha256": ""},
    ):
        with pytest.raises(ValueError):
            service.create_ingestion_identity(
                document, replace(manifest, additional_fields=fields), profile
            )


def test_index_record_service_creates_complete_records_and_checks_bad_outputs(
    canonical_fixture_dir, profile_factory, monkeypatch
):
    _, document, profile, identity, chunk, embedded = _domain_objects(
        canonical_fixture_dir, profile_factory
    )
    service = IndexRecordService()
    records = service.create_records(
        document=document,
        identity=identity,
        profile=profile,
        embedded_chunks=(embedded,),
    )
    record = records[0]
    assert record.chunk_id == chunk.chunk_id
    assert record.document_id == document.document_id
    assert record.embedding_dimensions == profile.embedding_dimensions

    for kwargs, error in (
        ({"document": object()}, TypeError),
        ({"identity": object()}, TypeError),
        ({"profile": object()}, TypeError),
        ({"embedded_chunks": []}, TypeError),
        ({"embedded_chunks": ()}, PermanentIngestionError),
    ):
        values = {
            "document": document,
            "identity": identity,
            "profile": profile,
            "embedded_chunks": (embedded,),
        }
        values.update(kwargs)
        with pytest.raises(error):
            service.create_records(**values)

    with pytest.raises(TypeError):
        service.create_records(
            document=document,
            identity=identity,
            profile=profile,
            embedded_chunks=(object(),),
        )

    invalid_fields = (
        {"index_record_id": "different"},
        {"document_id": "different"},
        {"ingestion_id": "different"},
        {"ingestion_profile_id": "different"},
        {"index_schema_version": "different"},
        {"text": "different"},
        {"start_offset": 1},
        {"start_page": 2},
        {"embedding_dimensions": 1},
        {"embedding": (float("inf"),) + record.embedding[1:]},
    )
    original_create = service._create_record
    for changes in invalid_fields:
        monkeypatch.setattr(
            service,
            "_create_record",
            lambda **kwargs: replace(original_create(**kwargs), **changes),
        )
        with pytest.raises(PermanentIngestionError):
            service.create_records(
                document=document,
                identity=identity,
                profile=profile,
                embedded_chunks=(embedded,),
            )
    monkeypatch.setattr(service, "_create_record", lambda **_kwargs: object())
    with pytest.raises(PermanentIngestionError, match="invalid record type"):
        service.create_records(
            document=document, identity=identity, profile=profile, embedded_chunks=(embedded,)
        )

    monkeypatch.setattr(service, "_create_record", lambda **_kwargs: record)
    with pytest.raises(PermanentIngestionError, match="count"):
        service._check_records(
            document=document,
            identity=identity,
            profile=profile,
            embedded_chunks=(embedded, embedded),
            records=(record,),
        )

    duplicate_chunk = replace(chunk, chunk_index=1)
    duplicate_embedded = replace(embedded, chunk=duplicate_chunk)
    with pytest.raises(PermanentIngestionError, match="unique"):
        service._check_records(
            document=document,
            identity=identity,
            profile=profile,
            embedded_chunks=(embedded, duplicate_embedded),
            records=(record, record),
        )
