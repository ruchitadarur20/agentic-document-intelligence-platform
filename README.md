# Agentic Document Intelligence Platform

An end-to-end AI document intelligence platform that uploads documents, indexes their
content, answers questions with citations, validates evidence support, tracks agent runs,
and displays live operational proof through a dashboard and Grafana monitoring.

This project is designed as a portfolio-ready enterprise AI system: it shows how a
retrieval-augmented generation workflow can be made auditable, observable, and safer for
regulated document use cases.

## What This Project Demonstrates

- Document ingestion for text, PDF, DOCX, CSV, presentation, and OCR-ready files.
- Chunking, embedding, and searchable evidence storage.
- Agentic question answering with planning, retrieval, ranking, response generation,
  validation, and evaluation steps.
- Source-grounded answers with clickable citations.
- Hallucination-risk checks and citation coverage scoring.
- Document classification for security, loan, vendor risk, incident, HR, and general
  documents.
- Compliance flagging for confidential data, retention rules, citation requirements,
  human review, loan records, financial records, possible SSNs, and account numbers.
- Human review queue for failed or high-risk answers.
- Audit log for demo actions such as uploads, processing, questions, reports, and resets.
- Live dashboard for proof of documents, chunks, agent runs, latency, faithfulness,
  readiness, citations, and traces.
- Prometheus and Grafana monitoring for API and agent metrics.
- Docker Compose setup for local end-to-end execution.

## Live Demo

Start the platform:

```bash
cp .env.example .env
docker compose up --build
```

Open:

- API: `http://127.0.0.1:8000`
- Live dashboard: `http://127.0.0.1:8000/dashboard`
- API documentation: `http://127.0.0.1:8000/docs`
- Metrics: `http://127.0.0.1:8000/metrics`
- Grafana: `http://127.0.0.1:3000`

Grafana login:

```text
username: admin
password: admin
```

In Grafana, open:

```text
Dashboards -> Document Intelligence -> Agentic Document Intelligence Monitoring
```

## Demo Script

Run the default end-to-end demo:

```bash
python scripts/demo_e2e.py
```

Run all presentation cases:

```bash
python scripts/demo_e2e.py --all-cases
```

The demo uploads sample documents, processes them into chunks, runs the agent workflow,
returns cited answers, stores run history, and updates the live dashboards.

## Demo Cases

The project includes five sample business scenarios:

| Case | File | What It Shows |
| --- | --- | --- |
| Security Policy | `sample_data/security_policy.txt` | Confidential document rules, retention, citation requirements |
| Loan Operations | `sample_data/loan_policy.txt` | Missing loan documentation, borrower summaries, retention |
| Vendor Risk | `sample_data/vendor_risk_policy.txt` | SOC 2 evidence, vendor review, control validation |
| Incident Response | `sample_data/incident_response_playbook.txt` | Escalation, containment, legal review, audit retention |
| HR Onboarding | `sample_data/hr_onboarding_policy.txt` | Access approval, onboarding controls, eligibility guardrails |

## Dashboard Features

The live dashboard at `http://127.0.0.1:8000/dashboard` is the best screen to show during
a presentation.

It includes:

- Upload and index button for new documents.
- Ask-with-citations workflow.
- Demo case buttons for realistic business examples.
- Search box to filter documents and agent runs.
- Side-by-side answer comparison across two documents.
- Recent documents with status, chunk count, classification, and compliance flags.
- Recent agent runs with status, answer preview, latency, faithfulness, and risk.
- Live answer proof panel with citations and agent trace steps.
- Human review queue for answers that need manual attention.
- Audit log for important actions.
- System readiness checklist for API, vector search, citations, validation, and Grafana.
- Downloadable HTML proof report.

## Architecture

```text
User / Demo Script
      |
      v
FastAPI Application
      |
      +--> Document Upload and Parsing
      |       |
      |       +--> Chunking and Metadata Extraction
      |       +--> Document Classification
      |       +--> PII and Compliance Flagging
      |
      +--> Vector and Keyword Retrieval
      |
      +--> Agent Workflow
      |       |
      |       +--> Planner Agent
      |       +--> Retrieval Agent
      |       +--> Ranking Agent
      |       +--> Response Agent
      |       +--> Validation Agent
      |       +--> Evaluation Agent
      |
      +--> Storage and Observability
              |
              +--> PostgreSQL / pgvector
              +--> MongoDB
              +--> Redis
              +--> Prometheus
              +--> Grafana
```

## Agent Workflow

1. Planner Agent decides the retrieval strategy.
2. Retrieval Agent searches indexed document chunks.
3. Ranking Agent deduplicates and orders the strongest evidence.
4. Response Agent generates a grounded answer.
5. Validation Agent checks citation coverage and unsupported claims.
6. Evaluation Agent scores relevance, faithfulness, completeness, latency, and token use.
7. Trace storage records the plan, evidence, answer, validation, and evaluation.

## Tech Stack

- Python 3.12
- FastAPI
- SQLAlchemy async
- PostgreSQL with pgvector image
- MongoDB
- Redis
- LangGraph-compatible agent workflow
- Azure OpenAI-compatible LLM and embedding configuration
- Prometheus
- Grafana
- OpenTelemetry
- Docker Compose
- Pytest

## Main API Endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | API health check |
| `GET` | `/auth/me` | Current demo identity |
| `POST` | `/documents/upload` | Upload a document |
| `POST` | `/documents/process` | Parse, chunk, embed, and index a document |
| `POST` | `/documents/process-async` | Queue document processing |
| `GET` | `/documents/{id}` | Read document metadata |
| `GET` | `/documents/{id}/preview` | Preview stored document content |
| `GET` | `/documents/{id}/chunks/{chunk_id}` | View a source evidence chunk |
| `DELETE` | `/documents/{id}` | Delete a document and its chunks |
| `POST` | `/chat` | Ask a question and receive cited answer |
| `POST` | `/agents/run` | Run the agent workflow directly |
| `POST` | `/evaluate` | Evaluate an answer |
| `GET` | `/history` | Fetch conversation history |
| `GET` | `/runs/{id}/trace` | View run trace proof |
| `GET` | `/metrics` | Prometheus metrics |
| `GET` | `/dashboard` | Live demo dashboard |
| `GET` | `/dashboard/data` | Dashboard data API |
| `GET` | `/dashboard/report` | HTML proof report |
| `POST` | `/dashboard/compare` | Compare answers across two documents |
| `POST` | `/dashboard/reset` | Reset demo data |

## Local Development Without Docker

Use Python 3.12:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,ocr]"
python scripts/init_db.py
uvicorn app.main:app --reload
```

Then open:

```text
http://127.0.0.1:8000/dashboard
```

## Environment Variables

Create a local `.env` file from the example:

```bash
cp .env.example .env
```

Important settings:

| Variable | Purpose |
| --- | --- |
| `APP_ENV` | Local or production environment |
| `DATABASE_URL` | PostgreSQL connection string |
| `MONGO_URL` | MongoDB connection string |
| `REDIS_URL` | Redis connection string |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API key |
| `AZURE_OPENAI_CHAT_DEPLOYMENT` | Chat model deployment |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | Embedding model deployment |
| `VECTOR_BACKEND` | Local memory or future production vector backend |
| `DEMO_API_KEY` | Optional demo user API key |
| `ADMIN_API_KEY` | Optional admin API key |

Do not commit real API keys. Use `.env.example` for safe placeholder values.

## Security And Access Control

Local mode works without an API key for fast demos.

To demonstrate API-key enforcement, set these values in `.env`:

```bash
DEMO_API_KEY=demo-secret
ADMIN_API_KEY=admin-secret
```

Then test identity:

```bash
curl -H "X-API-Key: admin-secret" http://127.0.0.1:8000/auth/me
```

## Observability

Prometheus scrapes API metrics from:

```text
http://127.0.0.1:8000/metrics
```

Grafana shows:

- API health
- Documents processed
- Agent runs
- Success rate
- Request latency
- CPU usage
- Memory usage
- Open file handles
- Requests by endpoint
- Live metric evidence

## Proof Report

The dashboard can export an HTML proof report at:

```text
http://127.0.0.1:8000/dashboard/report
```

The report includes:

- Total documents
- Indexed chunks
- Agent runs
- Average faithfulness
- Recent answers
- Risk level
- Evaluation details

## Testing

Run the test suite:

```bash
pytest
```

Run individual test areas:

```bash
pytest tests/test_chunking.py
pytest tests/test_llm_fallback.py
pytest tests/test_vector_store.py
pytest tests/test_api_e2e.py
```

## Suggested Presentation Flow

1. Open the live dashboard.
2. Open Grafana in another tab.
3. Run `python scripts/demo_e2e.py --all-cases`.
4. Show document totals and chunk counts increasing.
5. Open a recent document preview.
6. Open a recent run trace.
7. Ask a question from the dashboard.
8. Show the answer, citations, validation, faithfulness, and risk.
9. Compare two documents side by side.
10. Download the proof report.

## Repository Structure

```text
app/
  agents/          Agent workflow state and orchestration
  api/             FastAPI routes and dashboard
  core/            Configuration, logging, security
  db/              Database setup and sessions
  ingestion/       Parsing, chunking, document processing
  models/          SQLAlchemy entities
  observability/   Metrics and telemetry
  schemas/         API contracts
  services/        LLM, vector store, metadata, memory
  workers/         Async worker placeholders
infra/
  azure/           Azure deployment template
  grafana/         Grafana dashboards and provisioning
  prometheus.yml   Prometheus scrape configuration
sample_data/       Demo documents
scripts/           Demo and database initialization scripts
tests/             Unit and API tests
docs/              Architecture documentation
```

## Production Improvements

Planned production extensions:

- Replace local file storage with Azure Blob Storage.
- Use managed PostgreSQL with pgvector or Azure AI Search for large-scale retrieval.
- Move document processing to a queue-backed worker.
- Add tenant isolation and user-level authorization.
- Add streaming responses for long-running agent work.
- Persist audit logs in PostgreSQL instead of in-memory demo storage.
- Send OpenTelemetry traces to Azure Monitor or another OTLP backend.
- Add CI deployment to Azure Container Apps.

## Project Status

The current version is a complete local demo system with API, storage, sample data,
agentic retrieval, citations, validation, proof dashboard, report export, and monitoring.

