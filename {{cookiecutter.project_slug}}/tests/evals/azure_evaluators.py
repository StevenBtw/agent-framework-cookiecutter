"""Azure AI Evaluation backend.

Uses the ``azure-ai-evaluation`` SDK to score agent responses on
relevance, coherence, groundedness, fluency and similarity.  These
evaluators use an LLM-as-judge approach — they send the input/output
pair to a model that scores the response on a 1-5 scale.

Requirements:
    pip install azure-ai-evaluation

The evaluator model is configured via environment variables:
    AZURE_OPENAI_ENDPOINT  — your Azure OpenAI endpoint
    AZURE_OPENAI_DEPLOYMENT — the deployment used for evaluation
    (same settings as the main agent, or a separate eval deployment)

To swap this for another backend, implement ``BaseEvaluator`` from
``tests.evals.base`` and update ``conftest.py``.
"""

from __future__ import annotations

from azure.ai.evaluation import (
    CoherenceEvaluator,
    FluencyEvaluator,
    GroundednessEvaluator,
    RelevanceEvaluator,
    SimilarityEvaluator,
)

from .base import EvalCase, EvalResult


def _get_model_config() -> dict[str, str]:
    """Build the model config dict for Azure AI Evaluation.

    The evaluators need a model config to know which LLM to use as
    the judge.  This reads from the same env vars as the main agent.

    The dict format matches ``AzureOpenAIModelConfiguration``::

        {
            "azure_endpoint": "https://...",
            "azure_deployment": "gpt-4o",
            "api_key": "...",          # or omit for Entra ID auth
        }

    When ``api_key`` is omitted, pass a ``credential`` to the
    evaluator constructor instead (see below).
    """
    from {{ cookiecutter.package_name }}.config import get_settings

    settings = get_settings()
    return {
        "azure_endpoint": settings.azure_openai_endpoint,
        "azure_deployment": settings.azure_openai_deployment,
    }


class AzureRelevanceEvaluator:
    """Evaluates whether the response is relevant to the input query.

    Uses Azure AI Evaluation's ``RelevanceEvaluator`` which scores
    on a 1-5 scale.  Default threshold is 3 (acceptable).

    Call signature: ``(query=, response=)``
    Result keys: ``relevance`` (int), ``relevance_reason`` (str),
    ``relevance_result`` ("pass"/"fail")
    """

    def __init__(self, threshold: float = 3.0) -> None:
        self._threshold = threshold
        config = _get_model_config()
        self._evaluator = RelevanceEvaluator(config, threshold=int(threshold))

    async def evaluate(self, case: EvalCase) -> EvalResult:
        result = self._evaluator(
            query=case.input,
            response=case.output,
        )
        score = float(result.get("relevance", result.get("gpt_relevance", 0)))
        return EvalResult(
            metric="relevance",
            score=score,
            passed=score >= self._threshold,
            explanation=result.get("relevance_reason", result.get("gpt_relevance_reason", "")),
            details=result,
        )


class AzureCoherenceEvaluator:
    """Evaluates whether the response is coherent and well-structured.

    Call signature: ``(query=, response=)``
    Result keys: ``coherence`` (int), ``coherence_reason`` (str)
    """

    def __init__(self, threshold: float = 3.0) -> None:
        self._threshold = threshold
        config = _get_model_config()
        self._evaluator = CoherenceEvaluator(config, threshold=int(threshold))

    async def evaluate(self, case: EvalCase) -> EvalResult:
        result = self._evaluator(
            query=case.input,
            response=case.output,
        )
        score = float(result.get("coherence", result.get("gpt_coherence", 0)))
        return EvalResult(
            metric="coherence",
            score=score,
            passed=score >= self._threshold,
            explanation=result.get("coherence_reason", result.get("gpt_coherence_reason", "")),
            details=result,
        )


class AzureGroundednessEvaluator:
    """Evaluates whether the response is grounded in the provided context.

    This is the key metric for RAG quality — it checks that the agent
    doesn't hallucinate beyond what the retrieved documents support.
    Requires ``context`` in the eval case.

    Call signature: ``(response=, context=)`` — query is optional.
    Result keys: ``groundedness`` (int), ``groundedness_reason`` (str)
    """

    def __init__(self, threshold: float = 3.0) -> None:
        self._threshold = threshold
        config = _get_model_config()
        self._evaluator = GroundednessEvaluator(config, threshold=int(threshold))

    async def evaluate(self, case: EvalCase) -> EvalResult:
        context_str = "\n\n".join(case.context) if case.context else ""
        result = self._evaluator(
            response=case.output,
            context=context_str,
        )
        score = float(result.get("groundedness", result.get("gpt_groundedness", 0)))
        return EvalResult(
            metric="groundedness",
            score=score,
            passed=score >= self._threshold,
            explanation=result.get("groundedness_reason", result.get("gpt_groundedness_reason", "")),
            details=result,
        )


class AzureFluencyEvaluator:
    """Evaluates the grammatical correctness and readability of the response.

    Call signature: ``(response=)`` — query is NOT required.
    Result keys: ``fluency`` (int), ``fluency_reason`` (str)
    """

    def __init__(self, threshold: float = 3.0) -> None:
        self._threshold = threshold
        config = _get_model_config()
        self._evaluator = FluencyEvaluator(config, threshold=int(threshold))

    async def evaluate(self, case: EvalCase) -> EvalResult:
        result = self._evaluator(
            response=case.output,
        )
        score = float(result.get("fluency", result.get("gpt_fluency", 0)))
        return EvalResult(
            metric="fluency",
            score=score,
            passed=score >= self._threshold,
            explanation=result.get("fluency_reason", result.get("gpt_fluency_reason", "")),
            details=result,
        )


class AzureSimilarityEvaluator:
    """Evaluates how similar the response is to an expected reference answer.

    Useful for regression testing — check that a prompt change doesn't
    significantly alter the response.  Requires ``expected`` in the eval case.

    Call signature: ``(query=, response=, ground_truth=)``
    Result keys: ``similarity`` (int), ``similarity_result`` ("pass"/"fail")
    """

    def __init__(self, threshold: float = 3.0) -> None:
        self._threshold = threshold
        config = _get_model_config()
        self._evaluator = SimilarityEvaluator(config, threshold=int(threshold))

    async def evaluate(self, case: EvalCase) -> EvalResult:
        result = self._evaluator(
            query=case.input,
            response=case.output,
            ground_truth=case.expected,
        )
        score = float(result.get("similarity", result.get("gpt_similarity", 0)))
        return EvalResult(
            metric="similarity",
            score=score,
            passed=score >= self._threshold,
            explanation=result.get("similarity_reason", result.get("gpt_similarity_reason", "")),
            details=result,
        )


class ToolSelectionEvaluator:
    """Evaluates whether the agent selected the correct tools.

    This is a deterministic evaluator (no LLM needed). It compares
    the tools the agent actually called against the expected tools.
    """

    async def evaluate(self, case: EvalCase) -> EvalResult:
        actual_tools = {tc["name"] for tc in case.tool_calls if "name" in tc}
        expected_tools = set(case.expected_tools)

        if not expected_tools:
            return EvalResult(
                metric="tool_selection",
                score=1.0,
                passed=True,
                explanation="No expected tools specified.",
            )

        correct = actual_tools & expected_tools
        precision = len(correct) / len(actual_tools) if actual_tools else 0.0
        recall = len(correct) / len(expected_tools)
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        return EvalResult(
            metric="tool_selection",
            score=f1,
            passed=f1 >= 0.8,
            explanation=(
                f"Expected tools: {sorted(expected_tools)}. "
                f"Actual tools: {sorted(actual_tools)}. "
                f"Precision={precision:.2f}, Recall={recall:.2f}, F1={f1:.2f}."
            ),
        )
