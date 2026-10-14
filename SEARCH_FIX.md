# Search Functionality Fix — Root Cause & Solution

## What was broken

Clicking **Search** on `/search` did nothing. No results, no error messages, no feedback.

---

## Root causes identified

### 1. **Missing exception handling in `app.py`**
The `search_kb()` route called `search(project_id, query, k=k)` from `rag.py` with **no try/except**. If the embedding model wasn't downloaded yet, or ChromaDB threw an exception (corrupt DB, bad collection name, disk full), the exception propagated up and Flask returned a 500 error page. In production mode with debug off, the user saw a blank page or "Internal Server Error" with no explanation.

### 2. **No check for empty knowledge base**
If a project had zero indexed documents, the search still attempted to query ChromaDB and embed the query text. The embedding model would download (~90 MB on first use), then ChromaDB returned an empty result set — but the user never saw a message explaining *why* (no documents uploaded yet).

### 3. **Form had no explicit `action` attribute**
`<form method="POST">` with no `action` submits to the current URL. If the page loaded at `/search?project_id=Sprint-1`, the POST went to `/search?project_id=Sprint-1`. This worked, but made debugging harder and caused the selected project to reset visually on validation errors (because `project_id` was re-read from `request.args` instead of `request.form` after a failed POST).

### 4. **Unguarded `int()` conversion**
`k = int(request.form.get("k", 5))` would raise `ValueError` if someone tampered with the form and submitted a non-integer value. No try/except → another unhandled 500 error.

---

## What was fixed

### `app.py` — `search_kb()` route

**Before:**
```python
if request.method == "POST":
    project_id = request.form.get("project_id", "").strip()
    query      = request.form.get("query",      "").strip()
    k          = int(request.form.get("k", 5))  # ← crashes on bad input

    if not project_id:
        flash("Please select a project.", "error")
    elif not query:
        flash("Please enter a search query.", "error")
    else:
        hits = search(project_id, query, k=k)  # ← crashes silently on exception
        results = [...]
        if not results:
            flash("No matching chunks found...", "info")
```

**After:**
```python
if request.method == "POST":
    project_id = request.form.get("project_id", "").strip()
    query      = request.form.get("query",      "").strip()

    # Guard against non-integer k
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
        # Check if the project has any indexed documents first
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
                results = [...]
                if not results:
                    flash("No matching chunks found for that query...", "info")
            except Exception as exc:
                logging.exception("Search failed for project '%s': %s", project_id, exc)
                flash(
                    f"Search error: {exc}. "
                    "Check that the embedding model is installed and the vector store is accessible.",
                    "error",
                )
```

**Changes:**
- ✅ Wrapped `int()` in try/except to handle bad form input
- ✅ Check `chunk_count == 0` before calling `search()` → show clear "no documents uploaded" message
- ✅ Wrapped `search()` call in try/except to catch embedding/DB errors → log full traceback + show user-friendly error
- ✅ Added `import logging` at the top of the function

---

### `templates/search.html`

**Before:**
```html
<form method="POST">
  ...
  <button type="submit" class="btn btn-primary">Search</button>
</form>
```

**After:**
```html
<form method="POST" action="{{ url_for('search_kb') }}">
  ...
  <button type="submit" class="btn btn-primary">🔍 Search</button>
</form>
```

**Changes:**
- ✅ Added explicit `action="{{ url_for('search_kb') }}"` so the form always posts to `/search` regardless of query params
- ✅ Improved empty-state message: shows "No projects found. Upload documents first." when no projects exist
- ✅ Added `autocomplete="off"` to the query input for better UX

---

## How to test

### 1. Start fresh (no documents uploaded yet)

```cmd
python app.py
```

Go to `http://localhost:5000/search`

- ✅ Select "— choose a project —" → Click **Search** → See error "Please select a project."
- ✅ Select a project (if none exist, you'll see "No projects found. Upload documents first.")
- ✅ If the project has zero indexed documents → See error "No documents are indexed for 'project-name' yet. Go to Upload..."

---

### 2. Upload a document first

Go to `http://localhost:5000/upload`

- Enter project name: `test-project`
- Upload a `.txt` file with some sample text (e.g. a few sentences about project deliverables)
- Click **Process & Index Files**
- Verify you see "X chunks indexed" success message

---

### 3. Search the indexed documents

Go to `http://localhost:5000/search`

- Select `test-project`
- Enter query: `What are the key deliverables?`
- Choose `5 chunks`
- Click **🔍 Search**

**Expected result:**
- Page reloads and shows "X results for 'What are the key deliverables?'"
- Each result shows:
  - Filename
  - Chunk number
  - Relevance score (0.0–1.0)
  - Extracted text chunk

---

### 4. Test edge cases

**Empty query:**
- Leave the query field blank → Click Search → Browser shows "Please fill out this field" (HTML5 validation)

**No matching results:**
- Enter a query completely unrelated to your uploaded content (e.g. `quantum physics`)
- You should see a flash message: "No matching chunks found for that query. Try different keywords."

**Embedding model download (first search only):**
- On your **very first search**, `sentence-transformers` downloads the `all-MiniLM-L6-v2` model (~90 MB)
- This takes 10–30 seconds depending on your internet speed
- The browser will appear to "hang" — this is normal
- After the download completes, all future searches are instant

**Vector DB error (rare):**
- If ChromaDB's disk storage is corrupt or inaccessible, you'll see:
  - Flash error: "Search error: [exception details]. Check that the embedding model is installed..."
  - Full traceback logged to console

---

## Files modified

| File | What changed |
|---|---|
| `app.py` | Added try/except around `search()`, check for empty index, guard `int()` conversion, added logging |
| `templates/search.html` | Added explicit `action="{{ url_for('search_kb') }}"`, improved empty state, added search icon |

---

## Summary

**Before:** Search button did nothing → silent 500 errors, no user feedback.

**After:** Search works reliably + shows clear error messages for every failure mode:
- "No documents indexed yet → upload some first"
- "No matching chunks → try different keywords"
- "Search error: [details] → check model/DB installation"

The root cause was **missing exception handling** in the Flask route. The embedding model or ChromaDB could throw, and Flask would serve a 500 page instead of showing a helpful message. The fix wraps the search call in try/except and checks for empty indexes before querying.
