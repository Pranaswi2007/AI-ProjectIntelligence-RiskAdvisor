"""
RAG Pipeline — Chunking, Embedding, and Vector Indexing
========================================================
Step 1 : chunk_document  — split a Document into overlapping Chunks
Step 2 : embed_texts      — convert text to 384-dim vectors (sentence-transformers)
Step 3 : index_document   — store chunks in ChromaDB (one collection per project)
Step 4 : search           — retrieve the k most relevant chunks for a query
Helpers: list_sources, delete_document, get_project_stats
"""

import re
from typing import Optional

import chromadb
from langchain_text_splitters import RecursiveCharacterTextSplitter

from models import Chunk, Document, SearchResult

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CHROMA_PATH  = "./chroma_db"          # folder where the vector DB is persisted
EMBED_MODEL  = "all-MiniLM-L6-v2"    # ~90 MB, runs on CPU, 384-dim embeddings
CHUNK_SIZE   = 800                    # max characters per chunk
CHUNK_OVERLAP = 100                   # characters shared between neighbouring chunks

_model  = None   # sentence-transformer model (lazy-loaded)
_client = None   # ChromaDB persistent client (lazy-loaded)


# ---------------------------------------------------------------------------
# Step 1: Chunking
# ---------------------------------------------------------------------------

def chunk_document(doc: Document) -> list[Chunk]:
    """Split a Document into overlapping Chunks.

    The splitter tries paragraph breaks → line breaks → sentence ends → words,
    so each chunk stays as semantically coherent as possible.
    Overlap ensures a sentence split at a boundary still appears whole in one
    of the two neighbouring chunks.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    pieces = splitter.split_text(doc.text)
    return [
        Chunk(
            id=f"{doc.id}-{i}",
            document_id=doc.id,
            project_id=doc.project_id,
            source=doc.filename,
            index=i,
            text=piece,
        )
        for i, piece in enumerate(pieces)
    ]


# ---------------------------------------------------------------------------
# Step 2: Embeddings
# ---------------------------------------------------------------------------

def get_model():
    """Load the embedding model once (first call downloads ~90 MB)."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(EMBED_MODEL)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Convert a list of strings into 384-dimensional embedding vectors.

    Texts with similar meaning will have vectors pointing in similar directions,
    which is what makes semantic search possible.
    """
    vectors = get_model().encode(
        texts,
        normalize_embeddings=True,   # unit-length vectors → cosine sim = dot product
        show_progress_bar=False,
    )
    return vectors.tolist()


# ---------------------------------------------------------------------------
# Step 3: Vector Store
# ---------------------------------------------------------------------------

def _get_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=CHROMA_PATH)
    return _client


def get_collection(project_id: str):
    """Return (or create) the ChromaDB collection for a project.

    Collection names must only contain letters, digits, underscores, hyphens.
    """
    name = "project_" + re.sub(r"[^a-zA-Z0-9_-]", "_", project_id)
    return _get_client().get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )


def index_document(doc: Document) -> int:
    """Chunk, embed and store one Document.

    If the same file was uploaded before, its old chunks are removed first so a
    re-upload does not leave stale data behind.

    Returns the number of chunks stored.
    """
    chunks = chunk_document(doc)
    if not chunks:
        return 0

    collection = get_collection(doc.project_id)

    # Remove any previous version of this file
    collection.delete(where={"source": doc.filename})

    collection.add(
        ids=[c.id for c in chunks],
        documents=[c.text for c in chunks],
        embeddings=embed_texts([c.text for c in chunks]),
        metadatas=[
            {
                "source":       c.source,
                "chunk_index":  c.index,
                "document_id":  c.document_id,
            }
            for c in chunks
        ],
    )
    return len(chunks)


def delete_document(project_id: str, filename: str) -> int:
    """Remove all chunks belonging to a specific file from the vector store.

    Returns the number of chunks deleted.
    """
    collection = get_collection(project_id)
    existing = collection.get(where={"source": filename}, include=["metadatas"])
    count = len(existing["metadatas"])
    if count:
        collection.delete(where={"source": filename})
    return count


# ---------------------------------------------------------------------------
# Step 4: Retrieval
# ---------------------------------------------------------------------------

def search(
    project_id: str,
    query: str,
    k: int = 5,
    min_score: float = 0.0,
) -> list[SearchResult]:
    """Return the k chunks most semantically similar to the query.

    Args:
        project_id: which project's knowledge base to search.
        query:      natural-language question or keyword phrase.
        k:          maximum number of results to return.
        min_score:  discard results below this cosine similarity (0–1).
    """
    collection = get_collection(project_id)
    total = collection.count()
    if total == 0:
        return []

    result = collection.query(
        query_embeddings=embed_texts([query]),
        n_results=min(k, total),
        include=["documents", "metadatas", "distances"],
    )

    hits: list[SearchResult] = []
    for text, meta, dist in zip(
        result["documents"][0],
        result["metadatas"][0],
        result["distances"][0],
    ):
        score = round(1.0 - dist, 4)   # cosine distance → similarity
        if score >= min_score:
            hits.append(
                SearchResult(
                    text=text,
                    source=meta["source"],
                    chunk_index=meta["chunk_index"],
                    score=score,
                    document_id=meta.get("document_id", ""),
                )
            )

    hits.sort(key=lambda h: h.score, reverse=True)
    return hits


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def list_sources(project_id: str) -> dict[str, int]:
    """Return {filename: chunk_count} for every indexed file in this project."""
    collection = get_collection(project_id)
    metas = collection.get(include=["metadatas"])["metadatas"]
    counts: dict[str, int] = {}
    for m in metas:
        counts[m["source"]] = counts.get(m["source"], 0) + 1
    return counts


def get_project_stats(project_id: str) -> dict:
    """Summary statistics for the project's knowledge base."""
    sources = list_sources(project_id)
    collection = get_collection(project_id)
    return {
        "project_id":     project_id,
        "document_count": len(sources),
        "chunk_count":    collection.count(),
        "sources":        sources,
    }
