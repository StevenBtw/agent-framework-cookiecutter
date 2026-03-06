"""Agent evaluation framework.

This package provides an extensible evaluation harness for testing LLM output
quality, tool selection accuracy, memory recall relevance and conversation flow.

The default implementation uses **Azure AI Evaluation** (``azure-ai-evaluation``
on PyPI). The base classes are designed to be swappable so you can plug in
alternative evaluation backends:

- **DeepEval** (``pip install deepeval``): pytest-native LLM evaluation with
  50+ built-in metrics (GEval, AnswerRelevancy, Faithfulness, ToolCorrectness,
  etc.) and an optional cloud dashboard at https://app.confident-ai.com.
  Supports any LLM-as-judge via the ``model`` parameter on each metric.
  To switch, subclass ``BaseEvaluator`` and delegate to DeepEval metrics.

- **LangSmith** (``pip install langsmith openevals``): evaluation + observability
  platform from LangChain.  Works without LangChain — trace raw ``openai``
  SDK calls via ``wrap_openai()`` and run evals via ``langsmith.evaluate()``.
  Prebuilt LLM-as-judge evaluators live in the ``openevals`` package.  Provides
  annotation queues for human review and a pytest plugin.
  See https://docs.smith.langchain.com/.

- **promptfoo** (``npx promptfoo@latest``): YAML-based eval framework with a
  built-in web UI.  Language-agnostic (Node.js CLI) so it runs alongside your
  Python project.  Great for prompt regression testing and A/B comparisons.
  See https://www.promptfoo.dev/.

To add a new eval backend, implement ``BaseEvaluator`` and register it in
``conftest.py``.
"""
