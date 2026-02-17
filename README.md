# ADK Multi-Agent System

Production-ready multi-agent system using **ADK (Agent Development Kit)** in Python. All user communication goes through the **Supervisor**; **Weather** and **Finance** sub-agents never interact with the user directly.

## Architecture

- **Supervisor Agent**: Orchestrator — intent classification, routing, memory merge, response.
- **Weather Agent**: Sub-agent — uses `get_weather(location, date)`; returns structured JSON (location, temperature, condition, forecast).
- **Finance Agent**: Sub-agent — uses `get_stock_price(symbol)`; returns structured JSON (symbol, price, change).

**Memory**

- **Short-term**: Redis — session context, last N messages, conversation state; TTL 30 minutes.
- **Long-term**: MongoDB — `agent_long_memory` collection; user_id, session_id, messages, extracted_entities, user_preferences, intent_history; persisted permanently.
- **Episodic**: MongoDB — one episode per chat turn (event_type, content).
- **Semantic**: mem0 — one fact per turn (user message + intent).
- **Procedural**: MongoDB — saved how-to procedures (name, steps, description). Filled when the user says "remember this procedure" (ProcedureAgent); injected into context so the assistant can recall steps when the user asks "how do I do X?".

**Context management** (configurable via env):

- **Context offloading**: When short-term message count exceeds `CONTEXT_OFFLOAD_MESSAGE_THRESHOLD`, the oldest messages are written to MongoDB (`agent_offloaded_context`) and only the last `CONTEXT_OFFLOAD_KEEP_RECENT` messages are kept in Redis.
- **Context filtering**: Limits on how much is included: `CONTEXT_LONG_TERM_MAX_ITEMS`, `CONTEXT_LONG_TERM_MIN_SCORE` (optional), `CONTEXT_PROCEDURE_MAX_ITEMS`, `CONTEXT_SHORT_TERM_RECENT_N`.
- **Context caching**: Redis cache for long-term and procedure lookups (keyed by `user_id` and optionally message hash) with `CONTEXT_CACHE_TTL_SECONDS`. Procedure cache is invalidated when a new procedure is saved.
- **Context compaction**: Truncates each context part to `CONTEXT_COMPACTION_MAX_CHARS_PER_PART` and the combined context to `CONTEXT_COMPACTION_MAX_TOTAL_CHARS` so the prompt stays within size limits.

See **[Memory flow diagrams](docs/memory.md)** for short-term and long-term flows (Mermaid).

## Flows

### Request flow (POST /chat)

1. **API** receives `POST /chat` with `user_id`, `session_id`, `message`.
2. **Memory retrieve**  
   - Short-term: `get_short_term(session_id)` from Redis (last N messages).  
   - Long-term: `get_relevant_history(user_id, message, limit=5)` from MongoDB/mem0.  
   - Procedural: `list_procedures(user_id, limit=10)` from MongoDB (saved how-tos).
3. **Context build**  
   Assembled into one user message: `[Recent context]` (optional) + `[Relevant history]` (optional) + `[Saved procedures]` (optional) + `[Current user message]`. This is sent to the Supervisor.
4. **Session resolve**  
   ADK runner ensures a session exists for `(app_name, user_id, session_id)`; creates one if missing.
5. **Agent run**  
   Supervisor runs on the assembled message, classifies intent, and either:
   - **Delegates** to WeatherAgent, FinanceAgent, or ProcedureAgent (sub-agents call tools and return structured output), or  
   - **Responds directly** (e.g. general_query, or procedure recall using `[Saved procedures]`).
6. **Procedure persistence**  
   If ProcedureAgent called `save_procedure`, each pending procedure is written to procedural memory via `add_procedure(user_id, name, steps, description)`.
7. **Memory persist**  
   - Short-term: `save_short_term(session_id, { messages, session_context, current_conversation_state })`.  
   - Long-term: `save_long_term(user_id, session_id, { messages, intent_history, ... })` (MongoDB + mem0).  
   - Episodic: `add_episode(user_id, session_id, "turn", content)` (best effort).  
   - Semantic: `add_fact(user_id, fact)` (best effort).
8. **Response**  
   API returns `{ "session_id", "intent", "response" }` where `response` is the sub-agent output or the Supervisor’s message.

### Intent routing flow

| User intent        | Classification   | Behavior |
|--------------------|------------------|----------|
| Weather, forecast  | `weather_query`  | Delegate to **WeatherAgent** → `get_weather(location, date)` → return structured weather. |
| Stock, price, ticker | `finance_query` | Delegate to **FinanceAgent** → `get_stock_price(symbol)` → return structured quote. |
| “Remember this procedure”, “Save how to…” | `procedure_query` | Delegate to **ProcedureAgent** → `save_procedure(name, steps, description)` → procedure stored after run; return confirmation. |
| “How do I do X?”, “What are the steps for …?” | `general_query` | Supervisor uses **\[Saved procedures]** in context and replies with the matching procedure’s steps (no delegation). |
| Greetings, other   | `general_query`  | Supervisor responds briefly (no delegation). |

### Memory flow (per turn)

```
Retrieve (before agent run)     Persist (after agent run)
─────────────────────────────   ─────────────────────────────
short_term(session_id)    →     save_short_term(session_id, …)
get_relevant_history(user_id,   save_long_term(user_id, session_id, …)
  message)                 →     add_episode(user_id, session_id, "turn", …)
list_procedures(user_id)   →     add_fact(user_id, fact)
                                add_procedure(…) if ProcedureAgent saved any
```

- **Short-term** and **long-term** are always read and written every turn.  
- **Procedural** is read every turn (for context) and written only when the user saves a procedure.  
- **Episodic** and **semantic** are written every turn (best effort); they are not read during the chat flow (used for analytics or future retrieval).

## How to use the flows

| Goal | What to do |
|------|------------|
| **Send a message and get a reply** | `POST /chat` with `user_id`, `session_id`, `message`. Use the same `session_id` across turns so short-term context accumulates. |
| **Stream the reply (SSE)** | `POST /chat/stream` with the same body. Requires an existing ADK session (create one with a non-stream `/chat` first if needed). |
| **Inspect long-term conversation history** | `GET /memory/{user_id}` — returns mem0 long-term memories (messages, intent_history). |
| **Inspect turn-level events** | `GET /memory/{user_id}/episodic` — returns episodes (e.g. event_type `turn`, content with user_message, intent, response_preview). |
| **Inspect stored facts** | `GET /memory/{user_id}/semantic` — returns semantic facts (e.g. “User asked: …; intent was …”). |
| **Inspect saved procedures** | `GET /memory/{user_id}/procedural` — returns procedures (name, steps, description). |
| **Clear session buffer** | `DELETE /session/{session_id}` — removes short-term data for that session in Redis. |
| **Save a procedure via chat** | Send a message like “Remember this procedure: … Call it &lt;name&gt;.” → intent `procedure_query` → ProcedureAgent → procedure stored. |
| **Recall a procedure via chat** | Send a message like “How do I &lt;X&gt;?” or “What are the steps for &lt;name&gt;?” → Supervisor uses `[Saved procedures]` and replies with steps. |

## Folder Structure

```
/app
  /agents
    supervisor.py       # Supervisor (orchestrator; routes to sub-agents)
    weather_agent.py   # Weather sub-agent
    finance_agent.py   # Finance sub-agent
    procedure_agent.py # Procedure sub-agent (save how-tos)
  /memory
    memory_manager.py  # Wraps agent_memory; config from get_settings()
    short_term/        # Re-exports from agent_memory
    long_term/
    episodic/
    semantic/
    procedural/
  /tools
    weather_tool.py
    finance_tool.py
    procedure_tool.py  # save_procedure (pending → persisted after run)
  /api
    routes.py
    schemas.py
  /context               # Reusable context pipeline, config, persist (see app/context/README.md)
  /services
    base_supervisor_service.py    # BaseSupervisorService: build context → run agent → persist
    supervisor_service.py # ADK Supervisor (extends BaseSupervisorService)
  /utils
    circuit_breaker.py
  config.py
/agent_memory          # Reusable memory package (no app dependency)
/agent_context         # Reusable context pipeline + persist (no app dependency)
main.py
.env
```

## Common packages (like agent_memory)

- **agent_memory** — Reusable memory layer: short-term, long-term, episodic, semantic, procedural. Config via env or constructor; no app dependency. See [agent_memory/README.md](agent_memory/README.md).
- **agent_context** — Reusable context pipeline and after-turn persist: config, filter, compaction, cache, pipeline, persist. Use with any memory that implements the protocols; no app dependency. See [agent_context/README.md](agent_context/README.md). The app uses it via `app.context` (re-exports + `ContextConfig.from_settings(get_settings())`).

## Modular context and base supervisor

Context building and persist are **reusable** so you can plug them into any supervisor-style agent:

- **`app/context/`** — Re-exports [agent_context](agent_context/README.md): context pipeline (retrieve → filter → compact), config, and after-turn persist. Uses **protocols** for memory and cache. See [app/context/README.md](app/context/README.md).
- **`BaseSupervisorService`** (`app/services/base_supervisor_service.py`) — Abstract base: `_build_context()` (uses `ContextPipeline`), `_run_agent()` (you implement), `_persist_after_turn()` (uses `after_turn`), `chat()` that ties them together. Subclass and implement `_run_agent(user_id, session_id, user_message, flow_id) -> (intent, response_payload)` to use with another agent or runner.
- **`SupervisorService`** — Extends `BaseSupervisorService`, wires the ADK Supervisor agent, `PENDING_PROCEDURES`, and app exceptions.

To use in another project: depend on the same `app.context` and `BaseSupervisorService` pattern (or copy the package); implement the memory protocols and `_run_agent` for your agent.

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
| GET | `/memory/{user_id}/episodic` | Return episodic memory (turn events) for user |
| GET | `/memory/{user_id}/semantic` | Return semantic memory (facts) for user |
| GET | `/memory/{user_id}/procedural` | Return procedural memory (saved procedures) for user |
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

## Testing each memory type

Use the same `user_id` and `session_id` (e.g. `test-user`, `s1`) so short-term and long-term build up across turns.

| Memory type | How it’s populated | Example utterance / curl |
|-------------|--------------------|---------------------------|
| **Short-term** | Every chat turn (same session) | Any message in the same `session_id` |
| **Long-term** | Every chat turn | Any message; view with `GET /memory/{user_id}` |
| **Episodic** | One episode per turn | Any message; view with `GET /memory/{user_id}/episodic` |
| **Semantic** | One fact per turn | Any message; view with `GET /memory/{user_id}/semantic` |
| **Procedural** | Only when user asks to **save** a procedure | "Remember this procedure: … Call it &lt;name&gt;." |

### Short-term, long-term, episodic, semantic (any chat message)

```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test-user","session_id":"s1","message":"Hi, what is the weather in Mumbai?"}'
```

```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test-user","session_id":"s1","message":"What is the stock price of AAPL?"}'
```

### Procedural (save a procedure)

```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test-user","session_id":"s1","message":"Remember this procedure: To check the weather, first get the user location, then call the weather API, then format the response. Call it check_weather."}'
```

### Procedural recall (ask for saved steps)

After saving a procedure, ask how to do it; the assistant uses saved procedures from context:

```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test-user","session_id":"s1","message":"How do I check the weather? What are the steps?"}'
```

### Inspect stored memory

```bash
curl -s http://localhost:8000/memory/test-user
curl -s http://localhost:8000/memory/test-user/episodic
curl -s http://localhost:8000/memory/test-user/semantic
curl -s http://localhost:8000/memory/test-user/procedural
```

### One-shot sequence (all memory types)

Run in order with the same `user_id` and `session_id`:

1. **"Hi, what's up?"** — populates short-term, long-term, episodic, semantic.
2. **"What's the weather in Delhi?"** — same four.
3. **"Remember: to order coffee — 1. Open app 2. Select drink 3. Pay. Save as order_coffee."** — populates all five (including procedural).
4. **"How do I order coffee? What are the steps?"** — tests procedural recall.

## Session Flow Example

For a message like “What is weather in Delhi?”: API → memory retrieve (short-term, long-term, procedures) → context build → Supervisor classifies `weather_query` → delegates to WeatherAgent → `get_weather("Delhi", ...)` → Supervisor persists memory (short-term, long-term, episodic, semantic) → API returns `{ "session_id", "intent": "weather_query", "response": { ... } }`. See **[Flows](#flows)** above for the full step-by-step.

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
