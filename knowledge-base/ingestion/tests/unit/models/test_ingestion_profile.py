import pytest
from models.ingestion_profile import IngestionProfile
pytestmark = pytest.mark.unit

def test_normalizes_and_canonicalizes(profile_factory):
    p=profile_factory(embedding_provider=" BEDROCK ", embedding_model_options_json='{ "z": 2, "a": 1 }')
    assert p.embedding_provider == "bedrock"
    assert p.embedding_model_options_json == '{"a":1,"z":2}'

@pytest.mark.parametrize("field", ["ingestion_schema_version","chunker_type","chunker_version","embedding_provider","embedding_model_id","embedding_model_options_json","index_schema_version"])
def test_rejects_blank_required_strings(profile_factory, field):
    with pytest.raises((TypeError, ValueError)): profile_factory(**{field:"  "})

@pytest.mark.parametrize("field,value", [("chunk_size",0),("chunk_size",-1),("chunk_overlap",-1),("embedding_dimensions",0)])
def test_rejects_invalid_numbers(profile_factory, field, value):
    with pytest.raises((TypeError, ValueError)): profile_factory(**{field:value})

def test_overlap_must_be_less_than_size(profile_factory):
    with pytest.raises(ValueError): profile_factory(chunk_size=100, chunk_overlap=100)

@pytest.mark.parametrize("value", ["not-json", "[]", "null", '"x"'])
def test_options_must_be_json_object(profile_factory, value):
    with pytest.raises(ValueError): profile_factory(embedding_model_options_json=value)

def test_normalize_must_be_boolean(profile_factory):
    with pytest.raises(TypeError): profile_factory(embedding_normalize="true")

@pytest.mark.parametrize(
    "field",
    ["ingestion_schema_version", "chunker_type", "chunker_version", "embedding_provider",
     "embedding_model_id", "embedding_model_options_json", "index_schema_version"],
)
def test_required_fields_must_be_strings(profile_factory, field):
    with pytest.raises(TypeError):
        profile_factory(**{field: None})

@pytest.mark.parametrize(
    "field",
    ["chunk_size", "chunk_overlap", "embedding_dimensions"],
)
def test_numeric_fields_must_be_integers(profile_factory, field):
    with pytest.raises(TypeError):
        profile_factory(**{field: True})

def test_chunk_overlap_must_be_integer(profile_factory):
    with pytest.raises(TypeError):
        profile_factory(chunk_overlap=1.5)

def test_embedding_dimensions_must_be_integer(profile_factory):
    with pytest.raises(TypeError):
        profile_factory(embedding_dimensions=1.5)
