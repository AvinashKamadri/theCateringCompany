"""
Agent Orchestrator — shell around the new router + tools.

Persistence FK chain (unchanged from the pre-overhaul shell):
  users -> projects -> threads -> ai_conversation_states -> messages

What changed:
- The 42-node LangGraph state machine is GONE.
- Every turn runs exactly one Tool, picked by `agent.router.route()`.
- The Response Generator owns phrasing; Tools propose structured facts.
- `current_node` (DB column) now stores `conversation_phase` (S1..S19).

Safety: the outer try/except guarantees the API never returns a 500 to the
frontend on LLM / Instructor / OpenAI outages. On failure we preserve the
prior slots and emit a gentle fallback message.
"""

from __future__ import annotations

import asyncio
import logging
import traceback
from typing import Any, Dict, Optional

from langchain_core.messages import AIMessage, HumanMessage

from agent.response_generator import render as render_response
from agent.router import route as route_turn
from agent.trace_context import trace_scope, turn_scope
from agent.tools.base import ToolResult
from agent.state import (
    PHASE_GREETING,
    SLOT_NAMES,
    initialize_empty_slots,
)
from agent.tools import TOOL_REGISTRY
from agent.redis_cache import delete_state as _redis_delete, get_state as _redis_get, set_state as _redis_set
from database.db_manager import (
    create_project_and_thread,
    init_db,
    load_conversation_state,
    load_messages,
    save_conversation_state,
    save_message,
)

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """Persists state + delegates each turn to router + one Tool."""

    def __init__(self) -> None:
        self._initialized = False

    async def _ensure_init(self) -> None:
        if not self._initialized:
            await init_db()
            self._initialized = True

    async def process_message(
        self,
        thread_id: str,
        message: str,
        author_id: str = "user",
        project_id: Optional[str] = None,
        user_id: Optional[str] = None,
        preloaded_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        await self._ensure_init()

        # Redis → Postgres fallback for hot session state.
        # preloaded_state is passed by api.py when it already fetched Postgres state.
        if preloaded_state is not None:
            existing = preloaded_state
        else:
            existing = await _redis_get(thread_id)
            if existing is None:
                existing = await load_conversation_state(thread_id)
                if existing:
                    # Warm the cache for subsequent turns.
                    await _redis_set(thread_id, existing)

        if existing:
            state_id = existing["id"]
            project_id = existing.get("project_id") or project_id
            conversation_phase = existing.get("current_node") or PHASE_GREETING
            slots = existing["slots"]
        else:
            pid, tid, state_id = await create_project_and_thread(
                thread_id=thread_id,
                project_id=project_id,
                title="AI Catering Intake",
                user_id=user_id,
            )
            project_id = pid
            conversation_phase = PHASE_GREETING
            slots = initialize_empty_slots()

        # Rebuild history from DB and persist the user's new message in
        # parallel — neither depends on the other.
        db_messages, _ = await asyncio.gather(
            load_messages(thread_id),
            save_message(
                thread_id=thread_id,
                project_id=project_id,
                author_id=author_id,
                sender_type="client",
                content=message,
                ai_conversation_state_id=state_id,
            ),
        )
        history = []
        for m in db_messages:
            if m["sender_type"] == "user":
                history.append(HumanMessage(content=m["content"]))
            else:
                history.append(AIMessage(content=m["content"]))

        state: Dict[str, Any] = {
            "messages": history + [HumanMessage(content=message)],
            "conversation_id": state_id or "",
            "project_id": project_id,
            "thread_id": thread_id,
            "conversation_phase": conversation_phase,
            "slots": slots,
            "contract_data": None,
            "is_complete": False,
            "error": None,
        }

        agent_content = ""
        input_hint = None
        contract_data = None
        tool_used = None

        logger.info(
            "turn_start thread=%s phase=%s msg=%r",
            thread_id, conversation_phase, message[:120],
        )

        try:
          with turn_scope(thread_id=thread_id):
            with trace_scope(
                thread_id=thread_id,
                project_id=project_id,
                conversation_id=state_id or "",
                user_id=user_id,
                author_id=author_id,
                phase=conversation_phase,
                tool="router",
            ):
                decision = await route_turn(
                    message=message,
                    history=history,
                    state=state,
                )
            logger.info(
                "router_decision thread=%s action=%s confidence=%.2f tool=%s",
                thread_id,
                decision.action,
                decision.confidence,
                decision.tool_calls[0].tool_name if decision.tool_calls else "-",
            )

            if decision.action == "no_action":
                agent_content = (
                    "Your request is already with our team — we'll be in touch soon."
                )
            elif decision.action == "clarify" or not decision.tool_calls:
                tool_result = ToolResult(
                    state=state,
                    response_context={
                        "tool": "router",
                        "error": "could_not_route",
                        "clarifying_question": decision.clarifying_question,
                    },
                    # When the router already has a formed response (e.g. out-of-scope
                    # redirect), render it verbatim and skip the LLM generator call.
                    direct_response=decision.clarifying_question if decision.clarifying_question else None,
                )
                with trace_scope(
                    thread_id=thread_id,
                    project_id=project_id,
                    conversation_id=state_id or "",
                    user_id=user_id,
                    author_id=author_id,
                    phase=conversation_phase,
                    tool="response_generator",
                    source_tool="router",
                    target="clarify",
                ):
                    agent_content = await render_response(
                        tool_result=tool_result, user_message=message, history=history
                    )
            else:
                call = decision.tool_calls[0]
                tool = TOOL_REGISTRY[call.tool_name]
                tool_used = call.tool_name
                with trace_scope(
                    thread_id=thread_id,
                    project_id=project_id,
                    conversation_id=state_id or "",
                    user_id=user_id,
                    author_id=author_id,
                    phase=conversation_phase,
                    tool=tool_used,
                ):
                    tool_result = await tool.run(
                        message=message,
                        history=history,
                        state=state,
                    )
                state = tool_result.state
                slots = state["slots"]
                conversation_phase = state.get("conversation_phase", conversation_phase)
                input_hint = tool_result.input_hint
                contract_data = tool_result.response_context.get("pricing")
                logger.info(
                    "tool_done thread=%s tool=%s next_phase=%s filled=%s",
                    thread_id,
                    tool_used,
                    conversation_phase,
                    [f[0] for f in tool_result.response_context.get("filled_this_turn", [])],
                )
                with trace_scope(
                    thread_id=thread_id,
                    project_id=project_id,
                    conversation_id=state_id or "",
                    user_id=user_id,
                    author_id=author_id,
                    phase=conversation_phase,
                    tool="response_generator",
                    source_tool=tool_used,
                    target=(tool_result.response_context or {}).get("next_question_target"),
                ):
                    agent_content = await render_response(
                        tool_result=tool_result,
                        user_message=message,
                        history=history,
                    )
        except Exception as exc:
            logger.error("Orchestrator turn failed: %s\n%s", exc, traceback.format_exc())
            agent_content = (
                "I hit a snag on my end — could you try that again in a moment?"
            )

        is_complete = conversation_phase == "complete"

        # save_conversation_state upserts by thread_id and returns the existing
        # row's id when the row already exists — which it always does here,
        # because either `existing` was loaded above or `create_project_and_thread`
        # already created the row. So we can reuse `state_id` for the AI message
        # FK and run both writes concurrently.
        # Build the updated state dict so Redis gets a fresh copy.
        _updated_cache_state = {
            "id": state_id,
            "project_id": project_id,
            "current_node": conversation_phase,
            "slots": slots,
            "is_completed": is_complete,
        }

        new_state_id, _, _ = await asyncio.gather(
            save_conversation_state(
                thread_id=thread_id,
                project_id=project_id,
                current_node=conversation_phase,
                slots=slots,
                is_completed=is_complete,
            ),
            save_message(
                thread_id=thread_id,
                project_id=project_id,
                author_id="ai-agent",
                sender_type="ai",
                content=agent_content,
                ai_conversation_state_id=state_id,
            ),
            # Write to Redis cache concurrently with Postgres. Evict on complete
            # so stale completed sessions don't block new sessions with same thread.
            _redis_delete(thread_id) if is_complete else _redis_set(thread_id, _updated_cache_state),
        )

        slots_filled = sum(
            1 for k, s in slots.items()
            if s.get("filled") and not k.startswith("__")
        )

        return {
            "content": agent_content,
            "current_node": conversation_phase,
            "conversation_phase": conversation_phase,
            "slots_filled": slots_filled,
            "total_slots": len(SLOT_NAMES),
            "is_complete": is_complete,
            "ai_conversation_state_id": new_state_id,
            "project_id": project_id,
            "thread_id": thread_id,
            "slots": slots,
            "contract_data": contract_data,
            "input_hint": input_hint,
            "tool_used": tool_used,
        }

