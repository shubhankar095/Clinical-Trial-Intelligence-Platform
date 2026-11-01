import pytest
from indexers.opensearch_indexer import OpenSearchIndexer
pytestmark=[pytest.mark.contract,pytest.mark.local]

def test_mapping_contains_every_index_record_field():
    indexer=object.__new__(OpenSearchIndexer)
    properties=indexer._index_definition(384)["mappings"]["properties"]
    expected={"index_record_id","index_schema_version","document_id","ingestion_id","ingestion_profile_id","chunk_id","chunk_index","text","character_count","start_offset","end_offset","start_page","end_page","embedding","embedding_provider","embedding_model_id","embedding_dimensions","embedding_normalized","input_token_count","file_name","file_format","source_bucket","source_key","source_version_id","canonical_bucket","canonical_key","study_id","document_type","document_version","sponsor","phase"}
    assert expected==set(properties)
    assert properties["embedding"]["dimension"]==384
