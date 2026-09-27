from models.document import (
    ClinicalDocument,
)
from storage.base_document_store import (
    BaseDocumentStore,
)


class ConcreteDocumentStore(
    BaseDocumentStore
):

    def save(
        self,
        document,
    ):
        return BaseDocumentStore.save(
            self,
            document,
        )


def test_base_save_returns_none():
    store = ConcreteDocumentStore()

    document = ClinicalDocument(
        document_id="document-123",
        file_name="sample.pdf",
        file_format="pdf",
    )

    assert (
        store.save(document)
        is None
    )
