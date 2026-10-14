import hashlib
import re
from pathlib import Path

import pandas as pd
import pdfplumber
from docx import Document as DocxDocument

from models import Document


# ---------------------------------------------------------------------------
# Loaders — one per supported file type, each returns raw text
# ---------------------------------------------------------------------------

def load_pdf(path: Path) -> str:
    """Read every page of a PDF and join the text."""
    pages = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or "")
    return "\n\n".join(pages)


def load_docx(path: Path) -> str:
    """Read paragraphs and tables from a Word document."""
    doc = DocxDocument(path)
    parts = [p.text for p in doc.paragraphs]
    # python-docx keeps tables separate from paragraphs
    for table in doc.tables:
        for row in table.rows:
            parts.append(" | ".join(cell.text.strip() for cell in row.cells))
    return "\n".join(parts)


def load_csv(path: Path) -> str:
    """Convert each CSV row into a self-contained readable line.

    E.g.  Task: Build login page, Owner: Asha, Status: Delayed
    Including the column name next to each value means a chunk that contains
    only this line is still meaningful on its own — important for retrieval.
    """
    df = pd.read_csv(path).fillna("").astype(str)
    lines = []
    for _, row in df.iterrows():
        lines.append(", ".join(f"{col}: {row[col]}" for col in df.columns))
    return "\n".join(lines)


def load_txt(path: Path) -> str:
    """Plain text, meeting notes, progress updates, markdown."""
    return path.read_text(encoding="utf-8", errors="ignore")


LOADERS: dict = {
    ".pdf":  load_pdf,
    ".docx": load_docx,
    ".csv":  load_csv,
    ".txt":  load_txt,
    ".md":   load_txt,
}

SUPPORTED_EXTENSIONS = list(LOADERS.keys())


# ---------------------------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------------------------

def clean_text(text: str) -> str:
    """Normalise whitespace and remove artefacts common in extracted text."""
    text = text.replace("\x00", "")               # stray null bytes from some PDFs
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)           # collapse runs of spaces/tabs
    text = re.sub(r"\n{3,}", "\n\n", text)        # at most one blank line in a row
    return text.strip()


# ---------------------------------------------------------------------------
# Document ID
# ---------------------------------------------------------------------------

def make_doc_id(project_id: str, filename: str) -> str:
    """Same project + same filename always produces the same ID.
    This lets us replace a file cleanly when it is re-uploaded."""
    raw = f"{project_id}/{filename}".encode("utf-8")
    return hashlib.md5(raw).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ingest_file(path: str, project_id: str) -> Document:
    """Load, clean and wrap a single file as a Document.

    Raises ValueError for unsupported types or files with no extractable text.
    """
    p = Path(path)
    ext = p.suffix.lower()

    if ext not in LOADERS:
        supported = ", ".join(sorted(LOADERS))
        raise ValueError(
            f"Unsupported file type '{ext}'. Supported: {supported}"
        )

    raw_text = LOADERS[ext](p)
    text = clean_text(raw_text)

    if not text:
        raise ValueError(
            f"No text could be extracted from '{p.name}'. "
            "Scanned PDFs (image-only) require OCR pre-processing."
        )

    return Document(
        id=make_doc_id(project_id, p.name),
        project_id=project_id,
        filename=p.name,
        file_type=ext.lstrip("."),
        text=text,
    )


def ingest_folder(folder: str, project_id: str) -> list[Document]:
    """Ingest every supported file in a folder.

    Unsupported or unreadable files are skipped with a printed warning.
    """
    docs: list[Document] = []
    for path in sorted(Path(folder).iterdir()):
        if path.suffix.lower() not in LOADERS:
            continue
        try:
            docs.append(ingest_file(str(path), project_id))
        except Exception as exc:
            print(f"[ingestion] Skipped '{path.name}': {exc}")
    return docs
