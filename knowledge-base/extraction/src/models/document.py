from typing import Optional
from dataclasses import dataclass, field


@dataclass
class DocumentMetadata:

    study_id: Optional[str] = None
    document_type: Optional[str] = None
    version: Optional[str] = None
    sponsor: Optional[str] = None
    phase: Optional[str] = None



@dataclass
class DocumentPage:

    page_number: int
    text: str

    start_offset: int
    end_offset: int

    word_count: int = 0
    quality_score: float = 0.0

    requires_ocr: bool = False
    ocr_applied: bool = False

    extraction_method: str = "TEXT"


@dataclass
class DocumentTable:

    table_id: str
    page_number: int
    s3_key: str
    row_count: int
    column_count: int
    title: str | None = None

@dataclass
class DocumentImage:

    image_id: str
    page_number: int
    extension: str
    s3_key: str
    width: int
    height: int

@dataclass
class ClinicalDocument:

    document_id: str
    file_name: str
    file_format: str

    source_bucket: str = ""
    source_key: str = ""
    local_file_path: str = ""

    canonical_bucket: str = ""
    canonical_key: str = ""

    metadata: DocumentMetadata = field(default_factory=DocumentMetadata)

    raw_text: str = ""
    pages: list[DocumentPage] = field(default_factory=list)

    page_count: int = 0
    ocr_page_count: int = 0
    
    image_count: int = 0
    table_count: int = 0

    images: list[DocumentImage] = field(default_factory=list)
    tables: list[DocumentTable] = field(default_factory=list)

    warnings: list[str] = field(default_factory=list)

    source_version_id: str = ""
    processing_schema_version: str = ""

    already_processed: bool = False
    processing_status: str = "PENDING"
   

    error_message: Optional[str] = None