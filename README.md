# ADK Multi-Agent System

Production-ready multi-agent system using **ADK (Agent Development Kit)** in Python. All user communication goes through the **Supervisor**; **Weather** and **Finance** sub-agents never interact with the user directly.

## Architecture

- **Supervisor Agent**: Orchestrator — intent classification, routing, memory merge, response.
- **Weather Agent**: Sub-agent — uses `get_weather(location, date)`; returns structured JSON (location, temperature, condition, forecast).
- **Finance Agent**: Sub-agent — uses `get_stock_price(symbol)`; returns structured JSON (symbol, price, change).

**Memory**

- **Short-term**: Redis — session context, last N messages, conversation state; TTL 30 minutes.
- **Long-term**: MongoDB — `agent_long_memory` collection; user_id, session_id, messages, extracted_entities, user_preferences, intent_history; persisted permanently.

See **[Memory flow diagrams](docs/memory.md)** for short-term and long-term flows (Mermaid).

## Folder Structure

```
/app
  /agents
    supervisor.py      # Supervisor (orchestrator)
    weather_agent.py   # Weather sub-agent
    finance_agent.py   # Finance sub-agent
  /memory
    memory_manager.py  # Redis + MongoDB memory
  /tools
    weather_tool.py
    finance_tool.py
  /api
    routes.py
    schemas.py
  /services
    supervisor_service.py
  /utils
    circuit_breaker.py
  config.py
main.py
.env
```

## Run Instructions

```bash
# Create venv and install
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Copy env and set GOOGLE_API_KEY, MONGODB_URL, REDIS_URL
cp .env.example .env
# Edit .env with your keys and Redis/Mongo URLs

# Run API (use your own Redis and MongoDB, e.g. Atlas + Redis Labs)
uvicorn main:app --reload --host 0.0.0.0 --port 8000
# Or: python main.py
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/chat` | Send message → Supervisor → memory → routing → sub-agent → structured response |
| POST | `/chat/stream` | Same as `/chat` but stream events via SSE |
| GET | `/memory/{user_id}` | Return long-term memory for user |
| DELETE | `/session/{session_id}` | Clear Redis short-term session |

## Example cURL Requests

### Health

```bash
curl -s http://localhost:8000/health
```

### POST /chat

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "session_id": "session456",
    "message": "What is the weather in Mumbai?"
  }'
```

Example response:

```json
{
  "session_id": "session456",
  "intent": "weather_query",
  "response": {
    "location": "Mumbai",
    "temperature": "32°C",
    "condition": "Sunny",
    "forecast": "Sunny, 32°C. Highs in the low 30s, lows in the mid 20s."
  }
}
```

### POST /chat (finance)

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "session_id": "session456",
    "message": "What is the stock price of AAPL?"
  }'
```

### POST /chat/stream (SSE)

```bash
curl -N -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "session_id": "session456",
    "message": "What is the weather in Delhi?"
  }'
```

### GET /memory/{user_id}

```bash
curl -s http://localhost:8000/memory/user123
```

### DELETE /session/{session_id}

```bash
curl -X DELETE http://localhost:8000/session/session456
```

## Session Flow Example

1. User: "What is weather in Delhi?"
2. API → Supervisor.
3. Supervisor: classifies intent, retrieves memory (Redis + MongoDB), calls WeatherAgent.
4. WeatherAgent: calls `get_weather("Delhi", ...)`, returns structured JSON.
5. Supervisor: merges context, saves to Redis and MongoDB, returns response.
6. API: returns `{ "session_id", "intent": "weather_query", "response": { ... } }`.

## Enterprise Features

- **Async**: async/await across API, memory, and agent execution.
- **Structured logging**: JSON logging (structlog).
- **Error handling**: Middleware for 500 and consistent error payloads.
- **Retry**: Tenacity on weather and finance tool calls.
- **Circuit breaker**: Utility in `app/utils/circuit_breaker.py` for tool/runner calls.
- **Rate limiting**: In-memory per-IP (configurable); use Redis in production for distributed limits.
- **OpenTelemetry**: Placeholder (set `OTEL_ENABLED=true` and add instrumentation as needed).
- **Dependency injection**: FastAPI `Depends` for MemoryManager and SupervisorService.
- **Config**: All settings via environment variables (see `.env.example`).

## Requirements

- Python 3.10+
- Redis
- MongoDB
- Google API key (Gemini) in `.env`
