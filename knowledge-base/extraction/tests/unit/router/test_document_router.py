from unittest.mock import Mock

import pytest

from processors.unsupported_file import (
    UnsupportedFileProcessor,
)
from router import document_router


pytestmark = pytest.mark.unit


class FakeProcessor:

    pass


def test_pdf_processor_is_selected(
    monkeypatch,
):
    fake_processor = FakeProcessor()

    monkeypatch.setitem(
        document_router.PROCESSOR_FACTORIES,
        "pdf",
        lambda: fake_processor,
    )

    result = document_router.get_processor(
        "pdf"
    )

    assert result is fake_processor


def test_extension_is_case_insensitive(
    monkeypatch,
):
    fake_processor = FakeProcessor()

    monkeypatch.setitem(
        document_router.PROCESSOR_FACTORIES,
        "pdf",
        lambda: fake_processor,
    )

    result = document_router.get_processor(
        "PDF"
    )

    assert result is fake_processor


def test_leading_period_is_removed(
    monkeypatch,
):
    fake_processor = FakeProcessor()

    monkeypatch.setitem(
        document_router.PROCESSOR_FACTORIES,
        "pdf",
        lambda: fake_processor,
    )

    result = document_router.get_processor(
        ".pdf"
    )

    assert result is fake_processor


@pytest.mark.parametrize(
    "extension",
    [
        "docx",
        "txt",
        "csv",
        "unknown",
    ],
)
def test_unsupported_extension_returns_unsupported_processor(
    extension,
):
    result = document_router.get_processor(
        extension
    )

    assert isinstance(
        result,
        UnsupportedFileProcessor,
    )

    assert result.extension == extension


def test_factory_exception_is_propagated(
    monkeypatch,
):
    def failing_factory():
        raise RuntimeError(
            "Factory failed"
        )

    monkeypatch.setitem(
        document_router.PROCESSOR_FACTORIES,
        "pdf",
        failing_factory,
    )

    with pytest.raises(
        RuntimeError,
        match="Factory failed",
    ):
        document_router.get_processor(
            "pdf"
        )


def test_create_pdf_processor_uses_configured_dependencies(
    monkeypatch,
):
    fake_ocr = object()
    fake_processor = object()

    ocr_factory = Mock(
        return_value=fake_ocr
    )

    processor_factory = Mock(
        return_value=fake_processor
    )

    monkeypatch.setattr(
        document_router,
        "TextractOCR",
        ocr_factory,
    )

    monkeypatch.setattr(
        document_router,
        "PDFProcessor",
        processor_factory,
    )

    result = (
        document_router
        ._create_pdf_processor()
    )

    assert result is fake_processor

    ocr_factory.assert_called_once_with()

    processor_factory.assert_called_once_with(
        ocr_processor=fake_ocr,
        pages_to_read=(
            document_router.pages_to_read
        ),
        min_words_per_page=(
            document_router
            .min_words_per_page
        ),
        min_quality_score=(
            document_router
            .min_quality_score
        ),
    )
