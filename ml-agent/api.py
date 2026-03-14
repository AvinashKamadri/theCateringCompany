"""
FastAPI server wrapping the catering intake agent.
"""
# Code version — bump this to verify server is running latest code
_CODE_VERSION = "v6-2026-03-14"

import uuid
from contextlib import asynccontextmanager

from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from orchestrator import AgentOrchestrator
from tools.pricing import calculate_event_pricing
from database.db_manager import (
    init_db, close_client,
    load_conversation_state, load_messages,
    save_contract, load_contract, load_contracts_by_project,
    load_menu_by_category, load_pricing_packages,
    update_project_summary,
)


orchestrator = AgentOrchestrator()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"\n{'='*50}")
    print(f"  SERVER CODE VERSION: {_CODE_VERSION}")
    print(f"{'='*50}\n")
    await init_db()
    yield
    await close_client()


app = FastAPI(title="The Catering Company - AI Agent", lifespan=lifespan)


@app.get("/version")
async def get_version():
    """Check which code version the server is running."""
    return {"version": _CODE_VERSION}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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


class ChatResponse(BaseModel):
    thread_id: str
    project_id: str
    message: str
    current_node: str
    slots_filled: int
    total_slots: int
    is_complete: bool
    contract_id: str | None = None


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

    result = await orchestrator.process_message(
        thread_id=thread_id,
        message=req.message,
        author_id=req.author_id,
        project_id=req.project_id,
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

        # Build contract body as JSONB
        body = {
            "summary": contract_data.get("summary", ""),
            "slots": slot_vals,
            "contract_text": contract_data.get("contract_text", ""),
        }

        contract_id = await save_contract(
            project_id=project_id,
            client_name=slot_vals.get("name", "Unknown"),
            event_date=slot_vals.get("event_date", ""),
            body=body,
            total_amount=contract_data.get("total_amount"),
        )

        # Update project with event details
        await update_project_summary(
            project_id=project_id,
            event_date=slot_vals.get("event_date"),
            guest_count=guest_count if guest_count > 0 else None,
            summary=f"{slot_vals.get('event_type', '')} for {slot_vals.get('name', '')}",
        )

    return ChatResponse(
        thread_id=thread_id,
        project_id=result.get("project_id", ""),
        message=result["content"],
        current_node=result["current_node"],
        slots_filled=result["slots_filled"],
        total_slots=result["total_slots"],
        is_complete=result["is_complete"],
        contract_id=contract_id,
    )


@app.get("/conversation/{thread_id}")
async def get_conversation(thread_id: str):
    """Get conversation state + all messages for a thread."""
    state = await load_conversation_state(thread_id)
    if not state:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = await load_messages(thread_id)

    # Extract filled slot values
    slots = state.get("slots", {})
    filled_slots = {k: v["value"] for k, v in slots.items() if v.get("filled")}

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
    filled = {k: v["value"] for k, v in slots.items() if v.get("filled")}
    unfilled = [k for k, v in slots.items() if not v.get("filled")]

    return {
        "thread_id": thread_id,
        "current_node": state["current_node"],
        "filled": filled,
        "unfilled": unfilled,
        "slots_filled": len(filled),
        "total_slots": len(slots),
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
