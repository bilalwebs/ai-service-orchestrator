# Frontend–Backend API Integration Contract

This document serves as the official integration contract for frontend developers connecting to the Informal Service Orchestrator API. It guarantees a highly predictable, standard JSON response format across all non-streaming endpoints.

---

## 1. The Standard Response Format

**Rule of Thumb:** Every single non-streaming endpoint returns the following structure. You should always extract your primary payload from `response.data`.

```typescript
interface APIResponse<T> {
  success: boolean;       // True if request succeeded, false otherwise
  message: string;        // Human-readable summary of the result
  data: T | null;         // The actual payload (Array, Object, or null)
  error: {                // Only populated if success === false
    type: string;
    details: any;
  } | null;
}
```

### Usage Pattern (Axios Example)
```javascript
import axios from 'axios';

// Create a reusable fetcher
const apiClient = axios.create({ baseURL: 'http://127.0.0.1:8000' });

async function fetchData() {
    try {
        const response = await apiClient.get('/services/');
        // Extract the standardized fields
        const { success, message, data, error } = response.data;
        
        if (success) {
            console.log(message); // e.g., "Services retrieved successfully"
            return data;          // This is your actual payload!
        } else {
            console.error("API Error:", error.type, error.details);
        }
    } catch (err) {
        // Handle network errors or HTTP 4xx/5xx (which are also returned in APIResponse format)
        const errorData = err.response?.data;
        console.error("Server Error:", errorData?.error?.details || err.message);
    }
}
```

---

## 2. API Endpoint Definitions

### 🩺 Health Check
- **Method:** `GET`
- **Endpoint:** `/`
- **Request Body:** None
- **Sample Response:**
```json
{
  "success": true,
  "message": "System health check",
  "data": {
    "status": "online",
    "service": "Informal Service Orchestrator",
    "version": "1.0.0",
    "db_mode": "mock"
  },
  "error": null
}
```

### 📋 List Services
- **Method:** `GET`
- **Endpoint:** `/services/`
- **Request Body:** None
- **Sample Response:**
```json
{
  "success": true,
  "message": "Services retrieved successfully",
  "data": [
    { "id": "PLUMBER", "value": "plumber", "label": "Plumber" },
    { "id": "AC_TECHNICIAN", "value": "ac_technician", "label": "Ac Technician" }
  ],
  "error": null
}
```

### 👷 List Providers
- **Method:** `GET`
- **Endpoint:** `/services/providers`
- **Request Body:** None
- **Sample Response:**
```json
{
  "success": true,
  "message": "Providers retrieved successfully",
  "data": [
    {
      "id": "p5",
      "name": "Babar Azam",
      "service_type": "plumber",
      "price_per_hour": 800.0,
      "rating": 3.8
    }
  ],
  "error": null
}
```

### 🧠 Create Service Request (Standard AI Workflow)
- **Method:** `POST`
- **Endpoint:** `/requests/`
- **Request Body:**
```json
{
  "raw_query": "Mera AC paani leak kar raha hai. Jaldi koi bhejo!",
  "user_id": "usr_999",
  "location": { "address": "North Nazimabad, Karachi", "lat": 24.9333, "lng": 67.0333 },
  "urgency": "high",
  "language_detected": "ur"
}
```
- **Sample Response:**
```json
{
  "success": true,
  "message": "Booking confirmed. Babar Azam will contact you before 04:00 AM.",
  "data": {
    "status": "success",
    "provider": { "name": "Babar Azam", "phone": "+923459998877" },
    "appointment": { "booking_id": "BK-1779227644", "scheduled_time_display": "04:00 AM" },
    "next_steps": [
      { "title": "Provider call karega", "action_value": "+923459998877", "type": "action" }
    ],
    "trace": [...]
  },
  "meta": { "booking_id": "BK-1779227644" },
  "error": null
}
```

### 📅 Get User Booking History
- **Method:** `GET`
- **Endpoint:** `/bookings/user/{user_id}`
- **Request Body:** None
- **Sample Response:**
```json
{
  "success": true,
  "message": "User bookings retrieved successfully",
  "data": [
    {
      "id": "BK-1779227644",
      "provider_id": "p5",
      "status": "CONFIRMED",
      "scheduled_at": "2026-05-20T04:00:00"
    }
  ],
  "error": null
}
```

### ✅ Complete Booking
- **Method:** `POST`
- **Endpoint:** `/bookings/{booking_id}/complete`
- **Request Body:** None
- **Sample Response:**
```json
{
  "success": true,
  "message": "Booking BK-1779227644 marked as completed.",
  "data": {
    "trace": [...]
  },
  "error": null
}
```

---

## 3. Streaming API Contract (Special Case)

> [!WARNING]
> **CRITICAL STREAMING RULE:** The `/requests/stream` endpoint **DOES NOT** use the `APIResponse` format. It returns RAW Server-Sent Events (SSE). Do not attempt to parse it as standard JSON.

- **Method:** `POST`
- **Endpoint:** `/requests/stream`
- **Request Body:** *(Same as `/requests/`)*
- **Data Format:** Server-Sent Events (`text/event-stream`)

### Frontend Usage Pattern (Native Fetch API)
To safely consume the stream, use the browser's native `fetch` API to read the response body as a stream.

```javascript
async function streamServiceRequest(payload) {
    try {
        const response = await fetch('http://127.0.0.1:8000/requests/stream', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'text/event-stream'
            },
            body: JSON.stringify(payload)
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const dataStr = line.replace('data: ', '').trim();
                    
                    // Sentinel value marking the end of the stream
                    if (dataStr === '[DONE]') {
                        console.log("Stream completely finished.");
                        return;
                    }
                    
                    try {
                        const eventObj = JSON.parse(dataStr);
                        console.log("Received AI Stream Update:", eventObj);
                        
                        // Handle safe error chunks mid-stream
                        if (eventObj.event === 'error') {
                            console.error("Stream Error:", eventObj.detail);
                            break;
                        }
                        
                        // Example: update UI progress bar
                        if (eventObj.intent_parser) setProgress("Analyzing request...");
                        if (eventObj.provider_discovery) setProgress("Finding providers...");
                        
                    } catch (e) {
                        console.warn("Could not parse chunk:", dataStr);
                    }
                }
            }
        }
    } catch (err) {
        console.error("Failed to connect to stream:", err);
    }
}
```

---

## 4. Flow Summary for Frontend Integration
1. **Always destructure** `success`, `message`, `data`, and `error` from standard requests.
2. **Handle Errors Gracefully:** If `success` is `false`, safely display `message` to the user and log `error.details` for developers.
3. **Use SSE specifically for Loading UIs:** Use `/requests/stream` ONLY when you want to show live step-by-step UI updates (like "Thinking..."). If you just need a fast final result, use `/requests/`.
4. **No architecture changes:** The backend enforces these formats globally, meaning 404s and 500s will also arrive in the exact same JSON format!
