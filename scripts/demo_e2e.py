import argparse
import json
import mimetypes
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen


DEMO_CASES = [
    {
        "name": "security policy",
        "file": "sample_data/security_policy.txt",
        "question": "What are the retention and citation requirements for confidential documents?",
    },
    {
        "name": "loan operations",
        "file": "sample_data/loan_policy.txt",
        "question": "What must happen when loan documentation is missing, and how long are approved packages retained?",
    },
    {
        "name": "vendor risk",
        "file": "sample_data/vendor_risk_policy.txt",
        "question": "What evidence is required before approving vendors that handle confidential customer data?",
    },
    {
        "name": "incident response",
        "file": "sample_data/incident_response_playbook.txt",
        "question": "What is required when confidential customer data may have been exposed?",
    },
    {
        "name": "employee onboarding",
        "file": "sample_data/hr_onboarding_policy.txt",
        "question": "What must new employees complete before production access is granted?",
    },
]


def request_json(
    base_url: str,
    path: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    query: dict[str, Any] | None = None,
) -> dict[str, Any] | list[dict[str, Any]]:
    url = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    if query:
        url = f"{url}?{urlencode(query)}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if payload is not None else {},
    )
    try:
        with urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"{method} {url} failed with HTTP {exc.code}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not reach {base_url}. Is the API server running?") from exc


def upload_file(base_url: str, sample_file: Path) -> dict[str, Any]:
    boundary = "----docintel-demo-boundary"
    content_type = mimetypes.guess_type(sample_file.name)[0] or "application/octet-stream"
    file_bytes = sample_file.read_bytes()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{sample_file.name}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode("utf-8") + file_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")
    request = Request(
        urljoin(base_url.rstrip("/") + "/", "documents/upload"),
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Upload failed with HTTP {exc.code}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not reach {base_url}. Is the API server running?") from exc


def run_demo(base_url: str, sample_file: Path, question: str) -> dict[str, Any] | list[dict[str, Any]]:
    request_json(base_url, "/health")
    uploaded = upload_file(base_url, sample_file)
    processed = request_json(
        base_url,
        "/documents/process",
        method="POST",
        payload={"document_id": uploaded["document_id"], "force": True},
    )
    chat = request_json(
        base_url,
        "/chat",
        method="POST",
        payload={
            "query": question,
            "metadata_filters": {"document_id": uploaded["document_id"]},
        },
    )
    history = request_json(
        base_url,
        "/history",
        query={"conversation_id": chat["conversation_id"]},
    )
    return {"upload": uploaded, "process": processed, "chat": chat, "history": history}


def run_demo_cases(base_url: str) -> dict[str, Any]:
    results = []
    for case in DEMO_CASES:
        result = run_demo(base_url, Path(case["file"]), case["question"])
        chat = result["chat"]
        results.append(
            {
                "case": case["name"],
                "file": case["file"],
                "question": case["question"],
                "document_id": result["upload"]["document_id"],
                "run_id": chat["run_id"],
                "hallucination_risk": chat["validation"]["hallucination_risk"],
                "answer": chat["answer"],
                "citations": chat["citations"],
                "evaluation": chat["evaluation"],
            }
        )
    return {
        "case_count": len(results),
        "successful_cases": sum(1 for result in results if result["hallucination_risk"] == "low"),
        "results": results,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the document intelligence E2E demo.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--file", default="sample_data/security_policy.txt")
    parser.add_argument(
        "--question",
        default="What are the retention and citation requirements for confidential documents?",
    )
    parser.add_argument(
        "--all-cases",
        action="store_true",
        help="Run the full demo pack across several business document types.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    result = run_demo_cases(args.base_url) if args.all_cases else run_demo(args.base_url, Path(args.file), args.question)
    print(json.dumps(result, indent=2))
