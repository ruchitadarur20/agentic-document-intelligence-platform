from app.services.llm import LLMClient


def test_fallback_answer_uses_complete_relevant_sentences() -> None:
    prompt = """Question: What are the retention and citation requirements for confidential documents?

Evidence:
[1] The retention period for loan application documents is seven years after account closure. AI-generated summaries must cite the source document chunks used to produce each answer. Unsupported claims must be flagged for human review before the answer is sent to a customer or

[2] generated summaries must cite the source document chunks used to produce each answer. Unsupported claims must be flagged for human review before the answer is sent to a customer or regulator.
"""

    answer = LLMClient()._deterministic_response(prompt)

    assert "seven years after account closure" in answer
    assert "customer or [1]" not in answer
    assert answer.count("source document chunks") == 1
    assert "customer or regulator" in answer

