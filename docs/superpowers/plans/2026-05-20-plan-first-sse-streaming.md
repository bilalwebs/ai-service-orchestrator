# Plan-First SSE Streaming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace raw LangGraph SSE dumps with a typed plan-first event protocol so the mobile UI receives all 9 steps immediately and animates them to completion as the agent executes.

**Architecture:** The backend streaming endpoint manually orchestrates the 5 LangGraph node functions (instead of `astream`) so it can emit `connected → plan → step_start → step_complete → booking_ready → [DONE]` events with full control over timing. The mobile client dispatches on the `event` key and mutates the pre-populated trace list in place.

**Tech Stack:** FastAPI + LangGraph + Ollama (qwen2.5:3b) · Kotlin Multiplatform + Ktor + Jetpack Compose · Server-Sent Events

---

## File Map

| File | Repo | Change |
|---|---|---|
| `routers/requests.py` | backend | Rewrite `event_stream()`, add `_get_plan_message()` + `FIXED_PLAN_STEPS` |
| `core/src/commonMain/kotlin/com/corestack/khidmatai/core/domain/model/ServiceModels.kt` | mobile | Add `planMessage: String? = null` to `RequestState.Processing` |
| `core/src/commonMain/kotlin/com/corestack/khidmatai/core/data/repository/ApiServiceRepositoryImpl.kt` | mobile | Replace SSE parsing block in `submitRequestStream()` |
| `shared/src/commonMain/kotlin/com/corestack/khidmatai/ui/processing/ProcessingScreen.kt` | mobile | Show `planMessage` instead of static `processingDesc` |

---

## Task 1: Add `planMessage` to `RequestState.Processing`

**Files:**
- Modify: `core/src/commonMain/kotlin/com/corestack/khidmatai/core/domain/model/ServiceModels.kt:66`

- [ ] **Step 1: Edit `RequestState.Processing`**

  Replace line 66:
  ```kotlin
  data class Processing(val traces: List<com.corestack.khidmatai.core.domain.model.TraceItem>) : RequestState()
  ```
  With:
  ```kotlin
  data class Processing(
      val traces: List<com.corestack.khidmatai.core.domain.model.TraceItem>,
      val planMessage: String? = null
  ) : RequestState()
  ```

- [ ] **Step 2: Verify the project still compiles**

  In the mobile repo root (`/Users/zeeshanali/Documents/Hackathons/ai seekho/KhidmatAI`):
  ```bash
  ./gradlew :core:compileKotlinMetadata --no-daemon 2>&1 | tail -20
  ```
  Expected: `BUILD SUCCESSFUL` (all existing call sites pass only `traces`, the new param defaults to `null`)

- [ ] **Step 3: Commit**

  ```bash
  git add core/src/commonMain/kotlin/com/corestack/khidmatai/core/domain/model/ServiceModels.kt
  git commit -m "feat: add planMessage to RequestState.Processing"
  ```

---

## Task 2: Rewrite the backend streaming endpoint

**Files:**
- Modify: `routers/requests.py`

This task rewrites `event_stream()` inside `create_service_request_stream` and adds two module-level items: `FIXED_PLAN_STEPS` and `_get_plan_message()`.

- [ ] **Step 1: Update the import line from `agents.graph`**

  Replace the existing import at the top of `routers/requests.py`:
  ```python
  from agents.graph import app_graph, complete_booking_node, _make_trace
  ```
  With:
  ```python
  from agents.graph import (
      app_graph, complete_booking_node, _make_trace, llm,
      intent_parser_node, provider_discovery_node,
      ranking_node, booking_execution_node, followup_node,
  )
  from langchain_core.messages import HumanMessage, SystemMessage
  ```

- [ ] **Step 2: Add `FIXED_PLAN_STEPS` and `_get_plan_message()` after the `WORKFLOW_TIMEOUT_SECONDS` line**

  Find the line:
  ```python
  # Global registry to track active asyncio tasks by request_id
  active_tasks: Dict[str, asyncio.Task] = {}
  ```
  Insert before it:
  ```python
  FIXED_PLAN_STEPS = [
      {"stage": "intent_detection",       "status": "waiting"},
      {"stage": "llm_analysis",           "status": "waiting"},
      {"stage": "service_classification", "status": "waiting"},
      {"stage": "urgency_classification", "status": "waiting"},
      {"stage": "provider_discovery",     "status": "waiting"},
      {"stage": "provider_ranking",       "status": "waiting"},
      {"stage": "provider_selection",     "status": "waiting"},
      {"stage": "booking_execution",      "status": "waiting"},
      {"stage": "followup",               "status": "waiting"},
  ]


  async def _get_plan_message(query: str) -> str:
      """Quick LLM call: one warm sentence in the same language as query."""
      try:
          response = await asyncio.wait_for(
              llm.ainvoke([
                  SystemMessage(content=(
                      "You are an AI assistant for a home services booking app in Pakistan.\n"
                      "Given a user's service request, write ONE brief sentence (under 15 words) "
                      "in the SAME language/script as the query.\n"
                      "Acknowledge warmly and say what you will do. Return ONLY the sentence.\n\n"
                      "Examples:\n"
                      "Query: Mujhe kal subah G-13 mein AC technician chahiye\n"
                      "Response: G-13 mein aap ke liye kal subah AC technician dhundh raha hoon.\n\n"
                      "Query: I need an electrician urgently\n"
                      "Response: Finding a certified electrician near you right now.\n\n"
                      "Query: plumber chahiye leak hai\n"
                      "Response: Aap ke area mein trusted plumber abhi dhundh raha hoon."
                  )),
                  HumanMessage(content=f"Query: {query}"),
              ]),
              timeout=15.0,
          )
          return response.content.strip()
      except Exception:
          return "Finding the best service provider for you, please wait..."


  # Global registry to track active asyncio tasks by request_id
  active_tasks: Dict[str, asyncio.Task] = {}
  ```

- [ ] **Step 3: Replace `event_stream()` inside `create_service_request_stream`**

  Find the entire `async def event_stream():` block inside `create_service_request_stream` (currently lines ~234–270) and replace it completely with:

  ```python
      async def event_stream():
          active_tasks[request_id] = asyncio.current_task()
          final_state = dict(initial_state)
          try:
              # ── 1. Connected ────────────────────────────────────────────────
              yield f"data: {json.dumps({'event': 'connected', 'request_id': request_id})}\n\n"

              # ── 2. Plan message (quick LLM, 15s timeout → fallback) ─────────
              plan_message = await _get_plan_message(request.raw_query)
              yield f"data: {json.dumps({'event': 'plan', 'message': plan_message, 'steps': FIXED_PLAN_STEPS})}\n\n"

              # ── 3. Intent parsing ────────────────────────────────────────────
              yield f"data: {json.dumps({'event': 'step_start', 'stage': 'intent_detection'})}\n\n"
              intent_result = await intent_parser_node(final_state)
              final_state = {**final_state, **intent_result}
              intent_val   = final_state.get("intent")
              intent_str   = intent_val.value if intent_val else "unknown"
              lang_str     = final_state.get("language", "en")
              urgency_str  = final_state.get("urgency", "medium")
              yield f"data: {json.dumps({'event': 'step_complete', 'stage': 'intent_detection',       'message': 'Request understood'})}\n\n"
              yield f"data: {json.dumps({'event': 'step_complete', 'stage': 'llm_analysis',           'message': f'Language: {lang_str}'})}\n\n"
              yield f"data: {json.dumps({'event': 'step_complete', 'stage': 'service_classification', 'message': f'Service: {intent_str}'})}\n\n"
              yield f"data: {json.dumps({'event': 'step_complete', 'stage': 'urgency_classification', 'message': f'Urgency: {urgency_str}'})}\n\n"

              # ── 4. Provider discovery ────────────────────────────────────────
              yield f"data: {json.dumps({'event': 'step_start', 'stage': 'provider_discovery'})}\n\n"
              discovery_result = await provider_discovery_node(final_state)
              final_state = {**final_state, **discovery_result}
              provider_count = len(final_state.get("providers", []))
              yield f"data: {json.dumps({'event': 'step_complete', 'stage': 'provider_discovery', 'message': f'{provider_count} providers found nearby'})}\n\n"

              # ── 5. Ranking → two step_completes ──────────────────────────────
              yield f"data: {json.dumps({'event': 'step_start', 'stage': 'provider_ranking'})}\n\n"
              ranking_result = await ranking_node(final_state)
              final_state    = {**final_state, **ranking_result}
              selected       = final_state.get("selected_provider")
              selected_name  = selected.get("name") if selected else "None available"
              yield f"data: {json.dumps({'event': 'step_complete', 'stage': 'provider_ranking',  'message': 'Providers ranked by rating and distance'})}\n\n"
              yield f"data: {json.dumps({'event': 'step_complete', 'stage': 'provider_selection', 'message': f'Selected: {selected_name}'})}\n\n"

              # ── 6. Booking ───────────────────────────────────────────────────
              yield f"data: {json.dumps({'event': 'step_start', 'stage': 'booking_execution'})}\n\n"
              booking_result = await booking_execution_node(final_state)
              final_state    = {**final_state, **booking_result}
              booking        = final_state.get("booking")
              if booking:
                  slot_str = booking.scheduled_at.strftime("%I:%M %p, %d %b")
                  yield f"data: {json.dumps({'event': 'step_complete', 'stage': 'booking_execution', 'message': f'Slot booked: {slot_str}'})}\n\n"
                  yield f"data: {json.dumps({'event': 'booking_ready', 'booking_id': booking.id})}\n\n"
              else:
                  yield f"data: {json.dumps({'event': 'step_complete', 'stage': 'booking_execution', 'message': 'No provider available in range'})}\n\n"

              # ── 7. Follow-up ─────────────────────────────────────────────────
              yield f"data: {json.dumps({'event': 'step_start', 'stage': 'followup'})}\n\n"
              followup_result = await followup_node(final_state)
              final_state     = {**final_state, **followup_result}
              yield f"data: {json.dumps({'event': 'step_complete', 'stage': 'followup', 'message': 'Reminder scheduled 1 hour before appointment'})}\n\n"

              log_interaction(
                  request_id=request_id,
                  stage="workflow_completed",
                  message="Stream workflow completed successfully",
                  status="success",
                  booking_id=booking.id if booking else None,
                  intent=intent_str,
              )

          except asyncio.CancelledError:
              log_interaction(
                  request_id=request_id,
                  stage="workflow_cancelled",
                  message="LangGraph stream cancelled by user request",
                  status="cancelled",
              )
              db_service.log_request(AdminRequestLog(
                  id=request_id,
                  user_id=request.user_id,
                  raw_query=request.raw_query,
                  urgency=request.urgency.value,
                  intent=None,
                  language="en",
                  status="cancelled",
                  booking_id=None,
                  trace=initial_state.get("trace", []),
                  created_at=datetime.now().isoformat()
              ))
              yield f"data: {json.dumps({'event': 'cancelled', 'detail': 'Request cancelled by user'})}\n\n"
              raise
          except asyncio.TimeoutError:
              yield f"data: {json.dumps({'event': 'error', 'detail': 'Stream timed out'})}\n\n"
          except Exception as e:
              yield f"data: {json.dumps({'event': 'error', 'detail': str(e)})}\n\n"
          finally:
              active_tasks.pop(request_id, None)
              intent_val = final_state.get("intent")
              booking    = final_state.get("booking")
              db_service.log_request(AdminRequestLog(
                  id=request_id,
                  user_id=request.user_id,
                  raw_query=request.raw_query,
                  urgency=request.urgency.value,
                  intent=intent_val.value if intent_val else None,
                  language=final_state.get("language", "en"),
                  status="success" if booking else "no_provider",
                  booking_id=booking.id if booking else None,
                  trace=final_state.get("trace", []),
                  created_at=datetime.now().isoformat()
              ))
              yield "data: [DONE]\n\n"
  ```

- [ ] **Step 4: Verify the backend starts without import errors**

  From the backend repo root:
  ```bash
  cd "/Users/zeeshanali/Documents/Hackathons/ai seekho/ai-service-orchestrator"
  python -c "from routers.requests import router; print('OK')"
  ```
  Expected: `OK`

- [ ] **Step 5: Smoke-test the stream endpoint with curl**

  With the FastAPI server running (`uvicorn main:app --reload`), in another terminal:
  ```bash
  curl -N -X POST http://localhost:8000/requests/stream \
    -H "Content-Type: application/json" \
    -d '{"raw_query":"test","user_id":"u1","urgency":"medium","location":{"address":"G-13","lat":33.6333,"lng":72.9667}}' \
    2>/dev/null | head -5
  ```
  Expected first line: `data: {"event": "connected", "request_id": "..."}` within 1 second.
  Expected second line (after ~15s max): `data: {"event": "plan", "message": "...", "steps": [...]}`

- [ ] **Step 6: Commit**

  ```bash
  git add routers/requests.py
  git commit -m "feat: rewrite streaming endpoint with plan-first typed SSE events"
  ```

---

## Task 3: Rewrite mobile SSE parsing in `ApiServiceRepositoryImpl`

**Files:**
- Modify: `core/src/commonMain/kotlin/com/corestack/khidmatai/core/data/repository/ApiServiceRepositoryImpl.kt`

- [ ] **Step 1: Replace `submitRequestStream()` body entirely**

  Replace the entire function body from the opening brace of `override fun submitRequestStream(...)` through its closing brace (lines 102–206) with:

  ```kotlin
  override fun submitRequestStream(query: String, location: String, urgency: String): Flow<RequestState> = flow {
      emit(RequestState.Processing(emptyList()))

      try {
          val body = ServiceRequestBody(
              userId = getUserId(),
              rawQuery = query,
              urgency = urgency,
              location = LocationBody(address = location, lat = DEFAULT_LAT, lng = DEFAULT_LNG)
          )

          val accumulatedTraces = mutableListOf<TraceItem>()
          var planMessage: String? = null
          var connectedRequestId: String? = null
          var bookingId: String? = null
          var errorOccurred = false

          httpClient.preparePost("$BASE_URL/requests/stream") {
              contentType(ContentType.Application.Json)
              setBody(body)
          }.execute { response ->
              val channel = response.bodyAsChannel()
              while (!channel.isClosedForRead) {
                  val line = channel.readUTF8Line() ?: break
                  if (!line.startsWith("data: ")) continue
                  val rawData = line.substring(6).trim()
                  if (rawData == "[DONE]") break

                  val jsonObject = runCatching {
                      Json.parseToJsonElement(rawData).jsonObject
                  }.getOrNull() ?: continue

                  when (jsonObject["event"]?.jsonPrimitive?.content) {
                      "connected" -> {
                          connectedRequestId = jsonObject["request_id"]?.jsonPrimitive?.content
                      }
                      "plan" -> {
                          planMessage = jsonObject["message"]?.jsonPrimitive?.content
                          val steps = jsonObject["steps"]?.jsonArray
                          if (steps != null) {
                              accumulatedTraces.clear()
                              steps.forEachIndexed { index, stepElem ->
                                  val stepObj = stepElem.jsonObject
                                  val stage = stepObj["stage"]?.jsonPrimitive?.content
                                  if (stage != null) {
                                      accumulatedTraces.add(
                                          TraceItem(
                                              stage = stage,
                                              message = "",
                                              status = "waiting",
                                              // First item carries requestId so ViewModel can use it for cancel
                                              requestId = if (index == 0) connectedRequestId else null
                                          )
                                      )
                                  }
                              }
                              emit(RequestState.Processing(accumulatedTraces.toList(), planMessage))
                          }
                      }
                      "step_start" -> {
                          val stage = jsonObject["stage"]?.jsonPrimitive?.content
                          if (stage != null) {
                              val idx = accumulatedTraces.indexOfFirst { it.stage == stage }
                              if (idx >= 0) {
                                  accumulatedTraces[idx] = accumulatedTraces[idx].copy(status = "pending")
                                  emit(RequestState.Processing(accumulatedTraces.toList(), planMessage))
                              }
                          }
                      }
                      "step_complete" -> {
                          val stage = jsonObject["stage"]?.jsonPrimitive?.content
                          val message = jsonObject["message"]?.jsonPrimitive?.content ?: ""
                          if (stage != null) {
                              val idx = accumulatedTraces.indexOfFirst { it.stage == stage }
                              if (idx >= 0) {
                                  accumulatedTraces[idx] = accumulatedTraces[idx].copy(
                                      status = "completed",
                                      message = message
                                  )
                                  emit(RequestState.Processing(accumulatedTraces.toList(), planMessage))
                              }
                          }
                      }
                      "booking_ready" -> {
                          bookingId = jsonObject["booking_id"]?.jsonPrimitive?.content
                      }
                      "error" -> {
                          val detail = jsonObject["detail"]?.jsonPrimitive?.content ?: "Unknown error"
                          errorOccurred = true
                          emit(RequestState.Error(detail))
                          return@execute
                      }
                      else -> { /* connected, cancelled, unknown — ignore */ }
                  }
              }
          }

          if (!errorOccurred) {
              val finalBookingId = bookingId
              if (finalBookingId != null) {
                  val bookingDetails = getBookingDetails(finalBookingId)
                  val serviceResult = ServiceResult(
                      success = true,
                      status = bookingDetails.status,
                      message = "Booking confirmed successfully",
                      bookingId = bookingDetails.id,
                      detectedService = bookingDetails.serviceType,
                      detectedLanguage = "en",
                      urgency = urgency,
                      provider = Provider(
                          id = bookingDetails.providerId,
                          name = "Provider",
                          phone = "",
                          rating = 5.0f,
                          distanceKm = 0.0f,
                          experienceYears = 0,
                          reasoning = "Assigned to provider"
                      ),
                      appointment = Appointment(
                          bookingId = bookingDetails.id,
                          timeDisplay = bookingDetails.scheduledAt,
                          address = bookingDetails.address,
                          costPerHour = bookingDetails.totalCost?.toInt() ?: 0,
                          currency = "PKR"
                      ),
                      nextSteps = emptyList(),
                      trace = accumulatedTraces.toList(),
                      followup = null,
                      error = null
                  )
                  emit(RequestState.Success(serviceResult))
              } else {
                  emit(RequestState.Error("No booking was executed."))
              }
          }

      } catch (e: Exception) {
          emit(RequestState.Error(e.message ?: "Network error. Please check your connection."))
      }
  }
  ```

- [ ] **Step 2: Verify the module compiles**

  ```bash
  ./gradlew :core:compileKotlinMetadata --no-daemon 2>&1 | tail -20
  ```
  Expected: `BUILD SUCCESSFUL`

- [ ] **Step 3: Commit**

  ```bash
  git add core/src/commonMain/kotlin/com/corestack/khidmatai/core/data/repository/ApiServiceRepositoryImpl.kt
  git commit -m "feat: rewrite SSE client to handle typed plan-first events"
  ```

---

## Task 4: Show LLM plan message in ProcessingScreen

**Files:**
- Modify: `shared/src/commonMain/kotlin/com/corestack/khidmatai/ui/processing/ProcessingScreen.kt`

- [ ] **Step 1: Replace the static `processingDesc` text with dynamic plan message**

  Find line 85:
  ```kotlin
  Text(text = s.processingDesc, style = AppTypography.bodySmall, color = TextSecondary)
  ```
  Replace with:
  ```kotlin
  val planMsg = (requestState as? RequestState.Processing)?.planMessage
  Text(
      text = planMsg ?: s.processingDesc,
      style = AppTypography.bodySmall,
      color = TextSecondary
  )
  ```

- [ ] **Step 2: Verify the shared module compiles**

  ```bash
  ./gradlew :shared:compileKotlinMetadata --no-daemon 2>&1 | tail -20
  ```
  Expected: `BUILD SUCCESSFUL`

- [ ] **Step 3: Commit**

  ```bash
  git add shared/src/commonMain/kotlin/com/corestack/khidmatai/ui/processing/ProcessingScreen.kt
  git commit -m "feat: show LLM plan message in ProcessingScreen"
  ```

---

## Task 5: End-to-end verification

- [ ] **Step 1: Start the backend**

  ```bash
  cd "/Users/zeeshanali/Documents/Hackathons/ai seekho/ai-service-orchestrator"
  uvicorn main:app --reload --port 8000
  ```

- [ ] **Step 2: Verify the stream event sequence with curl**

  In a second terminal:
  ```bash
  curl -N -X POST http://localhost:8000/requests/stream \
    -H "Content-Type: application/json" \
    -d '{"raw_query":"Mujhe AC technician chahiye G-13 mein","user_id":"u1","urgency":"medium","location":{"address":"G-13, Islamabad","lat":33.6333,"lng":72.9667}}' \
    2>/dev/null
  ```

  Expected sequence (one line per SSE frame):
  ```
  data: {"event": "connected", "request_id": "..."}
  data: {"event": "plan", "message": "G-13 mein aap ke liye...", "steps": [...9 steps...]}
  data: {"event": "step_start", "stage": "intent_detection"}
  data: {"event": "step_complete", "stage": "intent_detection", "message": "Request understood"}
  data: {"event": "step_complete", "stage": "llm_analysis", "message": "Language: roman_urdu"}
  data: {"event": "step_complete", "stage": "service_classification", "message": "Service: ac_technician"}
  data: {"event": "step_complete", "stage": "urgency_classification", "message": "Urgency: medium"}
  data: {"event": "step_start", "stage": "provider_discovery"}
  data: {"event": "step_complete", "stage": "provider_discovery", "message": "N providers found nearby"}
  data: {"event": "step_start", "stage": "provider_ranking"}
  data: {"event": "step_complete", "stage": "provider_ranking", ...}
  data: {"event": "step_complete", "stage": "provider_selection", ...}
  data: {"event": "step_start", "stage": "booking_execution"}
  data: {"event": "step_complete", "stage": "booking_execution", "message": "Slot booked: ..."}
  data: {"event": "booking_ready", "booking_id": "BK-..."}
  data: {"event": "step_start", "stage": "followup"}
  data: {"event": "step_complete", "stage": "followup", ...}
  data: [DONE]
  ```

- [ ] **Step 3: Build and run the Android app**

  ```bash
  cd "/Users/zeeshanali/Documents/Hackathons/ai seekho/KhidmatAI"
  ./gradlew :androidApp:assembleDebug --no-daemon 2>&1 | tail -30
  ```
  Expected: `BUILD SUCCESSFUL`

  Install and run on emulator/device. Submit a service request. Verify:
  - ProcessingScreen appears immediately showing all 9 steps in waiting state
  - LLM plan message appears below the title (replaces static description)
  - Steps animate from waiting → pending → completed one by one
  - Progress bar advances as steps complete
  - App navigates to success screen after booking confirmation
