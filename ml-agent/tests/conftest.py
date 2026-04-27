"""
Pytest setup — pin the agent package import path to THIS project, not a stale
copy at c:/Projects/CateringCompany/ml-agent/ that some legacy tests reference
via hard-coded sys.path inserts.

Without this, `from agent.intents import ...` (a module added in the stability
pass) raises ImportError when tests run alongside files that do
`sys.path.insert(0, r"c:\\Projects\\CateringCompany\\ml-agent")`.
"""

from __future__ import annotations

import os
import sys


_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _is_from_project_root(mod_obj) -> bool:
    mod_path = getattr(mod_obj, "__file__", "") or ""
    if not mod_path:
        return True
    try:
        return os.path.normcase(os.path.abspath(mod_path)).startswith(
            os.path.normcase(_PROJECT_ROOT)
        )
    except Exception:
        return False


# Run at collection time, before any test module is imported.
def _pin_project_root() -> None:
    # Ensure this project root is FIRST on sys.path
    if _PROJECT_ROOT in sys.path:
        sys.path.remove(_PROJECT_ROOT)
    sys.path.insert(0, _PROJECT_ROOT)
    # Evict any cached `agent` modules loaded from a different location.
    for mod_name in list(sys.modules):
        if mod_name == "agent" or mod_name.startswith("agent."):
            mod_obj = sys.modules.get(mod_name)
            if mod_obj is None:
                continue
            if not _is_from_project_root(mod_obj):
                del sys.modules[mod_name]


_pin_project_root()
