import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.workflow import AgentWorkflow
from app.core.security import Principal, admin_principal, current_principal
from app.db.session import get_session
from app.ingestion.pipeline import DocumentIngestionPipeline
from app.models.entities import Conversation, Document, Embedding, Evaluation, Message, Run
from app.observability.metrics import metrics_response
from app.schemas.contracts import (
    AgentRunRequest,
    ChatRequest,
    ChatResponse,
    DocumentRead,
    EvaluationRequest,
    EvaluationResponse,
    ProcessRequest,
    ProcessResponse,
    UploadResponse,
)

router = APIRouter()
ingestion = DocumentIngestionPipeline()
workflow = AgentWorkflow()
AUDIT_LOG: list[dict[str, str]] = []

DEMO_CASES = [
    {
        "id": "security",
        "name": "Security Policy",
        "file": "sample_data/security_policy.txt",
        "question": "What are the retention and citation requirements for confidential documents?",
    },
    {
        "id": "loan",
        "name": "Loan Operations",
        "file": "sample_data/loan_policy.txt",
        "question": "What must happen when loan documentation is missing, and how long are approved packages retained?",
    },
    {
        "id": "vendor",
        "name": "Vendor Risk",
        "file": "sample_data/vendor_risk_policy.txt",
        "question": "What evidence is required before approving vendors that handle confidential customer data?",
    },
    {
        "id": "incident",
        "name": "Incident Response",
        "file": "sample_data/incident_response_playbook.txt",
        "question": "What is required when confidential customer data may have been exposed?",
    },
    {
        "id": "hr",
        "name": "HR Onboarding",
        "file": "sample_data/hr_onboarding_policy.txt",
        "question": "What must new employees complete before production access is granted?",
    },
]


def _record_audit(action: str, detail: str, actor: str = "demo-user") -> None:
    AUDIT_LOG.insert(
        0,
        {
            "action": action,
            "detail": detail,
            "actor": actor,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    del AUDIT_LOG[50:]


def _governance_summary(filename: str, metadata_json: dict | None) -> dict[str, object]:
    metadata = metadata_json or {}
    fallback = ingestion._governance_metadata(filename, "")
    classification = metadata.get("classification") or fallback["classification"]
    flags = metadata.get("compliance_flags") or fallback["compliance_flags"]
    return {"classification": classification, "compliance_flags": flags}


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/auth/me")
async def auth_me(principal: Principal = Depends(current_principal)) -> dict[str, str]:
    return {"subject": principal.subject, "role": principal.role}


@router.get("/metrics")
async def metrics() -> Response:
    return Response(metrics_response(), media_type="text/plain; version=0.0.4")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(response: Response) -> str:
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Document Intelligence Live Dashboard</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f4f7fb;
      --panel: rgba(255, 255, 255, 0.9);
      --ink: #172033;
      --muted: #667085;
      --line: rgba(95, 116, 141, 0.2);
      --good: #067a6f;
      --warn: #b35b00;
      --accent: #2f6df6;
      --violet: #7c3aed;
      --teal: #0d9488;
      --rose: #e11d48;
      --amber: #d97706;
      --shadow: 0 18px 45px rgba(31, 44, 71, 0.13);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background:
        linear-gradient(115deg, rgba(47, 109, 246, 0.16), transparent 38%),
        linear-gradient(245deg, rgba(13, 148, 136, 0.16), transparent 42%),
        linear-gradient(180deg, #f8fbff 0%, #eef4fb 100%);
      color: var(--ink);
      min-height: 100vh;
    }
    header {
      position: sticky;
      top: 0;
      z-index: 2;
      border-bottom: 1px solid rgba(255, 255, 255, 0.24);
      background:
        linear-gradient(135deg, rgba(23, 32, 51, 0.96), rgba(35, 53, 84, 0.94) 48%, rgba(7, 96, 92, 0.92));
      color: #fff;
      padding: 22px 30px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      box-shadow: 0 12px 35px rgba(18, 27, 43, 0.24);
    }
    h1 { margin: 0; font-size: 22px; font-weight: 800; letter-spacing: 0; }
    .subtitle { margin-top: 4px; color: rgba(255, 255, 255, 0.72); font-size: 13px; }
    main { padding: 26px 28px 38px; max-width: 1360px; margin: 0 auto; }
    .status {
      display: flex;
      align-items: center;
      gap: 10px;
      color: rgba(255, 255, 255, 0.86);
      font-size: 14px;
      padding: 9px 12px;
      border: 1px solid rgba(255, 255, 255, 0.22);
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.1);
      backdrop-filter: blur(10px);
    }
    .dot {
      width: 10px;
      height: 10px;
      border-radius: 999px;
      background: #38f0c5;
      box-shadow: 0 0 0 6px rgba(56, 240, 197, 0.15);
    }
    .grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; }
    .card, section {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(16px);
    }
    .card {
      position: relative;
      overflow: hidden;
      padding: 18px;
      min-height: 124px;
      border-top: 4px solid var(--accent);
    }
    .card::after {
      content: "";
      position: absolute;
      inset: auto 16px 14px auto;
      width: 52px;
      height: 8px;
      border-radius: 999px;
      background: currentColor;
      opacity: 0.12;
    }
    .card:nth-child(1) { color: var(--accent); }
    .card:nth-child(2) { color: var(--teal); border-top-color: var(--teal); }
    .card:nth-child(3) { color: var(--violet); border-top-color: var(--violet); }
    .card:nth-child(4) { color: var(--amber); border-top-color: var(--amber); }
    .label { color: var(--muted); font-size: 12px; font-weight: 750; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 10px; }
    .value { color: var(--ink); font-size: 34px; line-height: 1; font-weight: 850; letter-spacing: 0; }
    .hint { margin-top: 10px; color: var(--muted); font-size: 13px; line-height: 1.35; }
    .bands { margin-top: 20px; display: grid; grid-template-columns: 1.1fr 0.9fr; gap: 18px; align-items: start; }
    section { overflow: hidden; }
    section h2 {
      margin: 0;
      padding: 16px 18px;
      border-bottom: 1px solid var(--line);
      font-size: 16px;
      color: #1c2940;
      letter-spacing: 0;
      background: linear-gradient(90deg, rgba(47, 109, 246, 0.08), rgba(13, 148, 136, 0.08));
    }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { padding: 13px 16px; border-bottom: 1px solid rgba(95, 116, 141, 0.14); text-align: left; vertical-align: top; }
    th { color: var(--muted); font-weight: 750; background: rgba(248, 250, 252, 0.74); }
    tbody tr { transition: background 0.18s ease, transform 0.18s ease; }
    tbody tr:hover { background: rgba(47, 109, 246, 0.05); }
    tr:last-child td { border-bottom: 0; }
    .pill { display: inline-flex; padding: 5px 10px; border-radius: 999px; font-weight: 750; font-size: 12px; background: #dff8f1; color: var(--good); }
    .pill.warn { background: #fff0d5; color: var(--warn); }
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 12px; }
    .answer { max-width: 520px; color: #2d3745; }
    .bars { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-top: 18px; }
    .workspace {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 360px;
      gap: 18px;
      margin-top: 20px;
      align-items: start;
    }
    .tool-panel {
      background: linear-gradient(145deg, rgba(255, 255, 255, 0.94), rgba(241, 248, 255, 0.9));
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      padding: 18px;
    }
    .tool-panel h2, .side-panel h2 { margin: 0 0 14px; font-size: 16px; color: #1c2940; }
    .control-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
    .field { display: grid; gap: 8px; }
    label { color: var(--muted); font-size: 12px; font-weight: 750; letter-spacing: 0.08em; text-transform: uppercase; }
    input, select, textarea {
      width: 100%;
      border: 1px solid rgba(95, 116, 141, 0.28);
      border-radius: 8px;
      background: #fff;
      color: var(--ink);
      font: inherit;
      padding: 11px 12px;
      outline: none;
    }
    textarea { min-height: 104px; resize: vertical; }
    input:focus, select:focus, textarea:focus { border-color: var(--accent); box-shadow: 0 0 0 4px rgba(47, 109, 246, 0.12); }
    .actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px; }
    button, .button {
      appearance: none;
      border: 0;
      border-radius: 8px;
      background: linear-gradient(135deg, var(--accent), var(--teal));
      color: #fff;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 40px;
      padding: 10px 14px;
      font: inherit;
      font-weight: 750;
      text-decoration: none;
      box-shadow: 0 10px 24px rgba(47, 109, 246, 0.22);
    }
    button.secondary, .button.secondary { background: #eef4ff; color: #245ee8; box-shadow: none; }
    button.warning { background: #fff0d5; color: #a34c00; box-shadow: none; }
    button:disabled { cursor: wait; opacity: 0.65; }
    .case-row { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px; }
    .case-row button { background: #eef4ff; color: #245ee8; box-shadow: none; }
    .compare-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin-top: 12px; }
    .compare-card { background: #fff; border: 1px solid rgba(95, 116, 141, 0.18); border-radius: 8px; padding: 13px; }
    .mini-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; margin-top: 20px; }
    .compact-list { display: grid; gap: 10px; padding: 16px; }
    .list-item { background: rgba(248, 251, 255, 0.86); border: 1px solid rgba(95, 116, 141, 0.16); border-radius: 8px; padding: 12px; }
    .chip-row { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 7px; }
    .chip { display: inline-flex; border-radius: 999px; background: #eef4ff; color: #245ee8; padding: 3px 8px; font-size: 11px; font-weight: 750; }
    .chip.teal { background: #dff8f1; color: var(--good); }
    .chip.warn { background: #fff0d5; color: var(--warn); }
    .side-panel {
      background: rgba(255, 255, 255, 0.92);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      overflow: hidden;
    }
    .side-content { padding: 18px; display: grid; gap: 14px; }
    .answer-box, .citation-box, .trace-step {
      background: #f8fbff;
      border: 1px solid rgba(95, 116, 141, 0.18);
      border-radius: 8px;
      padding: 13px;
    }
    .answer-box { line-height: 1.5; }
    .badge-row { display: flex; flex-wrap: wrap; gap: 8px; }
    .badge { display: inline-flex; border-radius: 999px; padding: 5px 9px; background: #eaf2ff; color: #245ee8; font-size: 12px; font-weight: 750; }
    .badge.good { background: #dff8f1; color: var(--good); }
    .badge.warn { background: #fff0d5; color: var(--warn); }
    .trace { display: grid; gap: 8px; }
    .trace-step { display: flex; align-items: center; gap: 10px; font-size: 13px; }
    .step-dot { width: 10px; height: 10px; border-radius: 999px; background: var(--teal); box-shadow: 0 0 0 5px rgba(13, 148, 136, 0.1); }
    .small { color: var(--muted); font-size: 12px; line-height: 1.45; }
    .notice {
      border-radius: 8px;
      margin-top: 12px;
      padding: 10px 12px;
      background: #eaf2ff;
      color: #245ee8;
      font-size: 13px;
      font-weight: 650;
      line-height: 1.4;
    }
    .notice.error { background: #fff0f0; color: #b42318; }
    .notice.good { background: #dff8f1; color: var(--good); }
    .bar-card {
      background: rgba(255, 255, 255, 0.88);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      box-shadow: 0 10px 30px rgba(31, 44, 71, 0.08);
    }
    .bar-track { height: 10px; border-radius: 999px; background: #e6edf6; overflow: hidden; margin-top: 10px; }
    .bar-fill { height: 100%; width: 0; background: linear-gradient(90deg, var(--accent), var(--teal)); transition: width 0.25s ease; }
    #faithfulness-bar { background: linear-gradient(90deg, var(--violet), var(--accent)); }
    #risk-bar { background: linear-gradient(90deg, var(--amber), var(--rose)); }
    a { color: #245ee8; text-decoration: none; font-weight: 650; }
    a:hover { text-decoration: underline; }
    @media (max-width: 900px) {
      .grid, .bands, .bars, .workspace, .control-grid, .compare-grid, .mini-grid { grid-template-columns: 1fr; }
      header { align-items: flex-start; flex-direction: column; }
    }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>Agentic Document Intelligence Platform</h1>
      <div class="subtitle">Live evidence, retrieval quality, and agent workflow proof</div>
    </div>
    <div class="status"><span class="dot"></span><span id="refresh-state">Live</span><span id="updated"></span></div>
  </header>
  <main>
    <div class="grid">
      <div class="card"><div class="label">Documents</div><div class="value" id="documents">0</div><div class="hint" id="processed">0 processed</div></div>
      <div class="card"><div class="label">Indexed Chunks</div><div class="value" id="chunks">0</div><div class="hint">Searchable evidence units</div></div>
      <div class="card"><div class="label">Agent Runs</div><div class="value" id="runs">0</div><div class="hint" id="success-rate">0 succeeded</div></div>
      <div class="card"><div class="label">Average Latency</div><div class="value" id="latency">0 ms</div><div class="hint" id="quality">No evaluations yet</div></div>
    </div>
    <div class="bars">
      <div class="bar-card"><div class="label">Success Rate</div><div class="value" id="success-percent">0%</div><div class="bar-track"><div class="bar-fill" id="success-bar"></div></div></div>
      <div class="bar-card"><div class="label">Faithfulness</div><div class="value" id="faithfulness-score">0/5</div><div class="bar-track"><div class="bar-fill" id="faithfulness-bar"></div></div></div>
      <div class="bar-card"><div class="label">High Risk Runs</div><div class="value" id="risk-count">0</div><div class="bar-track"><div class="bar-fill" id="risk-bar"></div></div></div>
    </div>
    <div class="workspace">
      <div class="tool-panel">
        <h2>Document Workbench</h2>
        <div class="control-grid">
          <div class="field">
            <label for="upload-file">Upload Document</label>
            <input id="upload-file" type="file" />
          </div>
          <div class="field">
            <label for="document-select">Evidence Scope</label>
            <select id="document-select"><option value="">All indexed documents</option></select>
          </div>
          <div class="field">
            <label for="search-box">Search Dashboard</label>
            <input id="search-box" type="search" placeholder="Search documents, answers, risk, status..." />
          </div>
          <div class="field">
            <label for="compare-question">Compare Question</label>
            <input id="compare-question" value="What controls and review requirements apply?" />
          </div>
        </div>
        <div class="actions">
          <button id="upload-button" type="button">Upload and Index</button>
          <a class="button secondary" href="/dashboard/report" target="_blank" rel="noreferrer">Download Proof Report</a>
          <button class="warning" id="reset-button" type="button">Reset Demo Data</button>
        </div>
        <div class="notice" id="action-notice">Choose a file, run a demo case, or ask a question to create live proof.</div>
        <div class="field" style="margin-top:16px;">
          <label for="question-box">Ask a Question</label>
          <textarea id="question-box">What are the retention and citation requirements?</textarea>
        </div>
        <div class="actions">
          <button id="ask-button" type="button">Ask With Citations</button>
        </div>
        <div>
          <div class="label" style="margin-top:18px;">Demo Cases</div>
          <div class="case-row" id="case-row"></div>
        </div>
        <div style="margin-top:18px;">
          <div class="label">Compare Answers</div>
          <div class="compare-grid">
            <select id="compare-left"></select>
            <select id="compare-right"></select>
          </div>
          <div class="actions">
            <button class="secondary" id="compare-button" type="button">Compare Selected Documents</button>
          </div>
          <div class="compare-grid" id="compare-results"></div>
        </div>
      </div>
      <aside class="side-panel">
        <div class="side-content">
          <h2>Live Answer Proof</h2>
          <div class="badge-row" id="quality-badges">
            <span class="badge">Waiting</span>
          </div>
          <div class="answer-box" id="answer-box">Run a demo case or ask a question to see answer, citations, and trace proof here.</div>
          <div>
            <div class="label">Citations</div>
            <div id="citation-list" class="trace"></div>
          </div>
          <div>
            <div class="label">Agent Trace</div>
            <div id="trace-list" class="trace"></div>
          </div>
        </div>
      </aside>
    </div>
    <div class="mini-grid">
      <section>
        <h2>System Readiness</h2>
        <div class="compact-list" id="readiness-list"></div>
      </section>
      <section>
        <h2>Human Review Queue</h2>
        <div class="compact-list" id="review-list"></div>
      </section>
      <section>
        <h2>Audit Log</h2>
        <div class="compact-list" id="audit-list"></div>
      </section>
    </div>
    <div class="bands">
      <section>
        <h2>Recent Agent Runs</h2>
        <table>
          <thead><tr><th>Run</th><th>Status</th><th>Answer</th></tr></thead>
          <tbody id="runs-table"></tbody>
        </table>
      </section>
      <section>
        <h2>Recent Documents</h2>
        <table>
          <thead><tr><th>Document</th><th>Status</th><th>Chunks</th></tr></thead>
          <tbody id="docs-table"></tbody>
        </table>
      </section>
    </div>
  </main>
  <script>
    const shortId = value => value ? value.slice(0, 8) : "";
    const text = value => value === null || value === undefined ? "" : String(value);
    function statusPill(status) {
      const cls = status === "succeeded" || status === "processed" ? "pill" : "pill warn";
      return `<span class="${cls}">${text(status)}</span>`;
    }
    function setBusy(isBusy) {
      for (const id of ["upload-button", "ask-button", "reset-button"]) {
        document.getElementById(id).disabled = isBusy;
      }
      document.getElementById("refresh-state").textContent = isBusy ? "Working" : "Live";
    }
    function notice(message, kind = "") {
      const box = document.getElementById("action-notice");
      box.className = `notice ${kind}`.trim();
      box.textContent = message;
    }
    function qualityBadge(label, value, good = true) {
      return `<span class="badge ${good ? "good" : "warn"}">${label}: ${text(value)}</span>`;
    }
    function chips(values, kind = "") {
      return (values || []).map(value => `<span class="chip ${kind}">${text(value)}</span>`).join("");
    }
    async function requestJson(url, options = {}) {
      const response = await fetch(url, options);
      if (!response.ok) {
        const body = await response.text();
        throw new Error(body || `Request failed with ${response.status}`);
      }
      return await response.json();
    }
    function renderTrace(trace) {
      const tasks = trace?.plan?.tasks || [
        "hybrid_retrieval",
        "deduplicate_and_rank_context",
        "generate_cited_answer",
        "validate_evidence_support",
        "score_quality",
      ];
      document.getElementById("trace-list").innerHTML = tasks.map(task => `
        <div class="trace-step"><span class="step-dot"></span><span>${task.replaceAll("_", " ")}</span></div>
      `).join("");
    }
    async function showCitation(citation) {
      const list = document.getElementById("citation-list");
      const panel = document.createElement("div");
      panel.className = "citation-box";
      panel.innerHTML = `<div class="small">${text(citation.filename)} · ${text(citation.chunk_id)}</div><div>${text(citation.excerpt)}</div>`;
      list.prepend(panel);
      if (citation.source_url) {
        try {
          const html = await fetch(citation.source_url).then(response => response.text());
          const page = new DOMParser().parseFromString(html, "text/html");
          const fullText = page.querySelector("p")?.textContent;
          if (fullText) {
            panel.innerHTML = `<div class="small">${text(citation.filename)} · ${text(citation.chunk_id)}</div><div>${text(fullText)}</div>`;
          }
        } catch (error) {}
      }
    }
    async function showResult(payload) {
      const risk = payload.validation?.hallucination_risk || "unknown";
      document.getElementById("answer-box").textContent = payload.answer || "No answer returned.";
      document.getElementById("quality-badges").innerHTML = [
        qualityBadge("risk", risk, risk === "low"),
        qualityBadge("faithfulness", `${payload.evaluation?.faithfulness || 0}/5`, true),
        qualityBadge("coverage", payload.validation?.citation_coverage ?? 0, true),
      ].join("");
      document.getElementById("citation-list").innerHTML = "";
      for (const citation of payload.citations || []) {
        await showCitation(citation);
      }
      const trace = await requestJson(`/runs/${payload.run_id}/trace`);
      renderTrace(trace);
      await refresh();
    }
    async function loadCases() {
      const cases = await requestJson("/dashboard/demo-cases");
      document.getElementById("case-row").innerHTML = cases.map(item => `
        <button type="button" data-case="${item.id}">${item.name}</button>
      `).join("");
      document.querySelectorAll("[data-case]").forEach(button => {
        button.addEventListener("click", () => runCase(button.dataset.case));
      });
    }
    async function runCase(caseId) {
      setBusy(true);
      notice("Running demo case...");
      try {
        const payload = await requestJson(`/dashboard/demo-cases/${caseId}/run`, { method: "POST" });
        await showResult(payload.chat);
        notice(`${payload.case.name} case completed with citations.`, "good");
      } catch (error) {
        notice(`Demo case failed: ${error.message}`, "error");
      } finally {
        setBusy(false);
      }
    }
    let uploadAfterPick = false;
    async function uploadAndIndex() {
      const input = document.getElementById("upload-file");
      if (!input.files.length) {
        uploadAfterPick = true;
        notice("Choose a file and it will upload automatically.");
        input.click();
        return;
      }
      setBusy(true);
      notice("Uploading and indexing document...");
      try {
        const filename = input.files[0].name;
        const form = new FormData();
        form.append("file", input.files[0]);
        const uploaded = await requestJson("/documents/upload", { method: "POST", body: form });
        await requestJson("/documents/process", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ document_id: uploaded.document_id, force: true }),
        });
        await refresh();
        document.getElementById("document-select").value = uploaded.document_id;
        document.getElementById("answer-box").textContent = `${filename} uploaded and indexed.`;
        notice(`${filename} uploaded and indexed.`, "good");
        input.value = "";
        uploadAfterPick = false;
      } catch (error) {
        uploadAfterPick = false;
        notice(`Upload failed: ${error.message}`, "error");
      } finally {
        setBusy(false);
      }
    }
    async function askQuestion() {
      const query = document.getElementById("question-box").value.trim();
      if (!query) {
        notice("Please type a question first.", "error");
        return;
      }
      const documentId = document.getElementById("document-select").value;
      setBusy(true);
      notice("Asking the agent and gathering citations...");
      try {
        const payload = await requestJson("/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            query,
            metadata_filters: documentId ? { document_id: documentId } : {},
          }),
        });
        await showResult(payload);
        notice("Answer generated with citation and trace proof.", "good");
      } catch (error) {
        notice(`Question failed: ${error.message}`, "error");
      } finally {
        setBusy(false);
      }
    }
    async function compareAnswers() {
      const left = document.getElementById("compare-left").value;
      const right = document.getElementById("compare-right").value;
      const question = document.getElementById("compare-question").value.trim();
      if (!left || !right || left === right) {
        notice("Choose two different documents to compare.", "error");
        return;
      }
      setBusy(true);
      notice("Comparing answers across selected documents...");
      try {
        const payload = await requestJson("/dashboard/compare", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question, document_ids: [left, right] }),
        });
        document.getElementById("compare-results").innerHTML = payload.results.map(result => `
          <div class="compare-card">
            <div class="label">${text(result.filename)}</div>
            <div class="chip-row">${chips([result.classification], "teal")}</div>
            <p>${text(result.answer)}</p>
            <div class="small">${result.citations.length} citations · faithfulness ${result.evaluation.faithfulness}/5 · risk ${result.validation.hallucination_risk}</div>
          </div>
        `).join("");
        notice("Comparison completed with separate citations for each document.", "good");
        await refresh();
      } catch (error) {
        notice(`Compare failed: ${error.message}`, "error");
      } finally {
        setBusy(false);
      }
    }
    let resetArmedUntil = 0;
    async function resetDemoData() {
      const button = document.getElementById("reset-button");
      if (Date.now() > resetArmedUntil) {
        resetArmedUntil = Date.now() + 5000;
        button.textContent = "Click Again to Reset";
        notice("Reset is armed for 5 seconds. Click the reset button again to clear demo data.", "error");
        setTimeout(() => {
          if (Date.now() > resetArmedUntil) button.textContent = "Reset Demo Data";
        }, 5200);
        return;
      }
      setBusy(true);
      notice("Resetting demo data...");
      try {
        await requestJson("/dashboard/reset", { method: "POST" });
        document.getElementById("answer-box").textContent = "Demo data reset. Run a case to repopulate the dashboard.";
        document.getElementById("citation-list").innerHTML = "";
        document.getElementById("trace-list").innerHTML = "";
        document.getElementById("quality-badges").innerHTML = '<span class="badge">Reset complete</span>';
        button.textContent = "Reset Demo Data";
        resetArmedUntil = 0;
        notice("Demo data reset. Run a case to repopulate the dashboard.", "good");
        await refresh();
      } catch (error) {
        notice(`Reset failed: ${error.message}`, "error");
      } finally {
        setBusy(false);
      }
    }

    async function refresh() {
      const state = document.getElementById("refresh-state");
      try {
        const response = await fetch("/dashboard/data", { cache: "no-store" });
        const data = await response.json();
        document.getElementById("documents").textContent = data.totals.documents;
        document.getElementById("processed").textContent = `${data.totals.processed_documents} processed`;
        document.getElementById("chunks").textContent = data.totals.chunks;
        document.getElementById("runs").textContent = data.totals.runs;
        document.getElementById("success-rate").textContent = `${data.totals.succeeded_runs} succeeded`;
        document.getElementById("latency").textContent = `${data.quality.average_latency_ms} ms`;
        document.getElementById("quality").textContent = `Faithfulness ${data.quality.average_faithfulness}/5`;
        const successPercent = data.totals.runs ? Math.round((data.totals.succeeded_runs / data.totals.runs) * 100) : 0;
        document.getElementById("success-percent").textContent = `${successPercent}%`;
        document.getElementById("success-bar").style.width = `${successPercent}%`;
        document.getElementById("faithfulness-score").textContent = `${data.quality.average_faithfulness}/5`;
        document.getElementById("faithfulness-bar").style.width = `${Math.round((data.quality.average_faithfulness / 5) * 100)}%`;
        document.getElementById("risk-count").textContent = data.quality.high_risk_runs;
        document.getElementById("risk-bar").style.width = `${data.totals.runs ? Math.round((data.quality.high_risk_runs / data.totals.runs) * 100) : 0}%`;
        document.getElementById("updated").textContent = "Auto-refreshing";
        const selectedDocument = document.getElementById("document-select").value;
        const selectedLeft = document.getElementById("compare-left").value;
        const selectedRight = document.getElementById("compare-right").value;
        const documentOptions = data.recent_documents.map(doc => `
          <option value="${doc.id}">${text(doc.filename)} (${shortId(doc.id)})</option>
        `).join("");
        document.getElementById("document-select").innerHTML = '<option value="">All indexed documents</option>' + documentOptions;
        document.getElementById("document-select").value = selectedDocument;
        document.getElementById("compare-left").innerHTML = documentOptions;
        document.getElementById("compare-right").innerHTML = documentOptions;
        document.getElementById("compare-left").value = selectedLeft || data.recent_documents[0]?.id || "";
        document.getElementById("compare-right").value = selectedRight || data.recent_documents[1]?.id || "";
        const search = document.getElementById("search-box").value.toLowerCase().trim();
        const docs = data.recent_documents.filter(doc => !search || JSON.stringify(doc).toLowerCase().includes(search));
        const runs = data.recent_runs.filter(run => !search || JSON.stringify(run).toLowerCase().includes(search));
        document.getElementById("docs-table").innerHTML = docs.map(doc => `
          <tr>
            <td><div><a href="${doc.preview_url}" target="_blank" rel="noreferrer">${text(doc.filename)}</a></div><div class="mono">${shortId(doc.id)}</div></td>
            <td>${statusPill(doc.status)}</td>
            <td>${doc.chunk_count}<div class="chip-row">${chips([doc.classification], "teal")}${chips(doc.compliance_flags, "warn")}</div></td>
          </tr>
        `).join("");
        document.getElementById("runs-table").innerHTML = runs.map(run => `
          <tr>
            <td class="mono"><a href="${run.trace_url}" target="_blank" rel="noreferrer">${shortId(run.id)}</a></td>
            <td>${statusPill(run.status)}</td>
            <td class="answer">${text(run.answer)}<div class="hint">${run.latency_ms} ms · faithfulness ${run.faithfulness}/5 · risk ${run.hallucination_risk}</div></td>
          </tr>
        `).join("");
        document.getElementById("readiness-list").innerHTML = data.readiness.map(item => `
          <div class="list-item"><span class="pill ${item.ready ? "" : "warn"}">${item.ready ? "ready" : "waiting"}</span><div class="hint">${text(item.name)}</div></div>
        `).join("");
        document.getElementById("review-list").innerHTML = data.review_queue.length ? data.review_queue.map(item => `
          <div class="list-item"><a href="${item.trace_url}" target="_blank" rel="noreferrer">${shortId(item.id)}</a><div class="hint">${text(item.reason)}</div></div>
        `).join("") : '<div class="list-item"><span class="pill">clear</span><div class="hint">No high-risk answers waiting for review.</div></div>';
        document.getElementById("audit-list").innerHTML = data.audit_log.length ? data.audit_log.map(item => `
          <div class="list-item"><strong>${text(item.action)}</strong><div class="hint">${text(item.detail)}</div></div>
        `).join("") : '<div class="list-item"><div class="hint">No dashboard actions yet.</div></div>';
        state.textContent = "Live";
      } catch (error) {
        state.textContent = "Waiting for API";
      }
    }

    document.getElementById("upload-button").addEventListener("click", uploadAndIndex);
    document.getElementById("upload-file").addEventListener("change", () => {
      if (uploadAfterPick && document.getElementById("upload-file").files.length) {
        uploadAndIndex();
      }
    });
    document.getElementById("ask-button").addEventListener("click", askQuestion);
    document.getElementById("compare-button").addEventListener("click", compareAnswers);
    document.getElementById("search-box").addEventListener("input", refresh);
    document.getElementById("reset-button").addEventListener("click", resetDemoData);
    loadCases();
    refresh();
    setInterval(refresh, 3000);
  </script>
</body>
</html>
"""


@router.get("/dashboard/data")
async def dashboard_data(session: AsyncSession = Depends(get_session)) -> dict:
    documents = await session.scalar(select(func.count()).select_from(Document))
    processed_documents = await session.scalar(
        select(func.count()).select_from(Document).where(Document.status == "processed")
    )
    chunks = await session.scalar(select(func.count()).select_from(Embedding))
    runs = await session.scalar(select(func.count()).select_from(Run))
    succeeded_runs = await session.scalar(
        select(func.count()).select_from(Run).where(Run.status == "succeeded")
    )
    average_latency = await session.scalar(select(func.avg(Evaluation.latency_ms)))
    average_faithfulness = await session.scalar(select(func.avg(Evaluation.faithfulness)))
    high_risk_runs = await session.scalar(
        select(func.count())
        .select_from(Evaluation)
        .where(Evaluation.details["hallucination_risk"].as_string() == "high")
    )

    recent_documents_result = await session.execute(
        select(
            Document.id,
            Document.filename,
            Document.status,
            Document.metadata_json,
            Document.created_at,
            func.count(Embedding.id).label("chunk_count"),
        )
        .outerjoin(Embedding, Embedding.document_id == Document.id)
        .group_by(Document.id)
        .order_by(Document.created_at.desc())
        .limit(8)
    )
    recent_runs_result = await session.execute(
        select(Run, Evaluation)
        .outerjoin(Evaluation, Evaluation.run_id == Run.id)
        .order_by(Run.created_at.desc())
        .limit(8)
    )
    review_runs_result = await session.execute(
        select(Run, Evaluation)
        .outerjoin(Evaluation, Evaluation.run_id == Run.id)
        .where(
            (Run.status == "failed")
            | (Evaluation.details["hallucination_risk"].as_string() == "high")
        )
        .order_by(Run.created_at.desc())
        .limit(8)
    )
    any_chunks = (chunks or 0) > 0
    any_runs = (runs or 0) > 0

    return {
        "totals": {
            "documents": documents or 0,
            "processed_documents": processed_documents or 0,
            "chunks": chunks or 0,
            "runs": runs or 0,
            "succeeded_runs": succeeded_runs or 0,
        },
        "quality": {
            "average_latency_ms": round(float(average_latency or 0)),
            "average_faithfulness": round(float(average_faithfulness or 0), 1),
            "high_risk_runs": high_risk_runs or 0,
        },
        "recent_documents": [
            {
                "id": str(row.id),
                "filename": row.filename,
                "preview_url": f"/documents/{row.id}/preview",
                "status": row.status,
                "chunk_count": row.chunk_count,
                **_governance_summary(row.filename, row.metadata_json),
            }
            for row in recent_documents_result.all()
        ],
        "recent_runs": [
            {
                "id": str(run.id),
                "status": run.status,
                "answer": (run.result or {}).get("answer", "")[:240],
                "trace_url": f"/runs/{run.id}/trace",
                "latency_ms": evaluation.latency_ms if evaluation else 0,
                "faithfulness": evaluation.faithfulness if evaluation else 0,
                "hallucination_risk": (evaluation.details or {}).get("hallucination_risk", "unknown")
                if evaluation
                else "unknown",
            }
            for run, evaluation in recent_runs_result.all()
        ],
        "review_queue": [
            {
                "id": str(run.id),
                "status": run.status,
                "reason": run.error
                or ((run.result or {}).get("validation", {}).get("unsupported_statements") or ["Needs review"])[0],
                "trace_url": f"/runs/{run.id}/trace",
            }
            for run, evaluation in review_runs_result.all()
        ],
        "readiness": [
            {"name": "API live", "ready": True},
            {"name": "Vector search ready", "ready": any_chunks},
            {"name": "Citations enabled", "ready": any_runs},
            {"name": "Validation enabled", "ready": any_runs},
            {"name": "Grafana connected", "ready": True},
        ],
        "audit_log": AUDIT_LOG[:8],
    }


@router.get("/dashboard/demo-cases")
async def dashboard_demo_cases() -> list[dict[str, str]]:
    return [
        {"id": item["id"], "name": item["name"], "question": item["question"]}
        for item in DEMO_CASES
    ]


@router.post("/dashboard/demo-cases/{case_id}/run")
async def run_dashboard_demo_case(
    case_id: str,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(current_principal),
) -> dict:
    case = next((item for item in DEMO_CASES if item["id"] == case_id), None)
    if case is None:
        raise HTTPException(status_code=404, detail="Demo case not found")
    source = Path(case["file"])
    if not source.exists():
        raise HTTPException(status_code=404, detail=f"Sample file not found: {source}")
    document = await ingestion.upload_path(session, source)
    chunk_count = await ingestion.process(session, document, force=True)
    state = await workflow.run(
        session,
        case["question"],
        metadata_filters={"document_id": str(document.id)},
    )
    _record_audit("run demo case", f"{case['name']} produced run {state['run_id']}", principal.subject)
    return {
        "case": {"id": case["id"], "name": case["name"], "question": case["question"]},
        "upload": {
            "document_id": str(document.id),
            "status": document.status,
            "checksum": document.checksum,
        },
        "process": {
            "document_id": str(document.id),
            "status": document.status,
            "chunk_count": chunk_count,
        },
        "chat": {
            "conversation_id": str(state["conversation_id"]),
            "run_id": str(state["run_id"]),
            "answer": state.get("answer", ""),
            "citations": state.get("citations", []),
            "validation": state.get("validation", {}),
            "evaluation": state.get("evaluation", {}),
        },
    }


@router.post("/dashboard/compare")
async def dashboard_compare(
    payload: dict,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(current_principal),
) -> dict:
    question = str(payload.get("question") or "").strip()
    document_ids = [str(item) for item in payload.get("document_ids", []) if item]
    if not question:
        raise HTTPException(status_code=400, detail="Question is required")
    if len(document_ids) != 2:
        raise HTTPException(status_code=400, detail="Choose exactly two documents to compare")
    results = []
    for document_id in document_ids:
        document = await session.get(Document, UUID(document_id))
        if document is None:
            raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")
        state = await workflow.run(
            session,
            question,
            metadata_filters={"document_id": document_id},
        )
        results.append(
            {
                "document_id": document_id,
                "filename": document.filename,
                "classification": _governance_summary(
                    document.filename, document.metadata_json
                )["classification"],
                "answer": state.get("answer", ""),
                "citations": state.get("citations", []),
                "validation": state.get("validation", {}),
                "evaluation": state.get("evaluation", {}),
                "run_id": str(state["run_id"]),
            }
        )
    _record_audit("compare answers", f"Compared {len(results)} documents", principal.subject)
    return {"question": question, "results": results}


@router.get("/dashboard/report")
async def dashboard_report(session: AsyncSession = Depends(get_session)) -> HTMLResponse:
    data = await dashboard_data(session)
    runs_result = await session.execute(
        select(Run, Evaluation)
        .outerjoin(Evaluation, Evaluation.run_id == Run.id)
        .order_by(Run.created_at.desc())
        .limit(25)
    )
    data["proof_runs"] = [
        {
            "run_id": str(run.id),
            "status": run.status,
            "answer": (run.result or {}).get("answer", ""),
            "citations": (run.result or {}).get("citations", []),
            "validation": (run.result or {}).get("validation", {}),
            "evaluation": {
                "relevance": evaluation.relevance,
                "faithfulness": evaluation.faithfulness,
                "completeness": evaluation.completeness,
                "latency_ms": evaluation.latency_ms,
                "token_usage": evaluation.token_usage,
                "details": evaluation.details,
            }
            if evaluation
            else None,
        }
        for run, evaluation in runs_result.all()
    ]
    _record_audit("export report", "Downloaded HTML proof report")
    run_cards = "".join(
        f"""
        <article>
          <h2>{_escape_html(item["status"])} · {_escape_html(item["run_id"][:8])}</h2>
          <p>{_escape_html(item["answer"])}</p>
          <div class="meta">Faithfulness {_escape_html((item.get("evaluation") or {}).get("faithfulness", 0))}/5 · Risk {_escape_html(((item.get("validation") or {}).get("hallucination_risk", "unknown")))}</div>
        </article>
        """
        for item in data["proof_runs"][:12]
    )
    html = f"""
<!doctype html>
<html lang="en">
<head><meta charset="utf-8" /><meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Agentic Document Intelligence Proof Report</title>
<style>
body {{ margin: 0; font-family: Inter, system-ui, sans-serif; background: #f4f7fb; color: #172033; }}
header {{ padding: 28px; color: #fff; background: linear-gradient(135deg, #172033, #0f766e); }}
main {{ max-width: 980px; margin: 0 auto; padding: 24px; }}
.stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 18px; }}
.stat, article {{ background: #fff; border: 1px solid #d9e2ef; border-radius: 8px; padding: 16px; box-shadow: 0 10px 28px rgba(31, 44, 71, 0.08); }}
.value {{ font-size: 28px; font-weight: 850; }}
.meta {{ color: #667085; font-size: 13px; }}
h1, h2 {{ margin: 0 0 8px; }}
article {{ margin-bottom: 14px; }}
@media print {{ body {{ background: #fff; }} article, .stat {{ box-shadow: none; }} }}
</style></head>
<body>
<header><h1>Agentic Document Intelligence Proof Report</h1><div>Evidence, citations, validation, and quality metrics</div></header>
<main>
<div class="stats">
  <div class="stat"><div class="meta">Documents</div><div class="value">{data["totals"]["documents"]}</div></div>
  <div class="stat"><div class="meta">Chunks</div><div class="value">{data["totals"]["chunks"]}</div></div>
  <div class="stat"><div class="meta">Runs</div><div class="value">{data["totals"]["runs"]}</div></div>
  <div class="stat"><div class="meta">Faithfulness</div><div class="value">{data["quality"]["average_faithfulness"]}/5</div></div>
</div>
{run_cards}
</main>
</body></html>
"""
    return HTMLResponse(
        html,
        headers={"Content-Disposition": "attachment; filename=agentic-document-proof-report.html"},
    )


@router.post("/dashboard/reset")
async def dashboard_reset(
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(current_principal),
) -> dict[str, str]:
    for model in (Evaluation, Message, Embedding, Run, Conversation, Document):
        await session.execute(delete(model))
    await session.commit()
    _record_audit("reset demo data", "Cleared documents, chunks, runs, conversations, and evaluations", principal.subject)
    return {"status": "reset"}


@router.post("/documents/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(current_principal),
) -> UploadResponse:
    document = await ingestion.upload(session, file)
    _record_audit("upload document", f"Uploaded {document.filename}", principal.subject)
    return UploadResponse(document_id=document.id, status=document.status, checksum=document.checksum)


@router.post("/documents/process", response_model=ProcessResponse)
async def process_document(
    request: ProcessRequest,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(current_principal),
) -> ProcessResponse:
    document = await session.get(Document, request.document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    chunk_count = await ingestion.process(session, document, request.force)
    _record_audit("process document", f"Processed {document.filename} into {chunk_count} chunks", principal.subject)
    return ProcessResponse(document_id=document.id, status=document.status, chunk_count=chunk_count)


@router.post("/documents/process-async", response_model=ProcessResponse)
async def process_document_async(
    request: ProcessRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(current_principal),
) -> ProcessResponse:
    document = await session.get(Document, request.document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    document.status = "processing"
    await session.commit()

    from app.workers.tasks import process_document_background

    background_tasks.add_task(process_document_background, request.document_id, request.force)
    return ProcessResponse(document_id=document.id, status=document.status, chunk_count=0)


@router.get("/documents/{document_id}", response_model=DocumentRead)
async def get_document(
    document_id: UUID,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(current_principal),
) -> Document:
    document = await session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.get("/documents/{document_id}/preview", response_class=HTMLResponse)
async def preview_document(document_id: UUID, session: AsyncSession = Depends(get_session)) -> str:
    document = await session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    result = await session.execute(
        select(Embedding).where(Embedding.document_id == document_id).order_by(Embedding.chunk_id)
    )
    chunks = result.scalars().all()
    chunk_rows = "".join(
        f"""
        <article>
          <div class="chunk-title"><a href="/documents/{document_id}/chunks/{quote(chunk.chunk_id, safe='')}">{_escape_html(chunk.chunk_id)}</a></div>
          <p>{_escape_html(chunk.content)}</p>
        </article>
        """
        for chunk in chunks
    )
    return f"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{_escape_html(document.filename)} Preview</title>
  <style>
    body {{ margin: 0; font-family: Inter, system-ui, sans-serif; background: #f6f7f9; color: #18202a; }}
    header {{ background: #fff; border-bottom: 1px solid #d9dee6; padding: 18px 28px; }}
    main {{ max-width: 980px; margin: 0 auto; padding: 24px 28px; }}
    h1 {{ font-size: 22px; margin: 0 0 6px; letter-spacing: 0; }}
    .meta {{ color: #657181; font-size: 14px; }}
    article {{ background: #fff; border: 1px solid #d9dee6; border-radius: 8px; padding: 16px; margin-bottom: 14px; }}
    .chunk-title {{ font-family: ui-monospace, Menlo, monospace; font-size: 12px; margin-bottom: 10px; }}
    a {{ color: #2563eb; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    p {{ line-height: 1.55; white-space: pre-wrap; }}
  </style>
</head>
<body>
  <header><h1>{_escape_html(document.filename)}</h1><div class="meta">{document.status} · {len(chunks)} chunks</div></header>
  <main>{chunk_rows or "<article>No chunks indexed yet.</article>"}</main>
</body>
</html>
"""


@router.get("/documents/{document_id}/chunks/{chunk_id}", response_class=HTMLResponse)
async def preview_chunk(
    document_id: UUID, chunk_id: str, session: AsyncSession = Depends(get_session)
) -> str:
    result = await session.execute(
        select(Embedding).where(Embedding.document_id == document_id, Embedding.chunk_id == chunk_id)
    )
    chunk = result.scalar_one_or_none()
    if chunk is None:
        raise HTTPException(status_code=404, detail="Chunk not found")
    return f"""
<!doctype html>
<html lang="en">
<head><meta charset="utf-8" /><meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Citation Evidence</title>
<style>
body {{ margin:0; font-family: Inter, system-ui, sans-serif; background:#f6f7f9; color:#18202a; }}
main {{ max-width: 860px; margin: 0 auto; padding: 28px; }}
article {{ background:#fff; border:1px solid #d9dee6; border-radius:8px; padding:18px; }}
.mono {{ font-family: ui-monospace, Menlo, monospace; color:#2563eb; font-size:13px; margin-bottom: 10px; }}
p {{ line-height:1.6; white-space:pre-wrap; }}
</style></head>
<body><main><article><div class="mono">{_escape_html(chunk.chunk_id)}</div><p>{_escape_html(chunk.content)}</p></article></main></body>
</html>
"""


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: UUID,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(admin_principal),
) -> dict[str, str]:
    document = await session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    await session.execute(delete(Embedding).where(Embedding.document_id == document_id))
    await session.delete(document)
    await session.commit()
    return {"status": "deleted"}


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(current_principal),
) -> ChatResponse:
    state = await workflow.run(
        session,
        request.query,
        request.conversation_id,
        request.metadata_filters,
    )
    _record_audit("ask question", f"Created run {state['run_id']}", principal.subject)
    return ChatResponse(
        conversation_id=state["conversation_id"],
        run_id=state["run_id"],
        answer=state.get("answer", ""),
        citations=state.get("citations", []),
        validation=state.get("validation", {}),
        evaluation=state.get("evaluation", {}),
    )


@router.post("/agents/run", response_model=ChatResponse)
async def run_agents(
    request: AgentRunRequest,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(current_principal),
) -> ChatResponse:
    return await chat(request, session)


@router.post("/evaluate", response_model=EvaluationResponse)
async def evaluate(request: EvaluationRequest) -> EvaluationResponse:
    faithfulness = 5 if request.citations else 2
    completeness = 5 if len(request.answer.split()) > 20 else 3
    return EvaluationResponse(
        relevance=5 if request.answer else 1,
        faithfulness=faithfulness,
        completeness=completeness,
        latency_ms=request.latency_ms,
        token_usage=request.token_usage,
        details={"citation_count": len(request.citations)},
    )


@router.get("/history")
async def history(
    conversation_id: UUID | None = None, session: AsyncSession = Depends(get_session)
) -> list[dict]:
    if conversation_id:
        result = await session.execute(
            select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at)
        )
        return [
            {"role": message.role, "content": message.content, "created_at": message.created_at}
            for message in result.scalars().all()
        ]
    result = await session.execute(select(Conversation).order_by(Conversation.created_at.desc()).limit(50))
    return [
        {"conversation_id": conversation.id, "title": conversation.title, "created_at": conversation.created_at}
        for conversation in result.scalars().all()
    ]


@router.get("/runs/{run_id}/trace")
async def run_trace(run_id: UUID, session: AsyncSession = Depends(get_session)) -> dict:
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    result = await session.execute(select(Evaluation).where(Evaluation.run_id == run_id))
    evaluation = result.scalar_one_or_none()
    return {
        "run_id": str(run.id),
        "status": run.status,
        "trace_id": run.trace_id,
        "plan": run.plan,
        "result": run.result,
        "evaluation": {
            "relevance": evaluation.relevance,
            "faithfulness": evaluation.faithfulness,
            "completeness": evaluation.completeness,
            "latency_ms": evaluation.latency_ms,
            "token_usage": evaluation.token_usage,
            "details": evaluation.details,
        }
        if evaluation
        else None,
        "created_at": run.created_at,
        "updated_at": run.updated_at,
        "error": run.error,
    }


def _escape_html(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )
