# Intake + Modification Flow (Implementation Notes)

This document describes how the `ml-agent` intake chat supports **mid-flow edits** (e.g., “change my email”, “remove chicken”, “drop the wedding cake”), including the **ambiguous choice** UX (“Which one do you want to remove?”).

## Architecture (one tool per user turn)

Each user message is handled by a strict 3-stage pipeline:
1) **Router** chooses exactly one Tool to run for the turn (or asks for clarification).
2) **Tool** updates state via slot writes (first-fills, menu picks, or modifications).
3) **Response generator** renders the user-facing reply using deterministic prompts / tool facts.

Key files:
- `ml-agent/agent/router.py`
- `ml-agent/agent/prompt_registry.py`
- `ml-agent/agent/state.py`

## State model (slots + modification history)

State is stored in a `slots` dict where every slot value is wrapped with:
- `value`
- `filled` (bool)
- `modified_at` (timestamp)
- `modification_history[]` (old/new/timestamp)

All tools must write via `fill_slot()` to preserve history and keep the frontend stable.

Key files:
- `ml-agent/agent/state.py`

## Menu selection (DB-grounded)

Menu selection never writes arbitrary food text into state. User-provided items are resolved against the DB-backed menu so that:
- selections map to real menu items
- formatting is consistent (`name ($X/pp)` etc)
- category-level selections can be expanded/validated

Key files:
- `ml-agent/agent/tools/menu_selection_tool.py`
- `ml-agent/agent/menu_resolver.py`
- `ml-agent/database/db_manager.py` (menu loading)

## Modifications (remove / add / replace / reopen)

Modifications are handled centrally so users can change any already-filled slot without breaking flow.

Supported intents:
- **Scalar slots** (email, phone, date, venue, etc): extract the target slot and replace the value (validated by the owning flow where applicable).
- **List slots** (appetizers, mains, desserts, rentals): support add/remove/replace with grounding.
- **Reopen**: lets users “start over” on an entire section (e.g., reopen appetizers).

Key files:
- `ml-agent/agent/tools/modification_tool.py`
- `ml-agent/agent/list_slot_reopen.py`

## Ambiguous choice UX (disambiguation)

When the user references something fuzzy (“remove chicken”, “remove platter”, “remove egg and pork”), the agent may find multiple plausible matches among the **currently selected items**.

Behavior:
- Detect ambiguity and return a numbered list of matches.
- Store a pending-choice marker in state (internal slot) so the **next** user message can be treated as a deterministic selection (number or exact text).
- Apply the chosen operation (add/remove/replace) to the correct slot items.

Key files:
- `ml-agent/agent/ambiguous_choice.py` (normalize + resolve `1`/exact-match)
- `ml-agent/agent/tools/modification_tool.py` (ambiguous grounding + prompts)
- `ml-agent/agent/tools/menu_selection_tool.py` (similar pending-choice flow for menu turns)

## Models used (env-overridable)

The OpenAI model snapshots are centralized and can be overridden via env vars.

Defaults (as seen in logs and code):
- Router / routing extraction: `ML_MODEL_ROUTER` (example: `gpt-5.4-2026-03-05`)
- Tool structured extraction: `ML_MODEL_EXTRACT` (example: `gpt-5.4-mini-2026-03-17`)
- Response generation: `ML_MODEL_RESPONSE` (used by the response generator)

Key files:
- `ml-agent/agent/instructor_client.py`
- `ml-agent/agent/trace_context.py` (request tags, prompt cache key)

## Observability + proof (sanitized logs)

The following excerpt is a **sanitized** copy of real service logs demonstrating:
- router selecting `finalization_tool`
- tool extraction using the configured model
- state slot updates (including `conversation_status=pending_staff_review`)
- token + cached token reporting

Note: identifiers and PII (thread ids, email/phone) are redacted before being written here. Do not commit raw production-like logs with PII.

```text
openai_extract_request schema=OrchestratorDecision model=gpt-5.4-2026-03-05 attempt=1
openai_extract_response schema=TurnRoutingSignals model=gpt-5.4-2026-03-05 elapsed_ms=1951
router_decision action=tool_call confidence=0.96 tool=finalization_tool

openai_extract_request schema=FinalizationExtraction model=gpt-5.4-mini-2026-03-17 attempt=1
openai_extract_response schema=FinalizationExtraction model=gpt-5.4-mini-2026-03-17 elapsed_ms=1255

slot_update slot=additional_notes action=fill old=None new='arrive before 9 am'
tool_done tool=finalization_tool next_phase=S18_followup filled=['additional_notes']

turn_llm_calls total=3
turn_tokens input=3401 output=109 cached_input=2176
conversation_tokens_cumulative turns=55 input=173069 output=4632 cached_input=39296 total=177701

chat_request phase=S18_followup message='yes'
router_decision action=tool_call confidence=1.00 tool=finalization_tool
slot_update slot=followup_call_requested action=fill old=None new=True
slot_update slot=conversation_status action=fill old=None new='pending_staff_review'
tool_done tool=finalization_tool next_phase=complete filled=['followup_call_requested']
```

## Where to look next

- If the UI is repeating the “locked in and sent” message too early: check `ml-agent/agent/tools/finalization_tool.py` and `ml-agent/agent/prompt_registry.py` wrap-up rules.
- If ambiguous removal lists include unrelated items: check `ml-agent/agent/tools/modification_tool.py` grounding prompts and matching logic.

