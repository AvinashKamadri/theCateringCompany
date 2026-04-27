# Weekly Status — TheCateringCompany

**As of:** 2026-04-27
**Owner:** Avinash (ml-agent + backend safety layer)
**Audience:** Senior engineer review / Trey feedback follow-up

This is a snapshot of where the system stands across the four areas
that were called out: guardrails, Trey's feedback, email integrations,
and overall this-week deliverables.

---

## TL;DR

| Area | Status | Notes |
|---|---|---|
| Allergen safety guardrails | ✅ Shipped | Slices 1–3 + drift hygiene + fallback UX (scope b) all in main |
| Trey's chat-failure feedback | ✅ Fixed | Both error states ("Failed to send message" + "I apologize, encountered an issue") resolved — see §3 |
| Email integration | 🟡 In progress | Payment reminders migration shipped; outbound delivery wiring is the open item |
| Auth / UI polish | ✅ Shipped | Auth redesign, SVG corner decorations, sidebar polling fix, session-end modal |
| Reset → seed → derive workflow | ✅ Self-healing | `prisma migrate reset` no longer needs the manual `quick_setup.sql` step |

---

## 1. Guardrails — allergen safety system

The week's biggest delivery. The system is now **correct, locked, and
resilient**.

### What shipped

- **Data-derived allergens**: `menu_items.allergens` and
  `menu_items.allergen_confidence` are denormalized from the
  ingredients → dishes graph by `MenuAllergenDerivationService`. Single
  writer, auditable, no LLM tagging.
- **Three-state confidence model**: `derived` | `incomplete` | (with
  `incomplete` as the fail-closed default).
- **Single hard filter**: `filter_excluded_allergens(menu, excluded)`
  — every menu read funnels through it; `incomplete` items drop when
  any concern is set.
- **Hybrid guard** (fail-loud-in-dev / fail-CLOSED-in-prod): every
  `load_*` and `resolve_*` entry point requires
  `excluded_allergens=_user_excluded_allergens(slots)`. Forgotten
  kwarg in dev → `ValueError`; in prod → excludes all FALCPA
  allergens + `CRITICAL ALLERGEN_GUARD_TRIGGERED` log with caller
  frame.
- **Fallback UX (scope b)**: empty-state copy when filter exhausts a
  slot; "Tiramisu isn't safe — alternatives: Fruit Tart, Lemon Bars,
  Sorbet Trio" when a user asks to add a blocked item.
- **8-test regression suite** in `tests/test_allergen_filter_regression.py`
  locking the bug history.
- **Drift hygiene**: 3 new migrations (`add_menu_item_allergen_confidence`,
  `drift_capture_waste_logs_and_price_unit`, `seed_baseline_roles`)
  +  the `payment_reminders` migration's stray DROP of
  `menu_categories.section` removed. Reset → seed reproduces from zero.

### Full reference

See [docs/allergen-implementation.md](allergen-implementation.md) — that
doc is the engineering source of truth for the safety layer (architecture,
contract, every wired call site, tests, ops quick-reference).

### Architectural rule

> Allergen safety is **derived from data**, **enforced at every menu
> entry point**, and **fails closed** when data is incomplete.

---

## 2. Other guardrails in place

These already existed but are worth listing for the review:

| Guardrail | Where | What it prevents |
|---|---|---|
| Cascade map | `agent/cascade.py` | Dependent slot drift on edits (e.g. event_type change → partner_name cleared if no longer wedding) |
| Locked slots | modification tool | `bartender`, `conversation_status` are unmodifiable |
| Cross-category replace confirmation | modification tool | Accidentally moving items between desserts ↔ apps |
| Single-writer for menu_items.allergens | derivation service | LLM or callers can't tag items |
| Phase-locked router | router | LLM doesn't bounce between phases mid-extraction |
| Fail-closed filter default | `filter_excluded_allergens` | Unknown = unsafe when concern set |
| Idempotent migrations | every new migration this week | Reset / partial-state DBs are safe to re-apply |

---

## 3. Trey's feedback — chat failures (RESOLVED)

Trey hit two error states during onboarding flows:

### 3.1 "Failed to send message. Please try again."

Surfaced in the birthday flow after entering guest count. Root cause:
backend was returning a non-2xx on a slot validator branch. **Status:
fixed** in earlier commit (a7db2e9 — Vercel build error + content
replacement bug). Validation now returns a clarifying question instead
of throwing.

### 3.2 "I apologize, but I encountered an issue. Could you please try again?"

Surfaced in the wedding flow after answering service style ("Both" for
cocktail + reception). Root cause: agent-side exception when both
service-style branches were active and the cascade map didn't have a
defined route. **Status: fixed** as part of the cascade architecture
adoption (commit 0e53f77 — `feat(ml-agent): adopt cascade architecture
from ml-agent-branch`).

### Verification asks for Trey

When he retests, he should be able to complete:

- Wedding → fiancée → date → venue → 150 guests → "Both" → cocktail
  hour question (no apology error)
- Birthday → name → date → venue → 150 → 100 (correction) → no
  "Failed to send" toast

Both flows pass our regression suite locally.

---

## 4. Email integration — current state

### Shipped

- **Payment reminders schema** —
  `20260420061929_add_payment_reminders_and_conversation_summary`
  migration is in main. Tables in place for scheduled reminders +
  conversation summaries.
- **Conversation summary write path** — agent persists summaries on
  finalization for follow-up emails.

### Open

- **Outbound delivery wiring** — the cron/worker that picks up due
  reminders and sends them via the SMTP/SendGrid path. Schema is
  ready; the dispatcher is the open task.
- **Trigger conditions** — exact rules for "send 7 days before event"
  / "send on payment-due date" still need a small spec doc + a
  per-tenant opt-out flag.
- **Templates** — payment reminder + confirmation email copy hasn't
  been finalized.

### Recommended next step

Half-day spec on dispatcher rules → 1-day worker implementation →
manual smoke test with a sandbox tenant before enabling for production
projects.

---

## 5. UI / UX shipped this week

(From git log — ratified shipped, not in flight.)

- Auth pages redesigned (`c4ea040`, `2b29ff7`)
- SVG corner decorations + Vennela's UI improvements (`74cb41a`)
- Bottom-image overlap removed (`923447b`)
- Sidebar polling/short-polling fix (`1a0547c`)
- Session-end modal redesigned (`811768b`)
- Chat UI markdown rendering (`4813aad`)
- Menu items grouped into categories in chat (`f5b5b81`)
- Navbar (`5195810`)
- Multi-select response polish (`ae9f2ae`)

---

## 6. What's NOT done (honest list)

- Email dispatcher (see §4).
- Ranking within safe items (popularity, event fit, diversity) — next
  natural follow-up to the allergen fallback work; will move us from
  "safe" to "smart."
- Mini-dessert sub-items still inherit parent confidence rather than
  having their own derivation. Acceptable for now; flagged in the
  allergen doc.
- Production telemetry on `ALLERGEN_GUARD_TRIGGERED` — log lines exist
  but no dashboard / alert pipe yet.

---

## 7. Risks / things to watch

| Risk | Likelihood | Mitigation |
|---|---|---|
| New `load_*` callers ship without `excluded_allergens` | Medium (codebase grows) | Guard catches in dev tests; CRITICAL log catches in prod |
| Inventory data quality regresses → `incomplete` count grows → menus look sparse | Medium | Health-check script flags counts; fallback UX softens user impact |
| Email dispatcher delays | Medium | Schema is ready; isolated worker scope |
| Trey hits a fresh edge case during retest | Low | Both reported errors fixed and covered by golden transcripts |

---

## 8. Quick-reference commands

```bash
# Reset + reseed + verify allergen state (one sequence, no manual SQL):
cd backend
npx prisma migrate reset
npm run seed:users
npm run seed:menu
npx ts-node src/scripts/seed-perfect-dataset.ts
npx ts-node src/scripts/recompute-menu-allergens.ts

# Run allergen regression suite:
cd ml-agent
python -m pytest tests/test_allergen_filter_regression.py -q
# → 8 passed
```
