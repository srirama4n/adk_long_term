# How to test short-term memory

Short-term memory is **Redis-backed**, **per session**: the last N messages (see `SHORT_TERM_MAX_MESSAGES`) are stored under a `session_id` and sent to the Supervisor as "[Recent context]" on each `/chat`. TTL is 30 minutes by default.

**Same `session_id`** = same conversation window = short-term memory is shared.  
**Different `session_id`** = different conversation = no short-term memory shared.

---

## 1. Test: agent “remembers” within the session

Use one **fixed `session_id`** and two messages. The second reply should reflect the first (from short-term context).

**Step 1 – Store something in this session**
```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "alice",
    "session_id": "session-1",
    "message": "Remember: my favorite color is blue and I live in Tokyo."
  }'
```

**Step 2 – Ask about it (same session)**
```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "alice",
    "session_id": "session-1",
    "message": "What is my favorite color and where do I live?"
  }'
```

If short-term memory works, the second response should mention **blue** and **Tokyo** (from the recent context injected into the Supervisor).

---

## 2. Test: different session = no short-term memory

**Step 1 – Same user, session A**
```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": "bob", "session_id": "session-A", "message": "My name is Bob."}'
```

**Step 2 – Same user, different session B**
```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": "bob", "session_id": "session-B", "message": "What is my name?"}'
```

Here the agent has **no** short-term context from session-A (different `session_id`), so it may not say "Bob" unless it’s in long-term memory from a previous chat with `user_id=bob`.

---

## 3. Clear short-term memory for a session

Short-term data is stored per `session_id`. To clear it for one session:

```bash
curl -s -X DELETE "http://localhost:8000/session/session-1"
```

After this, the next `/chat` with `session_id=session-1` has no recent messages in short-term memory.

---

## 4. Health check

```bash
curl -s http://localhost:8000/health
```

Expected: `{"status":"healthy","service":"adk-multi-agent"}`
