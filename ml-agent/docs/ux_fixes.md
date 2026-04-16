# UX Fixes — Response Variation, Menu Presentation, Dessert Tracking, Ambiguity Handling

---

## 1. Rotating Questions (Response Variation at Temperature=0)

**Problem:** Bot asks the same question the same way every conversation. Feels robotic.

**Root Cause:** `temperature=0` is deterministic — same prompt → same output every time. NODE_PROMPTS have rotation hints like "rotate between these styles" but the LLM picks the same one each time.

**Solution: Variation Seed + Phrasing Banks**

Two-layer approach:

**Layer A — Inject a variation seed into every `llm_respond` call:**

In `helpers.py`, modify `llm_respond` to inject a per-turn variation seed:

```python
import hashlib

async def llm_respond(system_prompt: str, context: str, conversation_id: str = "", turn: int = 0) -> str:
    seed = int(hashlib.md5(f"{conversation_id}:{turn}".encode()).hexdigest(), 16) % 100
    variation_directive = (
        f"\n\nVariation seed: {seed}. Use this to subtly vary your phrasing, "
        "word choice, and sentence structure. Never repeat the exact same opener twice."
    )
    # ... rest of llm_respond with system_prompt + variation_directive + slot_authority
```

This works because different prompts → different outputs even at `temperature=0`. The seed changes per turn and per conversation.

**Layer B — Phrasing banks for high-frequency nodes:**

In `helpers.py`, add:

```python
PHRASING_BANKS = {
    "confirm_name": [
        "Nice to meet you, {name}!",
        "Got it — thanks, {name}.",
        "Hey {name}!",
        "Perfect, {name}.",
    ],
    "ask_date": [
        "Do you have a date set yet?",
        "When's the big day?",
        "What date are you planning for?",
        "When are we celebrating?",
    ],
    "confirm_venue": [
        "Great spot.",
        "Nice choice.",
        "Love that venue.",
        "Perfect.",
    ],
    "confirm_guest_count": [
        "Got it, {count} guests!",
        "Planning for {count} — sounds good.",
        "{count} guests, noted.",
    ],
    "transition_to_menu": [
        "Let's get into the fun part — the menu.",
        "Now let's build this out.",
        "Time for the good stuff — food.",
        "Let's dive into the planning.",
    ],
}

def pick_phrasing(key: str, conversation_id: str, turn: int, **kwargs) -> str:
    bank = PHRASING_BANKS.get(key, [""])
    seed = int(hashlib.md5(f"{key}:{conversation_id}:{turn}".encode()).hexdigest(), 16)
    phrase = bank[seed % len(bank)]
    return phrase.format(**kwargs) if kwargs else phrase
```

**Layer C — Deep variation via seed injection (covers ALL 41 nodes automatically):**

In `llm_respond`, inject a variation seed that changes per conversation + per turn. This makes the LLM generate different phrasing every time without maintaining any phrasing banks:

```python
async def llm_respond(system_prompt: str, context: str) -> str:
    import random
    seed = random.randint(1, 1000)
    variation = (
        f"\n\nVARIATION SEED: {seed}. "
        "Use this seed to vary your phrasing naturally. "
        "Change your opener, sentence structure, and word choice each time. "
        "Never start two consecutive messages the same way. "
        "Sound like a different real person each time — same warmth, different words."
    )
    # ... append variation to system_prompt before calling LLM
```

This works because at `temperature=0`, different prompts still produce different outputs. The random seed is enough to shift word choice, openers, and structure across conversations.

**Layer B (optional polish) — Phrasing banks for top 5 high-traffic nodes only:**

Keep small banks for the nodes every client hits — name confirmation, date ask, venue confirmation, guest count, and section transitions. These give you editorial control over the most-seen messages.

**Where to apply:**
- Layer C: one change in `helpers.py` `llm_respond` — covers everything
- Layer B: optional, `helpers.py` phrasing banks + 5-6 node files

**Files:** `helpers.py` (primary), optionally individual node files

**Effort:** ~15 min for Layer C (seed). ~20 min for Layer B banks if desired.

---

## 2. Present Menu Directly (Don't Ask "What Do You Want?")

**Problem:** Bot says "What kind of apps do you want to serve?" then waits, then shows menu only after user says "show me the menu". Should lead with the menu.

**Root Cause:** The `select_service_style` / `collect_guest_count` node transitions to `ask_appetizers` with a prompt that asks what they want instead of showing the menu immediately.

**Solution: Present-First Pattern**

Change the appetizer flow: instead of `ask_appetizers → (user says yes) → show menu`, collapse into one node that presents the menu directly with a casual intro.

**Current flow:**
```
collect_guest_count → "Would you like appetizers?" → user: "yes" → show appetizer menu
```

**New flow:**
```
collect_guest_count → "Here are our appetizer options — pick as many as you'd like:" [menu]
```

If user says "no" / "skip" / "no appetizers", detect that and skip.

**Implementation:**

In `collect_guest_count_node`, after confirming guest count, the response should include the appetizer menu directly:

```python
# After guest count is confirmed:
appetizer_context = await get_appetizer_context(state)
response = await llm_respond(
    f"{SYSTEM_PROMPT}\n\n"
    "Confirm the guest count briefly. Then present the appetizer menu directly — "
    "don't ask if they want appetizers, just show the options with a casual intro like: "
    "'Here are the appetizer options — pick as many as you'd like.' "
    "Suggest 3-5 options for their guest count. "
    "CRITICAL: Only list items from the database.",
    appetizer_context
)
state["current_node"] = "select_appetizers"  # skip ask_appetizers entirely
```

**Alternative (safer):** Keep `ask_appetizers` but change the NODE_PROMPT to present the menu immediately:

```python
"ask_appetizers": (
    "Present the appetizer menu directly with a casual intro. "
    "Don't ask 'would you like appetizers?' — just show the options. "
    "Start with crowd favorites, then show the full numbered list. "
    "Example: 'Cocktail hour is where things open up. Here are the appetizer options — "
    "some crowd favorites are charcuterie boards, bruschetta, and bacon chicken bites. "
    "Pick as many as you'd like:' [numbered list] "
    "If the customer says no/skip/pass to appetizers, that's fine — acknowledge and move on."
),
```

**Same for main menu:** The `present_menu` / `select_dishes` node should present with "Here's what we've got" not "What would you like?"

**Files:** `system_prompts.py` (NODE_PROMPTS for `ask_appetizers`, `present_menu`), possibly `menu.py` node logic

**Effort:** ~10 min. Mostly prompt changes.

---

## 3. Mini Desserts — Track Individual Selections, Not Bundle Name

**Problem:** When user picks 4 items from "Mini Desserts - Select 4", the slot stores "Mini Desserts - Select 4" instead of "Mini Desserts: Lemon Bars, Blondies, Brownies, Fruit Tarts".

**Root Cause:** `_resolve_to_db_items` matches to the parent DB item "Mini Desserts - Select 4". The individual items (Lemon Bars, etc.) are only in the description field, not as standalone DB items.

**Solution: Store as "Mini Desserts: item1, item2, item3, item4"**

In `select_desserts_node`, after the extraction and bundle detection:

```python
_BUNDLE_NAMES = {"mini desserts - select 4", "mini desserts"}

if matched_items and len(matched_items) == 1 and matched_items[0]["name"].lower() in _BUNDLE_NAMES:
    extraction_lower = extraction.strip().lower()
    if extraction_lower in _BUNDLE_NAMES:
        # User said package name only — ask which 4
        # (already implemented)
    else:
        # User gave individual items — format as "Mini Desserts: item1, item2, ..."
        resolved_text = f"Mini Desserts: {extraction.strip()}"
```

**Guardrail: Enforce exactly 4 selections for mini desserts:**

After extraction, count the items:
```python
items = [i.strip() for i in extraction.split(",") if i.strip()]
if len(items) > 4:
    # Cap at 4, tell user
    items = items[:4]
    response = "That's more than 4 — I've kept: " + ", ".join(items) + ". Want to swap any?"
elif len(items) < 4:
    remaining = 4 - len(items)
    response = f"You've picked {len(items)} so far. Pick {remaining} more from: [remaining options]"
```

**Storage format:**
```
Slot value: "Mini Desserts: Lemon Bars, Blondies, Brownies, Fruit Tarts"
```
NOT: `"Mini Desserts - Select 4 ($5.25/pp)"`

**Files:** `addons.py` (`select_desserts_node`), the cap logic already exists but needs the format fix

**Effort:** ~15 min

---

## 4. Ambiguous / Unclear Responses — Tiered Clarification

**Problem:** "my backyard" for venue gets re-asked. "yes why not" to multiple-choice doesn't pick an option.

**Root Cause:** 
- Venue extraction treats "my backyard" as unclear — but it's a valid answer (private outdoor space)
- Multiple-choice nodes use `is_affirmative()` which returns True for "yes why not" but doesn't pick an option

**Solution: Three-Tier Clarification Strategy**

**Tier 1 — Accept and infer when possible:**

"My backyard" is a valid venue. "My house", "at home", "the park", "TBD" are all valid. The extraction prompt already handles this (we fixed it). The LLM with `temperature=0` should accept these.

For any remaining edge cases, add to the venue extraction prompt:
```
Accept informal venues: 'my backyard' → 'Private Residence (Outdoor)', 
'my house' → 'Private Residence', 'the park' → store as-is.
```

**Tier 2 — Echo back and confirm when partially ambiguous:**

When the extraction succeeds but the value seems informal, the response should confirm:
```
"Got it — your backyard. How many guests are you thinking?"
```
Don't re-ask. Accept it and move on.

**Tier 3 — Re-ask with specific options when truly ambiguous:**

For "yes why not" to a multiple-choice (e.g. "coffee, bar, or both?"), the drinks node already handles this with the `ask` intent. Extend this pattern to ALL multiple-choice nodes:

```python
# Generic pattern for any multi-choice node:
intent = await llm_extract(
    "The customer was given options: [list]. Their reply was vague (e.g. 'yes', 'sure', 'why not'). "
    "If they didn't specify which option, return 'ask'. "
    "If they clearly chose one, return that option name.",
    user_msg
)
if intent == "ask":
    response = "I'll take that enthusiasm! Which one though — [option1], [option2], or [option3]?"
```

**The Two-Strike Rule:**

If a slot is still unclear after 2 attempts at the same question, accept the best interpretation and move on. Don't loop forever:

```python
# In _extract_and_respond or individual nodes:
retry_key = f"_retry_{slot_name}"
retries = state.get(retry_key, 0)
if retries >= 2:
    # Accept best guess and move on
    fill_slot(state["slots"], slot_name, user_msg.strip())
    state[retry_key] = 0
    # ... advance to next node
else:
    state[retry_key] = retries + 1
    # ... re-ask
```

**Add to SYSTEM_PROMPT:**

```
When the user's response is ambiguous:
1. If you can reasonably infer intent, accept it and confirm naturally.
2. If genuinely unclear, re-ask with SPECIFIC options — never repeat the same question.
3. Never ask more than twice for the same info. After 2 tries, accept the best interpretation.
Do not over-clarify. "My backyard" is a valid venue. "Next Saturday" is a valid date.
```

**Files:** `system_prompts.py` (SYSTEM_PROMPT + individual NODE_PROMPTS), `helpers.py` (two-strike counter), multi-choice nodes in `addons.py`

**Effort:** ~20 min

---

## Implementation Order

1. **Menu presentation** (#2) — 10 min, prompt-only change, zero risk
2. **Dessert tracking format** (#3) — 15 min, one edit in `select_desserts_node`
3. **Ambiguity handling** (#4) — 20 min, SYSTEM_PROMPT + multi-choice nodes
4. **Response variation** (#1) — 30 min, needs threading conversation_id through `llm_respond`

**Total: ~1.5 hours**
