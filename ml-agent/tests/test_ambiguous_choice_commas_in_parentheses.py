import sys

from agent.ambiguous_choice import resolve_multi_choice_selection  # noqa: E402

def test_resolve_multi_choice_selection_does_not_split_commas_in_parentheses() -> None:
    options = [
        "Adobo Lime Chicken Bites",
        "Meatballs (BBQ, Swedish, Sweet and Sour)",
        "Filet Tip Crostini",
    ]
    msg = "Meatballs (BBQ, Swedish, Sweet and Sour)"
    assert resolve_multi_choice_selection(msg, options) == [options[1]]

