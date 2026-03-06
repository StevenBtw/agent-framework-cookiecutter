"""Base evaluator interface.

Provides an abstract ``BaseEvaluator`` that all evaluation backends implement.
This makes it straightforward to swap Azure AI Evaluation for DeepEval,
LangSmith or any other framework without changing your test cases.

Each evaluator receives an ``EvalCase`` (input + expected output + actual
output + context) and returns an ``EvalResult`` with a score and explanation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class EvalCase:
    """A single evaluation case.

    Attributes:
        input: The user message or prompt sent to the agent.
        output: The actual response from the agent.
        expected: The expected or reference response (optional).
        context: Retrieved context (RAG documents, recalled memories).
        tool_calls: Tools the agent chose to call (name + arguments).
        expected_tools: Tools that should have been called.
        conversation: Full conversation history for multi-turn evals.
        metadata: Arbitrary metadata (user_id, session_id, etc.).
    """

    input: str = ""
    output: str = ""
    expected: str = ""
    context: list[str] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    expected_tools: list[str] = field(default_factory=list)
    conversation: list[dict[str, str]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvalResult:
    """Result of a single evaluation.

    Attributes:
        metric: Name of the metric (e.g. "relevance", "groundedness").
        score: Numeric score, typically 0.0-1.0 or 1-5.
        passed: Whether the score meets the threshold.
        explanation: LLM-generated or rule-based explanation.
        details: Provider-specific extra data.
    """

    metric: str
    score: float
    passed: bool
    explanation: str = ""
    details: dict[str, Any] = field(default_factory=dict)


class BaseEvaluator(Protocol):
    """Protocol for evaluation backends.

    Implement this to plug in a new evaluation framework. Each evaluator
    runs one metric against one eval case and returns a result.

    Example — wrapping a DeepEval metric::

        from deepeval.metrics import AnswerRelevancyMetric
        from deepeval.test_case import LLMTestCase

        class DeepEvalRelevancy:
            def __init__(self, threshold: float = 0.7):
                self.metric = AnswerRelevancyMetric(threshold=threshold)

            async def evaluate(self, case: EvalCase) -> EvalResult:
                tc = LLMTestCase(
                    input=case.input,
                    actual_output=case.output,
                    retrieval_context=case.context,
                )
                self.metric.measure(tc)
                return EvalResult(
                    metric="answer_relevancy",
                    score=self.metric.score,
                    passed=self.metric.is_successful(),
                    explanation=self.metric.reason,
                )

    Example — wrapping a LangSmith evaluator::

        from openevals.llm import create_llm_as_judge
        from openevals.prompts import CORRECTNESS_PROMPT

        class LangSmithCorrectness:
            def __init__(self, model: str = "gpt-4o"):
                self._judge = create_llm_as_judge(
                    prompt=CORRECTNESS_PROMPT,
                    model=model,
                    feedback_key="correctness",
                )

            async def evaluate(self, case: EvalCase) -> EvalResult:
                result = self._judge(
                    inputs=case.input,
                    outputs=case.output,
                    reference_outputs=case.expected,
                )
                return EvalResult(
                    metric="correctness",
                    score=1.0 if result["score"] else 0.0,
                    passed=bool(result["score"]),
                    explanation=result.get("comment", ""),
                )
    """

    async def evaluate(self, case: EvalCase) -> EvalResult: ...
