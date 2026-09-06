import hashlib
import json
from typing import Any

from app.core.config import settings


PROMPT_REGISTRY = {
    "planner": {
        "version": "planner-v1.0.0",
        "template": "Plan retrieval and validation steps for a document intelligence question.",
    },
    "response": {
        "version": "response-v1.0.0",
        "template": "You answer only from provided evidence. Cite every factual claim with chunk ids.",
    },
    "validation": {
        "version": "validation-v1.0.0",
        "template": "Check that every factual claim is supported by retrieved source chunks.",
    },
    "evaluation": {
        "version": "evaluation-v1.0.0",
        "template": "Score relevance, faithfulness, completeness, latency, and token use.",
    },
}


def _fingerprint(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]


def build_llmops_metadata() -> dict[str, Any]:
    config = {
        "app_env": settings.app_env,
        "service_name": settings.service_name,
        "vector_backend": settings.vector_backend,
        "embedding_dimensions": settings.embedding_dimensions,
        "chunk_size": settings.chunk_size,
        "chunk_overlap": settings.chunk_overlap,
        "retrieval_top_k": settings.retrieval_top_k,
    }
    prompts = {
        name: {
            "version": entry["version"],
            "fingerprint": _fingerprint(entry),
        }
        for name, entry in PROMPT_REGISTRY.items()
    }
    models = {
        "chat_provider": "azure_openai_compatible",
        "chat_deployment": settings.azure_openai_chat_deployment,
        "embedding_deployment": settings.azure_openai_embedding_deployment,
        "api_version": settings.azure_openai_api_version,
    }
    return {
        "llmops_version": "llmops-v1.0.0",
        "prompt_versions": prompts,
        "model_versions": models,
        "config_version": f"config-{_fingerprint(config)}",
        "config": config,
        "traceability": {
            "run_metadata_schema": "run-metadata-v1",
            "records_prompt_model_config": True,
            "records_retrieval_filters": True,
            "records_validation_metrics": True,
        },
    }

