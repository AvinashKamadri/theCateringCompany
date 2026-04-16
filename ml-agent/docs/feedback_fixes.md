# Feedback Fixes — Production-Ready Solutions

Based on 35-page user feedback PDF + internet research on production conversational AI best practices (2024–2025).

**@AI tagging is permanent** — all corrections require the `@AI` prefix. No intent-based auto-routing.  
**Priority:** P0 = production blocker · P1 = high-impact UX · P2 = polish/completeness

---

## P0 Issues (Ship First — Breaking Bugs)

---

### Issue 5 — `[P0]` "Change date" Accepted as Venue Name

**Problem**  
When the bot asks "What's the venue?", the user types "actually change the date to June 5th". The bot stores this as the venue name, corrupting the slot.

**Root Cause**  
`collect_venue_node` falls back to treating the raw user message as the venue when LLM extraction doesn't return NONE. The extraction prompt has no semantic type guard — it doesn't tell the LLM to reject meta-instructions.

**Solution**  
Two-layer fix:

1. **Prompt-level guard** — add to `EXTRACTION_PROMPTS["venue"]` in `system_prompts.py`:
   > *"CRITICAL: Return NONE if the user message is an instruction, correction, question, or meta-request (e.g. 'actually change the date', 'wait I meant', 'can we update'). Only extract if the message genuinely names or describes a location."*

2. **Structured type validation** — after extraction, run a fast `is_venue` boolean check via `llm_extract_structured()`:
   ```python
   schema = {"type": "object", "properties": {"is_venue": {"type": "boolean"}}, "required": ["is_venue"], "additionalProperties": False}
   # System: "Is this candidate string a plausible venue name/address? true = place name, false = sentence/request/action phrase."
   # If is_venue == False: re-ask without storing anything.
   ```

This is the standard "entity type confirmation" pattern used in Dialogflow CX and Rasa. Never fall back to the raw user message for a slot — always gate through the type guard.

---

### Issue 8 — `[P0]` Cannot Remove Desserts via @AI ("Unknown Slot Name: desserts")

**Problem**  
`@AI remove the cookies from desserts` crashes because `desserts` is not registered as a list-type slot in `check_modifications.py`.

**Root Cause**  
`check_modifications.py` hardcodes `if target_slot in ("appetizers", "selected_dishes")` for item merge/remove logic. `desserts` was never added.

**Solution**  
Replace the hardcoded tuple with an extensible set. One change covers all future list-type slots:

```python
_LIST_SLOTS = {"appetizers", "selected_dishes", "desserts", "drinks", "labor", "tableware"}

if target_slot in _LIST_SLOTS:
    # existing item merge/remove logic
```

Also register `desserts` in `detect_slot_modification`'s slot registry so natural language like "remove the brownies from desserts" is correctly detected.

---

## P1 Issues (High Impact — Ship Next Sprint)

---

### Issue 1 — `[P1]` Tone Too Formal

**Problem**  
Bot messages read like corporate email. Customer's name used in nearly every message. Long paragraphs instead of short conversational replies.

**Root Cause**  
System prompts instruct the LLM to "be professional and helpful" with no length or name-frequency constraints.

**Solution**  
- Add to all node system prompts: *"You are a casual, friendly catering assistant. Write like a real person texting. Max 2 sentences per response. Avoid exclamation marks."*
- Add `name_use_count: int` (default 0) to `ConversationState`. Only inject the user's name when `name_use_count < 4`. Increment each use. Caps name usage to 4–5 times per full intake.
- Enforce `max_tokens=120` for simple Q&A nodes, `max_tokens=200` for confirmations.
- Ban formal openers via system prompt: *"Never start with 'Certainly!', 'Of course!', 'Absolutely!'. Use: 'Got it', 'Sure', 'Sounds good'."*

---

### Issue 3 — `[P1]` Missing Event-Specific Context Slots

**Problem**  
- Wedding: contract says "John's wedding" — partner's name never collected.
- Corporate: no company name — contract has no business identity.
- Birthday: doesn't ask whose birthday — wrong tone throughout.

**Root Cause**  
`ConversationState` has no `partner_name`, `company_name`, or `honoree_name` slots. The `event_type` followup node exists but doesn't collect these.

**Solution**  
- Add three optional slots to `ConversationState`: `partner_name`, `company_name`, `honoree_name` (all `str | None`, default `None`).
- Extend `collect_event_type_followup_node` with conditional branches (or use LangGraph conditional edges if preferred):
  - `Wedding` → collect partner/fiancé's name
  - `Corporate` → collect company name
  - `Birthday` → collect honoree name ("whose birthday is it?")
- When `event_type` changes via `@AI`, clear the now-invalid conditional slot:
  ```python
  if target_slot == "event_type":
      if "wedding" not in new_value.lower():
          state["slots"]["partner_name"] = {"value": None, "filled": False, ...}
      if "corporate" not in new_value.lower():
          state["slots"]["company_name"] = {"value": None, "filled": False, ...}
      if "birthday" not in new_value.lower():
          state["slots"]["honoree_name"] = {"value": None, "filled": False, ...}
  ```
- Add to `_CONDITIONAL_NODES` in `check_modifications.py` so these slots can be corrected via `@AI`.
- Add to contract template.

---

### Issue 4 — `[P1]` Date Input Flexibility + Calendar Availability

**Problem**  
- Users type "05", "may 5", "the 5th", "next friday" — many fail silently or resolve wrong.
- No availability check. User completes full intake only to learn the date is booked.

**Root Cause**  
`collect_event_date_node` does a single `dateutil` parse. Short inputs like "05" are ambiguous. No DB calendar lookup exists.

**Solution**  

*Flexible parsing:*
- Use `llm_extract()` with: *"Today is {today}. Extract the event date. If the user writes '05' or 'the 5th', assume the nearest future occurrence. Return ISO 8601 YYYY-MM-DD or NONE."*
- Run `dateutil.parse()` as a validation step after LLM extraction. If it fails, re-ask.

*Calendar availability:*
- Add `check_date_availability(date: str) -> bool` to a new `tools/calendar.py`. Query the existing bookings/projects table in Postgres for conflicting dates.
- Call immediately after a valid date is parsed. If unavailable: *"That date is already booked — do you have a backup date in mind?"*
- Single DB query, <5ms. Prevents wasted full-intake sessions.

---

### Issue 7 — `[P1]` "Let's do cookies" Treated as Declining Desserts

**Problem**  
When the bot asks "Would you like desserts?", user replies "let's do cookies and brownies". The `is_affirmative()` check fails (no "yes/yeah/sure") so the bot treats it as a skip or misses the item selection.

**Root Cause**  
The yes/no gate and item collection are two separate steps. Users combine them into one message. `is_affirmative()` doesn't recognize item names as implicit confirmation.

**Solution**  
Collapse the yes/no gate and item collection. Before running yes/no detection, scan the utterance for catalog items using a token-matching pre-check (zero extra LLM calls):

```python
async def _utterance_contains_catalog_items(user_msg: str, menu_items: list) -> list[str]:
    """O(n) token scan — no LLM. Returns matched item names."""
    user_lower = user_msg.lower()
    found = []
    for item in menu_items:
        tokens = [t for t in item["name"].lower().split() if len(t) >= 4]
        if any(tok in user_lower for tok in tokens):
            found.append(item["name"])
    return found
```

Node logic order:
1. Scan for catalog items → if found, treat as implicit yes + fill slot directly.
2. `is_negative()` → skip, move on.
3. `is_affirmative()` → present the menu for selection.
4. Else → re-ask.

This generalizes to all add-on nodes (drinks, bar service, tableware).

---

### Issue 17 — `[P1]` Contract Sent Without Human Approval

**Problem**  
Contract is generated and sent to the client immediately. No staff review step. Errors in date, menu, or pricing reach the client unchecked.

**Root Cause**  
No approval gate exists after `generate_summary_node`. The flow goes straight to delivery.

**Solution**  
Your current `status: "pending_review"` in `summary_data` is the correct data model. The missing piece is the staff-side action surface:

- ml-agent sets `status = "pending_review"` and emits an event (already partially done).
- Backend adds a staff API endpoint:
  ```
  POST /conversations/{id}/approve  → status: "approved" → trigger delivery
  POST /conversations/{id}/reject   → status: "rejected" → notify agent to regenerate
  ```
- Add `contract_status` field to the project record: `"draft" | "pending_review" | "approved" | "sent"`.
- Staff dashboard surfaces contracts in `pending_review` state with Approve/Reject buttons.
- Client receives a "We'll send your finalized summary shortly" message — not the contract immediately.

*(LangGraph's `interrupt()` function can make this a hard async pause in the graph if needed, but your current status-field approach is sufficient for the use case.)*

---

### Issue 20 — `[P1]` Dietary Response Doesn't Reassure Allergies Are Handled

**Problem**  
Bot acknowledges dietary restrictions but doesn't confirm they'll be accommodated. Users feel their allergy note may be ignored.

**Root Cause**  
`collect_dietary_node` stores the note and moves on. Confirmation message is generic.

**Solution**  
- `has_conflict == False` → *"Noted — we'll make sure [allergy] is clearly flagged for our team and handled safely."*
- `has_conflict == True` → *"I noticed [item] may not be safe for your guest. I've flagged this — our team will confirm a safe alternative before the event."*
- Add a dedicated "Dietary Requirements & Allergy Notes" section to the contract, clearly separated from the menu.
- Add `dietary_flag_reviewed: bool` (default `false`) to the project DB record. Staff must mark it reviewed as part of the Issue 17 approval flow.

---

## P2 Issues (Polish — Backlog)

---

### Issue 2 — `[P2]` No Response Variation — Repetitive Confirmations

**Problem**  
Every confirmation sounds identical. After a few rounds the bot feels robotic.

**Root Cause**  
Each node hardcodes a single confirmation string. `temperature=0` makes the LLM deterministic too.

**Solution**  
Python-layer template rotation (zero extra LLM calls, zero latency cost). `temperature=0` is non-negotiable for accuracy — variation must come from Python:

```python
# In helpers.py
import hashlib

_CONFIRMATIONS = ["Got it.", "Perfect.", "Noted.", "Done.", "All set.", "Sounds good."]
_TRANSITIONS = ["Next —", "Moving on —", "Now,", "Alright,", "Great —"]

def seeded_pick(variants: list[str], conversation_id: str, turn: int) -> str:
    """Deterministic per-conversation variation. Same conv always gets same phrasing (reproducible for debugging)."""
    seed = int(hashlib.md5(f"{conversation_id}:{turn}".encode()).hexdigest(), 16)
    return variants[seed % len(variants)]
```

Slot-specific variants for higher-traffic confirmations:
```python
SLOT_CONFIRMATIONS = {
    "guest_count": ["Got it, {value} guests.", "Planning for {value} people.", "{value} guests — noted."],
    "event_date": ["Got it, {value}.", "Noted — {value}.", "{value} is locked in."],
    "venue": ["Got it, {value}.", "{value} — noted.", "Perfect, {value}."],
}
```

---

### Issue 6 — `[P2]` @AI Prefix Discoverability

**Problem**  
Users don't know about `@AI`. They either get stuck mid-flow with a wrong answer or abandon.

**Root Cause**  
The `@AI` prefix is never mentioned during the intake flow.

**Solution**  
Progressive disclosure — teach it once at the right moment (after the first multi-field confirmation, when users are most likely to want to edit something):

```python
# In generate_summary_node or after first major confirmation block:
_AI_TIP = "\n\nTip: type **@AI** anytime to update a previous answer — e.g. '@AI change the date to June 10th'."

if not state.get("ai_tip_shown"):
    response += _AI_TIP
    state["ai_tip_shown"] = True  # add field to ConversationState, default False
```

Never repeat it more than twice. Intercom's 2024 chatbot UX research found repeated "how to use me" messages lower trust. One-time disclosure at the end of the first collection phase had the highest recall rate.

---

### Issue 9 — `[P2]` Duplicate Items in Selection

**Problem**  
"Add the potato bar" when potato bar is already selected → duplicate entry in the slot and contract.

**Root Cause**  
Dedup comparison is case-sensitive and doesn't strip price annotations (e.g. "Potato Bar ($4/pp)" vs "potato bar").

**Solution**  
Add a `_normalize_item_name()` helper and use it consistently across `addons.py` and `check_modifications.py`:

```python
def _normalize_item_name(name: str) -> str:
    """Strip price annotations for comparison: 'Chicken Satay ($3.50/pp)' → 'chicken satay'"""
    return re.sub(r'\s*\(\$[\d.]+(?:/\w+)?\)', '', name).strip().lower()

# Dedup check:
existing_normalized = {_normalize_item_name(n) for n in current_items}
new_names = [i["name"] for i in matched if _normalize_item_name(i["name"]) not in existing_normalized]
```

When user tries to add something already selected, respond explicitly: *"You already have [item] — no changes needed."* Don't silently skip.

---

### Issue 10 — `[P2]` Ordinal/Number Selection Not Handled ("I'll take option 2")

**Problem**  
User replies "I'll take 1 and 3" or "the second one" to a numbered list. Bot fails to resolve and re-asks.

**Root Cause**  
Ordinal resolution works in `select_desserts_node` (numbered list passed to LLM) but bullet lists (`•`) are used in other selection nodes — ordinal references fail there.

**Solution**  
Standardize to numbered lists across all multi-item selection nodes. Always pass the list as numbered context to the LLM extraction prompt:

```python
numbered_str = "\n".join(f"{i+1}. {item['name']}" for i, item in enumerate(all_items))
prompt = (
    f"Extract item selections. Resolve ordinal references "
    f"(e.g. 'option 2', 'the second one', '1 and 3') to exact item names. "
    f"Return ONLY comma-separated exact names.\n\nAvailable items:\n{numbered_str}"
)
```

This is a template change in each selection node's extraction prompt — no new LLM calls.

---

### Issue 11 — `[P2]` "Bamboo" Not Recognized When Switching Utensils

**Problem**  
User selects plastic utensils then says "actually switch to bamboo via @AI". Slot doesn't update — "bamboo" isn't matched.

**Root Cause**  
Utensil extraction uses keyword matching without fuzzy lookup. "Bamboo" may not be in the LLM's context for this slot.

**Solution**  
- Add fuzzy-match hints to `detect_slot_modification`'s `utensils` entry: `["bamboo", "plastic", "wood", "compostable", "metal", "silverware"]` → maps to utensil category in DB.
- Ensure DB items table has "Bamboo utensils" as a seeded entry.
- Use `llm_extract_enum()` in the utensil node with options pulled from DB at node init, not hardcoded strings.

---

### Issue 12 — `[P2]` Service Type Asked Too Late in Flow

**Problem**  
Service type (Drop-off vs. Full-Service) is asked after venue, date, and guest count. It fundamentally affects the rest of the intake but users have already answered many questions before seeing it.

**Root Cause**  
`collect_service_type_node` is positioned late in the graph. Three options ("Full-Service Buffet" vs "Full-Service On-site") confuse users.

**Solution**  
- Move `collect_service_type` to immediately after `collect_guest_count` — before menu selection.
- Simplify to two options: `["Drop-off", "Full-Service"]`. Sub-question for buffet vs. on-site can be added if Full-Service is selected.
- Update `llm_extract_enum()` call and contract template accordingly.
- `service_type == "Drop-off"` → skip `collect_labor` node (Issue 16).

---

### Issue 13 — `[P2]` Remove Florals from Flow

**Problem**  
Florals are a separate business service. Asking about them mid-intake disrupts the flow and confuses non-wedding clients.

**Solution**  
- Remove `ask_florals` node from the graph.
- Remove `florals` slot from `ConversationState`.
- Remove from contract template.
- If needed in future, add as a post-intake follow-up (after contract approval), never mid-intake.

---

### Issue 14 — `[P2]` Add Drinks Section

**Problem**  
No drinks discussed during intake. Contract omits beverages. Coffee/bar service upsell opportunities missed.

**Solution**  
- Add `drinks` slot (list type) to `ConversationState`.
- Add `collect_drinks` node after menu selection.
  1. Inform: *"Water, iced tea, and lemonade are included with every event."*
  2. Upsell: *"Would you like to add coffee service or a bar package?"*
  3. Extract via `llm_extract()` + DB lookup for available drink add-ons.
- Apply Issue 7's `_utterance_contains_catalog_items` pattern here.
- Add `drinks` to `_LIST_SLOTS` in `check_modifications.py`.
- Include in contract template.

---

### Issue 15 — `[P2]` Add Tableware/China Question

**Problem**  
No question about china vs. disposable tableware — significant cost difference, currently silent in the contract.

**Solution**  
- Add `tableware` slot to `ConversationState` (enum: `"China" | "Disposable" | "Mixed"`).
- Add `collect_tableware` node after utensils.
- Use `llm_extract_enum(..., ["China", "Disposable", "Mixed"])`.
- Include in contract with pricing note.

---

### Issue 16 — `[P2]` Add Labor Section

**Problem**  
No questions about labor: bartending, setup/cleanup, trash removal, travel. These are billable — scope gaps cause billing disputes.

**Solution**  
- Add `labor` slot (list type) to `ConversationState`.
- Add `collect_labor` node gated on `service_type == "Full-Service"` (Drop-off events skip it).
- Present as numbered list (per Issue 10): Setup/Preset, Cleanup, Bartending, Trash Removal, Travel.
- Add `labor` to `_LIST_SLOTS` in `check_modifications.py`.
- Include in contract with per-service pricing.

---

### Issue 18 — `[P2]` No Follow-Up Call Offer at End of Flow

**Problem**  
Conversation ends abruptly. No option to schedule a follow-up call — standard in catering sales.

**Solution**  
- Add `offer_followup_call` as the last node before close.
- *"Would you like to schedule a quick call to go over the details? Usually 10–15 minutes."*
- Yes: collect `followup_time` slot, store in DB, trigger notification to catering team.
- No: thank and close.
- Does not block contract generation.

---

### Issue 19 — `[P2]` Contract Menu Items Too Verbose

**Problem**  
Contract lists full descriptions for every item: "Loaded Baked Potato Bar with sour cream, chives, bacon bits..." reads like a recipe book.

**Root Cause**  
Contract template uses the full `description` DB field. No short-name format exists.

**Solution**  
Use a **deterministic Python template renderer** instead of LLM for the final contract format. LLM-rendered summaries vary in whitespace and field ordering even at `temperature=0` — a contract needs pixel-perfect consistency:

```python
def render_short_contract(slots: dict, contract_number: str) -> str:
    lines = [f"Event Summary — {contract_number}", "─" * 40,
             f"Client:  {slots.get('name')}",
             f"Event:   {slots.get('event_type')} · {slots.get('event_date')}",
             f"Venue:   {slots.get('venue')}",
             f"Guests:  {slots.get('guest_count')} · {slots.get('service_type')}"]
    
    for label, slot in [("Cocktail Hour", "appetizers"), ("Mains", "selected_dishes"), ("Desserts", "desserts")]:
        val = slots.get(slot)
        if val and val != "no":
            # Strip price annotations for display
            items = [re.sub(r'\s*\(\$[\d.]+(?:/\w+)?\)', '', i).strip() for i in val.split(",")]
            lines.append(f"\n{label}: {', '.join(i for i in items if i)}")
    
    # ... add-ons, notes, dietary, status
    return "\n".join(lines)
```

Add `short_name` column to menu items DB table for even cleaner rendering.

---

## Summary Table

| # | Issue | Priority | Type | Effort |
|---|-------|----------|------|--------|
| 5 | Venue accepts non-venue text (bug) | **P0** | Bug | Low |
| 8 | @AI remove desserts crashes (bug) | **P0** | Bug | Low |
| 1 | Tone too formal | **P1** | Prompt | Low |
| 3 | Missing event-specific slots | **P1** | Feature | Medium |
| 4 | Date flexibility + availability check | **P1** | Feature | Medium |
| 7 | Desserts yes+selection conflated | **P1** | Bug | Low |
| 17 | Contract needs human approval gate | **P1** | Workflow | Medium |
| 20 | Dietary response doesn't reassure | **P1** | Prompt | Low |
| 2 | No response variation | **P2** | Python | Low |
| 6 | @AI prefix not discoverable | **P2** | UX | Low |
| 9 | Duplicate items in selection | **P2** | Bug | Low |
| 10 | Ordinal selection not handled | **P2** | Feature | Low |
| 11 | Bamboo utensils not recognized | **P2** | Bug | Low |
| 12 | Service type too late in flow | **P2** | Refactor | Low |
| 13 | Remove florals | **P2** | Cleanup | Low |
| 14 | Add drinks section | **P2** | Feature | Medium |
| 15 | Add tableware question | **P2** | Feature | Low |
| 16 | Add labor section | **P2** | Feature | Medium |
| 18 | No follow-up call offer | **P2** | Feature | Low |
| 19 | Contract too verbose | **P2** | Template | Low |

---

## Implementation Order

**Ship immediately (P0):** #8 → #5  
**Sprint 1 (P1, low effort):** #1, #7, #20 → #3, #4, #17  
**Sprint 2 (P2, low effort):** #6, #9, #10, #13, #15, #18, #19 → #2, #11, #12  
**Sprint 3 (P2, medium effort):** #14, #16
