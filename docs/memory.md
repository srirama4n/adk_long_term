# Memory architecture: short-term and long-term

This document describes how short-term (Redis) and long-term (MongoDB + mem0) memory work and how they are used in the chat flow.

---

## Short-term memory (Redis)

Session-scoped buffer: last N messages, TTL. Implemented by `ShortTermMemory` in `app.memory.short_term`.

### Component flow

```mermaid
flowchart LR
    subgraph App["App layer"]
        API[API / SupervisorService]
        MM_ST[MemoryManager]
    end

    subgraph ShortTerm["Short-term (session)"]
        ST_Store[ShortTermMemory]
        Redis[(Redis)]
    end

    API -->|save_short_term / get_short_term / clear_session| MM_ST
    MM_ST -->|save / get / clear| ST_Store
    ST_Store -->|setex / get / delete| Redis

    note1[TTL + max_messages per session]
```

### Sequence (one chat turn)

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant MemoryManager
    participant ShortTermMemory
    participant Redis

    Client->>API: POST /chat (user_id, session_id, message)
    API->>MemoryManager: get_short_term(session_id)
    MemoryManager->>ShortTermMemory: get(session_id)
    ShortTermMemory->>Redis: GET key
    Redis-->>ShortTermMemory: payload or nil
    ShortTermMemory-->>MemoryManager: context or None
    MemoryManager-->>API: short_term context

    Note over API: Run supervisor, get response

    API->>MemoryManager: save_short_term(session_id, data)
    MemoryManager->>ShortTermMemory: save(session_id, data)
    ShortTermMemory->>Redis: SETEX key TTL json
    Redis-->>ShortTermMemory: OK
    ShortTermMemory-->>MemoryManager: done
    MemoryManager-->>API: done
    API-->>Client: response
```

---

## Long-term memory (MongoDB + mem0)

Persistent, searchable by user. Raw docs in MongoDB; semantic search via mem0 (vectors in MongoDB). Implemented by `LongTermMemory` in `app.memory.long_term`.

### Component flow

```mermaid
flowchart LR
    subgraph App["App layer"]
        API2[API / SupervisorService]
        MM_LT[MemoryManager]
    end

    subgraph LongTerm["Long-term (persistent)"]
        LT_Store[LongTermMemory]
        Mongo[(MongoDB raw docs)]
        Mem0[mem0]
        MongoVec[(MongoDB vectors)]
    end

    API2 -->|save_long_term / get_relevant_history| MM_LT
    MM_LT -->|save / get_relevant| LT_Store
    LT_Store -->|insert_one| Mongo
    LT_Store -->|add / search / get_all| Mem0
    Mem0 -->|embeddings + vectors| MongoVec
```

### Sequence: save (after each turn)

```mermaid
sequenceDiagram
    participant API
    participant MemoryManager
    participant LongTermMemory
    participant MongoDB
    participant mem0

    API->>MemoryManager: save_long_term(user_id, session_id, data)
    MemoryManager->>LongTermMemory: save(messages, metadata, ...)
    LongTermMemory->>MongoDB: insert_one(doc)
    MongoDB-->>LongTermMemory: OK
    LongTermMemory->>LongTermMemory: normalize content to string
    LongTermMemory->>mem0: add(messages, user_id, metadata)
    mem0->>mem0: embed + optional fact extraction
    mem0->>MongoDB: store vectors (mem0 collection)
    mem0-->>LongTermMemory: results
    LongTermMemory-->>MemoryManager: done
    MemoryManager-->>API: done
```

### Sequence: retrieve (relevant history)

```mermaid
sequenceDiagram
    participant API
    participant MemoryManager
    participant LongTermMemory
    participant mem0
    participant MongoDB

    API->>MemoryManager: get_relevant_history(user_id, query, limit)
    MemoryManager->>LongTermMemory: get_relevant(user_id, query, limit)
    alt query present
        LongTermMemory->>mem0: search(query, user_id, limit)
        mem0->>MongoDB: vector search
        MongoDB-->>mem0: results
    else empty query
        LongTermMemory->>mem0: get_all(user_id, limit)
        mem0->>MongoDB: list by user_id
        MongoDB-->>mem0: results
    end
    mem0-->>LongTermMemory: results
    LongTermMemory-->>MemoryManager: list of history items
    MemoryManager-->>API: list[dict]
```

---

## Combined chat flow

```mermaid
flowchart TB
    subgraph Request["Request"]
        Chat[POST /chat]
    end

    subgraph Memory["Memory (MemoryManager)"]
        direction TB
        ST[Short-term\nRedis, TTL]
        LT[Long-term\nMongoDB + mem0]
    end

    subgraph Flow["Chat flow"]
        GetMem[Load short + long context]
        Supervisor[Run Supervisor]
        SaveST[Save short-term]
        SaveLT[Save long-term]
    end

    Chat --> GetMem
    GetMem --> ST
    GetMem --> LT
    GetMem --> Supervisor
    Supervisor --> SaveST
    Supervisor --> SaveLT
    SaveST --> ST
    SaveLT --> LT
```

---

## MongoDB collection names (long-term)

| Purpose        | Env / default           | Where to look in MongoDB        |
|----------------|-------------------------|----------------------------------|
| Raw documents  | `MONGODB_COLLECTION` → `agent_long_memory`  | DB: `MONGODB_DB` (e.g. `agent_memory`) |
| mem0 vectors   | `MEM0_COLLECTION` → `mem0_long_memory`     | Same DB; created on first mem0 write. Requires Atlas Search. |

If the mem0 collection is missing, see [Long-term memory README](../app/memory/long_term/README.md#if-you-dont-see-the-mem0-collection-in-mongodb).

---

## Related docs

- [Short-term memory (Redis)](../app/memory/short_term/README.md) — usage and config for `ShortTermMemory`.
- [Long-term memory (MongoDB + mem0)](../app/memory/long_term/README.md) — usage and config for `LongTermMemory`.
