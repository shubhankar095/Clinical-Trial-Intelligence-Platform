from models.document import ClinicalDocument
from services.chunking_service import ChunkingService
from services.indexing_service import IndexingService
from services.embedding_service import EmbeddingService
from indexers.opensearch_indexer import OpenSearchIndexer
from chunkers.recursive_character_chunker import RecursiveCharacterChunker
from embedders.sentence_transformer_embedder import SentenceTransformerEmbedder



class DocumentProcessingService:

    def __init__(self):

        self.chunking_service = ChunkingService(RecursiveCharacterChunker())

        self.embedding_service = EmbeddingService(SentenceTransformerEmbedder())

        self.indexing_service = IndexingService(OpenSearchIndexer())


    def process_document(
        self,
        bucket_name: str,
        object_key: str,
        s3_metadata: dict
    ) -> ClinicalDocument:

        # Step 1
        document = (
            self.registration_service.register(
                bucket_name=bucket_name,
                object_key=object_key,
                s3_metadata=s3_metadata
            )
        )

        # Step 2
        processor = get_processor(document.file_format)

        # Step 3
        document = processor.process(document)

        # Step 4
        document = self.chunking_service.chunk_document(document)

        # Step 5
        document = self.embedding_service.embed_document(document)

        # Step 6
        document = self.indexing_service.index_document(document)

        return document