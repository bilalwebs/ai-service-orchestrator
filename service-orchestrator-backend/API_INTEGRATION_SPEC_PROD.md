# 📄 API INTEGRATION SPECIFICATION (PRODUCTION READY)

## 📌 Project: AI Service Orchestrator – Frontend Integration (Production)

---

### 1. 🔗 BACKEND BASE CONFIG

```text id="base1"
BASE_URL = https://api.myservice.com   # Production endpoint (HTTPS)
```

> **Note:** All requests must use HTTPS. CORS is locked to the approved frontend origins (see section 2).

---

### 2. 📡 AVAILABLE API ENDPOINTS

#### 2.1 Create Service Request

```text id="ep1"
POST /requests/
```
**Purpose:**
- Accepts a service request payload.
- Executes the LangGraph workflow to find and rank providers.
- Creates a booking record and returns the full trace for UI debugging.

#### 2.2 Complete Booking

```text id="ep2"
POST /requests/bookings/{booking_id}/complete
```
**Purpose:**
- Marks a booking as completed.
- Triggers post‑booking actions (e.g., notifications, analytics).

---

### 3. 🔐 AUTHENTICATION & AUTHORIZATION

- All endpoints require a **Bearer JWT** in the `Authorization` header.
- Token must be issued by the central Auth service and contain the `user_id` claim.
- Tokens are verified on each request; expired or missing tokens return **401 Unauthorized**.

```http
Authorization: Bearer <jwt-token>
```

---

### 4. 📥 REQUEST PAYLOAD (Frontend → Backend)

```json id="req1"
{
  "raw_query": "AC repair karna hai jaldi",
  "user_id": "user123",
  "urgency": "high",
  "location": {
    "address": "Karachi, Gulshan",
    "lat": 24.92,
    "lng": 67.03
  },
  "language_detected": "en"
}
```
> The `user_id` must match the subject claim in the JWT; otherwise a **403 Forbidden** is returned.

---

### 5. 📤 RESPONSE STRUCTURE (Backend → Frontend)

```json id="res1"
{
  "success": true,
  "data": {
    "status": "success",
    "message": "Booking confirmed",
    "provider": {
      "id": "p1",
      "name": "Kamran Khan",
      "phone": "+92xxxxxxxx",
      "rating": 4.7,
      "distance_km": 1.5
    },
    "appointment": {
      "booking_id": "BK-123456",
      "scheduled_time_display": "12:00 AM, 18 May"
    },
    "next_steps": [],
    "followup": {},
    "trace": []
  },
  "meta": {
    "booking_id": "BK-123456",
    "detected_intent": "ac_technician",
    "urgency": "high",
    "detected_language": "roman_urdu"
  }
}
```
#### 5.1 Field Explanation (Production)
- **success**: `true` if request succeeded, otherwise `false`.
- **data.status**: High‑level workflow status (`success`, `partial`, `failed`).
- **data.message**: UI‑friendly message for end users.
- **data.provider**: Provider details used for contact and display.
- **data.appointment.booking_id**: Immutable booking identifier.
- **data.appointment.scheduled_time_display**: Pre‑formatted string respecting user locale.
- **data.next_steps**: Optional actions (e.g., payment, additional info).
- **data.followup**: Any follow‑up instructions (reminders, surveys).
- **data.trace**: Debug trace; may be omitted in minimal responses via `?trace=0` query param.
- **meta**: Convenience fields for UI filtering and analytics.

---

### 6. 🧠 FRONTEND INTEGRATION FLOW (Production)

#### 6.1 API CALL (Fetch)
```js id="js1"
async function createRequest(payload, token) {
  const response = await fetch(`${BASE_URL}/requests/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${token}`
    },
    body: JSON.stringify(payload)
  });
  return await response.json();
}
```

#### 6.2 Data Extraction
```text id="extract1"
Provider Name → data.data.provider.name
Phone → data.data.provider.phone
Rating → data.data.provider.rating
Booking ID → data.data.appointment.booking_id
Appointment Time → data.data.appointment.scheduled_time_display
Status Message → data.data.message
```

#### 6.3 Rendering UI
- Show loading states (see section 9).
- Populate UI components with the extracted values.
- Respect error handling (section 8).

---

### 7. 🔁 BOOKING COMPLETION FLOW

```js id="bk1"
async function completeBooking(bookingId, token) {
  const response = await fetch(`${BASE_URL}/requests/bookings/${bookingId}/complete`, {
    method: "POST",
    headers: { "Authorization": `Bearer ${token}` }
  });
  return await response.json();
}
```
**Success response:** `{ "success": true, "message": "Booking marked as completed" }`

---

### 8. ⚠️ ERROR HANDLING

| HTTP Status | Meaning | Frontend Action |
|-------------|---------|-----------------|
| 400 | Invalid request (malformed JSON) | Show "Invalid request – please try again."
| 401 | Missing/invalid JWT | Redirect to login flow.
| 403 | Authenticated but not authorized (user_id mismatch) | Show "You are not allowed to perform this action."
| 422 | Validation error – missing required fields | Highlight missing fields in the form.
| 500 | Internal server error | Show generic "Something went wrong, please try later" and log for support.
| Network error | No response / timeout | Show "Network error – check your connection" and provide retry.

---

### 9. ⏳ LOADING STATES (Production UI)
- "Processing request…"
- "Finding providers…"
- "Ranking providers…"
- "Creating booking…"
- "Finalizing response…"

---

### 10. 📊 OPTIONAL / ADVANCED FEATURES
- **Trace Timeline**: UI component that visualises `data.trace` for debugging.
- **Provider Ranking List**: Show all candidates with scores.
- **Booking History**: Paginated endpoint `GET /bookings?user_id={}` (not covered here).
- **Auto‑Refresh**: Poll `GET /bookings/{booking_id}` every 30 s while a booking is pending.

---

### 11. 📜 RULES & NON‑FUNCTIONAL REQUIREMENTS
- Do **NOT** modify backend logic.
- All requests must be over **HTTPS**.
- CORS is restricted to the approved production origins (e.g., `https://app.myservice.com`).
- Rate‑limit: **30 requests per minute per user** (returns 429 on excess).
- Monitoring: Backend emits Prometheus metrics for request latency and error rates.
- Logging: Sensitive data (e.g., phone numbers) are masked in logs.

---

### 12. 🎯 FINAL OBJECTIVE
The frontend must be able to:
- Authenticate using a JWT.
- Send a correctly‑shaped service request.
- Handle all defined loading, success, and error states.
- Display provider and booking information reliably.
- Complete a booking via the dedicated endpoint.
- Optionally surface trace/debug information for power users.

---

# ✅ END OF SPEC