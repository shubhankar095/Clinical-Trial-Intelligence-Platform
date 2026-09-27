import json
from dataclasses import asdict
from models.document import ClinicalDocument


class DocumentSerializer:

    @staticmethod
    def serialize(document: ClinicalDocument) -> str:

        payload = asdict(document)

        payload.pop("local_file_path", None )

        return json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        )