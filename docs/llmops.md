# LLMOps Versioning

This project records prompt, model, retrieval, and runtime configuration metadata with each
agent run. The metadata is stored inside the run result and is also returned by the run
trace endpoint.

## What Is Versioned

- Prompt versions for planner, response, validation, and evaluation behavior.
- Prompt fingerprints based on deterministic SHA-256 hashes.
- Chat model deployment name.
- Embedding model deployment name.
- Azure OpenAI API version.
- Vector backend.
- Retrieval `top_k`.
- Chunk size and overlap.
- Metadata filters used for the run.
- LangGraph graph availability.
- CrewAI-compatible adapter specification.

## Where To See It

Run a demo case and open the run trace:

```text
http://127.0.0.1:8000/runs/{run_id}/trace
```

The response includes an `llmops` object with:

```text
llmops_version
prompt_versions
model_versions
config_version
config
orchestration
retrieval
traceability
```

This gives a reviewer enough information to connect an answer back to the prompt versions,
model deployments, retrieval settings, and document filters used to produce it.

