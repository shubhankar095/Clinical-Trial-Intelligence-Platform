from dataclasses import FrozenInstanceError
import pytest
from models.storage_location import StorageLocation
pytestmark = pytest.mark.unit

def test_normalizes_values():
    value = StorageLocation(" bucket ", " key.json ", " v1 ")
    assert (value.bucket, value.key, value.version_id) == ("bucket", "key.json", "v1")

def test_allows_blank_bucket_for_non_s3_store():
    assert StorageLocation("  ", "key").bucket == ""

@pytest.mark.parametrize("key", ["", " ", "\n"])
def test_rejects_blank_key(key):
    with pytest.raises(ValueError, match="key must not be empty"):
        StorageLocation("bucket", key)

@pytest.mark.parametrize("version", ["", " ", "\n"])
def test_rejects_blank_version(version):
    with pytest.raises(ValueError, match="must not be blank"):
        StorageLocation("bucket", "key", version)

@pytest.mark.parametrize("field,value", [("bucket", None), ("bucket", 1), ("key", None), ("key", 1)])
def test_requires_string_bucket_and_key(field, value):
    data={"bucket":"bucket", "key":"key"}; data[field]=value
    with pytest.raises(TypeError): StorageLocation(**data)

def test_is_immutable():
    value=StorageLocation("bucket", "key")
    with pytest.raises(FrozenInstanceError): value.key="other"  # type: ignore[misc]

def test_version_id_must_be_string_when_present():
    with pytest.raises(TypeError, match="version_id must be a string"):
        StorageLocation("bucket", "key", 1)
