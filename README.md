# Production-Ready Hotel Reservation AI Agent (Flask + Ollama Cloud)

This project implements a deterministic hotel reservation AI backend that:

- Uses **Ollama Cloud LLMs** for structured extraction.
- Uses **Flask** for API endpoints.
- Uses **Pydantic** for strict schema validation.
- Integrates with a **hotel management API client** as the only source of inventory truth.
- Never invents room categories/types/meal plans/availability.
- Supports **draft reservations**, **partial updates**, and confirmation workflow.

## Folder Structure

```text
app/
  __init__.py                 # Flask app factory + dependency wiring
  config.py                   # Environment config
  routes.py                   # /chat, /availability, /reservation/draft, /reservation/confirm
  models/
    reservation.py            # Pydantic request/response/domain schemas
  clients/
    ollama_client.py          # Structured JSON extraction with repair strategy
    hotel_api_client.py       # External hotel API abstraction (mock included)
  services/
    reservation_service.py    # Core orchestration/business rules
    room_allocator.py         # Intelligent room combination engine
    state_store.py            # Conversation/session draft state store
run.py                        # Entry point
tests/
  test_reservation_service.py
  test_room_allocator.py
```

## Reservation Format

The draft/confirmed reservation schema follows:

```json
{
  "check_in": "YYYY-MM-DD",
  "check_out": "YYYY-MM-DD",
  "guests": 2,
  "name": "Jane Doe",
  "email": "jane@example.com",
  "phone": "+15555555555",
  "rooms": [
    {
      "room_category": "Standard",
      "room_type": "Queen",
      "meal_plan": "Breakfast",
      "room_count": 1
    }
  ],
  "status": "draft"
}
```

## Key Deterministic Behaviors

1. **No hallucination**: room options must exist in hotel API availability.
2. **Partial updates**: only fields provided with non-null values are applied.
3. **Null-safe merge**: null from new LLM/user patch never overwrites valid existing data.
4. **Schema enforcement**: strict Pydantic validation (`extra=forbid`).
5. **Date and occupancy checks**: rejects invalid date ranges and impossible allocations.
6. **Follow-up prompts**: missing mandatory fields are returned as `missing_fields`.

## Intelligent Room Allocation

`RoomAllocationEngine` computes room combinations using live availability:

- Enumerates feasible room counts per inventory type.
- Filters combinations that can accommodate all guests.
- Ranks by:
  1. Lowest unused capacity.
  2. Fewest room types used.
  3. Lower total capacity.
- Returns top valid combinations.

If no feasible solution exists, response clearly states impossibility and suggests changing dates/guest count.

## API Endpoints

### `POST /chat`
Natural-language update + structured extraction + state update + suggestions.

Request:

```json
{
  "session_id": "abc123",
  "message": "Need 5 guests from 2026-06-02 to 2026-06-05, under John."
}
```

### `GET /availability?check_in=YYYY-MM-DD&check_out=YYYY-MM-DD`
Fetches dynamic inventory from hotel API client.

### `POST /reservation/draft`
Direct structured patch update.

```json
{
  "session_id": "abc123",
  "reservation": {
    "email": "john@example.com",
    "phone": "+12025551234"
  }
}
```

### `POST /reservation/confirm`
Confirms reservation only when required fields are present and room selection is valid.

```json
{
  "session_id": "abc123"
}
```

## Ollama Structured Extraction Strategy

- Uses `ollama.Client.chat(..., format="json")` with strict schema prompt.
- Applies JSON parsing with fallback recovery (`_best_effort_json`) for malformed outputs.
- Validates output against `ReservationPatch`; rejects invalid structure.

## Example Conversation Flow

1. User: "I need a room for 3 guests next Friday."
2. `/chat` extracts partial fields (`guests`, maybe dates) and stores draft.
3. Backend checks availability and returns room suggestions.
4. Missing fields list includes `name`, `email`, `phone`, and any missing dates/rooms.
5. User provides missing details in follow-up messages.
6. `/reservation/confirm` sets status to `confirmed` only after validation succeeds.

## Error Handling Strategy

- Request validation errors -> HTTP `400` with structured error message.
- LLM malformed output -> repaired if possible, otherwise deterministic error.
- Invalid room options or overbooking -> explicit `400` with exact conflict.
- Invalid date ordering -> explicit `400`.

## Scalability Considerations

For production scaling, replace and extend:

- `InMemoryStateStore` -> Redis/PostgreSQL-backed state.
- Mock `HotelAPIClient` methods -> authenticated HTTP requests with retry/circuit breaker.
- Add idempotency keys and reservation locking to avoid race conditions.
- Add observability (OpenTelemetry, structured logs, metrics).
- Cache high-frequency availability queries with short TTL.
- Deploy Flask with Gunicorn/Uvicorn workers behind API gateway.

## Run Locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python run.py
```

Run tests:

```bash
pytest -q
```
