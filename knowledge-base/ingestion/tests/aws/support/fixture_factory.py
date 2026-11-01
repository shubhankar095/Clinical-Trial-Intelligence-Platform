from __future__ import annotations
import copy, hashlib, json, uuid
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class PublishedFixture:
    run_id: str; document_id: str; prefix: str; manifest_key: str; keys: tuple[str,...]

def fixture_directory() -> Path:
    root=Path(__file__).resolve().parents[2]/"data"/"canonical-documents"
    return next(path for path in root.iterdir() if path.is_dir())

def publish_fixture(deployment, *, invalid: bool=False) -> PublishedFixture:
    source=fixture_directory(); run_id=uuid.uuid4().hex
    original_document_id=source.name
    document_id=hashlib.sha256(f"aws-test:{run_id}".encode()).hexdigest()
    prefix=f"canonical-documents/{document_id}"; s3=deployment.client("s3"); keys=[]
    for path in sorted(source.rglob("*")):
        if not path.is_file() or path.name=="_SUCCESS.json": continue
        relative=path.relative_to(source).as_posix(); key=f"{prefix}/{relative}"
        body=path.read_bytes()
        if path.suffix==".json":
            text=body.decode().replace(original_document_id,document_id).replace("clinical-kb-processed-dev",deployment.canonical_bucket)
            body=text.encode()
        if path.name=="extracted-document.json":
            payload=json.loads(body); payload["document_id"]=document_id
            payload["canonical_bucket"]=deployment.canonical_bucket
            payload["canonical_key"]=f"{prefix}/extracted-document.json"
            payload["source_version_id"]=f"aws-test-{run_id}"
            body=json.dumps(payload,separators=(",",":"),sort_keys=True).encode()
            if invalid: body=b'{"document_id":"invalid"}'
        s3.put_object(Bucket=deployment.canonical_bucket,Key=key,Body=body); keys.append(key)
    manifest=json.loads((source/"_SUCCESS.json").read_text()); manifest["document_id"]=document_id
    manifest["canonical_bucket"]=deployment.canonical_bucket
    manifest["canonical_key"]=f"{prefix}/extracted-document.json"
    manifest["source_version_id"]=f"aws-test-{run_id}"
    trigger=f"{prefix}/_SUCCESS.json"
    s3.put_object(Bucket=deployment.canonical_bucket,Key=trigger,
      Body=json.dumps(manifest,separators=(",",":"),sort_keys=True).encode(),ContentType="application/json")
    keys.append(trigger)
    return PublishedFixture(run_id,document_id,prefix,trigger,tuple(keys))

########################################################################
