from prometheus_client import Counter, Histogram, generate_latest


DOCUMENTS_PROCESSED = Counter("documents_processed_total", "Documents processed", ["status"])
AGENT_RUNS = Counter("agent_runs_total", "Agent workflow runs", ["status"])
REQUEST_LATENCY = Histogram("request_latency_seconds", "Request latency", ["endpoint"])


def metrics_response() -> bytes:
    return generate_latest()

