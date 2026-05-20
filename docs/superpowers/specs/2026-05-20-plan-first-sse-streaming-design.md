# Plan-First SSE Streaming Design

**Date:** 2026-05-20  
**Project:** KhidmatAI — AI Service Orchestrator (Hackathon)  
**Scope:** Backend streaming endpoint + mobile SSE client

---

## Problem

The `POST /requests/stream` endpoint emits raw LangGraph node state dumps
(`{"intent_parser": {...}, "trace": [...]}`) which the mobile client cannot
reliably receive because:

1. No data is sent until Ollama completes the first LLM call (~30–60s with
   `qwen2.5:3b`). OkHttp's default 10s read timeout kills the connection first.
2. Backend logs show `workflow_cancelled` — confirmed client disconnect.
3. Even if the connection survived, the mobile's trace stage names
   (`intent_detection`, `llm_analysis`, etc.) don't match the backend's
   (`intent_understanding`, `provider_search`, etc.).

The fix resolves all three issues by switching to a clean typed-event protocol
and manually orchestrating nodes so we can emit events immediately.

---

## Goals

- Mobile receives the first SSE frame within ~1s of connecting (before any LLM call)
- UI shows all 9 steps in "waiting" state immediately, then animates them to
  "pending" → "completed" as the agent works
- A personalized LLM-generated sentence describes what the agent will do
- Stage names in events match exactly what `TraceRowComponent` expects
- Non-streaming endpoint (`POST /requests/`) is unchanged

---

## SSE Event Protocol

Every frame is `data: <JSON>\n\n`. All JSON payloads contain an `"event"` key.

| Event | When | Payload |
|---|---|---|
| `connected` | Immediately on stream open | `{event, request_id}` |
| `plan` | After plan-message LLM call | `{event, message, steps: [{stage, status:"waiting"}]}` |
| `step_start` | Before each node runs | `{event, stage}` |
| `step_complete` | After each node finishes | `{event, stage, message}` |
| `booking_ready` | When booking is created | `{event, booking_id}` |
| `error` | On unhandled exception | `{event, detail}` |
| `[DONE]` | End of stream | text sentinel (not JSON) |

Raw LangGraph `{node_name: state_delta}` dumps are removed from the streaming
response.

### Plan steps (fixed vocabulary, 9 stages)

```json
[
  {"stage": "intent_detection",       "status": "waiting"},
  {"stage": "llm_analysis",           "status": "waiting"},
  {"stage": "service_classification", "status": "waiting"},
  {"stage": "urgency_classification", "status": "waiting"},
  {"stage": "provider_discovery",     "status": "waiting"},
  {"stage": "provider_ranking",       "status": "waiting"},
  {"stage": "provider_selection",     "status": "waiting"},
  {"stage": "booking_execution",      "status": "waiting"},
  {"stage": "followup",               "status": "waiting"}
]
```

---

## Backend Changes (`routers/requests.py`)

### Plan message LLM call

A new helper `_get_plan_message(query: str) -> str` makes a single short LLM
call asking for a 1-sentence acknowledgment in the same language as the query.

System prompt (paraphrased):
> Given a service request, write ONE sentence (≤15 words) in the same
> language acknowledging it. Example: "AC repair ke liye certified technician
> dhundh raha hoon, jaldi book karunga."

Wrapped in `asyncio.wait_for(timeout=15)` with fallback:
`"Finding the best provider for you, please wait..."`

### `event_stream()` rewrite

Replaces `app_graph.astream()` with direct node function calls:

```
1.  yield connected_event
2.  plan_message = await _get_plan_message(query)          # 15s timeout
3.  yield plan_event(plan_message, FIXED_STEPS)
4.  yield step_start("intent_detection")
5.  state = {**state, **await intent_parser_node(state)}
6.  yield step_complete("intent_detection", f"Detected: {intent}")
7.  yield step_complete("llm_analysis",           f"Language: {lang}")
8.  yield step_complete("service_classification", f"Service: {intent}")
9.  yield step_complete("urgency_classification", f"Urgency: {urgency}")
10. yield step_start("provider_discovery")
11. state = {**state, **await provider_discovery_node(state)}
12. yield step_complete("provider_discovery", f"{n} providers found")
13. yield step_start("provider_ranking")
14. state = {**state, **await ranking_node(state)}
15. yield step_complete("provider_ranking", "Providers ranked")
16. yield step_complete("provider_selection", f"Selected: {name}")
17. yield step_start("booking_execution")
18. state = {**state, **await booking_execution_node(state)}
19. yield step_complete("booking_execution", f"Slot: {time}")
20. yield booking_ready_event(booking_id)                  # if booking exists
21. yield step_start("followup")
22. state = {**state, **await followup_node(state)}
23. yield step_complete("followup", "Reminder scheduled")
24. yield "[DONE]"
```

All existing error/cancellation/timeout handling is preserved (CancelledError,
TimeoutError, generic Exception) within the same try/except/finally structure.

The `AdminRequestLog` is written after the stream ends using the final `state`.

---

## Mobile Changes

### `ServiceModels.kt`

Add optional `planMessage` to `RequestState.Processing`:

```kotlin
data class Processing(
    val traces: List<TraceItem>,
    val planMessage: String? = null
) : RequestState()
```

All existing call sites pass only `traces`; the new parameter is optional with
`null` default so no other files break.

### `ApiServiceRepositoryImpl.submitRequestStream()`

Replace the existing SSE parsing block with event-type dispatch:

```
when (event["event"]?.jsonPrimitive?.content) {
  "connected"  → ignore
  "plan"       → init accumulatedTraces from steps (status=waiting),
                  set planMessage, emit Processing(traces, planMessage)
  "step_start" → find step by stage, set status="pending", emit Processing
  "step_complete" → find step by stage, set status="completed" + message, emit Processing
  "booking_ready" → capture bookingId
  "error"      → emit Error(detail)
  null         → (LangGraph dumps, no longer sent — silently ignored)
}
```

After `[DONE]`:
- If `bookingId != null`: fetch booking → emit `Success`
- If `bookingId == null`: emit `Error("No booking was executed")`

### `ProcessingScreen.kt`

Add one new `Text` element below the existing title, showing
`(requestState as Processing).planMessage` when it is non-null/non-blank.
Style: `MaterialTheme.typography.bodyMedium`, muted color, max 2 lines.

No other UI component changes. `TraceRowComponent`, progress bar, and orb
already handle `waiting` / `pending` / `completed` statuses correctly.

---

## Files Changed

| File | Change |
|---|---|
| `routers/requests.py` | Rewrite `event_stream()`, add `_get_plan_message()` |
| `core/.../ServiceModels.kt` | Add `planMessage` to `Processing` |
| `core/.../ApiServiceRepositoryImpl.kt` | Replace SSE parsing with event dispatch |
| `shared/.../ProcessingScreen.kt` | Add plan message subtitle |

`agents/graph.py`, `AppModule.kt` — no changes required.

---

## Error / Edge Cases

| Scenario | Handling |
|---|---|
| Plan message LLM times out (>15s) | Fallback message used, stream continues |
| Ollama down entirely | `intent_parser_node` raises, caught by outer except, `error` event + `[DONE]` sent |
| No providers found | `ranking_node` sets `selected_provider=None`, `booking_execution_node` emits failed trace, stream completes with `Error` |
| Client disconnects mid-stream | `CancelledError` caught, log written, `[DONE]` sent (client already gone) |
| `qwen2.5:3b` returns malformed plan JSON | Not applicable — plan is hardcoded; only plan message comes from LLM |
