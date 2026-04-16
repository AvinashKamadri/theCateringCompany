# ML Agent — Production Plan & Optimization Strategy

> Research-backed plan for scaling the catering intake slot-filling flow.
> Based on 2024-2025 literature, engineering blogs, and production case studies.
> Last updated: 2026-04-03

---

## 1. Current Architecture Assessment

### What We Have
- 27-node LangGraph state machine
- Single-turn guided Q&A (one slot per turn)
- GPT-4o-mini at temperature=0
- Prisma (Python) for state persistence
- Custom routing with regex correction detection

### What Is Already Production-Grade
| Component | Status |
|---|---|
| `temperature=0` for extraction | Done |
| Structured outputs for categorical slots (`llm_extract_enum`) | Done |
| Structured outputs for numeric slots (`llm_extract_integer`) | Done |
| Centralised null-extraction guard (`is_null_extraction`) | Done |
| `fill_slot` null guard at state level | Done |
| Past-date rejection (Python-side, same clock as LLM) | Done |
| Guest count bounds validation | Done |
| `dietary_conflict_attempts` in ConversationState schema | Done |
| Combined dietary LLM call (note + conflict in one call) | Done |
| `logger.debug` replacing `print()` in check_modifications | Done |

---

## 2. State of the Art: What Modern Systems Do (2024-2025)

### The Shift from State Machines to LLM-Native Flows

Traditional Rasa/Dialogflow-style systems (intent → NLU → DST: three separate models) are being replaced by:

- **AutoTOD (ACL 2024)** — A fully zero-shot agent using a single instruction-following LLM with instruction schemas. Deprecates modular pipelines entirely.
- **CALM (Rasa 2024)** — Rasa's own pivot: uses LLMs for dialogue understanding within a controlled structure.
- **HierTOD** — Hierarchical goal structures for complex multi-level task dependencies.
- **SynTOD** — Graph-guided response simulation to generate structured training conversations.

**Key insight for our system:** Our 27-node state machine is closer to the old paradigm. This is not necessarily wrong — single-turn guided intake is a valid production pattern — but we should be aware of where the field is moving.

### Structured Outputs: The Biggest 2024 Leap

OpenAI's gpt-4o-2024-08-06 with Structured Outputs achieves **100% schema compliance** vs. <40% without it on complex schemas. This is constrained decoding at the token level — the model literally cannot emit a value outside the schema.

**We already use this.** The remaining extraction calls (`name`, `venue`, `event_date`) are free-text and still rely on `is_null_extraction` + `fill_slot` guards.

---

## 3. Cost Analysis

### Current Cost Per Conversation (Estimate)

| Phase | Input Tokens | Output Tokens |
|---|---|---|
| Basic info (6 turns) | ~1,800 | ~600 |
| Menu selection (4 turns) | ~2,400 | ~800 |
| Add-ons (5 turns) | ~1,500 | ~500 |
| Final + contract (4 turns) | ~3,000 | ~2,000 |
| **Total** | **~8,700** | **~3,900** |

**GPT-4o-mini pricing (2025):** $0.15/M input, $0.60/M output

- Input cost: 8,700 × $0.15/1,000,000 = **$0.0013**
- Output cost: 3,900 × $0.60/1,000,000 = **$0.0023**
- **Total per conversation: ~$0.004 (< half a cent)**

This is already very low. Optimisation targets below are about reliability and latency, not just cost.

### Cost Benchmarks (2025 Pricing)
| Model | Input $/M | Output $/M | Best For |
|---|---|---|---|
| GPT-4o-mini | $0.15 | $0.60 | Our current extraction |
| GPT-4o | $2.50 | $10.00 | Complex ambiguity only |
| Claude 3.5 Haiku | $0.80 | $4.00 | Alternative extraction |
| Gemini Flash-Lite | $0.075 | $0.30 | Cheapest option |
| Gemini Flash 2.0 | $0.10 | $0.40 | Budget alternative |

---

## 4. Optimisation Roadmap

### Priority 1 — Prompt Caching (High impact, low effort)

**What:** Cache the system prompt and node prompts across turns. They are static and account for ~40% of input tokens per turn.

**How:** OpenAI supports prompt caching automatically for prompts >1024 tokens. For Anthropic, use the `cache_control` header. Cached tokens cost **10% of normal input price** (90% savings on that portion).

**Expected saving:** ~30-40% reduction in input token cost.

**Implementation:** No code changes needed for OpenAI — caching is automatic. Ensure the system prompt is at the top of every call (it already is via `SYSTEM_PROMPT` prepended to each node prompt).

---

### Priority 2 — Instructor Library for Extraction Reliability

**What:** Replace our custom `llm_extract_enum` / `llm_extract_integer` / `llm_extract_structured` with [Instructor](https://python.useinstructor.com/) (3M+ monthly downloads, 11k GitHub stars).

**Why:** Instructor provides:
- Pydantic-backed type-safe extraction
- Automatic retry on validation failure (retries with a different prompt, not the same call)
- Multi-provider support (swap OpenAI for Anthropic/Gemini without changing extraction code)
- Full IDE type safety

**Current gap:** Our `llm_extract_structured` fallback on failure returns `{}` and silently continues. Instructor's retry mechanism re-prompts with the validation error attached, which improves success rate without infinite loops.

**Example migration:**
```python
# Current
result = await llm_extract_structured(prompt, user_msg, _DIETARY_SCHEMA)

# With Instructor
class DietaryResult(BaseModel):
    note: str
    has_conflict: bool

result = await client.chat.completions.create(
    model="gpt-4o-mini",
    response_model=DietaryResult,
    messages=[...]
)
```

---

### Priority 3 — Model Routing (Medium impact, medium effort)

**What:** Route simple extraction calls to a cheaper/faster model and reserve gpt-4o for genuinely ambiguous cases.

**Decision framework:**
| Slot | Complexity | Recommended Model |
|---|---|---|
| `service_type` (3 options) | Very low | gpt-4o-mini (already) |
| `event_type` (5 options) | Low | gpt-4o-mini (already) |
| `guest_count` (integer) | Very low | gpt-4o-mini (already) |
| `event_date` (relative dates) | Medium | gpt-4o-mini (already) |
| `name` | Low | gpt-4o-mini (already) |
| `venue` (free text) | Medium | gpt-4o-mini (already) |
| Contract generation | High | Consider gpt-4o |
| Dietary conflict + note | Medium | gpt-4o-mini (already) |

**Conclusion:** Current model choice is already optimal. Contract generation is the only candidate for upgrading to gpt-4o for quality. A/B test both.

---

### Priority 4 — Retry Pattern (Medium impact, low effort)

**Current gap:** When extraction returns `NONE` or fails validation, the node re-asks the user. This is correct. But there is no intelligent re-prompt — the same extraction prompt is re-run with the same user message on the next turn.

**Better approach (graduated retry):**
1. First attempt: structured extraction (already done)
2. On first NONE: fallback to regex for structured fields (date, phone, number)
3. On second NONE: ask user with a different, more specific question (already partially done)
4. On third NONE: gracefully offer to skip or escalate

**Do NOT:**
- Retry the identical LLM call (same output at temperature=0)
- Increase temperature to fix extraction (introduces hallucination)
- Loop indefinitely (add max retry counter per slot)

**Implementation:** Add `slot_retry_counts: dict[str, int]` to `ConversationState`. After 3 failed attempts on any slot, route to a graceful skip or human handoff node.

---

### Priority 5 — Context Window Trimming (Medium impact, medium effort)

**Current behaviour:** Full conversation history is passed on every turn. By turn 15, the context is 4,000+ tokens of prior messages, most of which are irrelevant to the current extraction.

**Problem:** This inflates input token cost and can confuse the LLM with old context.

**Solution:** Pass only the last N messages to extraction calls (not to response generation):
- `llm_extract` calls: last 3 messages only (user answer + AI question + prior answer)
- `llm_respond` calls: full context (needed for coherent response)

**Expected impact:** 30-50% reduction in tokens for extraction calls on later turns.

---

### Priority 6 — Async Parallelism for Independent Calls (Low effort, good latency win)

**Current:** `collect_dietary_node` now does one combined call (fixed). But the contract generation node (`generate_contract_node`) runs pricing calculation and LLM contract writing sequentially.

**Opportunity:** `calculate_event_pricing` (DB call) and the contract prompt construction are independent. Run them concurrently with `asyncio.gather`.

```python
pricing, contract_prompt = await asyncio.gather(
    calculate_event_pricing(...),
    build_contract_prompt(slots),
)
```

---

### Priority 7 — Fine-Tuning (Long-term, high investment)

**When to consider:** Once the intake flow has processed 500+ real conversations and you have labelled examples of:
- Correct extractions
- Edge case handling
- Clarification patterns

**What to fine-tune:** A small model (gpt-4o-mini or Phi-3-mini) specifically for extraction. Fine-tuned models at 4o-mini scale can match gpt-4o accuracy on domain-specific extraction at 10x lower cost.

**Minimum data requirement:** 200-500 annotated examples (50-100 absolute minimum).

**Not recommended yet** — premature optimisation without real conversation data.

---

## 5. Reliability Guardrails — What Remains

### Already Implemented
- Structured outputs for 4 slots
- `is_null_extraction` covering 20+ null variants
- `fill_slot` null guard (state level)
- Past-date rejection
- Guest count bounds
- `dietary_conflict_attempts` loop cap
- Venue vague/inappropriate detection

### Still Missing (Ordered by Risk)
| Gap | Risk | Effort |
|---|---|---|
| Max retry counter per slot | Medium — infinite loops possible | Low |
| `slot_retry_counts` in state schema | Medium | Low |
| Name validation (2 words, alphabetic) | Medium — garbage names stored | Low |
| Regex pre-check for date before LLM | Low | Low |
| Context trimming for extraction calls | Low | Medium |
| Instructor library adoption | Low (already have fallbacks) | Medium |
| Circuit breaker for OpenAI API failures | Medium — production outages | Medium |

---

## 6. LangGraph Production Considerations

### State Persistence
- **Current:** Prisma (Python) for state — custom implementation
- **LangGraph native:** `PostgresSaver` checkpointer is the recommended pattern
- **Recommendation:** Current approach works. If migrating, `PostgresSaver` adds time-travel debugging for free.

### Cross-Conversation State
- LangGraph checkpointers **cannot share state across threads** natively
- For user-level context (e.g., returning customer), implement a `Store` interface or query the users table directly
- Not needed for current single-session intake flow

### Async Performance
- LangGraph native async (`astream`) gives **50x concurrent user improvement** over sync
- Current implementation uses `ainvoke` — already async. Correct.

### Known Limitations
1. State keys not in TypedDict are silently dropped between invocations — fixed with `dietary_conflict_attempts`
2. Sub-graph loops can cause unexpected node jumps — mitigated by `current_node` explicit control
3. No built-in max-turn limit — add turn counter to state if needed

---

## 7. Architecture Evolution Path

```
Current (Phase 1)        Recommended (Phase 2)       Future (Phase 3)
─────────────────        ─────────────────────        ──────────────────
27-node sequential   →   27-node + slot retry    →    Hybrid: free-form
state machine            counter + context            first turn + guided
                         trimming + Instructor        fill for missing
GPT-4o-mini for all  →   GPT-4o-mini + regex    →    Fine-tuned small
extraction               pre-checks                   model for extraction
Full history in      →   Trimmed context for    →    Semantic compression
every call               extraction calls             (LLMLingua)
Manual null checks   →   Instructor Pydantic    →    Auto-generated
(is_null_extraction)     models + auto-retry         validators from schema
```

---

## 8. Immediate Next Steps (Actionable)

| # | Action | Effort | Impact |
|---|---|---|---|
| 1 | Add `slot_retry_counts: dict` to `ConversationState` | 30 min | Prevents infinite loops |
| 2 | Add name validation (2 words, alpha-only) to `collect_name_node` | 1 hr | Stops garbage names |
| 3 | Add `asyncio.gather` to contract generation (pricing + prompt) | 1 hr | Latency reduction |
| 4 | Context trimming: pass last 3 messages to `llm_extract` calls | 2 hr | Token cost reduction |
| 5 | A/B test gpt-4o vs gpt-4o-mini for contract generation | 1 hr | Quality/cost trade-off data |
| 6 | Migrate to Instructor for extraction (replaces custom helpers) | 1 day | Reliability + maintainability |

---

## 9. Contract Generation — Deep Dive

### Current State (Verified)

`generate_contract_node` passes **only slot values** to the LLM — zero conversation history. This is already optimal. The prompt contains:
- Filled slot dict (`_slots_context`)
- Pricing breakdown (from DB via `calculate_event_pricing`)
- Modification history (`_build_modification_notes`)
- Static business rules (cancellation policy, fees, contact info from `config`)

No conversation turns, no redundant context. ✓

---

### What the Research Says About Contract Generation

#### Template-Hybrid vs Fully LLM-Generated

Production systems at Ironclad, Icertis, and LexCheck use a **modular clause architecture**:
- Static boilerplate (cancellation, liability, payment terms) → templated, never LLM-generated
- Dynamic clauses (guest-specific obligations, menu terms, venue notes) → LLM-generated
- Rule engine validates clause combinations before LLM gets context

**For our system:** The contract prompt already mixes static policy strings (from `config`) with dynamic slot data. This is the right pattern. The LLM's job is connecting them into readable prose, not inventing legal terms.

#### Hallucination Risk in Contract Generation

LLMs hallucinate ~58% of the time on legal tasks. Risk is **lower for drafting than analysis** (we're drafting). Mitigations specific to our case:

- ✓ All numbers (pricing, guest count, dates) come from structured slots, not LLM inference
- ✓ Business policies (cancellation, fees) are injected as literal strings from `config`, not asked from LLM
- ✓ Menu items are resolved DB names, not LLM-invented strings
- ⚠ The LLM still writes narrative clauses — these should be validated to contain the slot values

**Recommended guard (not yet implemented):** After contract generation, run a quick structured check confirming that `guest_count`, `event_date`, `venue`, `grand_total` appear verbatim in the generated text. If any are missing → flag for review.

#### Model Choice: gpt-4o-mini vs gpt-4o

SpotDraft October 2024 benchmark (300+ fields, 45 contracts):
- Party information extraction → gpt-4o-mini wins (speed + accuracy balance)
- Contract summarisation → Gemini 1.5 Flash wins
- Risk identification → GPT-4o wins

**For contract *drafting* (our case):** gpt-4o-mini is the right choice. The structured data is already clean — the LLM is doing formatting/prose, not reasoning. gpt-4o costs 25x more on output with no meaningful quality difference for this task.

**Cost per contract:**
| Model | ~3,000 output tokens | Cost |
|---|---|---|
| gpt-4o-mini | 3,000 × $0.60/M | **$0.0018** |
| gpt-4o | 3,000 × $10.00/M | **$0.030** |

Stick with gpt-4o-mini. A/B test is recommended but unlikely to justify 16x cost increase.

---

### Optimisation Opportunities for Contract Generation

#### 1. Prompt Caching on Static Boilerplate (High impact, zero effort)

OpenAI prompt caching activates **automatically** for prompts >1024 tokens. Cached tokens cost **10% of normal input price** (90% saving on that portion).

**Structure to maximise cache hits:**
```
[STATIC - gets cached after first use]
  System prompt (contract writer persona)
  Company policies (cancellation, payment, liability, T&C)
  Format rules (signature block, footer, contact info)

[DYNAMIC - never cached, unique per contract]
  Client: {name}
  Date: {event_date}
  Venue: {venue}
  Pricing breakdown: {pricing_text}
  Menu: {selected_dishes}
  ...
```

Our current `contract_prompt` puts dynamic data at the top and static rules at the bottom. **This is backwards for caching.** Static content should come first in the prompt so the cache prefix is as long as possible.

**Estimated saving:** The static portion (system prompt + format rules + policies) is ~600-800 tokens per call. After the cache warms up (~2-3 contracts), those tokens cost 90% less. For 100 contracts/day: saves ~$0.07/day (small in absolute terms but free to implement).

#### 2. `asyncio.gather` for Pricing + Prompt Construction (Low effort, ~9% latency win)

Currently sequential:
```python
pricing = await calculate_event_pricing(...)   # ~200ms DB call
# Then prompt is built with pricing data
```

`calculate_event_pricing` and the static parts of `contract_prompt` (system persona, format rules, client name/date/venue) are independent. They can run concurrently:

```python
pricing, static_prompt_parts = await asyncio.gather(
    calculate_event_pricing(...),
    build_static_contract_parts(slots),
)
contract_prompt = finalize_prompt(static_prompt_parts, pricing)
```

Saves ~200ms per contract generation (the DB call is fully hidden behind prompt assembly).

#### 3. Streaming Contract to Frontend (High UX impact, medium effort)

Contracts are 2,000-4,000 tokens of output (~8-15 seconds at gpt-4o-mini speed). Users see nothing until completion.

**Streaming reduces perceived wait by up to 70%** — users see the contract sections appear progressively rather than a blank screen.

FastAPI + LangGraph streaming pattern:
```python
@app.post("/contract/stream")
async def stream_contract(request):
    async def generate():
        async for chunk in graph.astream_events(state, stream_mode="messages"):
            yield f"data: {json.dumps(chunk)}\n\n"
    return StreamingResponse(generate(), media_type="text/event-stream")
```

This requires frontend support for SSE (Server-Sent Events) — the Next.js frontend can consume this natively.

**Current blocker:** The existing `/chat` endpoint returns a single response. Streaming needs a separate `/contract/stream` endpoint or modifying the existing one to support SSE for contract-only turns.

#### 4. Semantic Caching for Repeat Contracts (Long-term, after 50+ contracts)

After generating 50+ contracts, similar events (same venue, similar guest counts, overlapping menus) can be matched via embedding similarity and the cached contract returned with slot substitutions.

Research shows 61-68% cache hit rate for semantically similar queries. For a catering company with repeat venues and standard menus, this could be significant.

**Tools:** GPTCache (open source), Redis Semantic Cache, or a simple cosine similarity check on slot embeddings.

**Not recommended yet** — premature without production traffic data.

---

### Contract Generation: Recommended Action Order

| # | Action | Effort | Impact |
|---|---|---|---|
| 1 | Move static contract sections to top of prompt (cache ordering) | 30 min | 90% cost reduction on static tokens |
| 2 | Add `asyncio.gather` for pricing + prompt construction | 1 hr | ~200ms latency reduction |
| 3 | Add post-generation slot value presence check (hallucination guard) | 1 hr | Reliability |
| 4 | Streaming endpoint for contract output | 1 day | UX — eliminates blank wait screen |
| 5 | Semantic caching (post-50 contracts) | 2 days | 15-30% cost reduction at volume |

---

## 10. Sources

- [Zero-shot Slot Filling in the Age of LLMs (COLING 2025)](https://arxiv.org/html/2411.18980v1)
- [AutoTOD: Zero-Shot Autonomous TOD Agent (ACL 2024)](https://aclanthology.org/2024.acl-long.152/)
- [HierTOD: Hierarchical Goals for TOD](https://arxiv.org/html/2411.07152)
- [OpenAI Structured Outputs (100% schema compliance)](https://developers.openai.com/api/docs/guides/structured-outputs)
- [Instructor: Structured LLM Outputs](https://python.useinstructor.com/)
- [LangGraph Persistence Patterns](https://www.baihezi.com/mirrors/langgraph/how-tos/persistence/index.html)
- [Prompt Caching: 90% Cost Reduction](https://aisdr.com/blog/reduce-llm-costs-prompt-caching/)
- [LLM Token Optimization Guide (Redis)](https://redis.io/blog/llm-token-optimization-speed-up-apps/)
- [Retries, Fallbacks, Circuit Breakers in LLM Apps](https://portkey.ai/blog/retries-fallbacks-and-circuit-breakers-in-llm-apps/)
- [LLM Infinite Loop Patterns (GDELT)](https://blog.gdeltproject.org/llm-infinite-loops-in-llm-entity-extraction-when-temperature-basic-prompt-engineering-cant-fix-things/)
- [Guardrails AI $7.5M Seed (2024)](https://www.globenewswire.com/news-release/2024/02/15/2830261/0/en/Guardrails-AI-is-Solving-the-LLM-Reliability-Problem-for-AI-Developers-With-$7.5-Million-in-Seed-Funding)
- [Anyscale: 23x LLM Throughput with Continuous Batching](https://www.anyscale.com/blog/continuous-batching-llm-inference)
- [Microsoft Copilot Studio: Slot-Filling Best Practices](https://learn.microsoft.com/en-us/microsoft-copilot-studio/guidance/slot-filling-best-practices)
- [Why I Switched to Async LangGraph (50x concurrency)](https://nishant-mishra.medium.com/why-i-switched-to-async-langchain-and-langgraph-and-you-should-too-c30635c9cf19)
