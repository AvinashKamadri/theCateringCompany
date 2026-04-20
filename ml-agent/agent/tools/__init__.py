"""Domain Tools — each owns a slice of the conversation slots."""

from agent.tools.base import Tool, ToolResult
from agent.tools.basic_info_tool import BasicInfoTool
from agent.tools.menu_selection_tool import MenuSelectionTool
from agent.tools.add_ons_tool import AddOnsTool
from agent.tools.modification_tool import ModificationTool
from agent.tools.finalization_tool import FinalizationTool


TOOL_REGISTRY: dict[str, Tool] = {
    "basic_info_tool": BasicInfoTool(),
    "menu_selection_tool": MenuSelectionTool(),
    "add_ons_tool": AddOnsTool(),
    "modification_tool": ModificationTool(),
    "finalization_tool": FinalizationTool(),
}


def get_tool(name: str) -> Tool:
    if name not in TOOL_REGISTRY:
        raise KeyError(f"Unknown tool: {name}")
    return TOOL_REGISTRY[name]


__all__ = [
    "Tool",
    "ToolResult",
    "TOOL_REGISTRY",
    "get_tool",
    "BasicInfoTool",
    "MenuSelectionTool",
    "AddOnsTool",
    "ModificationTool",
    "FinalizationTool",
]
