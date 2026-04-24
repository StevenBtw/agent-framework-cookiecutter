"""End-to-end cookiecutter generation tests across all governance tiers."""

from __future__ import annotations

from pathlib import Path

import pytest


def _read(project: Path, rel: str) -> str:
    return (project / rel).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Tier: none
# ---------------------------------------------------------------------------

def test_none_tier_generates_no_governance_files(generate) -> None:
    project = generate(governance_level="none")

    assert not (project / "policies.yaml").exists()
    assert not (project / "src" / "test_agent" / "governance.py").exists()
    assert not (project / "tests" / "test_governance.py").exists()


def test_none_tier_pyproject_has_no_agt_dep(generate) -> None:
    project = generate(governance_level="none")
    pyproject = _read(project, "pyproject.toml")
    assert "agent-os-kernel" not in pyproject
    assert "agent-governance-toolkit" not in pyproject


def test_none_tier_env_example_has_no_agt_block(generate) -> None:
    project = generate(governance_level="none")
    env = _read(project, ".env.example")
    assert "AGT_" not in env


# ---------------------------------------------------------------------------
# Tier: minimal
# ---------------------------------------------------------------------------

def test_minimal_tier_generates_governance_module(generate) -> None:
    project = generate(governance_level="minimal")
    assert (project / "src" / "test_agent" / "governance.py").exists()
    assert (project / "policies.yaml").exists()
    assert (project / "tests" / "test_governance.py").exists()


def test_minimal_tier_pyproject_pins_agent_os_kernel(generate) -> None:
    project = generate(governance_level="minimal")
    pyproject = _read(project, "pyproject.toml")
    assert "agent-os-kernel" in pyproject
    assert "agent-governance-toolkit" not in pyproject


def test_minimal_tier_env_documents_policy_path(generate) -> None:
    project = generate(governance_level="minimal")
    env = _read(project, ".env.example")
    assert "AGT_POLICY_PATH" in env


def test_minimal_tier_config_exposes_governance_settings(generate) -> None:
    project = generate(governance_level="minimal")
    config_py = _read(project, "src/test_agent/config.py")
    assert "AgentGovernanceSettings" in config_py


def test_minimal_tier_orchestrator_wires_policy_tool_filter(generate) -> None:
    project = generate(governance_level="minimal")
    orch_py = _read(project, "src/test_agent/orchestrator.py")
    assert "PolicyToolFilter" in orch_py


def test_minimal_tier_policies_yaml_is_valid_yaml(generate) -> None:
    import yaml
    project = generate(governance_level="minimal")
    data = yaml.safe_load((project / "policies.yaml").read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    assert "rules" in data


# ---------------------------------------------------------------------------
# Tier: standard
# ---------------------------------------------------------------------------

def test_standard_tier_includes_input_output_providers(generate) -> None:
    project = generate(governance_level="standard")
    gov_py = _read(project, "src/test_agent/governance.py")
    assert "PolicyInputProvider" in gov_py
    assert "PolicyOutputProvider" in gov_py


def test_standard_tier_orchestrator_registers_providers(generate) -> None:
    project = generate(governance_level="standard")
    orch_py = _read(project, "src/test_agent/orchestrator.py")
    assert "PolicyInputProvider" in orch_py
    assert "PolicyOutputProvider" in orch_py


def test_standard_tier_pyproject_uses_agent_os_kernel(generate) -> None:
    project = generate(governance_level="standard")
    pyproject = _read(project, "pyproject.toml")
    assert "agent-os-kernel" in pyproject
    assert "agent-governance-toolkit" not in pyproject


# ---------------------------------------------------------------------------
# Tier: full
# ---------------------------------------------------------------------------

def test_full_tier_pyproject_uses_agt_full_extra(generate) -> None:
    project = generate(governance_level="full")
    pyproject = _read(project, "pyproject.toml")
    assert "agent-governance-toolkit[full]" in pyproject
    assert "agent-os-kernel" not in pyproject


def test_full_tier_audit_log_fn_mentions_compliance(generate) -> None:
    project = generate(governance_level="full")
    logging_py = _read(project, "src/test_agent/utils/logging.py")
    assert "_agt_compliance_logger" in logging_py


# ---------------------------------------------------------------------------
# End-to-end smoke: generate, uv sync, run generated pytest
#
# Opt-in because it requires `uv` on PATH and network access to resolve the
# AGT packages from PyPI. Enable with: AGT_SMOKE=1 pytest tests
# ---------------------------------------------------------------------------

import os
import shutil
import subprocess

SMOKE_ENABLED = os.environ.get("AGT_SMOKE") == "1"


@pytest.mark.skipif(not SMOKE_ENABLED, reason="Set AGT_SMOKE=1 to run the tier smoke matrix")
@pytest.mark.parametrize("tier", ["none", "minimal", "standard", "full"])
def test_generated_project_pytest_passes(generate, tier: str) -> None:
    if shutil.which("uv") is None:
        pytest.skip("uv not on PATH")
    project = generate(governance_level=tier)

    sync = subprocess.run(
        ["uv", "sync"], cwd=project, capture_output=True, text=True, timeout=600,
    )
    assert sync.returncode == 0, sync.stderr

    run = subprocess.run(
        ["uv", "run", "pytest", "-q"],
        cwd=project,
        capture_output=True,
        text=True,
        timeout=600,
        env={**os.environ, "PYTHONWARNINGS": "ignore"},
    )
    assert run.returncode == 0, run.stdout + "\n" + run.stderr
