"""
LangGraph state machine for the catering intake conversation flow.
"""

from langgraph.graph import StateGraph, END
from agent.state import ConversationState
from agent.nodes import NODE_MAP
from agent.routing import route_message


def build_conversation_graph():
    """
    Build the LangGraph state machine with all conversation nodes.

    Flow: start -> basic info -> menu building -> add-ons -> final -> summary
    Each node processes ONE user message then routes to END.
    The router uses current_node to determine which node runs next.
    """
    workflow = StateGraph(ConversationState)

    # Add all nodes from the node map
    for name, func in NODE_MAP.items():
        workflow.add_node(name, func)

    # Conditional entry point: route based on current_node
    route_map = {name: name for name in NODE_MAP}
    workflow.set_conditional_entry_point(route_message, route_map)

    # Every node goes to END after processing (single-message-per-invocation)
    for name in NODE_MAP:
        workflow.add_edge(name, END)

    return workflow.compile()
