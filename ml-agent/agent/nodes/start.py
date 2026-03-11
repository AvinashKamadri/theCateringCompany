"""Start node - initializes the conversation."""

from agent.state import ConversationState, initialize_empty_slots
from agent.nodes.helpers import add_ai_message, llm_respond
from prompts.system_prompts import SYSTEM_PROMPT, NODE_PROMPTS


async def start_node(state: ConversationState) -> ConversationState:
    """Initialize conversation and welcome the customer."""
    state = dict(state)

    # Initialize slots if empty
    if not state.get("slots") or all(
        not v.get("filled") for v in state.get("slots", {}).values()
    ):
        state["slots"] = initialize_empty_slots()

    response = await llm_respond(
        f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['start']}",
        "A new customer has started a conversation. Welcome them and ask for their name."
    )

    state["current_node"] = "collect_name"
    state["messages"] = add_ai_message(state, response)
    return state
