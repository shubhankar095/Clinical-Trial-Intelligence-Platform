from ocr.base_ocr import BaseOCR
from aws_utils.textract import TextractService


class TextractOCR(BaseOCR):

    def __init__(self):
        self.textract_service = TextractService()

    def extract_text(self, image_bytes: bytes) -> str:

        response = self.textract_service.extract_text(image_bytes)

        lines = []

        for block in response["Blocks"]:

            if block["BlockType"] == "LINE":

                lines.append(
                    block["Text"]
                )

        return "\n".join(lines)