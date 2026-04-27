"""
Routing decision tree — a structured view of agent.router.route().

The historical `route()` function is a sequence of ~18 bypasses with subtle
order dependencies. That works but is hard to reason about. This module names
each decision step explicitly so future maintainers can:

  1. Find where a particular intent is handled (search by step name)
  2. Add a new bypass without re-deriving the existing precedence
  3. Remove an obsolete bypass with confidence about what it was doing

The actual routing logic STILL lives in agent/router.py — this module is the
authoritative documentation of the order, plus a `routing_steps()` helper that
returns the canonical list for tests/diagnostics. We did NOT rewrite route()
because doing so on the demo deadline carried unnecessary risk; the existing
implementation has 169 passing tests around it. Future cleanup: collapse the
bypasses into method calls on this module.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RoutingStep:
    """One named decision in the routing pipeline.

    Attributes:
      name:        unique short identifier
      handles:     human description of what this step decides
      output_tool: the Tool this step routes to when it fires (or 'clarify')
      lives_in:    the function/section where this code currently lives
    """

    name: str
    handles: str
    output_tool: str
    lives_in: str


# The canonical ordered list of routing steps. If you're debugging "why did
# message X go to tool Y?", read this top-to-bottom — the first match wins.
ROUTING_STEPS: tuple[RoutingStep, ...] = (
    RoutingStep(
        name="conversation_status_inactive",
        handles="conversation already closed (pending_staff_review / contract_sent)",
        output_tool="no_action",
        lives_in="route() — top of function",
    ),
    RoutingStep(
        name="pending_state_ttl",
        handles="auto-clear stale __pending_* slots older than 2 turns",
        output_tool="(side effect — clears slots, no routing decision)",
        lives_in="route() → validate_pending_state()",
    ),
    RoutingStep(
        name="pending_routes",
        handles="any __pending_* slot is set: route to its owning tool FIRST",
        output_tool="modification_tool / menu_selection_tool",
        lives_in="route() — _pending_routes block",
    ),
    RoutingStep(
        name="out_of_scope_guard",
        handles="clearly off-topic messages (politics, jokes that match OOS regex)",
        output_tool="clarify (canned reply)",
        lives_in="route() → _out_of_scope_response()",
    ),
    RoutingStep(
        name="greeting_bypass",
        handles="PHASE_GREETING phase always handles via basic_info_tool",
        output_tool="basic_info_tool",
        lives_in="route() — pre-FAQ greeting bypass",
    ),
    RoutingStep(
        name="cancel_event_bypass",
        handles="explicit 'cancel my event' style requests",
        output_tool="modification_tool",
        lives_in="route() — cancel-event regex",
    ),
    RoutingStep(
        name="cancel_confirm_pending",
        handles="user is mid-cancel-confirmation flow",
        output_tool="modification_tool",
        lives_in="route() — __pending_cancel_event_confirm",
    ),
    RoutingStep(
        name="dont_want_or_i_want_intent",
        handles="'dont want X' / 'I want X' phrases at non-free-text phases",
        output_tool="modification_tool",
        lives_in="route() — pre-FAQ intent bypass",
    ),
    RoutingStep(
        name="command_bypass",
        handles="add/remove/change/etc. command verbs (with skip-gate exemption)",
        output_tool="modification_tool",
        lives_in="route() — pre_faq_command_bypass",
    ),
    RoutingStep(
        name="collection_phase_bypass",
        handles="user is mid-collecting special_requests / dietary free-text",
        output_tool="finalization_tool",
        lives_in="route() — collection_phase_bypass",
    ),
    RoutingStep(
        name="menu_phase_answer_bypass",
        handles="menu phase + clear menu pick (commas/numbers/<30 chars, no OOS markers)",
        output_tool="menu_selection_tool",
        lives_in="route() — menu_phase_answer_bypass",
    ),
    RoutingStep(
        name="conditional_followup_bypass",
        handles="PHASE_CONDITIONAL_FOLLOWUP — partner/honoree/company name collection",
        output_tool="basic_info_tool",
        lives_in="route() — conditional_followup_bypass",
    ),
    RoutingStep(
        name="free_text_intake_bypass",
        handles="PHASE_EVENT_DATE / VENUE / GUEST_COUNT / EVENT_TYPE answers",
        output_tool="basic_info_tool",
        lives_in="route() — free_text_intake_bypass",
    ),
    RoutingStep(
        name="binary_gate_bypass",
        handles="PHASE_SERVICE_TYPE / PHASE_WEDDING_CAKE structured answers",
        output_tool="basic_info_tool",
        lives_in="route() — binary_gate_bypass",
    ),
    RoutingStep(
        name="addons_phase_answer_bypass",
        handles="PHASE_DRINKS_BAR / TABLEWARE / RENTALS / LABOR answers",
        output_tool="add_ons_tool",
        lives_in="route() — addons_phase_answer_bypass",
    ),
    RoutingStep(
        name="finalization_phase_bypass",
        handles="PHASE_SPECIAL_REQUESTS / DIETARY / FOLLOWUP / REVIEW answers",
        output_tool="finalization_tool",
        lives_in="route() — finalization_phase_bypass",
    ),
    RoutingStep(
        name="faq_classifier",
        handles="catering service questions (pricing, allergies, water, etc.)",
        output_tool="clarify (LLM-generated answer)",
        lives_in="route() → _in_scope_faq_response()",
    ),
    RoutingStep(
        name="vague_response",
        handles="'idk' / 'whatever' / similar non-answers",
        output_tool="clarify (gentle nudge)",
        lives_in="route() → _vague_response()",
    ),
    RoutingStep(
        name="personality_oos_response",
        handles="personal statements ('I have ulcers'), expressive OOS markers",
        output_tool="clarify (warm waiter redirect)",
        lives_in="route() → _personality_oos_response()",
    ),
    RoutingStep(
        name="service_type_structured_value",
        handles="bare 'onsite' / 'drop-off' answers when prior AI prompt asked for service type",
        output_tool="basic_info_tool",
        lives_in="route() — service-type recent-prompt detection",
    ),
    RoutingStep(
        name="quick_route_deterministic",
        handles="20+ deterministic phase/value-specific routes (skip gates, replace verbs, etc.)",
        output_tool="(varies)",
        lives_in="route() → _quick_route()",
    ),
    RoutingStep(
        name="llm_router_fallback",
        handles="anything not caught above — LLM-based routing decision",
        output_tool="(varies)",
        lives_in="route() — bottom of function",
    ),
)


def routing_steps() -> tuple[RoutingStep, ...]:
    """Return the canonical routing pipeline as an ordered tuple."""
    return ROUTING_STEPS


def find_step(name: str) -> RoutingStep | None:
    """Look up a routing step by name. Returns None if not found."""
    for step in ROUTING_STEPS:
        if step.name == name:
            return step
    return None


def explain_routing() -> str:
    """Return a human-readable description of the full routing pipeline.

    Useful in HANDOVER.md and during incident debugging:
      from agent.routing import explain_routing
      print(explain_routing())
    """
    lines = [
        "AGENT ROUTING PIPELINE",
        "=" * 60,
        "Each step below is checked in order. First match wins.",
        "",
    ]
    for i, step in enumerate(ROUTING_STEPS, 1):
        lines.append(f"{i:>2}. {step.name}")
        lines.append(f"     handles: {step.handles}")
        lines.append(f"     routes to: {step.output_tool}")
        lines.append(f"     code: {step.lives_in}")
        lines.append("")
    return "\n".join(lines)


__all__ = ["RoutingStep", "ROUTING_STEPS", "routing_steps", "find_step", "explain_routing"]
