import time
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.crewai_adapter import CrewAIWorkflowAdapter
from app.agents.state import AgentState
from app.core.config import settings
from app.models.entities import Conversation, Evaluation, Message, Run
from app.observability.metrics import AGENT_RUNS
from app.services.llm import LLMClient
from app.services.llmops import build_llmops_metadata
from app.services.memory import ConversationMemory
from app.services.vector_store import RetrievedChunk, VectorStore


class AgentWorkflow:
    def __init__(self) -> None:
        self.llm = LLMClient()
        self.vector_store = VectorStore()
        self.memory = ConversationMemory()
        self.crewai = CrewAIWorkflowAdapter()
        self.graph = self._compile_graph()

    async def run(
        self,
        session: AsyncSession,
        query: str,
        conversation_id: uuid.UUID | None = None,
        metadata_filters: dict[str, Any] | None = None,
    ) -> AgentState:
        started = time.perf_counter()
        conversation = await self._conversation(session, conversation_id)
        run = Run(conversation_id=conversation.id, status="running")
        session.add(run)
        session.add(Message(conversation_id=conversation.id, role="user", content=query))
        await session.commit()
        await session.refresh(run)
        await self.memory.append(conversation.id, "user", query)

        state: AgentState = {
            "query": query,
            "conversation_id": conversation.id,
            "run_id": run.id,
            "metadata_filters": metadata_filters or {},
            "llmops": self._run_metadata(metadata_filters or {}),
        }
        try:
            state = await self._execute(session, state)
            state["latency_ms"] = int((time.perf_counter() - started) * 1000)
            state = self._evaluate(state)
            run.status = "succeeded"
            run.plan = state.get("plan", {})
            run.result = {
                "answer": state.get("answer", ""),
                "citations": state.get("citations", []),
                "validation": state.get("validation", {}),
                "evaluation": state.get("evaluation", {}),
                "llmops": state.get("llmops", {}),
            }
            session.add(
                Message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content=state.get("answer", ""),
                    token_count=state.get("token_usage", 0),
                )
            )
            await self.memory.append(conversation.id, "assistant", state.get("answer", ""))
            evaluation = state["evaluation"]
            session.add(
                Evaluation(
                    run_id=run.id,
                    relevance=evaluation["relevance"],
                    faithfulness=evaluation["faithfulness"],
                    completeness=evaluation["completeness"],
                    latency_ms=evaluation["latency_ms"],
                    token_usage=evaluation["token_usage"],
                    details=evaluation["details"],
                )
            )
            await session.commit()
            AGENT_RUNS.labels(status="succeeded").inc()
            return state
        except Exception as exc:
            run.status = "failed"
            run.error = str(exc)
            await session.commit()
            AGENT_RUNS.labels(status="failed").inc()
            raise

    def _compile_graph(self) -> Any:
        try:
            from langgraph.graph import END, StateGraph

            graph = StateGraph(AgentState)
            graph.add_node("planner", self._planner)
            graph.add_node("retrieval", self._retrieval)
            graph.add_node("ranking", self._ranking)
            graph.add_node("validation", self._validation)
            graph.add_node("response", self._response)
            graph.add_node("evaluation", self._evaluate)
            graph.set_entry_point("planner")
            graph.add_edge("planner", "retrieval")
            graph.add_edge("retrieval", "ranking")
            graph.add_edge("ranking", "response")
            graph.add_edge("response", "validation")
            graph.add_edge("validation", "evaluation")
            graph.add_edge("evaluation", END)
            return graph.compile()
        except Exception:
            return None

    async def _execute(self, session: AsyncSession, state: AgentState) -> AgentState:
        state = self._planner(state)
        state = await self._retrieval(session, state)
        state = self._ranking(state)
        state = self._response(state)
        state = self._validation(state)
        return state

    async def _conversation(
        self, session: AsyncSession, conversation_id: uuid.UUID | None
    ) -> Conversation:
        if conversation_id:
            existing = await session.get(Conversation, conversation_id)
            if existing:
                return existing
        conversation = Conversation(title="Document intelligence conversation")
        session.add(conversation)
        await session.commit()
        await session.refresh(conversation)
        return conversation

    def _planner(self, state: AgentState) -> AgentState:
        query = state["query"]
        state["plan"] = {
            "intent": "answer_with_evidence",
            "tasks": [
                "hybrid_retrieval",
                "deduplicate_and_rank_context",
                "generate_cited_answer",
                "validate_evidence_support",
                "score_quality",
            ],
            "retrieval_strategy": {
                "semantic": True,
                "keyword": True,
                "metadata_filters": state.get("metadata_filters", {}),
                "top_k": settings.retrieval_top_k,
            },
            "orchestration": {
                "primary_graph": "LangGraph StateGraph",
                "compiled_graph_available": self.graph is not None,
                "crew_adapter": self.crewai.crew_spec(),
            },
            "query_summary": query[:240],
        }
        return state

    def _run_metadata(self, metadata_filters: dict[str, Any]) -> dict[str, Any]:
        metadata = build_llmops_metadata()
        metadata["orchestration"] = {
            "primary_framework": "LangGraph",
            "primary_graph": "StateGraph",
            "crew_ai_adapter": self.crewai.crew_spec(),
        }
        metadata["retrieval"] = {
            "metadata_filters": metadata_filters,
            "top_k": settings.retrieval_top_k,
            "vector_backend": settings.vector_backend,
        }
        return metadata

    async def _retrieval(self, session: AsyncSession, state: AgentState) -> AgentState:
        query = state["query"]
        vector = self.llm.embed_query(query)
        state["retrieved_chunks"] = await self.vector_store.search(
            session,
            vector,
            query,
            settings.retrieval_top_k,
            state.get("metadata_filters", {}),
        )
        return state

    def _ranking(self, state: AgentState) -> AgentState:
        seen: set[str] = set()
        ranked: list[RetrievedChunk] = []
        for chunk in sorted(state.get("retrieved_chunks", []), key=lambda item: item.score, reverse=True):
            signature = chunk.content[:300].lower()
            if signature in seen:
                continue
            seen.add(signature)
            ranked.append(chunk)
        state["ranked_chunks"] = ranked[: settings.retrieval_top_k]
        return state

    def _response(self, state: AgentState) -> AgentState:
        chunks = state.get("ranked_chunks", [])
        if not chunks:
            state["answer"] = "I could not find enough indexed evidence to answer this question."
            state["citations"] = []
            state["token_usage"] = len(state["answer"].split())
            return state

        context = "\n\n".join(
            f"[{idx}] {chunk.content}" for idx, chunk in enumerate(chunks, start=1)
        )
        answer = self.llm.chat(
            "You answer only from provided evidence. Cite every factual claim with chunk ids.",
            f"Question: {state['query']}\n\nEvidence:\n{context}",
        )
        citations = [
            {
                "document_id": str(chunk.document_id) if chunk.document_id else None,
                "chunk_id": chunk.chunk_id,
                "filename": (chunk.metadata or {}).get("filename"),
                "excerpt": chunk.content[:350],
                "source_url": f"/documents/{chunk.document_id}/chunks/{quote_chunk_id(chunk.chunk_id)}"
                if chunk.document_id
                else None,
            }
            for chunk in chunks[:5]
        ]
        state["answer"] = answer
        state["citations"] = citations
        state["token_usage"] = len(answer.split()) + sum(len(chunk.content.split()) for chunk in chunks)
        return state

    def _validation(self, state: AgentState) -> AgentState:
        answer = state.get("answer", "")
        chunks = state.get("ranked_chunks", [])
        citation_count = len(state.get("citations", []))
        unsupported = []
        if chunks and "could not find enough indexed evidence" not in answer.lower() and citation_count == 0:
            unsupported.append("Answer has retrieved evidence but no citations.")
        state["validation"] = {
            "supported": not unsupported and bool(chunks),
            "citation_coverage": min(1.0, citation_count / max(1, len(chunks))),
            "unsupported_statements": unsupported,
            "hallucination_risk": "low" if not unsupported and chunks else "high",
        }
        return state

    def _evaluate(self, state: AgentState) -> AgentState:
        validation = state.get("validation", {})
        has_answer = bool(state.get("answer"))
        has_citations = bool(state.get("citations"))
        state["evaluation"] = {
            "relevance": 5 if has_answer else 1,
            "faithfulness": 5 if validation.get("supported") else 2,
            "completeness": 4 if has_citations else 2,
            "latency_ms": state.get("latency_ms", 0),
            "token_usage": state.get("token_usage", 0),
            "details": {
                "hallucination_risk": validation.get("hallucination_risk", "unknown"),
                "citation_coverage": validation.get("citation_coverage", 0),
            },
        }
        return state


def quote_chunk_id(chunk_id: str) -> str:
    from urllib.parse import quote

    return quote(chunk_id, safe="")
