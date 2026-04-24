"""Agent Governance Toolkit (AGT) integration.

Generated only when ``governance_level`` is ``minimal``, ``standard`` or
``full``.  Hosts:

* :func:`load_policies` — reads a YAML policy document from disk.
* :class:`PolicyToolFilter` — middleware filter that blocks tool calls
  violating the loaded policy.
{%- if cookiecutter.governance_level in ["standard", "full"] %}
* :class:`PolicyInputProvider` — evaluates the latest user message before
  the LLM runs; can halt the turn if input violates policy.
* :class:`PolicyOutputProvider` — evaluates the model response; can
  rewrite or replace the response if it violates policy.
{%- endif %}

Policy evaluation is deterministic and runs before any human approval
step so that deny decisions short-circuit without operator involvement.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from agent_os.policies import (  # type: ignore[import-not-found]
    PolicyAction,
    PolicyDocument,
    PolicyEvaluator,
)

from {{ cookiecutter.package_name }}.middleware import (
    ContextProvider,
    SessionContext,
    ToolFilter,
    ToolInvocationContext,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Policy loading
# ---------------------------------------------------------------------------

def _allow_all() -> PolicyDocument:
    """Fallback policy used when no YAML file is present."""
    return PolicyDocument(
        name="allow-all-fallback",
        version="1.0",
        defaults={"action": PolicyAction.ALLOW},
        rules=[],
    )


def load_policies(path: Path | str) -> PolicyDocument:
    """Load a :class:`PolicyDocument` from a YAML file.

    A missing file produces an allow-all fallback with a warning (so dev
    environments do not hard-fail).  Malformed YAML raises; policy syntax
    must be fixed rather than silently ignored.
    """
    p = Path(path)
    if not p.exists():
        logger.warning("governance.policy_file_missing", extra={"path": str(p)})
        return _allow_all()

    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Policy file {p} must contain a YAML mapping at the top level")
    return PolicyDocument(**raw)


# ---------------------------------------------------------------------------
# Tool-call filter
# ---------------------------------------------------------------------------

class PolicyToolFilter(ToolFilter):
    """Blocks tool calls that violate the loaded policy document.

    Inserted into the middleware pipeline *before* HumanApprovalFilter so
    deterministic denials short-circuit before a human is paged.
    """

    def __init__(self, evaluator: PolicyEvaluator) -> None:
        self._evaluator = evaluator

    async def before_tool(self, context: ToolInvocationContext) -> None:
        decision = self._evaluator.evaluate({
            "tool_name": context.tool_name,
            "arguments": context.arguments,
            "user_id": context.session.user_id,
            "session_id": context.session.session_id,
        })
        if getattr(decision, "action", None) == PolicyAction.DENY:
            context.approved = False
            context.denial_reason = (
                f"Blocked by policy rule '{getattr(decision, 'matched_rule', 'unknown')}'"
            )


{%- if cookiecutter.governance_level in ["standard", "full"] %}


# ---------------------------------------------------------------------------
# Input / output context providers (standard+)
# ---------------------------------------------------------------------------

class PolicyInputProvider(ContextProvider):
    """Evaluates the user's latest message against the policy document."""

    source_id = "policy-input"

    def __init__(self, evaluator: PolicyEvaluator) -> None:
        self._evaluator = evaluator

    async def before_run(self, context: SessionContext) -> None:
        user_msg = next(
            (m["content"] for m in reversed(context.messages) if m.get("role") == "user"),
            "",
        )
        if not user_msg:
            return
        decision = self._evaluator.evaluate({
            "stage": "input",
            "user_id": context.session_id,
            "content": user_msg,
        })
        if getattr(decision, "action", None) == PolicyAction.DENY:
            context.state["policy_block"] = {
                "stage": "input",
                "reason": getattr(decision, "matched_rule", "policy"),
            }


class PolicyOutputProvider(ContextProvider):
    """Evaluates the model's response against the policy document."""

    source_id = "policy-output"

    def __init__(self, evaluator: PolicyEvaluator) -> None:
        self._evaluator = evaluator

    async def after_run(self, context: SessionContext, response: str) -> None:
        decision = self._evaluator.evaluate({
            "stage": "output",
            "user_id": context.session_id,
            "content": response,
        })
        if getattr(decision, "action", None) == PolicyAction.DENY:
            context.state["policy_block"] = {
                "stage": "output",
                "reason": getattr(decision, "matched_rule", "policy"),
            }
{%- endif %}


# ---------------------------------------------------------------------------
# Public builder
# ---------------------------------------------------------------------------

def build_evaluator(policy_path: Path | str) -> PolicyEvaluator:
    """Load the YAML policy document and return a :class:`PolicyEvaluator`."""
    return PolicyEvaluator(policies=[load_policies(policy_path)])
