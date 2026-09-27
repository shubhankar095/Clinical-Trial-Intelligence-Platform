from models.document import (
    ClinicalDocument,
)
from processors.base_processor import (
    BaseProcessor,
)


class ConcreteProcessor(
    BaseProcessor
):

    def process(
        self,
        document,
    ):
        return BaseProcessor.process(
            self,
            document,
        )


def test_base_processor_configures_logger():
    processor = ConcreteProcessor()

    assert processor.logger is not None

    assert (
        processor.logger.name
        == "ConcreteProcessor"
    )


def test_base_process_returns_none():
    processor = ConcreteProcessor()

    document = ClinicalDocument(
        document_id="document-123",
        file_name="sample.pdf",
        file_format="pdf",
    )

    assert (
        processor.process(document)
        is None
    )
