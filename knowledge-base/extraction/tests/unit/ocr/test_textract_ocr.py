from unittest.mock import Mock

import pytest

from ocr.textract_ocr import (
    TextractOCR,
)


pytestmark = pytest.mark.unit


@pytest.fixture
def ocr():
    textract_ocr = TextractOCR()

    textract_ocr.textract_service = (
        Mock()
    )

    return textract_ocr


def test_extract_text_sends_image_bytes_to_textract(
    ocr,
):
    image_bytes = b"image-content"

    (
        ocr.textract_service
        .extract_text
        .return_value
    ) = {
        "Blocks": [],
    }

    ocr.extract_text(
        image_bytes
    )

    (
        ocr.textract_service
        .extract_text
        .assert_called_once_with(
            image_bytes
        )
    )


def test_extract_text_returns_line_blocks(
    ocr,
):
    (
        ocr.textract_service
        .extract_text
        .return_value
    ) = {
        "Blocks": [
            {
                "BlockType": "LINE",
                "Text": "First line",
            },
            {
                "BlockType": "LINE",
                "Text": "Second line",
            },
        ]
    }

    result = ocr.extract_text(
        b"image-content"
    )

    assert result == (
        "First line\n"
        "Second line"
    )


def test_extract_text_ignores_non_line_blocks(
    ocr,
):
    (
        ocr.textract_service
        .extract_text
        .return_value
    ) = {
        "Blocks": [
            {
                "BlockType": "PAGE",
            },
            {
                "BlockType": "WORD",
                "Text": "Ignored word",
            },
            {
                "BlockType": "LINE",
                "Text": "Included line",
            },
            {
                "BlockType": "CELL",
                "Text": "Ignored cell",
            },
        ]
    }

    result = ocr.extract_text(
        b"image-content"
    )

    assert result == (
        "Included line"
    )


def test_extract_text_preserves_line_order(
    ocr,
):
    (
        ocr.textract_service
        .extract_text
        .return_value
    ) = {
        "Blocks": [
            {
                "BlockType": "LINE",
                "Text": "Line three",
            },
            {
                "BlockType": "LINE",
                "Text": "Line one",
            },
            {
                "BlockType": "LINE",
                "Text": "Line two",
            },
        ]
    }

    result = ocr.extract_text(
        b"image-content"
    )

    assert result.splitlines() == [
        "Line three",
        "Line one",
        "Line two",
    ]


def test_extract_text_requires_blocks(
    ocr,
):
    (
        ocr.textract_service
        .extract_text
        .return_value
    ) = {}

    with pytest.raises(
        KeyError,
        match="Blocks",
    ):
        ocr.extract_text(
            b"image-content"
        )


def test_extract_text_returns_empty_string_for_empty_blocks(
    ocr,
):
    (
        ocr.textract_service
        .extract_text
        .return_value
    ) = {
        "Blocks": [],
    }

    result = ocr.extract_text(
        b"image-content"
    )

    assert result == ""


def test_extract_text_requires_text_for_line_block(
    ocr,
):
    (
        ocr.textract_service
        .extract_text
        .return_value
    ) = {
        "Blocks": [
            {
                "BlockType": "LINE",
            }
        ]
    }

    with pytest.raises(
        KeyError,
        match="Text",
    ):
        ocr.extract_text(
            b"image-content"
        )


def test_non_line_block_does_not_require_text(
    ocr,
):
    (
        ocr.textract_service
        .extract_text
        .return_value
    ) = {
        "Blocks": [
            {
                "BlockType": "PAGE",
            },
            {
                "BlockType": "CELL",
            },
        ]
    }

    result = ocr.extract_text(
        b"image-content"
    )

    assert result == ""


def test_extract_text_preserves_unicode(
    ocr,
):
    (
        ocr.textract_service
        .extract_text
        .return_value
    ) = {
        "Blocks": [
            {
                "BlockType": "LINE",
                "Text": "café",
            },
            {
                "BlockType": "LINE",
                "Text": "日本語",
            },
        ]
    }

    result = ocr.extract_text(
        b"image-content"
    )

    assert result == (
        "café\n"
        "日本語"
    )


def test_extract_text_propagates_textract_failure(
    ocr,
):
    (
        ocr.textract_service
        .extract_text
        .side_effect
    ) = RuntimeError(
        "Textract request failed"
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "Textract request failed"
        ),
    ):
        ocr.extract_text(
            b"image-content"
        )