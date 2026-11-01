import json
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).parents[1] / "data"

def fixture_path(relative: str) -> Path:
    path = (DATA_DIR / relative).resolve()
    if DATA_DIR.resolve() not in path.parents:
        raise ValueError("Fixture path escapes tests/data.")
    return path

def read_json(relative: str) -> Any:
    return json.loads(fixture_path(relative).read_text(encoding="utf-8"))

def read_text(relative: str) -> str:
    return fixture_path(relative).read_text(encoding="utf-8")
