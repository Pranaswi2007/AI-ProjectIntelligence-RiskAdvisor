"""
AI Project Intelligence & Risk Advisor — Flask Application
===========================================================
Milestone 1: Document ingestion, RAG pipeline, and knowledge-base search.

Routes
------
GET  /                        → Dashboard (project stats + recent uploads)
GET  /upload                  → Upload page
POST /upload                  → Process uploaded files
GET  /knowledge-base          → Browse indexed documents per project
POST /knowledge-base/delete   → Remove a document from the vector store
GET  /search                  → Search form
POST /search                  → Execute RAG search and show results
"""

import os
import uuid
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, url_for

from ingestion import LOADERS, ingest_file
from rag import delete_document, get_project_stats, index_document, list_sources, search

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "dev-secret-change-in-prod")

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {ext.lstrip(".") for ext in LOADERS}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_all_projects() -> list[dict]:
    """Scan the uploads folder and build a list of project summaries."""
    projects = []
    if UPLOAD_DIR.exists():
        for folder in sorted(UPLOAD_DIR.iterdir()):
            if folder.is_dir():
                stats = get_project_stats(folder.name)
                projects.append({
                    "id":   folder.name,
                    "name": folder.name.replace("-", " ").title(),
                    **stats,
                })
    return projects


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def dashboard():
    projects = get_all_projects()
    total_docs   = sum(p["document_count"] for p in projects)
    total_chunks = sum(p["chunk_count"]    for p in projects)
    return render_template(
        "dashboard.html",
        projects=projects,
        total_docs=total_docs,
        total_chunks=total_chunks,
    )


@app.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "GET":
        return render_template("upload.html", allowed=sorted(ALLOWED_EXTENSIONS))

    # ---- POST: process uploaded files ----
    project_id = request.form.get("project_id", "").strip()
    if not project_id:
        flash("Please enter a project name.", "error")
        return redirect(url_for("upload"))

    # Sanitise project_id — keep only alphanumeric, hyphens, underscores
    project_id = "".join(c if c.isalnum() or c in "-_" else "-" for c in project_id).strip("-")
    if not project_id:
        flash("Invalid project name. Use letters, numbers, hyphens or underscores.", "error")
        return redirect(url_for("upload"))

    files = request.files.getlist("documents")
    if not files or all(f.filename == "" for f in files):
        flash("No files selected.", "error")
        return redirect(url_for("upload"))

    project_dir = UPLOAD_DIR / project_id
    project_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for f in files:
        if f.filename == "":
            continue
        if not allowed_file(f.filename):
            results.append({"name": f.filename, "status": "error",
                             "message": f"Unsupported type. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"})
            continue

        save_path = project_dir / f.filename
        f.save(str(save_path))

        try:
            doc   = ingest_file(str(save_path), project_id)
            n     = index_document(doc)
            results.append({
                "name":    f.filename,
                "status":  "success",
                "message": f"{n} chunks indexed  |  {doc.word_count:,} words",
            })
        except Exception as exc:
            results.append({"name": f.filename, "status": "error", "message": str(exc)})

    return render_template("upload_result.html", project_id=project_id, results=results)


@app.route("/knowledge-base")
def knowledge_base():
    project_id = request.args.get("project_id", "").strip()
    projects   = get_all_projects()

    sources = {}
    if project_id:
        sources = list_sources(project_id)

    return render_template(
        "knowledge_base.html",
        projects=projects,
        selected_project=project_id,
        sources=sources,
    )


@app.route("/knowledge-base/delete", methods=["POST"])
def kb_delete():
    project_id = request.form.get("project_id", "").strip()
    filename   = request.form.get("filename",   "").strip()

    if project_id and filename:
        deleted = delete_document(project_id, filename)
        # Also remove the file from disk if it exists
        disk_path = UPLOAD_DIR / project_id / filename
        if disk_path.exists():
            disk_path.unlink()
        flash(f"Removed '{filename}' ({deleted} chunks deleted).", "success")
    else:
        flash("Invalid delete request.", "error")

    return redirect(url_for("knowledge_base", project_id=project_id))


@app.route("/search", methods=["GET", "POST"])
def search_kb():
    import logging
    projects   = get_all_projects()
    results    = []
    query      = ""
    k          = 5
    # Seed project selector from URL param on GET; overridden by form on POST
    project_id = request.args.get("project_id", "").strip() or \
                 (projects[0]["id"] if projects else "")

    if request.method == "POST":
        project_id = request.form.get("project_id", "").strip()
        query      = request.form.get("query",      "").strip()

        # Guard against non-integer k values
        try:
            k = int(request.form.get("k", 5))
            if k < 1:
                k = 1
        except (ValueError, TypeError):
            k = 5

        if not project_id:
            flash("Please select a project.", "error")
        elif not query:
            flash("Please enter a search query.", "error")
        else:
            # Check the project has indexed documents before hitting the model
            stats = get_project_stats(project_id)
            if stats["chunk_count"] == 0:
                flash(
                    f"No documents are indexed for '{project_id}' yet. "
                    "Go to Upload and add some documents first.",
                    "error",
                )
            else:
                try:
                    hits = search(project_id, query, k=k)
                    results = [
                        {
                            "source":      h.source,
                            "chunk_index": h.chunk_index,
                            "score":       h.score,
                            "text":        h.text,
                        }
                        for h in hits
                    ]
                    if not results:
                        flash(
                            "No matching chunks found for that query. "
                            "Try different keywords.",
                            "info",
                        )
                except Exception as exc:
                    logging.exception("Search failed for project '%s': %s", project_id, exc)
                    flash(
                        f"Search error: {exc}. "
                        "Check that the embedding model is installed and the vector store is accessible.",
                        "error",
                    )

    return render_template(
        "search.html",
        projects=projects,
        selected_project=project_id,
        query=query,
        results=results,
        k=k,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True, port=5000)
