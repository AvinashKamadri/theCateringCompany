import sys
from typing import get_args


# Keep imports consistent with the rest of the suite (run from repo root).
sys.path.insert(0, r"c:\Projects\CateringCompany\ml-agent")


def test_tool_registry_matches_toolname_literal() -> None:
    """Adding a new tool must update BOTH ToolName and TOOL_REGISTRY.

    This test makes that requirement explicit so routing doesn't break at runtime
    with a KeyError in the orchestrator.
    """
    from agent.models import ToolName
    from agent.tools import TOOL_REGISTRY

    toolname_values = set(get_args(ToolName))
    registry_names = set(TOOL_REGISTRY.keys())
    assert toolname_values == registry_names


def test_phase_to_tool_values_are_valid_tools() -> None:
    """Router phase ownership must only reference known tools."""
    from agent.models import ToolName
    from agent.router import _PHASE_TO_TOOL

    toolname_values = set(get_args(ToolName))
    assert set(_PHASE_TO_TOOL.values()).issubset(toolname_values)

