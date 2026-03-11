"""
LangGraph node implementations for the catering intake flow.
"""

from agent.nodes.start import start_node
from agent.nodes.basic_info import (
    collect_name_node,
    collect_event_date_node,
    select_service_type_node,
    select_event_type_node,
    wedding_message_node,
    collect_venue_node,
    collect_guest_count_node,
    select_service_style_node,
)
from agent.nodes.menu import (
    select_dishes_node,
    ask_appetizers_node,
    select_appetizers_node,
    menu_design_node,
    ask_menu_changes_node,
    collect_menu_changes_node,
)
from agent.nodes.addons import (
    ask_utensils_node,
    select_utensils_node,
    ask_desserts_node,
    select_desserts_node,
    ask_more_desserts_node,
    ask_rentals_node,
    ask_florals_node,
)
from agent.nodes.final import (
    ask_special_requests_node,
    collect_special_requests_node,
    collect_dietary_node,
    ask_anything_else_node,
    collect_anything_else_node,
    generate_contract_node,
)
from agent.nodes.check_modifications import check_modifications_node

# Map node names to their functions
NODE_MAP = {
    "start": start_node,
    "collect_name": collect_name_node,
    "collect_event_date": collect_event_date_node,
    "select_service_type": select_service_type_node,
    "select_event_type": select_event_type_node,
    "wedding_message": wedding_message_node,
    "collect_venue": collect_venue_node,
    "collect_guest_count": collect_guest_count_node,
    "select_service_style": select_service_style_node,
    "select_dishes": select_dishes_node,
    "ask_appetizers": ask_appetizers_node,
    "select_appetizers": select_appetizers_node,
    "menu_design": menu_design_node,
    "ask_menu_changes": ask_menu_changes_node,
    "collect_menu_changes": collect_menu_changes_node,
    "ask_utensils": ask_utensils_node,
    "select_utensils": select_utensils_node,
    "ask_desserts": ask_desserts_node,
    "select_desserts": select_desserts_node,
    "ask_more_desserts": ask_more_desserts_node,
    "ask_rentals": ask_rentals_node,
    "ask_florals": ask_florals_node,
    "ask_special_requests": ask_special_requests_node,
    "collect_special_requests": collect_special_requests_node,
    "collect_dietary": collect_dietary_node,
    "ask_anything_else": ask_anything_else_node,
    "collect_anything_else": collect_anything_else_node,
    "generate_contract": generate_contract_node,
    "check_modifications": check_modifications_node,
}

__all__ = list(NODE_MAP.keys()) + ["NODE_MAP"]
