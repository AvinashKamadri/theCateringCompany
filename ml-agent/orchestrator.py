"""
Agent Orchestrator — persists everything via production FK chain:
  users -> projects -> threads -> ai_conversation_states -> messages
"""

import uuid
import traceback
from typing import Dict, Any, Optional

from langchain_core.messages import HumanMessage, AIMessage
from agent.graph import build_conversation_graph
from agent.state import initialize_empty_slots, ConversationState, SLOT_NAMES
from agent.nodes.helpers import set_current_project_id
from database.db_manager import (
    save_conversation_state, save_message,
    load_conversation_state, load_messages,
    create_project_and_thread, init_db,
)


class AgentOrchestrator:
    """
    Main orchestrator that processes messages and persists to:
      - projects / threads / ai_conversation_states (FK chain)
      - messages (every user + agent message)
    """

    def __init__(self):
        self.graph = build_conversation_graph()
        self._initialized = False

    async def _ensure_init(self):
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
        """
        Process a user message through the conversation graph.
        Creates project/thread FK chain on first message, then persists state + messages.
        """
        await self._ensure_init()

        # Load existing conversation state or create new
        existing = await load_conversation_state(thread_id)

        if existing:
            state_id = existing["id"]
            project_id = existing.get("project_id") or project_id
            current_node = existing["current_node"]
            slots = existing["slots"]
        else:
            # First message — create the full FK chain
            pid, tid, state_id = await create_project_and_thread(
                thread_id=thread_id,
                project_id=project_id,
                title="AI Catering Intake",
                user_id=user_id,
            )
            project_id = pid
            current_node = "start"
            slots = initialize_empty_slots()

        # Set project ID for AI generation logging
        set_current_project_id(project_id)

        # Rebuild messages from DB
        db_messages = await load_messages(thread_id)
        messages = []
        for m in db_messages:
            if m["sender_type"] == "user":
                messages.append(HumanMessage(content=m["content"]))
            else:
                messages.append(AIMessage(content=m["content"]))

        # Add current user message
        messages.append(HumanMessage(content=message))

        # Save user message to messages table
        await save_message(
            thread_id=thread_id,
            project_id=project_id,
            author_id=author_id,
            sender_type="client",
            content=message,
            ai_conversation_state_id=state_id,
        )

        # Build state for graph
        state: ConversationState = {
            "messages": messages,
            "conversation_id": state_id or "",
            "project_id": project_id,
            "thread_id": thread_id,
            "current_node": current_node,
            "slots": slots,
            "next_action": "",
            "error": None,
            "contract_data": None,
            "is_complete": False,
        }

        try:
            result = await self.graph.ainvoke(state)

            agent_content = ""
            for msg in reversed(list(result["messages"])):
                if isinstance(msg, AIMessage):
                    agent_content = msg.content
                    break

            is_complete = result.get("is_complete", False)
            new_node = result.get("current_node", current_node)
            new_slots = result.get("slots", slots)
            contract_data = result.get("contract_data")

        except Exception as e:
            agent_content = "I apologize, but I encountered an issue. Could you please try again?"
            is_complete = False
            new_node = current_node
            new_slots = slots
            contract_data = None
            print(f"[ERROR] Graph execution failed: {e}")
            traceback.print_exc()

        # Save conversation state
        new_state_id = await save_conversation_state(
            thread_id=thread_id,
            project_id=project_id,
            current_node=new_node,
            slots=new_slots,
            is_completed=is_complete,
        )

        # Save agent response to messages table
        await save_message(
            thread_id=thread_id,
            project_id=project_id,
            author_id="ai-agent",
            sender_type="ai",
            content=agent_content,
            ai_conversation_state_id=new_state_id,
        )

        # Count filled slots
        slots_filled = sum(1 for s in new_slots.values() if s.get("filled"))

        return {
            "content": agent_content,
            "current_node": new_node,
            "slots_filled": slots_filled,
            "total_slots": len(SLOT_NAMES),
            "is_complete": is_complete,
            "ai_conversation_state_id": new_state_id,
            "project_id": project_id,
            "thread_id": thread_id,
            "slots": new_slots,
            "contract_data": contract_data,
        }
