"""Regression: dessert resolution must not return an allergen-unsafe item.

Locks the bug where modification-tool "add tiramisu" paths (and pickers,
and resolvers) could surface nut-bearing desserts when the user had
declared a nut allergy. Covers:

  - filter_excluded_allergens: the post-fetch hard filter
  - load_dessert_menu_expanded: dessert menu + sub-item inheritance
  - resolve_dessert_choices: the modification entry point
  - annotate_allergen_safety: review-recap booleans
  - _guard_excluded: dev fail-loud / prod fail-CLOSED contract
"""
from __future__ import annotations

import sys

import pytest


sys.path.insert(0, r"c:\Users\avina\projects\flashback\TheCateringCompany\ml-agent")


@pytest.fixture
def fake_menu(monkeypatch):
    """Patch the shared cache loader so tests are deterministic."""
    menu = {
        "Desserts": [
            {
                "name": "Tiramisu",
                "unit_price": 6.0,
                "price_type": "per_person",
                "allergens": ["dairy", "egg", "tree_nuts"],
                "allergen_confidence": "derived",
            },
            {
                "name": "Fruit Tart",
                "unit_price": 5.0,
                "price_type": "per_person",
                "allergens": ["gluten"],
                "allergen_confidence": "derived",
            },
            {
                "name": "Mystery Mousse",
                "unit_price": 5.5,
                "price_type": "per_person",
                "allergens": [],
                "allergen_confidence": "incomplete",
            },
        ],
    }

    async def fake_loader():
        return menu

    import agent.menu_resolver as mr

    monkeypatch.setattr(mr, "_load_cached_menu", fake_loader)
    monkeypatch.setattr(mr, "_MENU_CACHE", None, raising=False)
    return menu


@pytest.mark.asyncio
async def test_load_dessert_menu_drops_nut_unsafe_when_user_excludes_nuts(fake_menu):
    from agent.menu_resolver import load_dessert_menu_expanded

    items = await load_dessert_menu_expanded(excluded_allergens=["tree_nuts"])
    names = {it["name"] for it in items}

    assert "Tiramisu" not in names, "nut-bearing dessert must be filtered out"
    assert "Mystery Mousse" not in names, "incomplete-confidence items must fail closed"
    assert "Fruit Tart" in names, "safe derived item should remain"


@pytest.mark.asyncio
async def test_resolve_dessert_choices_refuses_to_match_unsafe_item(fake_menu):
    """The bug we shipped a fix for: 'add tiramisu' with a nut allergy must
    not resolve to Tiramisu — the resolver only sees the filtered menu."""
    from agent.menu_resolver import resolve_dessert_choices

    resolution = await resolve_dessert_choices(
        ["tiramisu"],
        excluded_allergens=["tree_nuts"],
    )

    matched_names = {it["name"] for it in resolution.matched_items}
    assert "Tiramisu" not in matched_names
    assert resolution.matched_items == [] or all(
        n != "Tiramisu" for n in matched_names
    )


@pytest.mark.asyncio
async def test_annotate_allergen_safety_three_state(fake_menu):
    from agent.menu_resolver import annotate_allergen_safety, load_dessert_menu_expanded

    items = await load_dessert_menu_expanded(excluded_allergens=[])
    annotated = annotate_allergen_safety(items, ["tree_nuts"])
    by_name = {it["name"]: it for it in annotated}

    assert by_name["Tiramisu"]["is_safe"] is False
    assert "tree_nuts" in by_name["Tiramisu"]["unsafe_allergens"]

    assert by_name["Fruit Tart"]["is_safe"] is True
    assert by_name["Fruit Tart"]["unsafe_allergens"] == []

    assert by_name["Mystery Mousse"]["is_safe"] is False
    assert by_name["Mystery Mousse"]["unsafe_allergens"] == ["unknown"]
    assert by_name["Mystery Mousse"]["allergen_confidence"] == "incomplete"


@pytest.mark.asyncio
async def test_guard_fails_loud_in_dev(fake_menu, monkeypatch):
    """Caller forgets excluded_allergens — dev must crash so the bypass
    is caught before merge."""
    from agent.menu_resolver import load_dessert_menu_expanded

    monkeypatch.setenv("ML_ENV", "development")
    monkeypatch.delenv("NODE_ENV", raising=False)

    with pytest.raises(ValueError, match="excluded_allergens is required"):
        await load_dessert_menu_expanded()


@pytest.mark.asyncio
async def test_guard_fails_closed_in_prod(fake_menu, monkeypatch, caplog):
    """Caller forgets excluded_allergens in prod — must NOT serve unsafe
    items. Fail-CLOSED: defaults to excluding every FALCPA allergen, so
    only items with empty allergen lists and derived confidence survive."""
    from agent.menu_resolver import load_dessert_menu_expanded

    monkeypatch.setenv("ML_ENV", "production")
    monkeypatch.delenv("NODE_ENV", raising=False)

    with caplog.at_level("ERROR"):
        items = await load_dessert_menu_expanded()

    names = {it["name"] for it in items}
    assert "Tiramisu" not in names, "fail-closed must drop nut-bearing item"
    assert "Mystery Mousse" not in names, "fail-closed must drop incomplete items"
    assert "Fruit Tart" not in names, (
        "fail-closed excludes ALL FALCPA allergens — gluten counts"
    )
    assert any("FAIL-CLOSED" in rec.message for rec in caplog.records), (
        "missing-kwarg path must emit a loud log line for prod observability"
    )


def test_friendly_allergen_phrase():
    from agent.menu_resolver import friendly_allergen_phrase

    assert friendly_allergen_phrase([]) == ""
    assert friendly_allergen_phrase(["tree_nuts"]) == "nut-free"
    # peanuts and tree_nuts collapse to one "nut-free" label
    assert friendly_allergen_phrase(["tree_nuts", "peanuts"]) == "nut-free"
    assert friendly_allergen_phrase(["dairy", "tree_nuts"]) == "dairy-free, nut-free"


def test_safe_alternatives_re_filters_and_skips_blocked(fake_menu):
    """Even if a buggy caller passes unfiltered items, the helper must
    re-apply the allergen filter — the safety contract cannot be relaxed
    by accident in a fallback path."""
    from agent.menu_resolver import safe_alternatives_from_items

    unfiltered = fake_menu["Desserts"]  # includes Tiramisu + Mystery Mousse

    alts = safe_alternatives_from_items(
        unfiltered,
        ["tree_nuts"],
        exclude_names=["Tiramisu"],
        limit=5,
    )
    names = [a["name"] for a in alts]

    assert "Tiramisu" not in names, "blocked item must not be suggested back"
    assert "Mystery Mousse" not in names, "incomplete-confidence item must be excluded"
    assert names == ["Fruit Tart"], "only the safe derived item should remain"


def test_safe_alternatives_caps_at_limit(fake_menu):
    from agent.menu_resolver import safe_alternatives_from_items

    bulk = [
        {
            "name": f"Safe Item {i}",
            "allergens": [],
            "allergen_confidence": "derived",
            "unit_price": 1.0,
        }
        for i in range(10)
    ]
    alts = safe_alternatives_from_items(bulk, ["tree_nuts"], limit=3)
    assert len(alts) == 3
