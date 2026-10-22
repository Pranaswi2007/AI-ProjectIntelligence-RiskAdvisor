# AI Project Intelligence & Risk Advisor

## Project Overview

The **AI Project Intelligence & Risk Advisor** is an AI-powered application designed to help software development teams and student project groups manage project information more effectively.

Project-related information is often scattered across proposals, meeting notes, progress reports, task lists, and other documents. Manually analyzing these documents can be time-consuming and may cause teams to overlook important risks, blockers, and delivery challenges.

This project aims to build a unified, RAG-powered project knowledge base that organizes uploaded documents and enables intelligent information retrieval. The initial milestone focuses on document ingestion, text processing, embedding generation, vector storage, and semantic search.

## Objectives

- Accept different types of project-related documents.
- Extract and process text from uploaded files.
- Divide documents into smaller, meaningful chunks.
- Generate text embeddings for semantic representation.
- Store document chunks and embeddings in a vector database.
- Retrieve relevant project information using semantic search.
- Establish the foundation for future AI-powered project intelligence and risk analysis.

## Technologies Used

- **Python** — Core programming language
- **Streamlit** — User interface
- **Sentence Transformers** — Text embedding generation
- **ChromaDB** — Vector storage and retrieval
- **Pandas** — CSV processing and data handling
- **PyPDF** — PDF text extraction
- **python-docx** — DOCX document processing

## Current Features

- Upload project documents in PDF, DOCX, CSV, and TXT formats.
- Extract text from supported document types.
- Split extracted text into manageable chunks.
- Generate embeddings using Sentence Transformers.
- Store document chunks and embeddings in ChromaDB.
- Search for relevant document content using semantic similarity.
- Access document processing and search functionality through a Streamlit interface.

## Modules Implemented — Milestone 1

**Milestone 1: Document Ingestion and RAG Pipeline Foundation**

- **Document Ingestion Module:** Supports uploading and processing PDF, DOCX, CSV, and plain-text files.
- **Text Processing Module:** Extracts document content and divides it into smaller chunks.
- **Embedding Generation Module:** Converts text chunks into numerical vector representations using Sentence Transformers.
- **Vector Storage Module:** Stores the generated embeddings and associated document content in ChromaDB.
- **Semantic Search Module:** Retrieves relevant document chunks based on the meaning of a search query.

## Project Status

**In Progress — Milestone 1 Completed**

The initial document ingestion and retrieval pipeline has been implemented. The application currently supports document uploads, text extraction, chunking, embedding generation, vector storage, and semantic search.

Future milestones will extend this foundation with AI agents for scope and deliverable extraction, risk detection, delivery forecasting, blocker identification, documentation generation, project health scoring, and conversational project assistance.

## How to Run

### Prerequisites

- Python installed on your system
- pip package manager

### 1. Clone the repository

```bash
git clone https://github.com/Pranaswi2007/AI-ProjectIntelligence-RiskAdvisor.git
```

### 2. Navigate to the project directory

```bash
cd AI-ProjectIntelligence-RiskAdvisor
```

### 3. Install the dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the application

```bash
python -m streamlit run app.py
```

Open the local URL displayed in your terminal to access the application.

## Future Development

The upcoming milestones will focus on:

- RAG-based question answering using retrieved project context.
- AI agents for scope extraction, risk identification, and delivery forecasting.
- Automatic identification of blockers and action items.
- Generation of user stories and risk registers.
- Project health scoring and insights dashboards.
- A conversational assistant for project-related queries.

## Author

**Pranaswi Ch**

GitHub: [Pranaswi2007](https://github.com/Pranaswi2007)

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
