# Architecture

## Request Flow

1. A user uploads a file to `POST /documents/upload`.
2. The API stores the original file, creates a PostgreSQL document record, and mirrors raw metadata into MongoDB.
3. `POST /documents/process` parses the file, cleans text, splits it into overlapping chunks, creates embeddings, stores vectors and chunk text in PostgreSQL, and mirrors chunk metadata into MongoDB.
4. `POST /chat` creates or resumes a conversation, writes messages to PostgreSQL and Redis memory, then runs the agent workflow.
5. The workflow plans retrieval, executes hybrid search, ranks and deduplicates chunks, generates a cited answer, validates evidence coverage, scores the answer, and stores the run trace.

## Agent Graph

- Planner Agent: derives intent, task list, and retrieval strategy.
- Retrieval Agent: combines semantic vector similarity, keyword matching, and metadata filters.
- Context Ranking Agent: deduplicates chunks and keeps the strongest evidence.
- Response Agent: generates an answer grounded in ranked evidence.
- Validation Agent: checks citation coverage and flags unsupported output.
- Evaluation Agent: scores relevance, faithfulness, completeness, latency, and token usage.

## Storage

- PostgreSQL: users, conversations, messages, documents, embeddings, evaluations, prompt versions, experiments, and runs.
- MongoDB: raw document metadata and chunk metadata.
- Redis: short-term conversation memory for fast agent context.
- Upload storage: local filesystem by default; in production this should map to Azure Blob Storage.

## Observability

- `/metrics` exposes Prometheus counters and latency primitives.
- OpenTelemetry instruments FastAPI and sets the service resource name.
- Runs persist plan, final result, validation, evaluation, trace id placeholder, and error state.

## Production Extensions

- Replace JSON vectors with pgvector columns and HNSW/IVFFlat indexes.
- Move parsing and embedding to a queue-backed worker for high-volume ingestion.
- Add Azure AI Search as a vector backend behind `VectorStore`.
- Add authentication and tenant isolation.
- Stream long-running agent runs over server-sent events.
- Persist OpenTelemetry traces to Azure Monitor or an OTLP collector.

