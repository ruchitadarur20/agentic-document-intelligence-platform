from typing import Any


class CrewAIWorkflowAdapter:
    """Optional CrewAI-style orchestration descriptor for presentation and extension."""

    name = "crewai-compatible-document-review-crew"
    version = "0.1.0"

    def available(self) -> bool:
        try:
            import crewai  # noqa: F401
        except Exception:
            return False
        return True

    def crew_spec(self) -> dict[str, Any]:
        return {
            "framework": "CrewAI",
            "adapter": self.name,
            "version": self.version,
            "available": self.available(),
            "agents": [
                {
                    "role": "Document Intake Analyst",
                    "goal": "Classify uploaded documents and identify compliance-sensitive content.",
                },
                {
                    "role": "Evidence Retrieval Specialist",
                    "goal": "Find the strongest cited chunks for a user question.",
                },
                {
                    "role": "Compliance Reviewer",
                    "goal": "Validate citation coverage and flag unsupported claims.",
                },
            ],
            "tasks": [
                "classify_document",
                "retrieve_evidence",
                "draft_cited_answer",
                "validate_answer_support",
                "prepare_human_review_if_needed",
            ],
        }

