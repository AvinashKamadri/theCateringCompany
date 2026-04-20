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

import logging
import traceback
from typing import Any, Dict, Optional

from langchain_core.messages import AIMessage, HumanMessage

from agent.response_generator import render as render_response
from agent.router import route as route_turn
from agent.tools.base import ToolResult
from agent.state import (
    PHASE_GREETING,
    SLOT_NAMES,
    initialize_empty_slots,
)
from agent.tools import TOOL_REGISTRY
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
    ) -> Dict[str, Any]:
        await self._ensure_init()

        existing = await load_conversation_state(thread_id)

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

        # Rebuild history from DB
        db_messages = await load_messages(thread_id)
        history = []
        for m in db_messages:
            if m["sender_type"] == "user":
                history.append(HumanMessage(content=m["content"]))
            else:
                history.append(AIMessage(content=m["content"]))

        await save_message(
            thread_id=thread_id,
            project_id=project_id,
            author_id=author_id,
            sender_type="client",
            content=message,
            ai_conversation_state_id=state_id,
        )

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
                )
                agent_content = await render_response(
                    tool_result=tool_result, user_message=message, history=history
                )
            else:
                call = decision.tool_calls[0]
                tool = TOOL_REGISTRY[call.tool_name]
                tool_used = call.tool_name
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

        new_state_id = await save_conversation_state(
            thread_id=thread_id,
            project_id=project_id,
            current_node=conversation_phase,
            slots=slots,
            is_completed=is_complete,
        )

        await save_message(
            thread_id=thread_id,
            project_id=project_id,
            author_id="ai-agent",
            sender_type="ai",
            content=agent_content,
            ai_conversation_state_id=new_state_id,
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
