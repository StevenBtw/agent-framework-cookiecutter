"""Eval tests for response quality.

These tests call the real LLM and evaluate the output using Azure AI
Evaluation metrics.  They are NOT run by default — use the ``evals``
pytest marker to include them::

    # Run only eval tests
    uv run pytest -m evals

    # Run all tests including evals
    uv run pytest --run-evals

    # Run evals for a specific category
    uv run pytest -m evals -k policy

Eval tests require:
    1. A configured LLM endpoint (AZURE_OPENAI_ENDPOINT / AZURE_OPENAI_DEPLOYMENT)
    2. The ``azure-ai-evaluation`` package installed
    3. Network access to the LLM

The eval dataset lives in ``datasets/eval_cases.jsonl``.  Add new test
scenarios there as JSONL entries.
"""

from __future__ import annotations

from typing import Any

import pytest

from {{ cookiecutter.package_name }}.orchestrator import Orchestrator

from .base import EvalCase, EvalResult
from .conftest import run_eval


pytestmark = pytest.mark.evals


@pytest.fixture
def orchestrator() -> Orchestrator:
    """Create a real orchestrator for eval tests.

    Unlike the unit test fixture, this uses the real model provider
    so eval tests hit the actual LLM.
    """
    return Orchestrator()


class TestResponseQuality:
    """Evaluate agent response quality against the eval dataset."""

    async def test_relevance(
        self,
        orchestrator: Orchestrator,
        eval_dataset: list[EvalCase],
        evaluators: dict[str, Any],
    ) -> None:
        """Every response should be relevant to the user's query."""
        evaluator = evaluators["relevance"]
        failures: list[str] = []

        for case in eval_dataset:
            case.output = await orchestrator.chat(case.input)
            result = await run_eval(case, evaluator)
            if not result.passed:
                failures.append(
                    f"[{case.metadata.get('category', '?')}] "
                    f"score={result.score:.1f}: {result.explanation}"
                )

        assert not failures, f"Relevance failures:\n" + "\n".join(failures)

    async def test_coherence(
        self,
        orchestrator: Orchestrator,
        eval_dataset: list[EvalCase],
        evaluators: dict[str, Any],
    ) -> None:
        """Every response should be coherent and well-structured."""
        evaluator = evaluators["coherence"]
        failures: list[str] = []

        for case in eval_dataset:
            if not case.output:
                case.output = await orchestrator.chat(case.input)
            result = await run_eval(case, evaluator)
            if not result.passed:
                failures.append(
                    f"[{case.metadata.get('category', '?')}] "
                    f"score={result.score:.1f}: {result.explanation}"
                )

        assert not failures, f"Coherence failures:\n" + "\n".join(failures)

    async def test_groundedness(
        self,
        orchestrator: Orchestrator,
        eval_dataset: list[EvalCase],
        evaluators: dict[str, Any],
    ) -> None:
        """Responses with context should be grounded in that context."""
        evaluator = evaluators["groundedness"]
        cases_with_context = [c for c in eval_dataset if c.context]
        if not cases_with_context:
            pytest.skip("No eval cases with context")

        failures: list[str] = []
        for case in cases_with_context:
            if not case.output:
                case.output = await orchestrator.chat(case.input)
            result = await run_eval(case, evaluator)
            if not result.passed:
                failures.append(
                    f"[{case.metadata.get('category', '?')}] "
                    f"score={result.score:.1f}: {result.explanation}"
                )

        assert not failures, f"Groundedness failures:\n" + "\n".join(failures)


class TestToolSelection:
    """Evaluate whether the agent selects the correct tools."""

    async def test_tool_selection_accuracy(
        self,
        orchestrator: Orchestrator,
        eval_dataset: list[EvalCase],
        evaluators: dict[str, Any],
    ) -> None:
        """Agent should select the expected tools for each scenario."""
        evaluator = evaluators["tool_selection"]
        cases_with_tools = [c for c in eval_dataset if c.expected_tools]
        if not cases_with_tools:
            pytest.skip("No eval cases with expected_tools")

        failures: list[str] = []
        for case in cases_with_tools:
            # In a real eval, you'd capture tool calls from the agent.
            # This is a placeholder — wire it to your orchestrator's
            # tool execution pipeline to capture actual tool invocations.
            case.output = await orchestrator.chat(case.input)
            # TODO: capture case.tool_calls from the agent execution
            result = await run_eval(case, evaluator)
            if not result.passed:
                failures.append(
                    f"[{case.metadata.get('category', '?')}] "
                    f"{result.explanation}"
                )

        if failures:
            pytest.xfail(
                "Tool selection eval requires wiring tool_calls capture. "
                f"Failures:\n" + "\n".join(failures)
            )
