"""
LangGraph node implementations for the catering intake flow.
"""

from agent.nodes.start import start_node
from agent.nodes.basic_info import (
    collect_name_node,
    collect_event_date_node,
    select_service_type_node,
    select_event_type_node,
    collect_event_type_followup_node,
    collect_venue_node,
    collect_guest_count_node,
    present_menu_node,
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
    ask_cocktail_hour_node,
    ask_buffet_or_plated_node,
    ask_desserts_node,
    select_desserts_node,
    ask_drinks_node,
    ask_bar_service_node,
    ask_tableware_node,
    ask_rentals_node,
    ask_labor_services_node,
)
from agent.nodes.final import (
    ask_special_requests_node,
    collect_special_requests_node,
    collect_dietary_node,
    generate_summary_node,
    offer_followup_call_node,
)
from agent.nodes.check_modifications import check_modifications_node

# Map node names to their functions
NODE_MAP = {
    "start": start_node,
    "collect_name": collect_name_node,
    "select_event_type": select_event_type_node,
    "collect_event_type_followup": collect_event_type_followup_node,
    "collect_event_date": collect_event_date_node,
    "collect_venue": collect_venue_node,
    "collect_guest_count": collect_guest_count_node,
    "select_service_type": select_service_type_node,
    "ask_cocktail_hour": ask_cocktail_hour_node,
    "select_appetizers": select_appetizers_node,
    "ask_appetizers": ask_appetizers_node,
    "ask_buffet_or_plated": ask_buffet_or_plated_node,
    "present_menu": present_menu_node,
    "menu_design": menu_design_node,
    "select_dishes": select_dishes_node,
    "ask_menu_changes": ask_menu_changes_node,
    "collect_menu_changes": collect_menu_changes_node,
    "ask_desserts": ask_desserts_node,
    "select_desserts": select_desserts_node,
    "ask_drinks": ask_drinks_node,
    "ask_bar_service": ask_bar_service_node,
    "ask_tableware": ask_tableware_node,
    "ask_rentals": ask_rentals_node,
    "ask_special_requests": ask_special_requests_node,
    "collect_special_requests": collect_special_requests_node,
    "ask_labor_services": ask_labor_services_node,
    "collect_dietary": collect_dietary_node,
    "generate_summary": generate_summary_node,
    "offer_followup_call": offer_followup_call_node,
    "check_modifications": check_modifications_node,
}

__all__ = list(NODE_MAP.keys()) + ["NODE_MAP"]
