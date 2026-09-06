# Agentic Document Intelligence Platform

Production-oriented FastAPI platform for document ingestion, retrieval-augmented multi-agent workflows, evidence validation, evaluation, trace storage, and conversation memory.

## Capabilities

- Upload, parse, clean, chunk, embed, and index PDFs, DOCX, TXT, CSV, PPTX placeholders, and OCR-ready images.
- Run a LangGraph-compatible workflow with planner, retrieval, ranking, validation, response, and evaluation agents.
- Store relational records in PostgreSQL, raw/chunk metadata in MongoDB, and conversation memory in Redis.
- Expose Prometheus metrics and OpenTelemetry tracing.
- Package services with Docker Compose and CI.

## Local Run

```bash
cp .env.example .env
docker compose up --build
```

The API starts at `http://127.0.0.1:8000`.

Open the live proof dashboard at `http://127.0.0.1:8000/dashboard`.

For a lightweight local run without containers, use a Python 3.12 environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,ocr]"
python scripts/init_db.py
uvicorn app.main:app --reload
```

Then run the included demo:

```bash
python scripts/demo_e2e.py
```

For a richer presentation demo with multiple business cases:

```bash
python scripts/demo_e2e.py --all-cases
```

## Main Endpoints

- `POST /documents/upload`
- `POST /documents/process`
- `GET /documents/{id}`
- `DELETE /documents/{id}`
- `POST /chat`
- `POST /agents/run`
- `POST /evaluate`
- `GET /history`
- `GET /metrics`
- `GET /health`
- `GET /dashboard`
- `GET /dashboard/data`
- `GET /auth/me`
- `GET /documents/{id}/preview`
- `GET /documents/{id}/chunks/{chunk_id}`
- `GET /runs/{id}/trace`
- `POST /documents/process-async`

## End-to-End Demo

The default demo uploads `sample_data/security_policy.txt`, processes it into chunks and
embeddings, asks a grounded question through the agent graph, and fetches the conversation
history.

The full demo pack runs five cases across security policy, loan operations, vendor risk,
incident response, and employee onboarding documents. Each case uploads a document, indexes
it, asks a scenario-specific question, returns citations, and records evaluation metrics.

Expected flow:

1. `/health` confirms the API is alive.
2. `/documents/upload` creates a document record.
3. `/documents/process` parses, chunks, embeds, indexes, and stores metadata.
4. `/chat` runs planner, retrieval, ranking, response, validation, and evaluation agents.
5. `/history` returns the persisted user and assistant messages.

## Live Demo Proof

Use these screens during a presentation:

- `http://127.0.0.1:8000/dashboard`: live operational dashboard with documents, chunks, runs, quality, latency, and hallucination risk.
- `http://127.0.0.1:8000/docs`: generated OpenAPI contract.
- `http://127.0.0.1:8000/metrics`: Prometheus metrics scrape output.
- `http://127.0.0.1:3000`: Grafana container for observability dashboards.

Grafana login:

```text
username: admin
password: admin
```

Open Dashboards, then `Document Intelligence / Agentic Document Intelligence Monitoring`.

Run `python scripts/demo_e2e.py --all-cases` while the dashboards are open. The document count, chunk count, run count, quality metrics, latency panels, endpoint table, and Grafana metrics refresh automatically.

Recent document rows link to indexed chunk previews. Recent run rows link to stored trace JSON with the agent plan, result, validation, and evaluation.

## Security And Roles

Local mode allows requests without an API key. To demonstrate API-key enforcement, set either value in `.env`:

```bash
DEMO_API_KEY=demo-secret
ADMIN_API_KEY=admin-secret
```

Then call protected identity proof:

```bash
curl -H "X-API-Key: admin-secret" http://127.0.0.1:8000/auth/me
```

## Production Vector Search

The local demo stores portable JSON vectors. For PostgreSQL pgvector proof, see `infra/postgres_pgvector.sql`, which enables the `vector` extension and adds an HNSW cosine index pattern.

## Notes

The default local mode creates relational tables on startup. Production deployments should
run Alembic migrations explicitly and keep `APP_ENV=production`.
# agentic-document-intelligence-platform
