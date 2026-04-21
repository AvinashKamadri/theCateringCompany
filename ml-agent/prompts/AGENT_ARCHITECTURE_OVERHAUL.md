# 🤖 Agentic Architecture Overhaul - Implementation Specification

**Last Updated:** Current Date
**Target Audience:** Backend/ML Engineers

## 1. Executive Summary

The current ML agent operates on a rigid 42-node state machine architecture (`agent/routing.py`, `agent/state.py`). It relies heavily on sequential execution, brittle regex patterns (`_UNSURE_RE`, `_VAGUE_VENUES`), and narrow LLM extraction prompts. While functional for linear "happy paths", it struggles with non-linear conversations, multi-slot updates, and natural language variations (as documented in `fixes_document.md` and `remaining_fixes.md`).

**The Goal:** Transition to a "sleek and simple" **LLM-Orchestrated Agentic Architecture**. This shifts control from hardcoded Python `if/elif` sequences to an intelligent LLM router (`gpt-4o` or `o3-mini`) that dynamically invokes specialized, domain-specific Tools.

**Constraints:** 
- **Strict UX Preservation:** Maintain the existing conversational experience. The architecture natively supports the classic "one-by-one" step-by-step pacing if the user replies minimally.
- **Model Exclusivity:** Exclusive use of OpenAI models (`o3-mini` or `gpt-4o` for reasoning/routing, `gpt-4o-mini` for extraction/responses).
- **Zero Frontend Changes:** The API contract between the Next.js frontend and the FastAPI ML-agent must remain identical. The frontend UI will render the new backend's output without any awareness of the architectural change.

---

## 2. Core Architectural Components

The new architecture is built on four pillars:

### 2.1 The Central Orchestrator (The "Brain")
- **Technology:** `gpt-4o` or `o3-mini` via OpenAI API.
- **Responsibility:** Replaces `NODE_SEQUENCE` and `route_message`. Analyzes the `ConversationState` and recent chat history to determine user intent. 
- **Action:** Decides *which Tool to call next* or generates a conversational fallback. It handles non-linear jumps naturally (e.g., user provides guest count while being asked for a venue).

### 2.2 Structured Extraction (Instructor + Pydantic)
- **Technology:** `gpt-4o-mini` + `Instructor` library + Pydantic `BaseModel`s.
- **Responsibility:** Replaces raw regex and generic `llm_extract` strings.
- **Action:** Forces the LLM to output type-safe JSON (e.g., `date` objects, constrained `Literal` enums). `Instructor` automatically handles validation and re-prompting if the LLM hallucinates schema structures.

### 2.3 Specialized Tools (Domain Logic)
- **Technology:** Python Classes/Functions.
- **Responsibility:** Consolidates the 42 micro-nodes into ~5 robust domains.
- **Action:** Each Tool receives **rich context** (the user's message, the full conversation history, currently filled slots, and external DB data like `menu.json`). It extracts necessary slots via Pydantic models, applies business rules, updates the `ConversationState`, and proposes a natural AI response.

### 2.4 Dynamic Response Generation
- **Technology:** `gpt-4o-mini`.
- **Responsibility:** Replaces static `NODE_PROMPTS`.
- **Action:** Generates human-like, varied responses based on the `SYSTEM_PROMPT` rules, ensuring a casual, friendly tone without repetitive "Got it" phrasing.

---

## 3. Tool Consolidation Map

We will collapse the existing 42 nodes into the following domain-specific Tools:

### 🛠️ 1. BasicInfoTool
**Handles:** Client Identity & Event Fundamentals.
- **Slots Managed:** `name`, `email`, `phone`, `event_type`, `event_date`, `venue`, `guest_count`, `partner_name`, `company_name`, `honoree_name`.
- **Replaces Nodes:** `collect_name`, `collect_event_date`, `collect_venue`, `collect_guest_count`, `select_event_type`, `wedding_message`, etc.
- **Key Logic:** Conditional context (asking for partner name only if event is a wedding), strict future-date validation.

### 🛠️ 2. MenuSelectionTool
**Handles:** Food & Dietary catalog selection.
- **Slots Managed:** `meal_style`, `selected_dishes`, `appetizers`, `appetizer_style`, `desserts`, `menu_notes`.
- **Replaces Nodes:** `present_menu`, `select_dishes`, `ask_appetizers`, `ask_desserts`, `menu_design`, etc.
- **Key Logic:** Scans input against `menu.json` using exact IDs/names. Resolves ordinals ("I'll take option 2"). Handles "Custom menu" escape hatch.

### 🛠️ 3. AddOnsTool
**Handles:** Services, equipment, and logistics.
- **Slots Managed:** `service_type`, `drinks`, `bar_service`, `tableware`, `utensils`, `rentals`, `labor`.
- **Replaces Nodes:** `select_service_type`, `ask_utensils`, `ask_rentals`, `collect_labor`.
- **Key Logic:** Calculates sub-flows (e.g., only ask about labor if `service_type` is "Onsite").

### 🛠️ 4. ModificationTool
**Handles:** All corrections, `@AI` commands, and mid-flow changes.
- **Slots Managed:** Generic access to modify any previously filled slot.
- **Replaces Nodes:** `check_modifications.py` and `_CORRECTION_SIGNALS` regex.
- **Key Logic:** Uses Pydantic to detect `target_slot`, `action` (add/remove/replace), and `new_value`. Capable of clearing dependent slots (e.g., if event changes from Wedding to Corporate, clear `partner_name`).

### 🛠️ 5. FinalizationTool
**Handles:** Wrap-up, summarization, and contract transition.
- **Slots Managed:** `special_requests`, `dietary_concerns`, `additional_notes`, `followup_call`.
- **Replaces Nodes:** `ask_special_requests`, `collect_dietary`, `offer_followup`, `generate_contract`.
- **Key Logic:** Formats the final client-facing summary (short format), calculates pricing, and changes state to `pending_staff_review`.

---

## 4. Solving Existing Fixes via Architecture

This architecture natively resolves the majority of the pending issues outlined in the PDF notes:

| Issue (from Docs) | Why the New Architecture Solves It Natively |
| :--- | :--- |
| **FIX-01: Venue accepts "change date"** | Pydantic `VenueExtraction` schema fails to parse meta-commands as locations. Orchestrator routes to `ModificationTool` instead. |
| **FIX-02: Cannot remove list items** | `ModificationTool` handles all lists generically using structural extraction, rather than hardcoded string matching. |
| **FIX-06: Date Validation stuck loops** | `EventDetailsExtraction(BaseModel)` enforces `datetime.date`. The Tool handles the "must be future date" Python logic gracefully. |
| **FIX-10: Dietary Reassurance** | Dynamic LLM response generation takes the "conflict detected" boolean and generates empathetic, contextual reassurances. |
| **FIX-12: Ordinal/Number selection** | `Instructor` maps inputs like "I'll take the 1st one" directly to the structured JSON array passed in the prompt context. |
| **Flexible Routing (Out of order)** | Orchestrator processes whatever data is given. If user says "150 guests" during name collection, `BasicInfoTool` extracts and fills `guest_count` instantly. |

---

## 5. Implementation Strategy (Phased Approach)

To prevent regressions, the migration should be executed in phases:

### Phase 1: Data Structures & Extraction Layer (Days 1-2)
1. Implement all Pydantic schemas in `agent/models.py` (e.g., `NameExtraction`, `MenuSelection`).
2. Integrate `Instructor` into the environment.
3. Create a standalone test script to verify `Instructor` successfully extracts complex, messy inputs against the new schemas.

### Phase 2: Tool Development (Days 3-5)
1. Scaffold the `agent/tools/` directory.
2. Port logic from existing nodes into the respective Tools (`BasicInfoTool`, `MenuSelectionTool`, etc.).
3. Connect the Tools to use the Pydantic models created in Phase 1 instead of `llm_extract`.

### Phase 3: The Orchestrator (Days 6-7)
1. Implement `agent/orchestrator.py` using `gpt-4o` (or `o3-mini`).
2. Define the `ToolCall` routing schema.
3. Connect the Orchestrator to the newly built Tools.

### Phase 4: State Management & Wiring (Days 8-9)
1. Update `agent/state.py` to remove `NODE_SEQUENCE` and `current_node` dependencies.
2. Wire the Orchestrator into the main API endpoint (`POST /chat` in the backend).
3. Ensure `ConversationState` persists correctly to Prisma/PostgreSQL.

### Phase 5: Testing & Tuning (Days 10-12)
1. Run existing conversation transcripts through the new Orchestrator.
2. Tune the `ORCHESTRATOR_PROMPT` to ensure it transitions smoothly between domains.
3. Verify the final `generate_contract` payload matches the expected ML Engineer schema.

---

## 6. Example Data Flow

**User Turn:** *"Hi, I'm Syed Ale. I need to plan my birthday for next Saturday. Around 40 people."*

1. **Input:** Message enters `Orchestrator`.
2. **Routing:** `o3-mini` analyzes intent. Recognizes basic info. Returns `ToolCall(tool_name="basic_info_tool")`.
3. **Execution:** `BasicInfoTool` invoked with full history and state.
4. **Extraction:** `Instructor` + `gpt-4o-mini` extracts against `EventDetailsExtraction`:
   ```json
   {
     "name": "Syed Ale",
     "event_type": "Birthday",
     "event_date": "2026-04-25", 
     "guest_count": 40
   }
   ```
5. **Validation & State Update:** Tool applies rules, fills slots in `ConversationState` via `fill_slot`.
6. **Response Generation:** Tool detects `venue`, `email`, `phone` are still missing. Suggests response context.
7. **Output:** LLM generates: *"Nice to meet you, Syed! A birthday next Saturday for 40 sounds great. Where's the party happening, and what's the best email to reach you at?"*

**Fallback to "One-by-One" Pacing:**
If the user replies to the above with just *"my backyard"*, the Orchestrator routes back to `BasicInfoTool`. The tool extracts the venue, sees `email` and `phone` are still missing, and generates: *"Got it, your backyard! And what's the best email and phone number to reach you?"* This ensures the classic, methodical step-by-step experience is perfectly preserved when users reply minimally.

---

## 7. Speed & Accuracy Guarantees

Agentic workflows can introduce latency or hallucination if designed poorly. This architecture enforces strict performance and reliability guardrails:

### ⚡ Speed (Target: < 1.5s TTFT)
- **Model Tiering:** `gpt-4o` (or `o3-mini`) is restricted to the low-token Orchestration/Routing step (fast execution). Heavy text generation and extraction are offloaded to the blazing-fast `gpt-4o-mini`.
- **Prompt Caching:** OpenAI native prompt caching will automatically hit on the `SYSTEM_PROMPT` and injected `menu.json` catalogs, drastically reducing latency on multi-turn conversations.
- **Async Parallelism:** DB lookups, pricing calculations, and LLM text generation will be executed concurrently using `asyncio.gather` wherever possible.

### 🎯 Accuracy (Target: 0% Hallucination)
- **Strict Structured Outputs:** `Instructor` + `Pydantic` ensures 100% schema compliance. The LLM physically cannot return an invalid data type (e.g., a string instead of an integer for `guest_count`).
- **Menu Grounding:** `MenuSelectionTool` strictly maps user inputs to exact `menu.json` IDs. It uses semantic matching against the real database, preventing the agent from inventing or modifying menu items.
- **State Validation:** Custom Python validation logic (e.g., "event date must be in the future") executes immediately after LLM extraction, maintaining strict business rules.

---

## 8. Backend & Frontend Schema Compliance (Zero-Bug Policy)

To ensure **zero frontend UI changes** and **zero Prisma database migrations**, the new architecture must strictly adhere to the existing data contracts.

### 8.1 Strict State Dictionary Shape
The Next.js frontend relies on the exact nested JSON structure of `ConversationState` to render UI cards and progress. 
- ❌ **DO NOT DO THIS:** `state["slots"]["event_date"] = "2026-04-30"` (This will crash the frontend).
- ✅ **DO THIS:** `fill_slot(state["slots"], "event_date", "2026-04-30")`. 
All Tools must use the `fill_slot` utility from `agent/state.py` to ensure the `value`, `filled` boolean, and `modification_history` arrays are perfectly maintained for the Next.js state manager.

### 8.2 Database Parity & Pricing Engine (The Post-Mortem Rule)
As learned in the `ML_AGENT_MIGRATION_POSTMORTEM.md`, the agent cannot bypass the real database logic.
- **Menu Selection:** Even with Pydantic extraction, the `MenuSelectionTool` MUST pass the extracted items through the existing `_resolve_to_db_items()` logic to ensure exact primary key matching with the PostgreSQL `menu_items` table.
- **Pricing:** The `FinalizationTool` MUST invoke `calculate_event_pricing()` from `tools/pricing.py` to generate the exact financial breakdown (subtotal, tax, gratuity, deposit) expected by the `POST /ml/contracts/generate` NestJS endpoint.

### 8.3 Safe API Fallbacks (No HTTP 500s)
Agentic workflows introduce dynamic API calls. To prevent frontend crashes during LLM latency or OpenAI outages:
- The Orchestrator must be wrapped in a global `try/except` block at the FastAPI endpoint level.
- If `gpt-4o` or `Instructor` fails or times out after 3 retries, the agent must return a graceful JSON payload: 
  ```json
  {
    "messages": [{"type": "ai", "content": "I'm having a little trouble connecting right now. Could you repeat that?"}],
    "state": { ...unchanged state... }
  }
  ```