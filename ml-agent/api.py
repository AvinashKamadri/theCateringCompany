"""
FastAPI server wrapping the catering intake agent.
"""
# Code version — bump this to verify server is running latest code
_CODE_VERSION = "v7-2026-04-20"

import os
import uuid
import logging
from contextlib import asynccontextmanager

from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from orchestrator import AgentOrchestrator
from agent.instructor_client import warmup as warmup_instructor
from agent.logging_config import configure_logging
from agent.trace_context import trace_scope

configure_logging()
from tools.pricing import calculate_event_pricing
from database.db_manager import (
    init_db, close_client,
    load_conversation_state, load_messages,
    save_contract, load_contract, load_contracts_by_project,
    load_menu_by_category, load_pricing_packages,
    update_project_summary,
    sync_slots_to_project,
)


orchestrator = AgentOrchestrator()
logger = logging.getLogger(__name__)


def _filled_slot_views(slots: dict | None) -> tuple[dict[str, object], dict[str, object]]:
    public: dict[str, object] = {}
    internal: dict[str, object] = {}
    for key, raw in (slots or {}).items():
        if not isinstance(raw, dict) or not raw.get("filled"):
            continue
        target = internal if str(key).startswith("__") else public
        target[str(key)] = raw.get("value")
    return public, internal


def _summarize_slots_for_log(values: dict[str, object], *, max_value_chars: int = 90, max_list_items: int = 4) -> str:
    """Make slot dicts readable in logs (truncate + compact list-like strings)."""
    import re as _re

    def _split_top_level_commas(text: str) -> list[str]:
        return [p.strip() for p in _re.split(r",(?![^(]*\))", text) if p.strip()]

    def _summarize_value(v: object) -> str:
        if v is None:
            return "None"
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, (int, float)):
            return str(v)

        s = str(v).strip()
        if not s:
            return '""'

        # Compact comma-separated menu/rental strings: show count + first few.
        if "," in s and len(s) > max_value_chars:
            parts = _split_top_level_commas(s)
            if len(parts) >= 5:
                head = ", ".join(parts[:max_list_items])
                return f"[{len(parts)} items] {head}, …"

        if len(s) > max_value_chars:
            return s[: max_value_chars - 1] + "…"
        return s

    items = []
    for k in sorted(values.keys()):
        items.append(f"{k}={_summarize_value(values[k])}")
    return "{" + ", ".join(items) + "}"


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"\n{'='*50}")
    print(f"  SERVER CODE VERSION: {_CODE_VERSION}")
    print(f"{'='*50}\n")
    await init_db()
    try:
        await warmup_instructor()
    except Exception as e:
        print(f"[WARN] Instructor warmup failed: {e}")
    yield
    await close_client()


app = FastAPI(title="The Catering Company - AI Agent", lifespan=lifespan)


@app.get("/version")
async def get_version():
    """Check which code version the server is running."""
    return {"version": _CODE_VERSION}

_cors_origins_env = os.getenv("CORS_ORIGIN", "").strip()
_cors_origins = [o.strip() for o in _cors_origins_env.split(",") if o.strip()] or [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    thread_id: str | None = None
    message: str
    author_id: str = "user"
    project_id: str | None = None
    user_id: str | None = None  # real authenticated user UUID


class ChatResponse(BaseModel):
    thread_id: str
    project_id: str
    message: str
    current_node: str
    slots_filled: int
    total_slots: int
    is_complete: bool
    contract_id: str | None = None
    input_hint: dict | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def serve_test_chat():
    """Serve the test chat UI."""
    html_path = Path(__file__).parent / "test-chat.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Send a message to the agent. Returns thread_id to continue conversation."""
    thread_id = req.thread_id or str(uuid.uuid4())

    # Resolve the real user UUID: prefer explicit user_id, fall back to author_id if it looks like a UUID
    import re as _re
    _uuid_pattern = _re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', _re.I)
    resolved_user_id = req.user_id or (req.author_id if _uuid_pattern.match(req.author_id) else None)

    with trace_scope(
        thread_id=thread_id,
        project_id=req.project_id,
        user_id=resolved_user_id,
        author_id=req.author_id,
    ):
        existing_state = await load_conversation_state(thread_id)
        before_public, before_internal = _filled_slot_views(existing_state.get("slots") if existing_state else None)
        logger.info(
            "chat_request thread=%s project=%s current_node=%s message=%r public_slots=%s internal_slots=%s",
            thread_id,
            req.project_id,
            existing_state.get("current_node") if existing_state else None,
            req.message,
            _summarize_slots_for_log(before_public),
            _summarize_slots_for_log(before_internal),
        )

        result = await orchestrator.process_message(
            thread_id=thread_id,
            message=req.message,
            author_id=req.author_id,
            project_id=req.project_id,
            user_id=resolved_user_id,
            preloaded_state=existing_state,
        )

    contract_id = None

    # Auto-save contract to DB when conversation completes
    contract_data = result.get("contract_data")
    if result["is_complete"] and contract_data:
        slots = result.get("slots", {})
        # Extract raw slot values
        slot_vals = {k: v.get("value") for k, v in slots.items() if v.get("filled")}

        try:
            guest_count = int(slot_vals.get("guest_count", 0))
        except (ValueError, TypeError):
            guest_count = 0

        project_id = result.get("project_id", "")

        # `contract_data` here is the pricing breakdown from FinalizationTool.
        body = {
            "slots": slot_vals,
            "pricing": contract_data,
        }
        total_amount = contract_data.get("grand_total") or contract_data.get("total_amount")

        contract_id = await save_contract(
            project_id=project_id,
            client_name=slot_vals.get("name", "Unknown"),
            event_date=slot_vals.get("event_date", ""),
            body=body,
            total_amount=total_amount,
        )

        # Update project with event details
        await update_project_summary(
            project_id=project_id,
            event_date=slot_vals.get("event_date"),
            guest_count=guest_count if guest_count > 0 else None,
            summary=f"{slot_vals.get('event_type', '')} for {slot_vals.get('name', '')}",
        )

    # Always sync current slot state to project so the project view stays live
    _project_id = result.get("project_id", "")
    _slots = result.get("slots", {})
    after_public, after_internal = _filled_slot_views(_slots)
    logger.info(
        "chat_response thread=%s project=%s current_node=%s slots_filled=%s is_complete=%s public_slots=%s internal_slots=%s",
        thread_id,
        _project_id,
        result.get("current_node"),
        result.get("slots_filled"),
        result.get("is_complete"),
        _summarize_slots_for_log(after_public),
        _summarize_slots_for_log(after_internal),
    )
    if _project_id and _slots:
        try:
            await sync_slots_to_project(_project_id, _slots, thread_id)
        except Exception as _e:
            pass  # non-fatal

    return ChatResponse(
        thread_id=thread_id,
        project_id=result.get("project_id", ""),
        message=result["content"],
        current_node=result["current_node"],
        slots_filled=result["slots_filled"],
        total_slots=result["total_slots"],
        is_complete=result["is_complete"],
        contract_id=contract_id,
        input_hint=result.get("input_hint"),
    )



@app.get("/conversation/{thread_id}")
async def get_conversation(thread_id: str):
    """Get conversation state + all messages for a thread."""
    state = await load_conversation_state(thread_id)
    if not state:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = await load_messages(thread_id)

    # Extract filled slot values (exclude internal bookkeeping keys prefixed with __)
    slots = state.get("slots", {})
    filled_slots = {k: v["value"] for k, v in slots.items() if v.get("filled") and not k.startswith("__")}
    _public, _internal = _filled_slot_views(slots)
    logger.info(
        "conversation_fetch thread=%s current_node=%s public_slots=%s internal_slots=%s",
        thread_id,
        state["current_node"],
        _summarize_slots_for_log(_public),
        _summarize_slots_for_log(_internal),
    )

    return {
        "thread_id": thread_id,
        "project_id": state.get("project_id"),
        "current_node": state["current_node"],
        "is_completed": state["is_completed"],
        "slots_filled": len(filled_slots),
        "slots": filled_slots,
        "messages": messages,
    }


@app.get("/conversation/{thread_id}/slots")
async def get_slots(thread_id: str):
    """Get current slot values for a conversation."""
    state = await load_conversation_state(thread_id)
    if not state:
        raise HTTPException(status_code=404, detail="Conversation not found")

    slots = state.get("slots", {})
    public_slots = {k: v for k, v in slots.items() if not k.startswith("__")}
    filled = {k: v["value"] for k, v in public_slots.items() if v.get("filled")}
    unfilled = [k for k, v in public_slots.items() if not v.get("filled")]
    _public, _internal = _filled_slot_views(slots)
    logger.info(
        "slot_fetch thread=%s current_node=%s public_slots=%s internal_slots=%s",
        thread_id,
        state["current_node"],
        _summarize_slots_for_log(_public),
        _summarize_slots_for_log(_internal),
    )

    return {
        "thread_id": thread_id,
        "current_node": state["current_node"],
        "filled": filled,
        "unfilled": unfilled,
        "slots_filled": len(filled),
        "total_slots": len(public_slots),
    }


@app.get("/contract/{contract_id}")
async def get_contract(contract_id: str):
    """Get a contract by ID."""
    contract = await load_contract(contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    return contract


@app.get("/project/{project_id}/contracts")
async def get_project_contracts(project_id: str):
    """Get all contracts for a project."""
    contracts = await load_contracts_by_project(project_id)
    return {"project_id": project_id, "contracts": contracts}


@app.get("/menu")
async def get_menu():
    """Get the full menu grouped by category."""
    menu = await load_menu_by_category()
    return {"categories": menu}


@app.get("/pricing")
async def get_pricing():
    """Get pricing packages."""
    packages = await load_pricing_packages()
    return {"packages": packages}


class PricingRequest(BaseModel):
    guest_count: int
    event_type: str = ""
    service_type: str = ""
    selected_dishes: str | None = None
    appetizers: str | None = None
    desserts: str | None = None
    utensils: str | None = None
    rentals: str | None = None


@app.post("/pricing/calculate")
async def calculate_pricing(req: PricingRequest):
    """Calculate pricing breakdown for given selections."""
    try:
        result = await calculate_event_pricing(
            guest_count=req.guest_count,
            event_type=req.event_type,
            service_type=req.service_type,
            selected_dishes=req.selected_dishes,
            appetizers=req.appetizers,
            desserts=req.desserts,
            utensils=req.utensils,
            rentals=req.rentals,
        )
        return result
    except Exception as e:
        print(f"[PRICING ERROR] {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "ok"}
