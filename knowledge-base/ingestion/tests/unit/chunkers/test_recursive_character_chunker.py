import hashlib
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from chunkers.recursive_character_chunker import (
    RecursiveCharacterChunker,
)
from models.canonical_document import (
    CanonicalDocument,
    CanonicalDocumentMetadata,
    CanonicalDocumentPage,
)
from models.ingestion_profile import (
    IngestionIdentity,
)


pytestmark = pytest.mark.unit

DOCUMENT_ID = "a" * 64
INGESTION_PROFILE_ID = "b" * 64
INGESTION_ID = "c" * 64

RAW_TEXT = "First page text.\nSecond page text."

FIRST_PAGE_TEXT = "First page text."
SECOND_PAGE_TEXT = "Second page text."

SECOND_PAGE_START = RAW_TEXT.index(
    SECOND_PAGE_TEXT
)


def create_document(
    *,
    raw_text: str = RAW_TEXT,
    pages: tuple[
        CanonicalDocumentPage,
        ...,
    ] | None = None,
) -> CanonicalDocument:
    if pages is None:
        pages = (
            CanonicalDocumentPage(
                page_number=1,
                text=FIRST_PAGE_TEXT,
                start_offset=0,
                end_offset=len(
                    FIRST_PAGE_TEXT
                ),
                word_count=3,
                quality_score=1.0,
                requires_ocr=False,
                ocr_applied=False,
                extraction_method="TEXT",
            ),
            CanonicalDocumentPage(
                page_number=2,
                text=SECOND_PAGE_TEXT,
                start_offset=(
                    SECOND_PAGE_START
                ),
                end_offset=len(
                    RAW_TEXT
                ),
                word_count=3,
                quality_score=1.0,
                requires_ocr=False,
                ocr_applied=False,
                extraction_method="TEXT",
            ),
        )

    return CanonicalDocument(
        document_id=DOCUMENT_ID,
        file_name="clinical-trial.pdf",
        file_format="pdf",
        source_bucket="source-bucket",
        source_key="documents/clinical-trial.pdf",
        source_version_id="source-version-1",
        canonical_bucket="canonical-bucket",
        canonical_key=(
            "canonical-documents/"
            f"{DOCUMENT_ID}/"
            "extracted-document.json"
        ),
        processing_schema_version=(
            "extraction-v1"
        ),
        processing_status="SUCCESS",
        metadata=CanonicalDocumentMetadata(
            study_id="STUDY-001",
            document_type="protocol",
            version="1.0",
            sponsor="Example Sponsor",
            phase="Phase 2",
        ),
        raw_text=raw_text,
        pages=pages,
        page_count=len(pages),
        ocr_page_count=0,
        images=(),
        image_count=0,
        tables=(),
        table_count=0,
        warnings=(),
        already_processed=False,
        error_message=None,
    )


def create_identity() -> IngestionIdentity:
    return IngestionIdentity(
        document_id=DOCUMENT_ID,
        ingestion_profile_id=(
            INGESTION_PROFILE_ID
        ),
        ingestion_id=INGESTION_ID,
        canonical_bucket="canonical-bucket",
        canonical_key=(
            "canonical-documents/"
            f"{DOCUMENT_ID}/"
            "extracted-document.json"
        ),
        canonical_version_id=(
            "canonical-version-1"
        ),
        canonical_sha256="d" * 64,
    )


def split_document(
    text: str,
    start_index: object,
) -> SimpleNamespace:
    return SimpleNamespace(
        page_content=text,
        metadata={
            "start_index": start_index,
        },
    )


def expected_chunk_id(
    *,
    chunk_index: int,
    start_offset: int,
    end_offset: int,
    text: str,
) -> str:
    text_sha256 = hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()

    payload = {
        "identity_type": (
            "document-chunk"
        ),
        "ingestion_id": INGESTION_ID,
        "chunk_index": chunk_index,
        "start_offset": start_offset,
        "end_offset": end_offset,
        "text_sha256": text_sha256,
    }

    serialized = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    return hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()


def test_chunk_creates_deterministic_chunks(
    profile_factory,
) -> None:
    document = create_document()
    identity = create_identity()
    profile = profile_factory(
        chunker_type=(
            "page-aware-recursive-character"
        ),
        chunk_size=100,
        chunk_overlap=10,
    )

    split_documents = [
        split_document(
            FIRST_PAGE_TEXT,
            0,
        ),
        split_document(
            SECOND_PAGE_TEXT,
            SECOND_PAGE_START,
        ),
    ]

    with patch(
        "chunkers.recursive_character_chunker."
        "RecursiveCharacterTextSplitter"
    ) as splitter_class:
        splitter = (
            splitter_class.return_value
        )
        splitter.create_documents.return_value = (
            split_documents
        )

        chunks = (
            RecursiveCharacterChunker()
            .chunk(
                document=document,
                identity=identity,
                profile=profile,
            )
        )

    splitter_class.assert_called_once_with(
        chunk_size=100,
        chunk_overlap=10,
        add_start_index=True,
        keep_separator=True,
        strip_whitespace=False,
    )

    splitter.create_documents.assert_called_once_with(
        texts=[RAW_TEXT],
    )

    assert len(chunks) == 2

    first_chunk = chunks[0]

    assert first_chunk.chunk_id == (
        expected_chunk_id(
            chunk_index=0,
            start_offset=0,
            end_offset=len(
                FIRST_PAGE_TEXT
            ),
            text=FIRST_PAGE_TEXT,
        )
    )
    assert (
        first_chunk.ingestion_id
        == INGESTION_ID
    )
    assert (
        first_chunk.ingestion_profile_id
        == INGESTION_PROFILE_ID
    )
    assert (
        first_chunk.document_id
        == DOCUMENT_ID
    )
    assert first_chunk.chunk_index == 0
    assert first_chunk.text == FIRST_PAGE_TEXT
    assert first_chunk.start_offset == 0
    assert first_chunk.end_offset == len(
        FIRST_PAGE_TEXT
    )
    assert first_chunk.start_page == 1
    assert first_chunk.end_page == 1
    assert (
        first_chunk.character_count
        == len(FIRST_PAGE_TEXT)
    )

    second_chunk = chunks[1]

    assert second_chunk.chunk_id == (
        expected_chunk_id(
            chunk_index=1,
            start_offset=(
                SECOND_PAGE_START
            ),
            end_offset=len(RAW_TEXT),
            text=SECOND_PAGE_TEXT,
        )
    )
    assert second_chunk.chunk_index == 1
    assert second_chunk.text == (
        SECOND_PAGE_TEXT
    )
    assert second_chunk.start_offset == (
        SECOND_PAGE_START
    )
    assert second_chunk.end_offset == len(
        RAW_TEXT
    )
    assert second_chunk.start_page == 2
    assert second_chunk.end_page == 2


def test_chunk_uses_authoritative_source_text(
    profile_factory,
) -> None:
    document = create_document()
    identity = create_identity()
    profile = profile_factory(
        chunker_type=(
            "page-aware-recursive-character"
        ),
    )

    with patch(
        "chunkers.recursive_character_chunker."
        "RecursiveCharacterTextSplitter"
    ) as splitter_class:
        splitter_class.return_value\
            .create_documents.return_value = [
                split_document(
                    "WRONG TEXT VALUE",
                    0,
                )
            ]

        chunks = (
            RecursiveCharacterChunker()
            .chunk(
                document=document,
                identity=identity,
                profile=profile,
            )
        )

    expected_text = RAW_TEXT[
        0:len("WRONG TEXT VALUE")
    ]

    assert len(chunks) == 1
    assert chunks[0].text == expected_text
    assert (
        chunks[0].character_count
        == len(expected_text)
    )


def test_chunk_skips_blank_documents(
    profile_factory,
) -> None:
    document = create_document()
    identity = create_identity()
    profile = profile_factory(
        chunker_type=(
            "page-aware-recursive-character"
        ),
    )

    with patch(
        "chunkers.recursive_character_chunker."
        "RecursiveCharacterTextSplitter"
    ) as splitter_class:
        splitter_class.return_value\
            .create_documents.return_value = [
                split_document(
                    "   ",
                    0,
                ),
                split_document(
                    "\n\t",
                    3,
                ),
                split_document(
                    FIRST_PAGE_TEXT,
                    0,
                ),
            ]

        chunks = (
            RecursiveCharacterChunker()
            .chunk(
                document=document,
                identity=identity,
                profile=profile,
            )
        )

    assert len(chunks) == 1
    assert chunks[0].chunk_index == 0
    assert chunks[0].text == FIRST_PAGE_TEXT


def test_chunk_returns_empty_tuple_when_no_splits(
    profile_factory,
) -> None:
    document = create_document()
    identity = create_identity()
    profile = profile_factory(
        chunker_type=(
            "page-aware-recursive-character"
        ),
    )

    with patch(
        "chunkers.recursive_character_chunker."
        "RecursiveCharacterTextSplitter"
    ) as splitter_class:
        splitter_class.return_value\
            .create_documents.return_value = []

        result = (
            RecursiveCharacterChunker()
            .chunk(
                document=document,
                identity=identity,
                profile=profile,
            )
        )

    assert result == ()


def test_chunk_maps_one_chunk_across_pages(
    profile_factory,
) -> None:
    document = create_document()
    identity = create_identity()
    profile = profile_factory(
        chunker_type=(
            "page-aware-recursive-character"
        ),
    )

    cross_page_text = RAW_TEXT[
        len(FIRST_PAGE_TEXT) - 4:
        SECOND_PAGE_START + 6
    ]
    start_offset = (
        len(FIRST_PAGE_TEXT) - 4
    )

    with patch(
        "chunkers.recursive_character_chunker."
        "RecursiveCharacterTextSplitter"
    ) as splitter_class:
        splitter_class.return_value\
            .create_documents.return_value = [
                split_document(
                    cross_page_text,
                    start_offset,
                )
            ]

        chunks = (
            RecursiveCharacterChunker()
            .chunk(
                document=document,
                identity=identity,
                profile=profile,
            )
        )

    assert len(chunks) == 1
    assert chunks[0].start_page == 1
    assert chunks[0].end_page == 2


def test_chunk_returns_no_page_mapping_for_gap(
    profile_factory,
) -> None:
    raw_text = "Page one. GAP Page two."

    pages = (
        CanonicalDocumentPage(
            page_number=1,
            text="Page one.",
            start_offset=0,
            end_offset=9,
            word_count=2,
            quality_score=1.0,
            requires_ocr=False,
            ocr_applied=False,
            extraction_method="TEXT",
        ),
        CanonicalDocumentPage(
            page_number=2,
            text="Page two.",
            start_offset=14,
            end_offset=len(raw_text),
            word_count=2,
            quality_score=1.0,
            requires_ocr=False,
            ocr_applied=False,
            extraction_method="TEXT",
        ),
    )

    document = create_document(
        raw_text=raw_text,
        pages=pages,
    )
    identity = create_identity()
    profile = profile_factory(
        chunker_type=(
            "page-aware-recursive-character"
        ),
    )

    with patch(
        "chunkers.recursive_character_chunker."
        "RecursiveCharacterTextSplitter"
    ) as splitter_class:
        splitter_class.return_value\
            .create_documents.return_value = [
                split_document(
                    "GAP",
                    10,
                )
            ]

        chunks = (
            RecursiveCharacterChunker()
            .chunk(
                document=document,
                identity=identity,
                profile=profile,
            )
        )

    assert len(chunks) == 1
    assert chunks[0].start_page is None
    assert chunks[0].end_page is None


@pytest.mark.parametrize(
    ("document", "identity", "profile_value",
     "expected_message"),
    [
        (
            None,
            create_identity(),
            "profile",
            (
                "document must be a "
                "CanonicalDocument"
            ),
        ),
        (
            create_document(),
            None,
            "profile",
            (
                "identity must be an "
                "IngestionIdentity"
            ),
        ),
    ],
)
def test_chunk_rejects_invalid_document_or_identity(
    document,
    identity,
    profile_value,
    expected_message: str,
    profile_factory,
) -> None:
    profile = profile_factory(
        chunker_type=(
            "page-aware-recursive-character"
        ),
    )

    del profile_value

    with pytest.raises(
        TypeError,
        match=expected_message,
    ):
        RecursiveCharacterChunker().chunk(
            document=document,
            identity=identity,
            profile=profile,
        )


def test_chunk_rejects_invalid_profile() -> None:
    with pytest.raises(
        TypeError,
        match=(
            "profile must be an "
            "IngestionProfile"
        ),
    ):
        RecursiveCharacterChunker().chunk(
            document=create_document(),
            identity=create_identity(),
            profile=None,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "metadata",
    [
        {},
        {
            "start_index": None,
        },
        {
            "start_index": "0",
        },
        {
            "start_index": 1.5,
        },
        {
            "start_index": True,
        },
    ],
)
def test_read_start_offset_rejects_invalid_value(
    metadata: dict[str, object],
) -> None:
    with pytest.raises(
        RuntimeError,
        match=(
            "did not return a valid "
            "start_index"
        ),
    ):
        RecursiveCharacterChunker()\
            ._read_start_offset(metadata)


def test_read_start_offset_rejects_negative_value() -> None:
    with pytest.raises(
        RuntimeError,
        match="negative start_index",
    ):
        RecursiveCharacterChunker()\
            ._read_start_offset(
                {
                    "start_index": -1,
                }
            )


def test_read_start_offset_accepts_zero() -> None:
    result = (
        RecursiveCharacterChunker()
        ._read_start_offset(
            {
                "start_index": 0,
            }
        )
    )

    assert result == 0


def test_create_chunk_id_is_deterministic() -> None:
    chunker = RecursiveCharacterChunker()
    identity = create_identity()

    first = chunker._create_chunk_id(
        identity=identity,
        chunk_index=0,
        start_offset=0,
        end_offset=10,
        text="trial text",
    )

    second = chunker._create_chunk_id(
        identity=identity,
        chunk_index=0,
        start_offset=0,
        end_offset=10,
        text="trial text",
    )

    assert first == second
    assert len(first) == 64
    assert all(
        character in "0123456789abcdef"
        for character in first
    )


@pytest.mark.parametrize(
    (
        "changed_field",
        "changed_value",
    ),
    [
        (
            "chunk_index",
            1,
        ),
        (
            "start_offset",
            1,
        ),
        (
            "end_offset",
            11,
        ),
        (
            "text",
            "different text",
        ),
    ],
)
def test_create_chunk_id_changes_with_identity_input(
    changed_field: str,
    changed_value: object,
) -> None:
    chunker = RecursiveCharacterChunker()
    identity = create_identity()

    values = {
        "identity": identity,
        "chunk_index": 0,
        "start_offset": 0,
        "end_offset": 10,
        "text": "trial text",
    }

    original = chunker._create_chunk_id(
        **values
    )

    values[changed_field] = changed_value

    changed = chunker._create_chunk_id(
        **values
    )

    assert changed != original