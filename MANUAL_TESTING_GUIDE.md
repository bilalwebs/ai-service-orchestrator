# Comprehensive Step-by-Step Manual Testing Guide

This guide covers the core AI orchestrator workflow, streaming endpoints, and **every single endpoint** across the Admin, Bookings, and Services routers. Follow these steps in your Swagger UI to test the entire lifecycle of the application.

---

## Prerequisites
1. Ensure your backend is running: `uvicorn main:app --reload`
2. Open your browser to the Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 🟢 Part 1: System Health & Services (GET)

### 1.1 Health Check
- **Endpoint**: `GET /`
- **Action**: Click **Try it out** → **Execute**
- **Expected Result**: Standardized JSON with `status: "online"`.

### 1.2 List All Service Types
- **Endpoint**: `GET /services/`
- **Action**: Click **Try it out** → **Execute**.
- **Expected Result**: A standardized JSON response with `success: true` containing all enum values in `data`.

### 1.3 List All Providers
- **Endpoint**: `GET /services/providers`
- **Action**: Click **Try it out** → **Execute**.
- **Expected Result**: A standardized JSON list containing all seeded providers (e.g., Kamran Khan, Zubair Ahmed) in the `data` array.

---

## 🤖 Part 2: AI Orchestrator Workflow (POST)
*These tests trigger the LangGraph AI to parse intent, rank providers, and schedule a booking.*

### 2.1 Scenario A: High Urgency AC Repair (Urdu/English mixed)
- **Endpoint**: `POST /requests/`
- **Action**: Click **Try it out**, paste the JSON below, and click **Execute**.
**Payload:**
```json
{
  "raw_query": "Mera AC paani leak kar raha hai aur bilkul cooling nahi kar raha. Jaldi koi bhejo!",
  "user_id": "usr_999",
  "location": {
    "address": "North Nazimabad, Karachi",
    "lat": 24.9333,
    "lng": 67.0333
  },
  "urgency": "high",
  "language_detected": "ur"
}
```
**Expected Result**: The AI detects `ac_technician`, finds a provider in Karachi, and returns `status: "success"`. **Copy the `booking_id` from `"meta": { "booking_id": "..." }` for Part 3.**

### 2.2 Scenario B: Low Urgency Home Tutor
- **Endpoint**: `POST /requests/`
- **Action**: Click **Try it out**, paste the JSON below, and click **Execute**.
**Payload:**
```json
{
  "raw_query": "I need a math tutor for my son in 9th grade starting next week.",
  "user_id": "usr_888",
  "location": {
    "address": "G-11, Islamabad",
    "lat": 33.6700,
    "lng": 72.9900
  },
  "urgency": "low",
  "language_detected": "en"
}
```

---

## 📅 Part 3: Bookings Endpoints (User Facing)
*Use the `booking_id` generated in Part 2. The `user_id` is `"usr_999"`.*

### 3.1 Get User Booking History
- **Endpoint**: `GET /bookings/user/{user_id}`
- **Action**: Click **Try it out**, input `usr_999`, and click **Execute**.
- **Expected Output**: Standardized JSON with `success: true` and an array of all bookings belonging to `usr_999`.

### 3.2 Get Booking Details
- **Endpoint**: `GET /bookings/detail/{booking_id}`
- **Action**: Click **Try it out**, input your `booking_id`, and click **Execute**.
- **Expected Output**: Returns the specific booking object with `status: "CONFIRMED"`.

### 3.3 Cancel a Booking
- **Endpoint**: `POST /bookings/{booking_id}/cancel`
- **Action**: Click **Try it out**, input your `booking_id`, and click **Execute**.
- **Expected Output**: Returns the updated booking object showing `status: "CANCELLED"`.

### 3.4 Complete a Booking
- **Endpoint**: `POST /bookings/{booking_id}/complete`
- **Action**: Click **Try it out**, input your `booking_id`, and click **Execute**.
- **Expected Output**: Returns the updated booking showing `status: "COMPLETED"`.

---

## 🛠️ Part 4: Admin Controls (POST/GET/PUT/DELETE)

### 4.1 Admin: Get All Bookings Globally
- **Endpoint**: `GET /admin/bookings/`
- **Action**: Click **Try it out** → **Execute**.

### 4.2 Admin: Get Specific Booking
- **Endpoint**: `GET /admin/bookings/{booking_id}`
- **Action**: Click **Try it out**, enter `booking_id`, and execute.

### 4.3 Admin: Force Complete Booking
- **Endpoint**: `POST /admin/bookings/{booking_id}/complete`
- **Action**: Click **Try it out**, enter a `booking_id`, and execute.

### 4.4 Admin: Force Cancel Booking
- **Endpoint**: `POST /admin/bookings/{booking_id}/cancel`
- **Action**: Click **Try it out**, enter a `booking_id`, and execute.

### 4.5 Admin: Get All Providers
- **Endpoint**: `GET /admin/providers/`
- **Action**: Click **Try it out** → **Execute**.

### 4.6 Admin: Create a New Provider
- **Endpoint**: `POST /admin/providers/`
- **Action**: Click **Try it out**, paste the JSON, and **Execute**.
**Payload**:
```json
{
  "name": "Ahmed Raza",
  "service_type": "plumber",
  "rating": 5.0,
  "location": {
    "address": "DHA Phase 6, Karachi",
    "lat": 24.8103,
    "lng": 67.0494
  },
  "phone": "+923210000000",
  "price_per_hour": 1200.0,
  "experience_years": 4,
  "availability": true
}
```
**Expected Output**: The newly created provider is returned. **Copy their generated `id` (e.g., `p-a1b2c3d4`).**

### 4.7 Admin: Update a Provider
- **Endpoint**: `PUT /admin/providers/{provider_id}`
- **Action**: Click **Try it out**, input the `provider_id` from 4.6, change the `price_per_hour` in the payload to `2000.0`, and **Execute**.

### 4.8 Admin: Toggle Provider Availability
- **Endpoint**: `PATCH /admin/providers/{provider_id}/availability`
- **Action**: Click **Try it out**, input the `provider_id` from 4.6, and **Execute**.

### 4.9 Admin: Delete a Provider
- **Endpoint**: `DELETE /admin/providers/{provider_id}`
- **Action**: Click **Try it out**, input the `provider_id` from 4.6, and **Execute**.

### 4.10 Admin: Get All Request Logs (AI Audits)
- **Endpoint**: `GET /admin/requests/`
- **Action**: Click **Try it out** → **Execute**.
- **Expected Output**: Array of all `AdminRequestLog` objects detailing every AI request processed.

### 4.11 Admin: Get Specific Request Log Trace
- **Endpoint**: `GET /admin/requests/{request_id}`
- **Action**: Click **Try it out**, input a `request_id`, and **Execute**.

---

## 📡 Part 5: SSE Streaming Endpoint (Terminal Test)
*Swagger UI does not visually support Server-Sent Events (SSE) streaming nicely. Use your terminal to test this.*

Open a new terminal window and run:
```bash
curl -N -X POST "http://127.0.0.1:8000/requests/stream" \
-H "Content-Type: application/json" \
-d '{"raw_query": "Need a plumber in DHA Phase 5 Lahore quickly", "user_id": "test", "urgency": "high"}'
```

**Expected Result**: You will see live JSON chunks stream into your terminal one by one (e.g., `intent_parser` finishing, `provider_discovery` finding someone) until the stream ends with `data: [DONE]`.
