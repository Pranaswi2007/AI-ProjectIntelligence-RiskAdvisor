from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Document:
    """Represents an uploaded project artifact (PDF, DOCX, CSV, TXT)."""
    id: str
    project_id: str
    filename: str
    file_type: str          # pdf | docx | csv | txt | md
    text: str
    uploaded_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )
    char_count: int = 0
    word_count: int = 0

    def __post_init__(self):
        if self.text:
            self.char_count = len(self.text)
            self.word_count = len(self.text.split())


@dataclass
class Chunk:
    """A sub-section of a Document, ready for embedding."""
    id: str
    document_id: str
    project_id: str
    source: str          # original filename
    index: int           # position within the document
    text: str


@dataclass
class Project:
    """Tracks a named project and its ingestion state."""
    id: str
    name: str
    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )
    document_count: int = 0
    chunk_count: int = 0
    last_updated: Optional[str] = None

    def update_stats(self, new_doc_count: int, new_chunk_count: int):
        self.document_count = new_doc_count
        self.chunk_count = new_chunk_count
        self.last_updated = datetime.now().isoformat(timespec="seconds")


@dataclass
class SearchResult:
    """A single retrieved chunk returned by the RAG search."""
    text: str
    source: str
    chunk_index: int
    score: float          # cosine similarity, 0–1 (higher = more relevant)
    document_id: str = ""
