"""
PostgreSQL database manager using Prisma Client Python (async).

Production tables (11):
  users, projects, threads, ai_conversation_states, messages,
  contracts, contract_clauses, menu_categories, menu_items,
  pricing_packages, ai_generations
"""

import uuid
import logging
from decimal import Decimal
from prisma import Prisma, Json

logger = logging.getLogger(__name__)

_client: Prisma | None = None

SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000001"


async def init_db():
    """Connect Prisma client."""
    global _client
    if _client is None:
        _client = Prisma()
        await _client.connect()
        logger.info("Prisma client connected")


async def close_client():
    """Disconnect Prisma client."""
    global _client
    if _client:
        await _client.disconnect()
        _client = None
        logger.info("Prisma client disconnected")


def _get_client() -> Prisma:
    if _client is None:
        raise RuntimeError("Prisma client not initialized. Call init_db() first.")
    return _client


# ---------------------------------------------------------------------------
# Project + Thread + AI Conversation State — FK chain setup
# ---------------------------------------------------------------------------

async def create_project_and_thread(
    thread_id: str,
    project_id: str | None = None,
    title: str = "AI Catering Intake",
    user_id: str | None = None,
) -> tuple[str, str, str]:
    """
    Ensure a project, thread, and ai_conversation_state exist for a conversation.
    Returns (project_id, thread_id, ai_conversation_state_id).

    If the thread already exists (by thread_id), returns the existing IDs.
    Otherwise creates the full FK chain: project -> thread -> ai_conversation_state.
    """
    client = _get_client()
    owner_id = user_id or SYSTEM_USER_ID

    # Check if thread already exists
    existing_thread = await client.threads.find_unique(where={"id": thread_id})
    if existing_thread:
        ai_state = await client.ai_conversation_states.find_unique(
            where={"thread_id": existing_thread.id}
        )
        return (
            existing_thread.project_id,
            existing_thread.id,
            ai_state.id if ai_state else "",
        )

    # Create project if needed
    pid = project_id or str(uuid.uuid4())
    existing_project = await client.projects.find_unique(where={"id": pid}) if project_id else None

    if not existing_project:
        await client.projects.create(
            data={
                "id": pid,
                "owner_user_id": owner_id,
                "title": title,
                "status": "draft",
                "created_via_ai_intake": True,
            }
        )
        # Add owner as collaborator so they can see and access the project.
        # Use raw SQL — project_collaborators is not in the Python Prisma schema.
        await client.execute_raw(
            "INSERT INTO project_collaborators (project_id, user_id, role, added_by, added_at) "
            "VALUES ($1::uuid, $2::uuid, 'owner', $3::uuid, now()) "
            "ON CONFLICT (project_id, user_id) DO NOTHING",
            pid, owner_id, owner_id,
        )

    # Create thread
    await client.threads.create(
        data={
            "id": thread_id,
            "project_id": pid,
            "subject": title,
            "created_by": owner_id,
        }
    )

    # Create ai_conversation_state
    state_id = str(uuid.uuid4())
    await client.ai_conversation_states.create(
        data={
            "id": state_id,
            "thread_id": thread_id,
            "project_id": pid,
            "current_node": "start",
            "slots": Json({}),
            "is_completed": False,
        }
    )

    # Link project to AI state
    await client.projects.update(
        where={"id": pid},
        data={"ai_conversation_state_id": state_id},
    )

    return pid, thread_id, state_id


# ---------------------------------------------------------------------------
# AI Conversation States
# ---------------------------------------------------------------------------

async def save_conversation_state(
    thread_id: str,
    project_id: str | None,
    current_node: str,
    slots: dict,
    is_completed: bool,
) -> str:
    """Upsert conversation state after every node execution."""
    client = _get_client()

    existing = await client.ai_conversation_states.find_unique(
        where={"thread_id": thread_id}
    )

    if existing:
        await client.ai_conversation_states.update(
            where={"id": existing.id},
            data={
                "current_node": current_node,
                "slots": Json(slots),
                "is_completed": is_completed,
            },
        )
        return existing.id
    else:
        state_id = str(uuid.uuid4())
        await client.ai_conversation_states.create(
            data={
                "id": state_id,
                "thread_id": thread_id,
                "project_id": project_id,
                "current_node": current_node,
                "slots": Json(slots),
                "is_completed": is_completed,
            }
        )
        return state_id


async def load_conversation_state(thread_id: str) -> dict | None:
    """Load conversation state by thread_id."""
    client = _get_client()
    row = await client.ai_conversation_states.find_unique(
        where={"thread_id": thread_id}
    )

    if not row:
        return None

    return {
        "id": row.id,
        "project_id": row.project_id,
        "thread_id": row.thread_id,
        "current_node": row.current_node,
        "slots": row.slots or {},
        "is_completed": row.is_completed,
    }


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

async def save_message(
    thread_id: str,
    project_id: str,
    author_id: str,
    sender_type: str,
    content: str,
    ai_conversation_state_id: str | None = None,
) -> str:
    """Save a message to the messages table.
    sender_type must be: 'user', 'ai', or 'system' (DB check constraint).
    """
    client = _get_client()
    msg_id = str(uuid.uuid4())

    # Normalize sender_type to match DB constraint
    if sender_type in ("client", "human"):
        sender_type = "user"

    # Resolve author_id: AI messages use system user, user messages use provided
    # UUID if valid, otherwise null (anonymous intake conversation)
    import re as _re
    _UUID_RE = _re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', _re.I)
    if sender_type == "ai":
        resolved_author = SYSTEM_USER_ID
    elif author_id and _UUID_RE.match(str(author_id)):
        resolved_author = author_id
    else:
        resolved_author = None

    await client.messages.create(
        data={
            "id": msg_id,
            "thread_id": thread_id,
            "project_id": project_id,
            "author_id": resolved_author,
            "sender_type": sender_type,
            "content": content,
            "ai_conversation_state_id": ai_conversation_state_id,
        }
    )

    return msg_id


async def load_messages(thread_id: str) -> list[dict]:
    """Load all messages for a thread, ordered by creation time."""
    client = _get_client()
    rows = await client.messages.find_many(
        where={"thread_id": thread_id},
        order={"created_at": "asc"},
    )

    return [
        {
            "sender_type": row.sender_type or "unknown",
            "content": row.content,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Contracts — with versioning support
# ---------------------------------------------------------------------------

async def save_contract(
    project_id: str,
    client_name: str,
    event_date: str,
    body: dict,
    total_amount: float | None = None,
    previous_version_id: str | None = None,
) -> str:
    """
    Save a generated contract with versioning.
    Title format: @ClientName Year.docx
    """
    client = _get_client()
    contract_id = str(uuid.uuid4())

    # Determine version
    if previous_version_id:
        prev = await client.contracts.find_unique(where={"id": previous_version_id})
        contract_group_id = prev.contract_group_id if prev else str(uuid.uuid4())
        version_number = (prev.version_number + 1) if prev else 1
    else:
        contract_group_id = str(uuid.uuid4())
        version_number = 1

    # Title: @ClientName Year.docx
    year = event_date[:4] if event_date and len(event_date) >= 4 else "2026"
    title = f"@{client_name} {year}.docx"

    await client.contracts.create(
        data={
            "id": contract_id,
            "contract_group_id": contract_group_id,
            "version_number": version_number,
            "previous_version_id": previous_version_id,
            "project_id": project_id,
            "status": "draft",
            "title": title,
            "body": Json(body),
            "total_amount": Decimal(str(total_amount)) if total_amount else None,
            "ai_generated": True,
            "created_by": SYSTEM_USER_ID,
            "is_active": True,
        }
    )

    return contract_id


async def load_contract(contract_id: str) -> dict | None:
    """Load a contract by ID."""
    client = _get_client()
    row = await client.contracts.find_unique(where={"id": contract_id})
    if not row:
        return None
    return {
        "id": row.id,
        "contract_group_id": row.contract_group_id,
        "version_number": row.version_number,
        "project_id": row.project_id,
        "title": row.title,
        "body": row.body,
        "total_amount": float(row.total_amount) if row.total_amount else None,
        "status": str(row.status),
        "ai_generated": row.ai_generated,
        "created_at": row.created_at.isoformat(),
    }


async def load_contracts_by_project(project_id: str) -> list[dict]:
    """Load all contracts for a project, newest first."""
    client = _get_client()
    rows = await client.contracts.find_many(
        where={"project_id": project_id},
        order={"created_at": "desc"},
    )
    return [
        {
            "id": row.id,
            "title": row.title,
            "version_number": row.version_number,
            "status": str(row.status),
            "ai_generated": row.ai_generated,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Menu — query real menu data from DB
# ---------------------------------------------------------------------------

async def load_menu_items(active_only: bool = True) -> list[dict]:
    """Load all menu items with their category names."""
    client = _get_client()
    where = {"active": True} if active_only else {}
    rows = await client.menu_items.find_many(
        where=where,
        include={"menu_categories": True},
        order={"name": "asc"},
    )
    def _cat_display(cat) -> str:
        if not cat:
            return "Uncategorized"
        section = cat.section or ""
        name = cat.name or ""
        if section and section != name:
            return f"{section} - {name}"
        return name

    return [
        {
            "id": row.id,
            "name": row.name,
            "description": row.description,
            "section": row.menu_categories.section if row.menu_categories else "",
            "category": _cat_display(row.menu_categories),
            "unit_price": float(row.unit_price) if row.unit_price else None,
            "price_type": str(row.price_type) if row.price_type else None,
            "minimum_quantity": row.minimum_quantity,
            "allergens": row.allergens,
            "tags": row.tags,
            "is_upsell": row.is_upsell,
        }
        for row in rows
    ]


async def load_menu_by_category(active_only: bool = True) -> dict[str, list[dict]]:
    """Load menu items grouped by category. Returns {category_name: [items]}."""
    client = _get_client()
    where = {"active": True} if active_only else {}
    categories = await client.menu_categories.find_many(
        where=where,
        include={"menu_items": True},
        order={"sort_order": "asc"},
    )
    result = {}
    for cat in categories:
        items = cat.menu_items or []
        if active_only:
            items = [i for i in items if i.active]
        items.sort(key=lambda i: i.name)
        if not items:
            continue
        # Build display key: "Section - Name" when they differ, else just "Name"
        section = cat.section or ""
        name = cat.name or ""
        display_key = f"{section} - {name}" if section and section != name else name
        result[display_key] = [
            {
                "id": item.id,
                "name": item.name,
                "description": item.description,
                "section": section,
                "category": name,
                "unit_price": float(item.unit_price) if item.unit_price else None,
                "price_type": str(item.price_type) if item.price_type else None,
                "allergens": item.allergens,
                "tags": item.tags,
                "is_upsell": item.is_upsell,
            }
            for item in items
        ]
    return result


async def load_menu_categories() -> list[dict]:
    """Load all active menu categories."""
    client = _get_client()
    rows = await client.menu_categories.find_many(
        where={"active": True},
        order={"sort_order": "asc"},
    )
    return [
        {
            "id": row.id,
            "section": row.section or "",
            "name": row.name,
        }
        for row in rows
    ]


async def load_dessert_items() -> list[dict]:
    """Load dessert menu items — includes Coffee and Desserts + Wedding Cakes."""
    client = _get_client()
    dessert_cats = await client.menu_categories.find_many(
        where={
            "active": True,
            "OR": [
                {"section": {"contains": "Dessert", "mode": "insensitive"}},
                {"section": {"contains": "Coffee", "mode": "insensitive"}},
                {"section": {"contains": "Cake", "mode": "insensitive"}},
                {"name": {"contains": "Dessert", "mode": "insensitive"}},
                {"name": {"contains": "Coffee", "mode": "insensitive"}},
                {"name": {"contains": "Cake", "mode": "insensitive"}},
            ],
        }
    )
    if not dessert_cats:
        return []
    cat_ids = [cat.id for cat in dessert_cats]
    rows = await client.menu_items.find_many(
        where={"category_id": {"in": cat_ids}, "active": True},
        order={"name": "asc"},
    )
    return [
        {
            "id": row.id,
            "name": row.name,
            "description": row.description,
            "unit_price": float(row.unit_price) if row.unit_price else None,
        }
        for row in rows
    ]


async def load_pricing_packages(active_only: bool = True) -> list[dict]:
    """Load pricing packages."""
    client = _get_client()
    where = {"active": True} if active_only else {}
    rows = await client.pricing_packages.find_many(
        where=where,
        order={"priority": "desc"},
    )
    return [
        {
            "id": row.id,
            "name": row.name,
            "description": row.description,
            "category": row.category,
            "base_price": float(row.base_price) if row.base_price else None,
            "price_type": str(row.price_type) if row.price_type else None,
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# AI Generations — audit logging
# ---------------------------------------------------------------------------

async def log_ai_generation(
    entity_type: str,
    model: str,
    project_id: str | None = None,
    entity_id: str | None = None,
    input_summary: dict | None = None,
    output: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    latency_ms: int | None = None,
    prompt_version: str | None = None,
    was_applied: bool = False,
) -> str:
    """Log an AI generation call for auditability."""
    client = _get_client()
    gen_id = str(uuid.uuid4())

    await client.ai_generations.create(
        data={
            "id": gen_id,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "project_id": project_id,
            "triggered_by": SYSTEM_USER_ID,
            "model": model,
            "prompt_version": prompt_version,
            "input_summary": Json(input_summary) if input_summary else None,
            "output": output,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency_ms": latency_ms,
            "was_applied": was_applied,
        }
    )

    return gen_id


# ---------------------------------------------------------------------------
# Project helpers
# ---------------------------------------------------------------------------

async def update_project_summary(
    project_id: str,
    event_date: str | None = None,
    guest_count: int | None = None,
    summary: str | None = None,
) -> None:
    """Update project with event details after intake completes."""
    client = _get_client()
    data = {}
    if event_date:
        from datetime import datetime
        try:
            data["event_date"] = datetime.strptime(event_date, "%Y-%m-%d")
        except (ValueError, TypeError):
            # Never crash the API on a malformed date — skip the field instead.
            pass
    if guest_count:
        data["guest_count"] = guest_count
    if summary:
        data["ai_event_summary"] = summary
    if data:
        await client.projects.update(where={"id": project_id}, data=data)


async def sync_slots_to_project(project_id: str, slots: dict, thread_id: str) -> None:
    """Write current filled slot values to ai_event_summary so the project view
    reflects live conversation progress. Called after every AI message."""
    client = _get_client()

    def slot_val(name: str):
        s = slots.get(name, {})
        return s.get("value") if s.get("filled") else None

    # Build addons list from individual add-on slots
    addons = []
    for addon_slot in ("utensils", "rentals", "florals"):
        v = slot_val(addon_slot)
        if v and str(v).lower() not in ("no", "none", ""):
            addons.append(v if isinstance(v, str) else str(v))

    desserts = slot_val("desserts")

    summary_json: dict = {"thread_id": thread_id}

    # Map slots → the shape the project page expects
    mappings = {
        "client_name": slot_val("name"),
        "event_type": slot_val("event_type"),
        "service_type": slot_val("service_type"),
        "service_style": slot_val("service_style"),
        "venue_name": slot_val("venue"),
        "main_dishes": slot_val("selected_dishes"),
        "appetizers": slot_val("appetizers"),
        "desserts": [desserts] if desserts and str(desserts).lower() not in ("no", "none") else [],
        "menu_notes": slot_val("menu_notes"),
        "addons": addons,
        "dietary_concerns": slot_val("dietary_concerns"),
        "special_requests": slot_val("special_requests"),
        "additional_notes": slot_val("additional_notes"),
    }
    for k, v in mappings.items():
        if v is not None and v != [] and v != "":
            summary_json[k] = v

    # Also update scalar project fields if we have them
    data: dict = {"ai_event_summary": Json(summary_json)}

    guest_count = slot_val("guest_count")
    if guest_count:
        try:
            data["guest_count"] = int(guest_count)
        except (ValueError, TypeError):
            pass

    event_date = slot_val("event_date")
    if event_date:
        try:
            from datetime import datetime
            data["event_date"] = datetime.strptime(str(event_date), "%Y-%m-%d")
        except (ValueError, TypeError):
            pass

    try:
        await client.projects.update(where={"id": project_id}, data=data)
    except Exception as e:
        logger.warning(f"sync_slots_to_project failed: {e}")
