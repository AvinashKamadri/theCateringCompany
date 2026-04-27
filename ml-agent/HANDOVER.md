# ML Agent — Handover

This document is for the next person maintaining this repo. It covers what
exists, why, and where to look first when something breaks.

---

## 1. What this thing is

A multi-stage catering intake agent. A customer chats with it through a web
UI; the agent collects event details (name, date, venue, menu, add-ons, etc.)
and submits a request for a human coordinator to follow up.

Each customer turn is processed by **three** sequential stages:

1. **Router** (`agent/router.py`) — picks one Tool to handle the turn.
2. **Tool** — proposes structured facts (slot fills, modifications, pricing).
   Tools live in `agent/tools/`.
3. **Response Generator** (`agent/response_generator.py`) — turns those facts
   into the user-facing reply.

State persists in Postgres via Prisma + Redis as a hot cache. The
orchestrator (`orchestrator.py`) wires the three stages together per turn.

---

## 2. The architecture you should know about

### 2.1 Routing pipeline

The router has 22 sequential decision steps. The first one that matches wins.
**See `agent/routing.py` for the canonical ordered list** with names,
descriptions, and where each step lives in code.

```python
from agent.routing import explain_routing
print(explain_routing())
```

When debugging "why did message X go to tool Y?", read `agent/routing.py`
top-to-bottom. The actual logic still lives in `agent/router.py:route()` —
`agent/routing.py` is the map.

### 2.2 State schema

`agent/state.py` defines:

- **Public slots** — customer-visible facts (`name`, `selected_dishes`,
  `event_date`, etc.)
- **Internal slots** — prefixed with `__`, track flow state (`__gate_desserts`,
  `__pending_modification_request`, `__wedding_cake_gate`, etc.)
- **Phases** — `S1_greeting` through `S19_review` plus `complete`. The
  router and tools branch on phase, so phase transitions matter.

Every slot read/write goes through `fill_slot()` / `clear_slot()` /
`get_slot_value()` — direct dict assignment breaks the frontend's slot card
rendering.

### 2.3 Pending state TTL

Internal slots prefixed `__pending_*` represent one-shot dialog state (e.g.
"do you want Dragon Chicken as a special request?"). They MUST be resolved
on the next turn or they go stale.

**`validate_pending_state()` runs at the top of every `route()` call** and
auto-clears any pending older than 2 turns. This prevents the "Dragon
Chicken bleed" — old offers haunting later turns.

When you set a `__pending_*` slot, include `created_turn` in the payload (or
the validator auto-stamps it on first observation).

### 2.4 Intent classification

`agent/intents.py` is the **single source of truth** for skip / decline
classification:

```python
from agent.intents import classify_skip_gate, classify_decline, is_generic_no
```

If you add a new "skip values for section X" list ANYWHERE ELSE, you're
duplicating logic that will drift. Add it to `_SECTION_SKIP_VALUES` in
`intents.py` instead.

### 2.5 Tight extractor history

LLM extractors hallucinate items from past turns when they see too much
history (the cause of the "ok ok" → "Plated service it is" bug). Every
tool's `_history_for_llm()` now uses `tight_history_for_llm()` from
`agent/tools/base.py` which returns at most the last AI question + last user
message.

If you add a new tool with an LLM extractor, use `tight_history_for_llm`
unless you have a specific reason not to.

---

## 3. Where things live

| What | Where |
|---|---|
| Routing decision pipeline (canonical) | `agent/routing.py` (read-only doc) |
| Routing logic (actual code) | `agent/router.py:route()` |
| Skip / decline values | `agent/intents.py` |
| Pending-state TTL | `agent/state.py:validate_pending_state` |
| Tight LLM history | `agent/tools/base.py:tight_history_for_llm` |
| Tool implementations | `agent/tools/{basic_info,menu_selection,modification,add_ons,finalization}_tool.py` |
| Pydantic extraction schemas | `agent/models.py` |
| System prompts (registry) | `agent/prompt_registry.py` |
| Frontend response rendering | `agent/response_generator.py` |
| Banned phrasings (guardrail) | `agent/response_generator.py:_BANNED_OPENERS, _BANNED_PHRASES` |

---

## 4. Common changes — where to make them

### 4.1 Add a new skip value for a section

`agent/intents.py` → `_SECTION_SKIP_VALUES[section_name]`. Don't add to
individual tools; the router and the tools both read from `intents.py`.

### 4.2 Add a new banned LLM phrasing

`agent/response_generator.py` → `_BANNED_OPENERS` (start of reply) or
`_BANNED_PHRASES` (anywhere). The guardrail discards the LLM output and
falls back to the registry variant if any banned phrase appears.

### 4.3 Tighten what an LLM extractor accepts

Don't trust the extractor blindly. After it returns, verify the user's
message actually contains the expected keyword. Example:
`agent/tools/menu_selection_tool.py` does this for `meal_style` (rejects
silent "buffet" inference from messages like "half").

### 4.4 Add a multi-action modification example

`agent/tools/modification_tool.py:_SYSTEM_PROMPT` — add an example showing
primary + `secondary_modifications`. The schema (`agent/models.py:
SecondaryModification`) supports up to 3 secondaries per turn.

### 4.5 Add a new pending state slot

1. Add the slot name to `_PENDING_SLOTS` in `agent/state.py` (gives it TTL).
2. Add a `_pending_routes` entry in `agent/router.py:route()` so the slot is
   checked before any phase bypass.
3. Use `created_turn` in the payload (or rely on auto-stamping).

---

## 5. Test strategy

### 5.1 Test pyramid

- **Unit tests** — `tests/test_demo_edge_cases.py` exercises individual
  helpers (`classify_decline`, `validate_pending_state`, etc.) in isolation.
- **Integration tests** — `tests/test_e2e_happy_path.py` drives real
  `route()` and tool code with mocked LLMs. Catches routing-order bugs that
  unit tests miss (this is how we caught the "skip dessert" routing
  regression that the old tests didn't see).
- **Legacy tests** — older tests under `tests/test_*.py` predate the
  stability refactor. Many were marked `@pytest.mark.skip` with the reason
  `"superseded by stability refactor..."` because they assert old behavior
  (ambiguity prompts, old turn-signals routing). They're kept as
  documentation of past behavior; delete or rewrite as needed.

### 5.2 Running tests

```bash
# Full suite (no DB needed for non-skipped)
python -m pytest tests/ --ignore=tests/test_integration.py --ignore=tests/test_golden_transcripts.py

# Just the demo + integration coverage (fastest, most relevant)
python -m pytest tests/test_demo_edge_cases.py tests/test_e2e_happy_path.py -v

# When tests pass in isolation but fail in the suite — it's the legacy
# `sys.path.insert` issue; check that `tests/conftest.py` is intact.
```

`tests/conftest.py` pins the project root to THIS repo and evicts stale
`agent.*` modules. Without it, the suite-wide path collisions return.

### 5.3 What's covered

- Skip / decline classification (`tests/test_demo_edge_cases.py`)
- Pending state TTL (`tests/test_demo_edge_cases.py`)
- Tight history extraction (`tests/test_demo_edge_cases.py`)
- Multi-action modification schema (`tests/test_demo_edge_cases.py`)
- Routing decisions per phase (`tests/test_e2e_happy_path.py`)
- menu_notes contamination guard (`tests/test_e2e_happy_path.py`)
- meal_style validator (`tests/test_e2e_happy_path.py`)
- Banned phrasings (`tests/test_e2e_happy_path.py`)
- Recap label sanity (`tests/test_e2e_happy_path.py`)

### 5.4 What's NOT covered (gaps to fill)

- A truly end-to-end orchestrator test (would need mocked Postgres + Redis)
- Frontend integration (the agent's structured `input_hint` types ↔ frontend
  widget rendering live in different codebases)
- Multi-turn conversation flow with real LLM calls (cost-prohibitive in CI)

---

## 6. Recently fixed bugs (don't reintroduce)

These were demo-blockers in the screenshot transcripts. Each has a guard;
breaking the guard will reintroduce the bug.

| Bug | Guard |
|---|---|
| Dragon Chicken bleed (stale pending offer) | `validate_pending_state` in `state.py` |
| "ok ok" → "Plated service it is" hallucination | `tight_history_for_llm` in `base.py` |
| `cocktail_hour` re-fill on appetizer paste with "Grilled Shrimp Cocktail" | menu_selection_tool extractor guard with `_already_same` and `_looks_like_item_list` |
| Event-type reset bypass | `_pending_routes` block at top of `route()` |
| menu_notes filled with "i have an ulcer" | menu_selection_tool validator (personal-statement + menu-keyword check) |
| "half" silently filling meal_style as buffet | `_meal_style_keyword_in_msg` regex check before fill |
| "skip dessert" reopening dessert menu | `classify_skip_gate` exemption from command bypass |
| "yes" to special-request offer didn't save | extractor history bounded so it can't hallucinate items_to_add on remove actions |
| Robotic "May I have your name?" | `_BANNED_PHRASES` guardrail discards the reply |
| "Now that we have the wedding noted..." preamble | `_BANNED_OPENERS` guardrail |

---

## 7. Known limits / future work

### 7.1 Router consolidation (deferred)

The 22-step pipeline in `agent/router.py:route()` is documented in
`agent/routing.py` but not yet refactored into discrete functions. A future
pass should turn each step into a method on a `Router` class for clearer
testing. Risk: any reordering breaks tests that depend on first-match
precedence.

### 7.2 Multi-action modification edge cases

`secondary_modifications` is bounded to 3 per turn. The LLM is taught two
examples in the system prompt. If users routinely send messages with 4+
cross-section actions, raise the cap and add more examples.

### 7.3 Frontend widget detection

The frontend matches text patterns in AI replies to decide which input
widget to show (`isAskingForPhone`, `isAskingForEmail`, etc. in
`frontend/components/chat/ai-chat.tsx`). This means changes to AI reply
phrasing can break widget rendering. Better long-term: have the agent send
an explicit `input_hint.type` and have the frontend use ONLY that field.

### 7.4 The legacy duplicate at `c:/Projects/CateringCompany/`

A 1.7GB stale copy of the project was renamed to
`c:/Projects/CateringCompany.STALE_BACKUP/` during the stability pass. It
was causing test pollution via hardcoded `sys.path.insert`. After ~1 week
of stability without anyone needing the backup, delete it permanently.

---

## 8. Local dev setup

```bash
# (from the repo root)
docker-compose up -d

# Or run the agent directly:
cd ml-agent
pip install -r requirements.txt
python -m uvicorn api:app --reload --port 8000

# Frontend:
cd ../frontend
pnpm install
pnpm dev
```

`OPENAI_API_KEY` must be set. Local Postgres + Redis come up via
`docker-compose`.

---

## 9. When in doubt

- **Routing decision unclear?** Read `agent/routing.py` — start at step 1.
- **LLM doing something weird?** Check the system prompt in
  `agent/prompt_registry.py` or the tool's `_SYSTEM_PROMPT`. The history
  it sees is `tight_history_for_llm(history)` — last AI Q + last user A.
- **Slot value got corrupted across turns?** Check if a `__pending_*` slot
  was set and not cleared. `validate_pending_state` should clear stale ones
  but won't catch logic bugs in the handler.
- **Reply has weird phrasing?** Check `_BANNED_OPENERS` / `_BANNED_PHRASES`.
  The guardrail should catch and fall back, but if the registry variant is
  also bad, fix the registry.
- **Test fails but works alone?** It's the `sys.path` collision —
  `tests/conftest.py` should pin the path. Verify it's intact.

Good luck.
