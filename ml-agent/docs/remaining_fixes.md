# Remaining Fixes — Post Session 1

Items not yet implemented from the client feedback PDF.

---

## P1 — Ship Next

### Collect email / phone number
**PDF ref:** p1  
**Problem:** PDF lists email/phone as required client info. We only collect name — no email or phone.  
**Solution:** Add `email` and `phone` slots. Add a node after `collect_name` (before event type): *"What's the best email and phone number to reach you?"* Extract both in one message via `llm_extract_structured`.  
**Files:** `state.py`, `basic_info.py`, `system_prompts.py`, `__init__.py`, `routing.py`

### FIX-09 · Human approval gate before contract is sent
**PDF ref:** p27  
**Problem:** Contract is generated and shown to the client immediately. No staff review.  
**Solution:** After `generate_contract_node`, set `status = "pending_staff_review"`. Bot tells client: *"We've got everything — our team will review and send your finalized summary within 24–48 hours."* Staff-side API endpoint (`POST /conversations/{id}/approve`) is a backend concern.  
**Files:** `ml-agent/agent/nodes/final.py`

### FIX-10 · Dietary reassurance wording
**PDF ref:** p26  
**Problem:** Bot notes allergy but doesn't confirm it will be handled.  
**Solution:** When dietary concern is noted, respond: *"Noted — those allergies are fully covered. We'll make sure every guest has a safe, well-thought-out option."* When conflict detected: *"I've flagged the conflict — our team will sort a safe alternative before the event."*  
**Files:** `ml-agent/prompts/system_prompts.py` (NODE_PROMPTS["collect_dietary"])

---

## P2 — Polish / New Sections

### Passed or station question (cocktail hour)
**PDF ref:** p1, p9  
**Problem:** PDF says to ask if the client wants appetizers passed or served at a station. Currently not asked.  
**Solution:** After appetizer selection is confirmed, ask: *"Do you want these passed around or set up at a station?"* Store in a `service_style_appetizers` slot or append to `menu_notes`. Only applies when cocktail hour is selected.  
**Files:** `state.py`, `addons.py` or `menu.py`, `system_prompts.py`

### No venue yet — skip gracefully
**PDF ref:** p6  
**Problem:** If user says "I don't have a venue yet" or "not sure", the bot re-asks. PDF says to move on gracefully.  
**Solution:** In `collect_venue_node`, detect "no venue", "not sure", "don't know yet", "TBD" → fill slot with "TBD", respond: *"No problem — we can circle back to that. How many guests are you thinking?"* and advance to guest count.  
**Files:** `basic_info.py`, `system_prompts.py` (venue extraction prompt already accepts "TBD")

### FIX-11 · @AI tip — show once early in flow
**PDF ref:** p8  
**Problem:** Users don't know about `@AI`. They get stuck when they want to change a previous answer.  
**Solution:** After the first major confirmation (event type + context question), append once: *"Tip: type @AI anytime to update a previous answer."* Add `ai_tip_shown` flag to state so it never repeats.  
**Files:** `ml-agent/agent/state.py`, `ml-agent/agent/nodes/basic_info.py`

### FIX-15 · Add drinks section
**PDF ref:** p18  
**Problem:** No drinks discussed. Water/tea/lemonade included but never mentioned. Coffee and bar are upsell opportunities.  
**Solution:** Add `drinks` slot + `collect_drinks` node after desserts, before utensils.  
- Inform: *"Water, iced tea, and lemonade are included."*
- Upsell: *"Want to add coffee service or a bar package?"*
- If bar: present options (Beer & wine / Beer & wine + 2 signatures / Full open bar)
- If bar selected: note bartenders included ($50/hr, 5-hr min)  
**Files:** `state.py`, `addons.py`, `system_prompts.py`, `__init__.py`, `routing.py`

### FIX-16 · Add tableware question (disposable vs china)
**PDF ref:** p19  
**Problem:** No question about china vs disposable. Significant cost difference.  
**Solution:** Add `tableware` slot + `collect_tableware` node after service type.  
- All contracts come with basic disposable (included)
- Upgrade: premium disposable gold/silver +$1pp
- Full china: price by guest count
- If plated selected → auto-note "China included with plated packages"  
**Files:** `state.py`, `addons.py`, `system_prompts.py`, `__init__.py`, `routing.py`

### FIX-17 · Add labor section
**PDF ref:** p2, p25–26  
**Problem:** No labor questions. Bartending, setup, cleanup, trash, travel are billable but never discussed.  
**Solution:** Add `labor` slot + `collect_labor` node, gated on `service_type == "Onsite"`. Present as numbered list:  
1. Ceremony Setup/Cleanup — $1.50pp
2. Table & Chair Setup — $2.00pp
3. Table Preset — $1.75pp
4. Reception Cleanup — $3.75pp
5. Trash Removal — $175 flat
6. Travel Fee — $150/$250/$375+ based on distance  
**Files:** `state.py`, `addons.py`, `system_prompts.py`, `__init__.py`, `routing.py`

### Coffee Bar incorrectly pulled as dessert
**PDF ref:** p17  
**Problem:** When user types mini dessert options, "Coffee Bar" gets auto-included as a dessert because it's in the Desserts DB category. User never asked for it.  
**Solution:** In `select_desserts_node`, when resolving items from the dessert menu, exclude "Coffee Bar" unless the user explicitly mentioned it. Coffee Bar should be part of the drinks section (FIX-15), not desserts.  
**Files:** `addons.py` (select_desserts_node extraction/resolution logic)

### FIX-18 · Duplicate items in selection
**PDF ref:** p18  
**Problem:** Adding same item twice creates duplicates in slot and contract.  
**Solution:** Add `_normalize_item_name()` helper — strips price annotations, lowercases. Use in all dedup checks across `addons.py` and `check_modifications.py`.  
**Files:** `ml-agent/agent/nodes/addons.py`, `ml-agent/agent/nodes/check_modifications.py`

### FIX-19 · Contract short format
**PDF ref:** p28  
**Problem:** Contract lists full descriptions for every item. Reads like a recipe book.  
**Solution:** Use deterministic Python template for the menu section — show item names only (e.g. "Potato Bar, Coffee Bar"), not full descriptions. Full descriptions stay in DB for the actual contract page.  
**Files:** `ml-agent/agent/nodes/final.py`

### FIX-20 · Follow-up call offer at end of flow
**PDF ref:** p27  
**Problem:** Conversation ends abruptly. No option to schedule a follow-up call.  
**Solution:** Add `offer_followup` node as the last step before `generate_contract`. *"Would you like to schedule a quick call to go over the details? Usually 10–15 minutes."* Yes → collect time, store in DB. No → proceed to contract.  
**Files:** `state.py`, `final.py`, `system_prompts.py`, `__init__.py`, `routing.py`

### FIX-23 · Custom menu escape hatch
**PDF ref:** p14  
**Problem:** If user doesn't see something they like on the menu, there's no way to schedule a call for a fully custom menu.  
**Solution:** After presenting main menu, add: *"Don't see something you love? Type 'custom' and we'll set up a quick call to design your menu."* Detect "custom"/"call"/"none of these" → fill `menu_notes` with "Custom menu requested" → skip dish selection → continue flow.  
**Files:** `ml-agent/agent/nodes/menu.py`, `ml-agent/prompts/system_prompts.py`

### Plated vs Buffet question (wedding)
**PDF ref:** p12  
**Problem:** No plated vs buffet question. Plated gets china automatically.  
**Solution:** Add question before main menu for weddings: *"Would you like a plated meal or buffet?"* If plated: *"While these menus are shown buffet-style, just pick what's closest — we'll fine-tune on a quick call."* Auto-add china note.  
**Files:** `ml-agent/agent/nodes/menu.py`

### Bar service sub-flow
**PDF ref:** p18  
**Problem:** Bar options not presented during intake. Bartender pricing not discussed.  
**Solution:** Within the drinks node, if user wants bar: present 3 options (Beer & wine / Beer & wine + 2 signatures / Full open bar). Note: *"All bar services include professional bartenders. $50/hr, 5-hour minimum."* Bar back package: $8.50pp. Ice only: $1.75pp.  
**Files:** `ml-agent/agent/nodes/addons.py`

---

## Frontend (Not ml-agent scope)

| Item | PDF ref | Description |
|------|---------|-------------|
| Accordion menu display | p9 | Collapsible categories for appetizers and main menu |
| Checkbox selection UI | p9 | Users select items via checkboxes instead of typing |
| Digital invoice with dropdowns | p28 | Contract review shows titles; expand for full description |
| Staff dashboard — edit project details | p28 | Dates, prices, names editable; link to client chatbot |
| Calendar integration | p5 | Check date availability before completing intake |
