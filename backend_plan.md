# Backend Implementation & Improvement Plan

## 1. Current State Analysis
Based on the review of the service orchestrator backend, here is the current status:
- **Architecture**: The application correctly uses FastAPI and LangGraph for agent orchestration. The separation of concerns (routers, agents, schemas, tools) is solid.
- **Agent Trigger**: The agent trigger is implemented in `POST /requests/` via `app_graph.invoke()`. It correctly kicks off the workflow, but it is currently **synchronous**.
- **Live Progress API**: ❌ **Not Implemented**. The current `POST /requests/` endpoint blocks the client until the entire LangGraph workflow (Intent -> Discovery -> Ranking -> Booking -> Followup) completes. It then returns the entire trace at the end. It does not stream intermediate steps to the frontend.
- **Database**: Using `mock_db.py` (Expected as per requirements).
- **Authentication**: Ignored as requested.

## 2. Step-by-Step Implementation Guide

### Phase 1: Implement Live Progress Streaming
To show real-time progress in the frontend, the backend must stream LangGraph node events as they happen.

1. **Refactor Agent Invocation to Async**: 
   - Update `app_graph.invoke()` to use LangGraph's async streaming capabilities, such as `app_graph.astream_events()` or `app_graph.astream()`.
2. **Create a Streaming Endpoint**:
   - Add a new endpoint in `routers/requests.py`: `POST /requests/stream`.
   - Use FastAPI's `StreamingResponse` to return a Server-Sent Events (SSE) stream.
   - Yield trace events (e.g., "intent_understanding", "provider_search") to the client as each node finishes its execution.
   - *Alternative*: Implement WebSockets for bidirectional communication if required.

### Phase 2: Async LLM and Node Optimizations
The current graph nodes are mostly synchronous.
1. **Async LLM Calls**: Update `intent_parser_node` in `agents/graph.py` to use `ainvoke` instead of `invoke` for the `ChatGoogleGenerativeAI` model. This prevents the event loop from blocking during the LLM API call.
2. **Async Nodes**: Convert the node functions (`intent_parser_node`, `provider_discovery_node`, etc.) to `async def` so they yield to the FastAPI event loop properly.

### Phase 3: Missing Endpoints for Frontend Data Needs
The frontend will likely need more than just the main orchestrator trigger to function properly.

1. **Booking History (`GET /bookings/{user_id}`)**:
   - Create an endpoint to retrieve past and upcoming bookings for a specific user.
2. **Booking Details (`GET /bookings/detail/{booking_id}`)**:
   - Create an endpoint to get the status of a specific booking.
3. **Cancel Booking (`POST /bookings/{booking_id}/cancel`)**:
   - Add functionality to update the booking status to `CANCELLED`.
4. **List Providers/Services (`GET /services` or `GET /providers`)**:
   - If the frontend needs to show an initial catalog of services or top-rated providers before the user sends a voice/text query.

### Phase 4: Database Preparation
While currently using a mock DB, prepare the schemas for migration.
1. **Define ORM Models**: If transitioning to PostgreSQL or similar, add SQLAlchemy models or Prisma schema mirroring the Pydantic schemas in `models.py`.
2. **Abstract DB Tool**: Ensure `db_tool.py` interface remains identical so that switching from `mock_db` to the real DB doesn't require changes in the agent logic.
