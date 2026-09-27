from typing import Optional
from dataclasses import dataclass, field


@dataclass
class DocumentChunk:

    chunk_id: str

    text: str

    start_offset: int
    end_offset: int

    start_page: Optional[int] = None
    end_page: Optional[int] = None

    embedding: list[float] = field(default_factory=list)

    metadata: dict = field(default_factory=dict)

