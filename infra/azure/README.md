# Azure Deployment

This folder contains the Azure Container Apps deployment template for the API service.

The intended production Azure architecture is:

- Azure Container Apps for the FastAPI service.
- Azure Container Registry for container images.
- Azure Database for PostgreSQL with pgvector support.
- Azure Cache for Redis for conversation memory.
- Azure Cosmos DB for MongoDB-compatible metadata storage.
- Azure Blob Storage for uploaded source documents.
- Azure Monitor or an OTLP collector for traces and metrics.
- Azure OpenAI for chat completions and embeddings.

Deploy the container app after building and pushing an image:

```bash
az deployment group create \
  --resource-group <resource-group> \
  --template-file infra/azure/container-app.bicep \
  --parameters appName=agentic-doc-intel image=<registry>/agentic-doc-intel:latest
```

