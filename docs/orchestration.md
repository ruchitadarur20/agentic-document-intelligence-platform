# Orchestration: LangGraph And CrewAI

The primary runtime workflow uses a LangGraph-compatible `StateGraph` pattern. The graph
contains planner, retrieval, ranking, response, validation, and evaluation steps.

The project also includes a CrewAI-compatible adapter in:

```text
app/agents/crewai_adapter.py
```

The adapter documents how the workflow maps to a crew-style setup:

- Document Intake Analyst
- Evidence Retrieval Specialist
- Compliance Reviewer

CrewAI is optional so the local demo remains lightweight. To experiment with it:

```bash
pip install -e ".[orchestration]"
```

