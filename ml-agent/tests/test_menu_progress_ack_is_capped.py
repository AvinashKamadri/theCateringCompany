import sys


sys.path.insert(0, r"c:\Projects\CateringCompany\ml-agent")


from agent.tools.menu_selection_tool import _list_progress_message  # noqa: E402


def test_list_progress_message_caps_large_added_lists() -> None:
    before: list[str] = []
    after = [f"Item {i}" for i in range(1, 10)]
    msg = _list_progress_message(label="main dishes", before=before, after=after)
    lowered = msg.lower()
    assert "added 9" in lowered
    assert "item 1" not in lowered  # should not inline the entire list

