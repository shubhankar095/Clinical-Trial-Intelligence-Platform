from ocr.base_ocr import BaseOCR


class ConcreteOCR(
    BaseOCR
):

    def extract_text(
        self,
        image_bytes,
    ):
        return BaseOCR.extract_text(
            self,
            image_bytes,
        )


def test_base_extract_text_returns_none():
    ocr = ConcreteOCR()

    assert (
        ocr.extract_text(
            b"image-content"
        )
        is None
    )
