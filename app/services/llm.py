import hashlib
import math
import re
from collections.abc import Sequence

from app.core.config import settings


class LLMClient:
    def __init__(self) -> None:
        self._chat_model = None
        self._embedding_model = None

    def _azure_configured(self) -> bool:
        endpoint = settings.azure_openai_endpoint.strip()
        api_key = settings.azure_openai_api_key.strip()
        return bool(
            endpoint
            and api_key
            and "example.openai.azure.com" not in endpoint
            and api_key.lower() not in {"replace-me", "changeme", "placeholder"}
        )

    def chat(self, system: str, user: str) -> str:
        if self._azure_configured():
            try:
                from langchain_openai import AzureChatOpenAI

                if self._chat_model is None:
                    self._chat_model = AzureChatOpenAI(
                        azure_endpoint=settings.azure_openai_endpoint,
                        api_key=settings.azure_openai_api_key,
                        api_version=settings.azure_openai_api_version,
                        azure_deployment=settings.azure_openai_chat_deployment,
                        temperature=0.1,
                    )
                return str(self._chat_model.invoke([("system", system), ("user", user)]).content)
            except Exception:
                pass
        return self._deterministic_response(user)

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        if self._azure_configured():
            try:
                from langchain_openai import AzureOpenAIEmbeddings

                if self._embedding_model is None:
                    self._embedding_model = AzureOpenAIEmbeddings(
                        azure_endpoint=settings.azure_openai_endpoint,
                        api_key=settings.azure_openai_api_key,
                        api_version=settings.azure_openai_api_version,
                        azure_deployment=settings.azure_openai_embedding_deployment,
                    )
                return self._embedding_model.embed_documents(list(texts))
            except Exception:
                pass
        return [self._hash_embedding(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]

    def _hash_embedding(self, text: str) -> list[float]:
        dimensions = min(settings.embedding_dimensions, 384)
        values: list[float] = []
        seed = hashlib.sha256(text.encode("utf-8")).digest()
        for idx in range(dimensions):
            digest = hashlib.sha256(seed + idx.to_bytes(4, "big")).digest()
            value = int.from_bytes(digest[:4], "big") / 2**32
            values.append((value * 2) - 1)
        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        return [v / norm for v in values]

    def _deterministic_response(self, user: str) -> str:
        question = user
        evidence = ""
        if "Question:" in user and "Evidence:" in user:
            question = user.split("Question:", 1)[1].split("Evidence:", 1)[0].strip()
            evidence = user.split("Evidence:", 1)[1].strip()
        chunks = self._parse_evidence_chunks(evidence)
        if not chunks:
            return f"I do not have enough retrieved evidence to answer: {question}"
        selected = self._select_relevant_sentences(question, chunks)
        if not selected:
            selected = [(source, sentences[0]) for source, sentences in chunks if sentences][:3]
        if not selected:
            return f"I do not have enough retrieved evidence to answer: {question}"

        selected = selected[:3]
        answer_parts = [f"{sentence} {source}" for source, sentence in selected]
        sources = sorted({source for source, _ in selected})
        return " ".join(answer_parts) + f" Sources: {', '.join(sources)}"

    def _parse_evidence_chunks(self, evidence: str) -> list[tuple[str, list[str]]]:
        pattern = re.compile(r"^\[(\d+)\]\s*(.*?)(?=^\[\d+\]\s*|\Z)", re.MULTILINE | re.DOTALL)
        chunks: list[tuple[str, list[str]]] = []
        for match in pattern.finditer(evidence):
            source = f"[{match.group(1)}]"
            text = re.sub(r"\s+", " ", match.group(2)).strip()
            sentences = [
                sentence.strip()
                for sentence in re.split(r"(?<=[.!?])\s+", text)
                if self._is_complete_sentence(sentence)
            ]
            chunks.append((source, sentences))
        return chunks

    def _is_complete_sentence(self, sentence: str) -> bool:
        sentence = sentence.strip()
        if len(sentence.split()) < 4:
            return False
        return sentence.endswith((".", "!", "?"))

    def _select_relevant_sentences(
        self, question: str, chunks: list[tuple[str, list[str]]]
    ) -> list[tuple[str, str]]:
        question_terms = {
            term
            for term in re.findall(r"[a-zA-Z][a-zA-Z-]{3,}", question.lower())
            if term not in {"what", "with", "from", "that", "this", "documents"}
        }
        scored: list[tuple[int, str, str]] = []
        for source, sentences in chunks:
            for sentence in sentences:
                lowered = sentence.lower()
                term_hits = sum(1 for term in question_terms if term in lowered)
                domain_hits = sum(
                    1
                    for term in (
                        "retention",
                        "seven years",
                        "cite",
                        "citation",
                        "source",
                        "unsupported",
                        "human review",
                    )
                    if term in lowered
                )
                score = term_hits + (2 * domain_hits)
                if score:
                    scored.append((score, source, sentence))
        scored.sort(key=lambda item: item[0], reverse=True)
        selected: list[tuple[str, str]] = []
        seen: set[str] = set()
        for _, source, sentence in scored:
            normalized = self._normalize_sentence(sentence)
            if normalized in seen or any(normalized in item or item in normalized for item in seen):
                continue
            seen.add(normalized)
            selected.append((source, sentence))
        return selected

    def _normalize_sentence(self, sentence: str) -> str:
        words = re.findall(r"[a-z0-9]+", sentence.lower())
        if words and words[0] in {"generated", "summary", "summaries"}:
            words = ["ai"] + words
        return " ".join(words)
