# Challenge 2: AI Service Orchestrator for Informal Economy

An advanced, multi-agent AI orchestration system built to automate the end-to-end lifecycle of informal service requests. This solution addresses the inefficiencies of the informal economy (WhatsApp messages, phone calls, informal referrals) by deploying an **Agentic AI System** powered by **Google Antigravity**, **FastAPI**, and **LangGraph**.

---

## 1. Challenge Overview & Problem Statement

The informal economy—plumbers, electricians, tutors, beauticians—operates without automation, resulting in inefficient matching and poor user experiences. Users struggle to find reliable, real-time availability.

**Our Solution:**
An end-to-end AI orchestrator that:
1. **Understands** user requests in natural language (Urdu, Roman Urdu, English).
2. **Identifies** relevant providers using location and context.
3. **Selects** and ranks the best providers based on distance, rating, and availability.
4. **Simulates** realistic booking and confirmation flows.
5. **Handles** automated follow-up interactions (reminders/status updates).
6. **Maintains** transparent, traceable reasoning logs via the agent workflow.

### Mandatory Requirement: Google Antigravity
This system leverages **Google Antigravity** as the central orchestration platform. Antigravity manages the multi-step reasoning pipelines, seamlessly integrates our external APIs (Maps, DB), and oversees the autonomous execution of booking and notification tasks.

---

## 2. System Architecture & Agentic Workflow

The backend follows a clean, modular, domain-driven architecture demonstrating strong autonomy and reasoning.

```text
[ Client Application ] (Web / Mobile)
    │
    ▼
[ FastAPI Routers ] (REST / SSE Endpoints, Input Validation)
    │
    ▼
[ Google Antigravity + LangGraph ] (Multi-agent AI Orchestration)
    │
    ├──> 1. Intent Parser Agent (NLP, Language Detection, Urgency)
    ├──> 2. Provider Discovery Agent (Geo-spatial DB & Maps logic)
    ├──> 3. Ranking Agent (Multi-variable scoring & selection)
    ├──> 4. Booking Execution Agent (Transaction Simulation)
    └──> 5. Follow-Up Agent (Reminders & Confirmations)
    │
    ▼
[ Tools & Repositories ] (DB Abstraction, Provider / Booking Logic)
    │
    ▼
[ Database Layer ] (Mock In-Memory DB OR PostgreSQL)
```

### The AI Workflow (Step-by-step)
When a user submits a raw request (e.g., *"Mujhe kal subah G-13 mein AC technician chahiye"*):

1. **Intent Understanding**: Antigravity orchestrates the parser to extract the service type (`ac_technician`), location (`G-13`), and time (`Tomorrow morning`).
2. **Provider Discovery**: The system queries the database/mock data for available technicians within the requested radius.
3. **Matching & Ranking**: Discovered providers are ranked based on rating, distance, experience, and the user's urgency. Clear reasoning is generated (e.g., *Closest available provider with high rating*).
4. **Action Simulation**: A slot is automatically reserved (e.g., *10:00 AM*), updating the database state and generating a confirmation.
5. **Follow-Up Automation**: The AI schedules reminders (e.g., *1 hour before appointment*) and provides the user with clear next steps.
6. **Delivery**: The FastAPI router wraps the final result in a standardized JSON payload or streams the agent's thought process live via SSE.

---

## 3. Installation & Setup

### Prerequisites
- Python 3.10+
- PostgreSQL (Optional, for production mode)

### Setup Commands

1. **Clone the repository**
   ```bash
   git clone <repository_url>
   cd informal-service-orchestrator
   ```

2. **Create and activate a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Setup Environment Variables**
   Create a `.env` file in the root directory:
   ```env
   # .env
   USE_REAL_DB=false
   DATABASE_URL=postgresql://user:password@localhost:5432/informal_services
   WORKFLOW_TIMEOUT_SECONDS=60
   ALLOWED_ORIGINS=*
   ```

5. **Run the server**
   ```bash
   uvicorn main:app --reload
   ```

---

## 4. API Endpoints & Integration

The system adheres to a strict, frontend-friendly JSON contract (`{ success, message, data, error }`).

- **`GET /`** : Health check and system status.
- **`GET /services/`** : Fetch the catalog of service categories.
- **`GET /services/providers`** : Fetch mock provider datasets.
- **`POST /requests/`** : Submit natural language requests for AI processing.
- **`POST /requests/stream`** : **[CRITICAL]** Submit requests and receive live SSE streams of the AI's step-by-step reasoning and state changes.
- **`GET /bookings/user/{user_id}`** : Track simulated booking history.
- **`POST /bookings/{id}/complete`** : Simulate the completion of a service.

---

## 5. Streaming (SSE) & Traceability

A key component of this hackathon submission is the **Agent Trace / Logs**. 

Using the `/requests/stream` endpoint, the system streams the AI's internal thought process live to the client using **Server-Sent Events (SSE)**.
- It provides a granular, real-time look into Antigravity's orchestration.
- Shows exactly how the NLP parsing, search limits, and ranking algorithms function in real-time before finalizing the booking.
- Includes transparent logs of decisions, tool usage, and action execution.

---

## 6. Database Modes & Action Simulation

Action simulation is a core requirement of this challenge. Our system maintains state changes through a flexible database layer controlled by the `USE_REAL_DB` environment variable.

### MockDB (Development & Simulation)
- **`USE_REAL_DB=false`**
- Uses a robust, in-memory Python dictionary store heavily populated with localized dummy data.
- Perfect for demonstrating the booking simulation, scheduling, and provider assignment rapidly without external dependencies.

### PostgreSQL (Production Ready)
- **`USE_REAL_DB=true`**
- Uses SQLAlchemy 2.0 with PostgreSQL for persistent, production-grade tracking of bookings, users, and provider availability.

---

## 7. Evaluation Criteria Alignment

1. **Use of Google Antigravity (25%)**: Antigravity serves as the core orchestration engine managing the LangGraph nodes, routing multi-step logic, and handling tools.
2. **Agentic Reasoning (20%)**: Employs a strict pipeline from intent parsing → discovery → ranking → execution → follow-up.
3. **Matching Quality (20%)**: Implements multi-variable weighted ranking (Distance, Rating, Experience) tailored to the urgency of the user's request.
4. **Action Simulation (15%)**: Realistically simulates end-to-end booking, maintaining database state, and handling localized follow-ups.
5. **Technical Implementation (10%)**: Clean, modular API design with safe streaming, standardized responses, and dual DB support.
6. **Innovation & UX (10%)**: Handles mixed Roman Urdu/English seamlessly, returning localized and actionable next steps.
