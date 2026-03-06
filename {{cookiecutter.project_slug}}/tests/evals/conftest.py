"""Eval test fixtures.

Provides the default evaluator suite (Azure AI Evaluation) and a helper
to run all evaluators against an eval case.

To swap evaluation backends, replace the evaluator instances here.
For example, to use DeepEval instead::

    from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric
    # ... wrap them in BaseEvaluator implementations

Or to use LangSmith::

    from langsmith import Client
    # ... create evaluators that call langsmith.evaluate()
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from .azure_evaluators import (
    AzureCoherenceEvaluator,
    AzureFluencyEvaluator,
    AzureGroundednessEvaluator,
    AzureRelevanceEvaluator,
    AzureSimilarityEvaluator,
    ToolSelectionEvaluator,
)
from .base import EvalCase, EvalResult


EVALS_DIR = Path(__file__).parent
DATASETS_DIR = EVALS_DIR / "datasets"


@pytest.fixture
def evaluators() -> dict[str, Any]:
    """Default evaluator suite.

    Returns a dict of evaluator name -> evaluator instance.
    Add or remove evaluators here to change what gets tested.
    """
    return {
        "relevance": AzureRelevanceEvaluator(threshold=3.0),
        "coherence": AzureCoherenceEvaluator(threshold=3.0),
        "fluency": AzureFluencyEvaluator(threshold=3.0),
        "groundedness": AzureGroundednessEvaluator(threshold=3.0),
        "similarity": AzureSimilarityEvaluator(threshold=3.0),
        "tool_selection": ToolSelectionEvaluator(),
    }


@pytest.fixture
def eval_dataset() -> list[EvalCase]:
    """Load the eval dataset from JSONL.

    Each line in ``datasets/eval_cases.jsonl`` is a JSON object with
    fields matching ``EvalCase``.  Add your test scenarios there.
    """
    dataset_path = DATASETS_DIR / "eval_cases.jsonl"
    if not dataset_path.exists():
        pytest.skip(f"No eval dataset at {dataset_path}")

    cases = []
    for line in dataset_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        data = json.loads(line)
        cases.append(EvalCase(**data))
    return cases


async def run_eval(case: EvalCase, evaluator: Any) -> EvalResult:
    """Run a single evaluator against a case.

    This is a helper used by the test functions.  It calls the
    evaluator's ``evaluate`` method and returns the result.
    """
    return await evaluator.evaluate(case)
